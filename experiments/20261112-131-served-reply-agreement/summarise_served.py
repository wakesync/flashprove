#!/usr/bin/env python3
"""Apply the registered bars (PREREG.md) to runs/forward.json + runs/served-ids.json -> runs/summary.json, runs/summary.md.

Reply position k (0-based) of a prompt with n_prompt prompt ids is input position n_prompt - 1 + k; its logits predict
reply_ids[k]. At a stop position (last reply id 248046 when finish_reason == stop) a path picks the served token iff its
argmax is 248046 or 248044 (PREREG). Ties are broken by lowest id (e2e.Stream)."""
import json, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent; R = HERE / "runs"
IM_END, ENDOFTEXT = 248046, 248044
PATHS = ["REF", "XS18", "XS20"]

def main():
    S = json.load(open(R / "served-ids.json")); FW = json.load(open(R / "forward.json"))
    inc = [q for q in S["prompts"] if q["included"]]
    per = []; dis = []; tot = {k: 0 for k in ("n", "REF_s", "XS18_s", "XS20_s", "XS18_r", "XS20_r", "prompt_n", "XS18_rp", "XS20_rp")}
    serving_prec = {"XS18": 0, "XS20": 0}; lowering = {"XS18": 0, "XS20": 0}; ref_serv = 0
    det = {}
    for q in inc:
        f = FW["prompts"][q["id"]]; npmt = len(q["prompt_ids"]); rids = q["reply_ids"]; stop = q["finish_reason"] == "stop"
        top = {"REF": f["ref_top1"]}
        guard = {}
        for p in ("XS18", "XS20"):
            pp = f["paths"].get(p); guard[p] = pp is None
            top[p] = pp["top1_path"] if pp else [None] * f["T"]
        for p2 in ("REF#2", "XS18#2"):
            if p2 in f["paths"] and f["paths"][p2] is not None:
                base = "REF" if p2 == "REF#2" else "XS18"
                det[f"{p2}|{q['id']}"] = f["paths"][p2]["top1_path"] == top[base]
        row = dict(id=q["id"], n_reply=len(rids), stop=stop)
        c = {k: 0 for k in ("REF_s", "XS18_s", "XS20_s", "XS18_r", "XS20_r")}
        for k, sid in enumerate(rids):
            t = npmt - 1 + k; is_stop = stop and k == len(rids) - 1
            ok = lambda v: (v in (IM_END, ENDOFTEXT)) if is_stop else (v == sid)
            m = f["ref_margin"][t]
            r_ok = ok(top["REF"][t]); c["REF_s"] += r_ok
            for p in ("XS18", "XS20"):
                s_ok = top[p][t] is not None and ok(top[p][t]); c[p + "_s"] += s_ok
                r_eq = top[p][t] is not None and top[p][t] == top["REF"][t]; c[p + "_r"] += r_eq
                if not s_ok:
                    if r_ok: lowering[p] += 1
                    else: serving_prec[p] += 1
            if not (r_ok and all(top[p][t] is not None and ok(top[p][t]) for p in ("XS18", "XS20"))) or \
               any(top[p][t] != top["REF"][t] for p in ("XS18", "XS20")):
                dis.append(dict(id=q["id"], reply_pos=k, input_pos=t, served=sid, stop_position=is_stop,
                                REF=top["REF"][t], XS18=top["XS18"][t], XS20=top["XS20"][t], ref_top2_margin=m))
        n = len(rids)
        row.update(n=n, **c, frac=dict(REF_served=c["REF_s"] / n, XS18_served=c["XS18_s"] / n, XS20_served=c["XS20_s"] / n,
                                       XS18_REF=c["XS18_r"] / n, XS20_REF=c["XS20_r"] / n),
                   whole_reply=dict(REF=c["REF_s"] == n, XS18=c["XS18_s"] == n, XS20=c["XS20_s"] == n), guard_error=guard,
                   reps_text_identical=q["reps_text_identical"])
        # descriptive: prompt positions 0..npmt-2 (their next token is a prompt token; REF vs XS only)
        pp = {p: sum(top[p][t] == top["REF"][t] for t in range(npmt - 1)) for p in ("XS18", "XS20")}
        row["prompt_positions"] = dict(n=npmt - 1, XS18_REF=pp["XS18"], XS20_REF=pp["XS20"])
        per.append(row)
        for k in c: tot[k] += c[k]
        tot["n"] += n; tot["prompt_n"] += npmt - 1; tot["XS18_rp"] += pp["XS18"]; tot["XS20_rp"] += pp["XS20"]
    N = tot["n"]
    fr = lambda k: tot[k] / N if N else float("nan")
    spread = {}
    for key in ("REF_served", "XS18_served", "XS20_served", "XS18_REF", "XS20_REF"):
        v = [r["frac"][key] for r in per]
        spread[key] = dict(median=statistics.median(v), min=min(v), max=max(v), sd=statistics.pstdev(v)) if v else None
    # registered check: residuals bit-identical after every layer (e2e.layer_all writes det_bit_equal per layer)
    layer_det = [all(json.loads(l)["det_bit_equal"].values()) for l in open(R / "divergence-abl.jsonl")]
    det["residuals_bit_equal_all_layers"] = bool(layer_det) and all(layer_det)
    det["layers_checked"] = len(layer_det)
    deterministic = all(v for k, v in det.items() if k != "layers_checked") if det else False
    sanity = fr("REF_s") >= 0.80
    h0 = fr("REF_s") >= 0.98
    h = {p: fr(p + "_s") >= 0.98 and fr(p + "_r") >= 0.99 for p in ("XS18", "XS20")}
    verdict = "BROKEN (sanity)" if not sanity else ("NOT DETERMINISTIC" if not deterministic else None)
    out = dict(n_included=len(inc), n_excluded=S["n_excluded"], measured_positions=N,
               pooled=dict(REF_served=fr("REF_s"), XS18_served=fr("XS18_s"), XS20_served=fr("XS20_s"),
                           XS18_REF=fr("XS18_r"), XS20_REF=fr("XS20_r"),
                           counts={k: tot[k] for k in ("REF_s", "XS18_s", "XS20_s", "XS18_r", "XS20_r")}),
               prompt_positions_descriptive=dict(n=tot["prompt_n"], XS18_REF=tot["XS18_rp"], XS20_REF=tot["XS20_rp"]),
               disagreements_vs_served=dict(serving_precision=serving_prec, lowering=lowering),
               spread_over_prompts=spread, determinism=det, deterministic=deterministic, sanity_ref_ge_80pct=sanity,
               verdict=dict(H0="PASS" if h0 and verdict is None else (verdict or "FAIL"),
                            H1_XS18="PASS" if h["XS18"] and verdict is None else (verdict or "FAIL"),
                            H2_XS20="PASS" if h["XS20"] and verdict is None else (verdict or "FAIL")),
               per_prompt=per, disagreement_positions=dis)
    (R / "summary.json").write_text(json.dumps(out, indent=1) + "\n")
    L = ["| prompt | reply tokens | served = REF | served = XS18 | served = XS20 | REF = XS18 | REF = XS20 | whole reply REF / XS18 / XS20 | 3 reps identical |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in per:
        w = r["whole_reply"]
        L.append(f"| {r['id']} | {r['n']} | {r['REF_s']}/{r['n']} | {r['XS18_s']}/{r['n']} | {r['XS20_s']}/{r['n']} | {r['XS18_r']}/{r['n']} | "
                 f"{r['XS20_r']}/{r['n']} | {'yes' if w['REF'] else 'no'} / {'yes' if w['XS18'] else 'no'} / {'yes' if w['XS20'] else 'no'} | "
                 f"{'yes' if r['reps_text_identical'] else 'no'} |")
    c = out["pooled"]["counts"]
    L.append(f"| all | {N} | {c['REF_s']}/{N} | {c['XS18_s']}/{N} | {c['XS20_s']}/{N} | {c['XS18_r']}/{N} | {c['XS20_r']}/{N} | | |")
    L += ["", "Disagreements (any path vs served, or XS vs REF):", "",
          "| prompt | reply pos | served id | REF | XS18 | XS20 | REF top-2 margin |", "|---|---|---|---|---|---|---|"]
    for d in dis:
        L.append(f"| {d['id']} | {d['reply_pos']}{' (stop)' if d['stop_position'] else ''} | {d['served']} | {d['REF']} | {d['XS18']} | {d['XS20']} | {d['ref_top2_margin']:.4g} |")
    L += ["", "Verdict: " + json.dumps(out["verdict"]), "Deterministic (REF#2, XS18#2 top-1 equal): " + str(deterministic)]
    (R / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__": main()
