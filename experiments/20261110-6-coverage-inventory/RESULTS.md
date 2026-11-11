# RESULTS: 20261110-6-coverage-inventory

Issue #6, lane coverage6, revised after review by lane fix97. Base main `ba1e3067`. PREREG `08a683f5` (committed alone, before any code), amendment `f9b5259b` (committed alone, before the repair run). Status of every number: **measured, unreplicated**, CPU only, stored synthetic fixtures. This is a descriptive inventory, not a complete one, plus three negative tests. It does not establish soundness, and finite tests do not establish it either.

**Evidence of record: the repair run** registered in the amendment, with scripts committed before it ran: [runs/negative-repair-20261111.json](runs/negative-repair-20261111.json) (started 2026-11-11T01:16:44Z, 35.1 s), [runs/inventory-check-20261111.json](runs/inventory-check-20261111.json), [runs/checker-selftest-20261111.json](runs/checker-selftest-20261111.json), all in commit `30b0de8d`. The first run's receipts (`runs/negative-registered.json`, `runs/inventory-check.json`, `runs/checker-selftest.json`) are kept unchanged; they came from scripts that were committed only after the run (see Deviations). The repair run's negative counts equal the first run's, with the same input SHA-256s.

## Verdict

| part | registered threshold | result | verdict |
|---|---|---|---|
| Inventory | >= 40 rows, every row has a site, every site resolves, four kinds only, every `prover_only` / `not_enforced` row in an open gap | 84 rows, 148 sites, checker exit 0, 0 faults (first version: 64 rows, 106 sites) | **PASS** on the threshold; the hypothesis's "every" is **not met** (Amendment 3) |
| Checker self-test (not a registered threshold, recorded per the Runs section) | a changed symbol must make the checker fail | real inventory 0 faults; every listed mutation faults: M1 renamed symbol, M2 moved file, M3 each of 21 gap rows dropped (21 of 21), M4 unknown kind, M5 unknown kind also declared in `kinds`, M6 extra declared category, M7 short symbol, M8 proof row in a plain gap, M9 excluded directory dropped, M10 excluded directory missing | as expected |
| N1 commitment substitution | 5 of 5 attacks rejected for the intended check, 5 of 5 controls accept | 5 of 5 `NO: model-statement` with the `id:` line; 5 of 5 controls `WITHIN LIMITS` | **PASS** |
| N2 policy substitution (a: no `-policy`, b: `-policy exact-match`) | 5 of 5 per sub-arm, controls 5 of 5 | 10 of 10 `NO: policy` with the expected `policy:` reason (5 a, 5 b); 5 of 5 controls `WITHIN LIMITS` | **PASS** |
| N3 coverage substitution | 5 of 5 attacks rejected for the intended check, 5 of 5 controls accept | 5 of 5 `check_proof: rejected: the request file's checked range is 60:64, but you expect 59:64`; 5 of 5 controls `verified`; `cp_verify` alone on the same files 5 of 5 `YES` | **PASS** |

No attack arm was accepted (0 of 20), in the repair run and in the first run. Raw: [runs/negative-repair-20261111.json](runs/negative-repair-20261111.json) (commands, exit codes, last 8 lines, the reason line, input SHA-256s). Inventory counts: [runs/inventory-check-20261111.json](runs/inventory-check-20261111.json). Self-test: [runs/checker-selftest-20261111.json](runs/checker-selftest-20261111.json). Diagnostic times of the repair run (min / median / max, s): N1 0.297 / 1.403 / 1.538, N2 0.003 / 0.005 / 1.73, N3 0.402 / 1.422 / 2.023.

## Inventory counts

From `python3 research/coverage/check_inventory.py` on this branch ([research/coverage/inventory.yaml](../../research/coverage/inventory.yaml)):

| | proof_constraint | verifier_validation | prover_only | not_enforced | total |
|---|---|---|---|---|---|
| shipped | 37 | 13 | 4 | 11 | 65 |
| research (fork prototypes, not in cp_verify) | 10 | 3 | 0 | 6 | 19 |
| total | 47 | 16 | 4 | 17 | 84 |

