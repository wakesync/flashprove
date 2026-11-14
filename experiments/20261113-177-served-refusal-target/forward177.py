#!/usr/bin/env python3
"""Teacher-forced float64 forwards of both checkpoints over prompt + served reply (PREREG "Metric"). CPU, REF path only.

Reused unchanged: PR #162 `u1_p03.forward` (stock layers 0..16 shared, then layers 17..63 fused: stock layer fetched
once, the abl layer = that dict with the 70 changed tensors fetched from the abl repo) and `u1_p03.by_layer`; PR #139
`u1_margin.final_hidden` / `u1_margin.two_way` (one streamed lm_head pass, KL both ways, top-1, margins); PR #124 `e2e.py`
and PR #88 `q1_forward.py` underneath. New here: building one input state holding several prompts (prompt ids + reply
ids except the last, per included prompt) instead of p03 alone, and writing the full per-position output.

The full output holds both checkpoints' top-1 ids at every position, which reveal the reply tokens; it is written to
<private_out> (lane scratch, outside the repo, PREREG publication rule). Weight manifests and progress logs go to <runs>.
Weights are streamed by HTTP range requests and never written to disk; residual states are saved to <scratch> (resume).

Usage:
  forward177.py run <scratch> <runs> <served-ids-private.json> <private_out.json>
  forward177.py inputs <served-ids.json>       print the teacher-forced input layout only (no weights)
"""
import json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261113-157-u1-margin-p03"))
import u1_p03 as P3         # PR #162, unchanged
U, E, F = P3.U, P3.E, P3.F  # PR #139 u1_margin, PR #124 e2e, PR #88 q1_forward, unchanged

def layout(S):
    inc = [q for q in S["prompts"] if q["included"]]
    seqs = {}
    for q in inc:
        inp = q["prompt_ids"] + q["reply_ids"][:-1]
        seqs[q["id"]] = dict(n_prompt=len(q["prompt_ids"]), n_reply=len(q["reply_ids"]), T=len(inp), input_ids=inp,
                             reply_ids=q["reply_ids"], finish_reason=q["finish_reason"])
    return seqs

def cmd_run(scratch, runs, ids_file, private_out):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    seqs = layout(json.load(open(ids_file)))
    diff, bylayer = P3.by_layer()
    stock, abl = F.Ckpt("stock", runs), F.Ckpt("abl", runs); pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = E.load_state(sc / "ckpt.npz"); St = {"S": X["S"], "A": X.get("A") or None}
        U.plog(runs, resume=True, meta=meta)
    else:
        emb = stock.emb_rows(sorted({t for s in seqs.values() for t in s["input_ids"]})); stock.save()
        St = {"S": {pid: np.stack([emb[t] for t in s["input_ids"]]) for pid, s in seqs.items()}, "A": None}
        meta = dict(next_layer=0, prompts=list(seqs), n_changed=len(diff))
        U.plog(runs, start=True, prompts=list(seqs), tokens=sum(s["T"] for s in seqs.values()), n_changed=len(diff),
               changed_layers=sorted(bylayer))
    P3.forward(stock, abl, St, meta, sc, runs, pool, range(0, 17), range(17, F.NL), bylayer)
    Hs = U.final_hidden(stock, {"REF": St["S"]}); Ha = U.final_hidden(abl, {"REF": St["A"]})
    t0 = time.time(); res = U.two_way(Hs, Ha, E.lm_head_chunks(stock)); stock.save(); abl.save()
    out = dict(note="float64 REF stock vs float64 REF abl over prompt + served reply; D = KL(stock || abl) in nats; "
                    "PRIVATE: top-1 ids reveal reply tokens", sequences=seqs, prompts=res, seconds=round(time.time() - t0, 1))
    Path(private_out).write_text(json.dumps(out) + "\n")
    pool.close(); pool.join(); U.plog(runs, logits_done=True, seconds=out["seconds"])

def cmd_inputs(ids_file):
    seqs = layout(json.load(open(ids_file)))
    for pid, s in seqs.items(): print(pid, "prompt", s["n_prompt"], "reply", s["n_reply"], "T", s["T"])
    print("total positions", sum(s["T"] for s in seqs.values()))

if __name__ == "__main__":
    a = sys.argv
    if a[1] == "run": cmd_run(a[2], a[3], a[4], a[5])
    elif a[1] == "inputs": cmd_inputs(a[2])
    else: raise SystemExit(__doc__)
