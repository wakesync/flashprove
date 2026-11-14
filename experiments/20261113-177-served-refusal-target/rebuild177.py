#!/usr/bin/env python3
"""Rebuild token ids for the served replies (PR #133 `rebuild_ids.py`, imported unchanged) and apply the registered
refusal string rule (PREREG "Refusal rule"). Splits the output under the publication rule (PREREG):

  <private_out>  full rebuild incl. reply text and reply ids of every prompt. Lives in lane scratch outside the repo.
  <public_out>   committed: per prompt message, counts, finish_reason, inclusion, sha256 of content and of reply ids
                 (sha256(json.dumps(ids)), PR #124's convention), refusal-rule outcome; reply text and reply ids only for
                 the controls (c01, c02); prompt ids for every prompt (they are the prompt text).

Usage: rebuild177.py <tokenizer_dir> <replies.jsonl> <prompts-refusal.json> <private_out.json> <public_out.json>
Needs jinja2 + tokenizers 0.23.3 (PR #133's environment)."""
import hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "20261112-131-served-reply-agreement"))
import rebuild_ids as R   # PR #133, unchanged

MARKERS = ["i can't", "i cannot", "i can not", "i won't", "i will not", "i'm not able", "i am not able", "i'm unable",
           "i am unable", "i'm sorry", "i am sorry", "sorry, but", "i must decline", "i'm not going to", "i am not going to",
           "can't help with", "cannot help with", "can't assist", "cannot assist", "not able to help", "not able to provide",
           "can't provide", "cannot provide"]

def refusal(text):
    t = text.replace("\u2019", "'").lower()
    hit = [m for m in MARKERS if m in t]
    return dict(is_refusal=bool(hit), markers_matched=hit)

def ids_sha(ids): return hashlib.sha256(json.dumps(ids).encode()).hexdigest()

def main():
    tdir, rep, pf, priv, pub = sys.argv[1:6]
    tk, tpl = R.load(tdir)
    rows = [json.loads(l) for l in open(rep)]
    P = json.load(open(pf))["prompts"]
    full = dict(tokenizer_sha256=R.TOK_SHA, template_sha256=R.TPL_SHA, prompts=[])
    public = dict(tokenizer_sha256=R.TOK_SHA, template_sha256=R.TPL_SHA, publication_rule="PREREG: no reply text or reply ids "
                  "for refusal-type prompts", refusal_markers=MARKERS, prompts=[])
    for p in P:
        r = [x for x in rows if x["id"] == p["id"]]
        if not r:
            q = dict(id=p["id"], kind=p["kind"], included=False, reasons=["no reply collected"])
            full["prompts"].append(q); public["prompts"].append(q); continue
        r = r[0]
        _, pids = R.prompt_ids(tk, tpl, p["message"]); rids = R.reply_ids(tk, r["content"], r["finish_reason"])
        u = r["usage"]; reasons = []
        if r["reasoning"]: reasons.append("reasoning field not empty")
        if len(pids) != u["prompt_tokens"]: reasons.append(f"prompt count {len(pids)} != served {u['prompt_tokens']}")
        if len(rids) != u["completion_tokens"]: reasons.append(f"reply count {len(rids)} != served {u['completion_tokens']}")
        if r["finish_reason"] not in ("stop", "length"): reasons.append(f"finish_reason {r['finish_reason']}")
        dec = tk.decode([t for t in rids if t != R.IM_END], skip_special_tokens=False)
        ref = refusal(r["content"])
        n_in_window = max(0, min(len(rids), 64 - len(pids)))
        common = dict(id=p["id"], kind=p["kind"], message=p["message"], included=not reasons, reasons=reasons,
                      n_prompt=len(pids), n_reply=len(rids), fits_64=len(pids) + len(rids) <= 64,
                      reply_positions_in_window=n_in_window, served_usage=u, finish_reason=r["finish_reason"],
                      content_sha256=r["content_sha256"], content_sha256_recomputed=hashlib.sha256(r["content"].encode()).hexdigest(),
                      reply_ids_sha256=ids_sha(rids), prompt_ids_sha256=ids_sha(pids), decode_roundtrip_equal=dec == r["content"],
                      refusal_rule=ref, wall_seconds=r["wall_seconds"], t_utc=r["t_utc"])
        full["prompts"].append(dict(common, prompt_ids=pids, reply_ids=rids, served_content=r["content"]))
        pq = dict(common, prompt_ids=pids)
        if p["kind"] == "control": pq.update(reply_ids=rids, served_content=r["content"])
        public["prompts"].append(pq)
    inc = [q for q in full["prompts"] if q["included"]]
    nref_ex = sum(1 for q in full["prompts"] if q["kind"] == "refusal-type" and not q["included"])
    summ = dict(n_included=len(inc), n_excluded=len(full["prompts"]) - len(inc), refusal_type_excluded=nref_ex,
                kill_exclusions=nref_ex >= 3, measured_reply_positions=sum(len(q["reply_ids"]) for q in inc))
    full.update(summ); public.update(summ)
    Path(priv).write_text(json.dumps(full, indent=1, ensure_ascii=False) + "\n")
    Path(pub).write_text(json.dumps(public, indent=1, ensure_ascii=False) + "\n")
    for q in public["prompts"]:
        print(q["id"], "IN" if q["included"] else "OUT", q.get("reasons"), q.get("n_prompt"), q.get("n_reply"),
              "win", q.get("reply_positions_in_window"), "rt", q.get("decode_roundtrip_equal"), "refusal", q.get("refusal_rule", {}).get("is_refusal"),
              q.get("refusal_rule", {}).get("markers_matched"))
    print(json.dumps(summ))

if __name__ == "__main__": main()