By category: 29 operator, 22 range/rounding, 24 committed input/state, 9 output position. 10 open gaps (7 plain-language gaps G-01 to G-07, 3 open obligations G-OB1 to G-OB3) cover all 21 `prover_only` and `not_enforced` rows (32 rows are named in some gap). 14 directories under `research/operators/`: 8 cited by a row, 6 listed under `excluded` with a reason. The classification is by reading source and docs; a row's site says where its enforcement lives, not that the enforcement is correct.

Rows added after review (20): OP-15 embedding lookup; IS-23 stream links between segments; RR-15 to RR-21 range conditions 1 to 6 and 8; OUT-08 tokens after e; OUT-09 the caller's y (split from OUT-03); OP-R8 to OP-R10 and IS-24 the GLM KDA prototypes; OP-R11 to OP-R14 and RR-R1 the qwen_ops relations and ranges. First version (64 rows, 31 / 15 / 4 / 14): [runs/inventory-check.json](runs/inventory-check.json). The inventory is not complete for the shipped verifier: nothing but review checks that.

## What the negative tests show, and what they do not

Each test hands a **complete, honestly made proof** (the stored synthetic examples, unaltered) to a caller who wants a different statement than the proof is about. That is the attack this class of row must stop: no bit is flipped, so the proof part of the verifier has nothing to reject.

- **N1** The clipped-gap example's own key, leaf, configuration, request and proof, under the exact-match example's commitment ID. The key stage recomputes the ID from the files and compares it with `-id`; it ends `NO: model-statement` with the line "id: these are not the files of the commitment that you named". With its own ID the same files end `WITHIN LIMITS`. So the commitment binding a client gets is exactly as good as the ID it brings itself (row IS-01).
- **N2** The same files under their own, correct ID, called by a client that expects exact match: (a) without `-policy`, `NO: policy` with "the request covers more than the output token, the parameter file sets another policy than exact-match, and the call has no -policy"; (b) with `-policy exact-match,256,256,0,16,8`, `NO: policy` with "the option -policy names another kind of policy". The proof is valid; it is a proof of a weaker claim (row IS-08). In 5 of 5 (a) and (b) runs the rejection came before any stage started (median 0.005 s).
- **N3** The exact-match example (range 60:64, 3 checked tokens and y) given to `integrations/check_proof.py` with `--range 59:64`. `check_proof.py` rejects it on its range comparison. `cp_verify` alone on the same files says `YES` 5 of 5: a coverage truncation is invisible to the proof and visible only to a client that compares the range with its own (row OUT-05).

Not shown: anything about a cheating prover that forges a proof (none was built), any other fixture or model, the full-size example, or any claim beyond "these three checks fire on these inputs". The times in the raw file are diagnostic only (shared, loaded host).

## Deviations from the PREREG

- The checker self-test writes its JSON with `--json`; the first call failed because `runs/` did not exist yet (no result lost; rerun after the negative run created it). Not a registered arm.
- `research/coverage/selftest_checker.py` was added after registration as the means for the self-test the Runs section asks for; the PREREG names only its output file.
- **Scripts were not committed before the registered run** (review of PR #97). `negative.py`, the checker, the self-test and the inventory first appear in `81c93f46` (23:27:14Z), together with the receipts of a run that ran 23:24:54Z to 23:25:29Z. The earlier text here said "No other deviation"; that was wrong. Repair: Amendment 1-2 of the PREREG (`f9b5259b`, committed and pushed alone) registered a repair run with the committed scripts; it ran at 01:16:44Z and is the evidence of record. The first receipts are kept as they were.
- **"Every" in the hypothesis was not met** (Amendment 3): review found 20 missing elements; they were added and the wording changed to "an inventory, not complete".
- **The checker changed after registration** (Amendment 4): fixed schema, minimum symbol length, plain-gap kind rule, research-directory check; self-test cases M5 to M10. It now runs in CI (claims-check).
- Debug before the first registered run was `negative.py --dry-run` only, which calls no verifier. The first run took 34.9 s and the repair run 35.1 s of the 900 s budget.

## Reproduce

```
verifier/build.sh
python3 research/coverage/check_inventory.py
python3 research/coverage/selftest_checker.py
taskset -c 0-5 python3 experiments/20261110-6-coverage-inventory/negative.py --out runs/negative-rerun.json
```

The last command refuses to overwrite an existing output file; give a new name.
