# U1 margin on the full registered prompt set (p03-repeat-word added)

Issue #157. Follows PR #139 (`experiments/20261112-134-u1-margin/`), which measured the float64 stock-vs-abliterated output distance D against PR #124's head-only integer lowering error E on 9 of the 10 registered prompts.

## What this does
- Computes D = KL(REF_stock || REF_abl) per teacher-forced position on the one missing prompt, p03-repeat-word (512 positions), with the same float64 reference code as PR #139.
- Merges it with PR #139's committed D for the other 9 prompts and applies PR #139's unchanged acceptance rule to all 10 prompts (1,461 positions).
- Runs p03 twice and compares the two outputs bit for bit (the variance statement for a deterministic computation).

## What this is not
- Not a proof. Nothing here is proved; it is a plain float64 numpy forward pass.
- E is not recomputed. It is read from PR #124's committed files (head-only integer lowering, XS18 primary, XS20 secondary).
- No served replies, no sampling, no refusal judgement. Top-1 tokens are reported as ids only.

## What is checked
- Gate (a): " Tokyo" (25358) at the last position of p01 on both checkpoints (PR #139's committed record).
- Gate (b): on p03, this run's REF top-1 and margins equal PR #124's committed `ref_top1` / `ref_margin` bit for bit on both checkpoints. On the 9 merged prompts, PR #139's 1e-6 rule, re-evaluated by its `analyse()`.
- Gate (c): every tensor this run fetched has the sha256 in PR #124's committed manifest and PR #87's committed hash; coverage is exactly the 850 stock tensors, embedding row 279 and the 71 abliterated tensors the pass needs.
- PR #139's committed D file is checked by sha256 before it is used.
- Every other fixed input `merge10.py` reads is also checked against its committed sha256 before anything is parsed (added after the round-2 PR #162 review, validation only): PR #124's E files `e2e-stock.json` / `e2e-abl.json`, its manifests and `prompts-e2e.json`, PR #87's manifests, PR #139's manifests, `analysis.json` and `analyse.py`. Any mismatch or missing file exits 2 with nothing written.

## Files
- `PREREG.md`: registration (first commit).
- `u1_p03.py`: driver. `run` (registered), `fixture` (debug on a prompt not in the suite).
- `run_p03.sh`: the registered job (slot grant log, memory wait, run 1 and run 2, watchdog for the hard stop, disk and memory).
- `merge10.py`: 10-prompt merge, gates, statistics (through PR #139's `analyse.analyse()`, unchanged), determinism check.
- `test_merge10.py`: hostile-input tests for `merge10.py` (added after the PR #162 reviews, validation only): the committed inputs reproduce `runs/merged-analysis.json` and `runs/merge-validation.json` byte for byte, and 12 malformed inputs (truncated JSON, duplicate keys, an absent prompt or arm in PR #124's E files, missing manifest keys or files) exit 2 with nothing written. Round 2 added 7 more cases, refused by the sha256 pins with exit 2 and nothing written: the reviewer's reproduction (PR #124 XS18 `kl[1:]` on p03 set to -1.0 in both E files, which the previous code accepted with exit 0 and PASS), one negative E value on another prompt, a whitespace-only change to an E file, and a one-byte change to a PR #124 manifest, a PR #87 manifest, PR #139's `analysis.json` and PR #139's `analyse.py`. 20 cases in total.
- `add_results_row.py`: writes the `research/results.yaml` row from `runs/merged-analysis.json`.
- `runs/run1/`, `runs/run2/`: per-position D (`d-p03.json`), manifests, progress logs, `run.time`.
- `runs/merged-analysis.json`, `runs/merge-validation.json`: the result.
- `runs/debug-fixture.json`: the debug fixture output.

## Reproduce
Analysis from the committed files (seconds, no weights):

    python3 merge10.py runs/run1 runs/run2 <new dir>

It refuses to overwrite an existing output; give it a new directory. Input tests (seconds, temporary copies only):

    python3 test_merge10.py

The p03 run (about 30 min per run on 6 cores, peak RSS under 9 GB, weights streamed over HTTP, nothing cached):

    flock <bigmem.lock> fp-heavy.sh taskset -c 10-15 /usr/bin/time -v bash run_p03.sh <scratch>

This writes into `runs/`; move the committed `runs/run1`, `runs/run2` and `runs/progress.log` aside first. Debug fixture:

    python3 u1_p03.py fixture <scratch> <out.json>
