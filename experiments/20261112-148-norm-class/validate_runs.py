#!/usr/bin/env python3
"""Input validation for summarise.py (review round 1 of PR #152, added after the registered run; no number changes).

summarise.py used to key rows by layer in a dict and skip an absent arm, so a duplicate row was silently absorbed (or,
if changed, silently replaced the original), a row with a prompt missing kept its pooled count, and a deleted arm
object shrank that arm's denominator (a reviewer showed a synthetic false PASS that way). This module refuses such
inputs before any summary is computed. Missing or inconsistent data must stop the summary, never shrink it.

load_runs(runs_dir) -> (baseline rows, arm rows, progress rows), or raises EvidenceError. What it requires:
  files       baseline.jsonl, arms.jsonl and progress.log.jsonl exist; every line is one JSON object; no blank line;
              no NaN / Infinity / overflowing number anywhere (rejected at parse time and again on every value).
  layers      baseline layers are unique and exactly 0..n-1 in file order (the run is sequential); arm layers are
              unique, in order, a subset of the baseline layers, and exactly the arm-on layers of one registered
              layer set (R33 or full) up to the last baseline layer; progress.log.jsonl logs exactly the baseline
              layers, once each, and its arms count is 5 on exactly the arm layers (catches trailing truncation);
              if it logs all_done, the baseline has all 64 layers.
  rows        exact top-level keys; type = the layer-type rule (full attention iff i mod 4 = 3) and equal in both files.
  prompts     every norm of every baseline row and every arm of every arm row carries exactly the six registered
              prompts; det_bit_equal carries exactly the two registered determinism prompts, booleans.
  arms        every arm row carries exactly the arms W, C, S3, S4, S5 (an arm that errored keeps an object
              {prompt: {"error": ...}} for all six prompts and is counted as a failing layer by summarise.py).
  counts      per prompt n_rows (= n_tokens) is the prompt's registered token count; n = n_rows x 5,120; hidden
              n = n_tokens x 17,408; class counters are non-negative integers, consistent with max and with the
              bit-length histogram (22 bins, sum = n); max_float matches max = |RNE(2^12 x)|; pooled n, n_rows,
              n_over_2047, rows_over_2047 equal the sums over prompts, pooled max the max over prompts,
              ch_over_2047 lies between the largest per-prompt count and min(5,120, sum); top_channels 8, sorted,
              first = pooled max.
  arm values  r = num / den_stream and c = num / den_out (rel 1e-12); den_stream and den_out are the same for every
              arm of a prompt; W's d = 0 and every d finite; arm W's mixer-input counters equal the baseline
              input_layernorm counters of the same layer and prompt (W only rounds at 2^12); C's integer inputs are
              in 2,047 and only C clamps; MLP n_m_over_2047 and m equal the MLP input counters; MLP shifts are
              weights e + k - 12 (gate, up) and e (down); mixer projection names are the layer type's.
The registered run's committed rows pass every check (RESULTS, Review round 1)."""
import json, math
from pathlib import Path

NL = 64
PROMPTS = {"p01-ordinary-short": 13, "p07-chat-ordinary": 23, "p08-chat-refusal": 39, "p09-multilingual": 21,
           "p04-repeat-punct": 64, "p03-repeat-word": 512}               # PREREG Setup: registered prompts and tokens
DET = {"p01-ordinary-short", "p09-multilingual"}
ARMS = {"W": 12, "C": 12, "S3": 3, "S4": 4, "S5": 5}                    # arm -> k
NORMS = ("input_layernorm", "post_attention_layernorm")
R33 = sorted({i for i in range(NL) if i % 4 in (0, 3)} | {26})
D, H = 5120, 17408
MIX_PROJ = {"linear_attention": {"linear_attn.in_proj_qkv.weight", "linear_attn.in_proj_z.weight", "linear_attn.in_proj_a.weight",
                                 "linear_attn.in_proj_b.weight"},
            "full_attention": {"self_attn.q_proj.weight", "self_attn.k_proj.weight", "self_attn.v_proj.weight"}}
QKEYS = {"n", "n_rows", "max", "n_over_2047", "rows_over_2047", "ch_over_2047", "n_ge_2e15", "n_ge_2e17", "n_ge_2e18"}
BKEYS = QKEYS | {"max_float", "argmax_token", "argmax_channel", "hist_bitlen"}
POOLKEYS = {"n", "n_rows", "max", "n_over_2047", "rows_over_2047", "ch_over_2047", "top_channels"}
AKEYS = {"r", "c", "d", "num", "den_stream", "den_out", "mix_rel", "mlp_rel", "n_tokens", "qa", "qm", "mlp"}
MLPKEYS = {"m", "gw", "u", "s", "h", "acc_down", "out", "n_m_over_2047", "n_gw_ge_2e18", "n_gw_ge_2e23", "n_u_ge_2e18", "n_u_ge_2e23",
           "n_h_ge_2e18", "n_h_ge_2e23", "n_silu_sat_lo", "n_silu_sat_hi", "n_acc_down_ge_ledger", "n_out_ge_2e31", "n_m", "n_hidden",
           "n_out", "shift_g", "shift_u", "shift_d"}


class EvidenceError(Exception):
    pass


def need(cond, msg):
    if not cond: raise EvidenceError(msg)


def layer_type(i): return "full_attention" if i % 4 == 3 else "linear_attention"


def _bad_const(s): raise EvidenceError(f"non-finite number {s}")


def _float(s):
    v = float(s)
    if not math.isfinite(v): raise EvidenceError(f"non-finite number {s}")
    return v


def read_jsonl(p):
    need(p.exists(), f"{p.name}: missing")
    raw = p.read_bytes()
    need(raw == b"" or raw.endswith(b"\n"), f"{p.name}: last line not terminated (truncated file)")
    rows = []
    for k, line in enumerate(raw.decode("utf-8").split("\n")[:-1] if raw else [], 1):
        need(line.strip() != "", f"{p.name} line {k}: blank line")
        try:
            r = json.loads(line, parse_constant=_bad_const, parse_float=_float)
        except json.JSONDecodeError as e:
            raise EvidenceError(f"{p.name} line {k}: not JSON ({e.msg})")
        need(isinstance(r, dict), f"{p.name} line {k}: not a JSON object")
        rows.append(r)
    return rows


def finite_all(x, where):
    if isinstance(x, bool) or x is None or isinstance(x, str): return
    if isinstance(x, (int, float)):
        need(math.isfinite(x), f"{where}: non-finite value"); return
    if isinstance(x, dict):
        for k, v in x.items(): finite_all(v, f"{where}.{k}")
        return
    if isinstance(x, list):
        for j, v in enumerate(x): finite_all(v, f"{where}[{j}]")
        return
    raise EvidenceError(f"{where}: unexpected value type {type(x).__name__}")


def is_int(v): return isinstance(v, int) and not isinstance(v, bool)


def intlike(v): return (is_int(v) or isinstance(v, float)) and float(v) == math.floor(float(v))


def check_counters(q, T, where, extra=frozenset()):
    need(set(q) == QKEYS | set(extra), f"{where}: keys {sorted(set(q) ^ (QKEYS | set(extra)))} differ")
    for k in QKEYS - {"max"}: need(is_int(q[k]) and q[k] >= 0, f"{where}.{k}: not a non-negative integer")
    need(intlike(q["max"]) and q["max"] >= 0, f"{where}.max: not a non-negative integer value")
    need(q["n_rows"] == T, f"{where}: n_rows {q['n_rows']} != registered tokens {T}")
    need(q["n"] == T * D, f"{where}: n {q['n']} != {T} x {D}")
    mx = q["max"]
    need(q["n_over_2047"] <= q["n"] and q["rows_over_2047"] <= T and q["ch_over_2047"] <= D, f"{where}: counter over its range")
    need(q["n_ge_2e18"] <= q["n_ge_2e17"] <= q["n_ge_2e15"] <= q["n_over_2047"], f"{where}: threshold counters not nested")
    for thr, k in ((2047, "n_over_2047"), (2 ** 15 - 1, "n_ge_2e15"), (2 ** 17 - 1, "n_ge_2e17"), (2 ** 18 - 1, "n_ge_2e18")):
        need((mx > thr) == (q[k] > 0), f"{where}: {k} = {q[k]} inconsistent with max {mx}")
    need((q["n_over_2047"] > 0) == (q["rows_over_2047"] > 0) == (q["ch_over_2047"] > 0), f"{where}: over-2,047 counters inconsistent")
    need(q["rows_over_2047"] <= q["n_over_2047"] and q["ch_over_2047"] <= q["n_over_2047"], f"{where}: rows/channels over exceed entries over")


def check_baseline_prompt(v, T, where):
    check_counters(v, T, where, extra={"max_float", "argmax_token", "argmax_channel", "hist_bitlen"})
    h = v["hist_bitlen"]
    need(isinstance(h, list) and len(h) == 22 and all(is_int(c) and c >= 0 for c in h), f"{where}.hist_bitlen: not 22 non-negative integers")
    need(sum(h) == v["n"], f"{where}: histogram sums to {sum(h)}, n is {v['n']}")
    need(sum(h[12:]) == v["n_over_2047"] and sum(h[16:]) == v["n_ge_2e15"] and sum(h[18:]) == v["n_ge_2e17"] and sum(h[19:]) == v["n_ge_2e18"],
         f"{where}: histogram tail disagrees with the class counters")
    top = max((j for j, c in enumerate(h) if c), default=0)
    need(top == int(v["max"]).bit_length(), f"{where}: histogram top bin {top} != bit length of max {v['max']}")
    need(isinstance(v["max_float"], (int, float)) and abs(v["max"] - 4096.0 * v["max_float"]) <= 0.5, f"{where}: max_float inconsistent with max")
    need(is_int(v["argmax_token"]) and 0 <= v["argmax_token"] < T and is_int(v["argmax_channel"]) and 0 <= v["argmax_channel"] < D, f"{where}: argmax out of range")


def check_baseline_row(r, where):
    need(set(r) == {"layer", "type", "norms"}, f"{where}: top-level keys {sorted(r)}")
    need(isinstance(r["norms"], dict) and set(r["norms"]) == set(NORMS), f"{where}: norms {sorted(r['norms']) if isinstance(r['norms'], dict) else r['norms']}")
    for nn in NORMS:
        d = r["norms"][nn]; w = f"{where} {nn}"
        need(isinstance(d, dict) and set(d) == {"prompts", "pooled"}, f"{w}: keys")
        P = d["prompts"]
        need(isinstance(P, dict) and set(P) == set(PROMPTS), f"{w}: prompt set {sorted(P)} is not the registered six")
        for pid, v in P.items(): check_baseline_prompt(v, PROMPTS[pid], f"{w} {pid}")
        po = d["pooled"]
        need(isinstance(po, dict) and set(po) == POOLKEYS, f"{w} pooled: keys")
        for k in ("n", "n_rows", "n_over_2047", "rows_over_2047"):
            need(po[k] == sum(v[k] for v in P.values()), f"{w} pooled.{k} = {po[k]} != sum over prompts {sum(v[k] for v in P.values())}")
        need(po["max"] == max(v["max"] for v in P.values()), f"{w} pooled.max != max over prompts")
        need(is_int(po["ch_over_2047"]) and max(v["ch_over_2047"] for v in P.values()) <= po["ch_over_2047"] <= min(D, sum(v["ch_over_2047"] for v in P.values())),
             f"{w} pooled.ch_over_2047 outside [max, sum] over prompts")
        tc = po["top_channels"]
        need(isinstance(tc, list) and len(tc) == 8 and all(isinstance(t, dict) and {"channel", "max"} <= set(t) for t in tc), f"{w} pooled.top_channels: not 8 entries")
        need(tc[0]["max"] == po["max"] and all(tc[j]["max"] >= tc[j + 1]["max"] for j in range(7)), f"{w} pooled.top_channels: not sorted from the pooled max")


def close(a, b): return math.isclose(a, b, rel_tol=1e-12, abs_tol=0.0)


def check_arm_row(r, brow, where):
    need(set(r) == {"layer", "type", "weights", "mixer_proj_exponents", "arms", "det_bit_equal"}, f"{where}: top-level keys {sorted(r)}")
    need(r["type"] == brow["type"], f"{where}: type differs from the baseline row")
    W = r["weights"]
    need(isinstance(W, dict) and set(W) == {"g", "u", "d"} and all(isinstance(W[k], dict) and is_int(W[k].get("e")) for k in W), f"{where}: weights")
    pe = r["mixer_proj_exponents"]
    need(isinstance(pe, dict) and set(pe) == MIX_PROJ[r["type"]] and all(is_int(e) for e in pe.values()), f"{where}: mixer_proj_exponents")
    det = r["det_bit_equal"]
    need(isinstance(det, dict) and set(det) == DET and all(isinstance(b, bool) for b in det.values()), f"{where}: det_bit_equal must hold exactly {sorted(DET)}, booleans")
    A = r["arms"]
    need(isinstance(A, dict) and set(A) == set(ARMS), f"{where}: arms {sorted(A) if isinstance(A, dict) else A} are not exactly {sorted(ARMS)}")
    dens = {}
    for arm, d in A.items():
        w = f"{where} arm {arm}"
        need(isinstance(d, dict) and set(d) == set(PROMPTS), f"{w}: prompt set {sorted(d) if isinstance(d, dict) else d} is not the registered six")
        errs = [isinstance(v, dict) and "error" in v for v in d.values()]
        if any(errs):
            need(all(errs) and all(set(v) == {"error"} and isinstance(v["error"], str) for v in d.values()), f"{w}: error entries must cover all six prompts and hold only 'error'")
            continue
        k = ARMS[arm]
        for pid, v in d.items():
            wp = f"{w} {pid}"; T = PROMPTS[pid]
            need(isinstance(v, dict) and set(v) == AKEYS, f"{wp}: keys {sorted(set(v) ^ AKEYS) if isinstance(v, dict) else v}")
            need(v["n_tokens"] == T, f"{wp}: n_tokens {v['n_tokens']} != registered {T}")
            for f in ("r", "c", "num", "den_stream", "den_out", "mix_rel", "mlp_rel", "d"):
                need(isinstance(v[f], (int, float)) and not isinstance(v[f], bool) and v[f] >= 0, f"{wp}.{f}: not a non-negative number")
            need(v["den_stream"] > 0 and v["den_out"] > 0, f"{wp}: zero denominator")
            need(close(v["r"], v["num"] / v["den_stream"]), f"{wp}: r != num / den_stream")
            need(close(v["c"], v["num"] / v["den_out"]), f"{wp}: c != num / den_out")
            if arm == "W": need(v["d"] == 0, f"{wp}: arm W's distance to itself is not 0")
            dens.setdefault(pid, (v["den_stream"], v["den_out"]))
            need(dens[pid] == (v["den_stream"], v["den_out"]), f"{wp}: den_stream / den_out differ between arms")
            check_counters(v["qa"], T, f"{wp}.qa", extra={"n_clamped"}); check_counters(v["qm"], T, f"{wp}.qm", extra={"n_clamped"})
            for q in ("qa", "qm"):
                need(is_int(v[q]["n_clamped"]) and 0 <= v[q]["n_clamped"] <= v[q]["n"], f"{wp}.{q}.n_clamped")
                if arm == "C": need(v[q]["max"] <= 2047, f"{wp}.{q}: arm C entry over 2,047")
                else: need(v[q]["n_clamped"] == 0, f"{wp}.{q}: only arm C clamps")
            if arm == "W":
                b = brow["norms"]["input_layernorm"]["prompts"][pid]
                need(all(v["qa"][kk] == b[kk] for kk in QKEYS), f"{wp}.qa: arm W's mixer input counters differ from the baseline input_layernorm counters")
            m = v["mlp"]
            need(isinstance(m, dict) and set(m) == MLPKEYS, f"{wp}.mlp: keys")
            need(m["n_m"] == T * D and m["n_out"] == T * D and m["n_hidden"] == T * H, f"{wp}.mlp: entry counts inconsistent with n_tokens")
            need(m["m"] == v["qm"]["max"] and m["n_m_over_2047"] == v["qm"]["n_over_2047"], f"{wp}.mlp: MLP input stats differ from qm")
            need(m["shift_g"] == W["g"]["e"] + k - 12 and m["shift_u"] == W["u"]["e"] + k - 12 and m["shift_d"] == W["d"]["e"], f"{wp}.mlp: shifts")
            for kk in MLPKEYS - {"shift_g", "shift_u", "shift_d"}:
                need(isinstance(m[kk], (int, float)) and not isinstance(m[kk], bool) and m[kk] >= 0, f"{wp}.mlp.{kk}: not a non-negative number")
            need(m["n_silu_sat_lo"] + m["n_silu_sat_hi"] <= m["n_hidden"], f"{wp}.mlp: SiLU exits over hidden entries")


def load_runs(R):
    R = Path(R)
    base = read_jsonl(R / "baseline.jsonl"); arms = read_jsonl(R / "arms.jsonl"); prog = read_jsonl(R / "progress.log.jsonl")
    need(base, "baseline.jsonl: empty")
    for name, rows in (("baseline.jsonl", base), ("arms.jsonl", arms)):
        seen = set()
        for k, r in enumerate(rows, 1):
            need(is_int(r.get("layer")) and 0 <= r["layer"] < NL, f"{name} line {k}: layer missing or outside 0..63")
            need(r["layer"] not in seen, f"{name} line {k}: duplicate row for layer {r['layer']}")
            seen.add(r["layer"])
            need(r.get("type") == layer_type(r["layer"]), f"{name} line {k}: type {r.get('type')} is not layer {r['layer']}'s")
            finite_all(r, f"{name} layer {r['layer']}")
    bl = [r["layer"] for r in base]; al = [r["layer"] for r in arms]
    need(bl == list(range(len(bl))), f"baseline.jsonl: layers are not 0..{len(bl) - 1} in order")
    last = bl[-1]
    sets = {"r33": [i for i in R33 if i <= last], "full": list(range(last + 1))}
    need(al in sets.values(), f"arms.jsonl: layers {al} are not the arm-on layers of R33 or the full set up to layer {last}")
    plog = [p for p in prog if "layer" in p]
    need([p["layer"] for p in plog] == bl, "progress.log.jsonl: logged layers differ from the baseline layers (truncated or extra rows)")
    need([p["layer"] for p in plog if p.get("arms") == 5] == al and all(p.get("arms") in (0, 5) for p in plog),
         "progress.log.jsonl: layers logged with arms differ from the arm rows")
    if any(p.get("all_done") for p in prog): need(len(bl) == NL, "progress.log.jsonl says all_done but the baseline is not 64 layers")
    B = {r["layer"]: r for r in base}
    for r in base: check_baseline_row(r, f"baseline layer {r['layer']}")
    for r in arms: check_arm_row(r, B[r["layer"]], f"arms layer {r['layer']}")
    return base, arms, prog
