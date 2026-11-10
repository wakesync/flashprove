# RESULTS: 20261110-6-coverage-inventory

Issue #6, lane coverage6. Base main `ba1e3067`. PREREG `08a683f5` (committed alone, before any code). Status of every number: **measured, unreplicated**, CPU only, stored synthetic fixtures. This is a descriptive inventory plus three negative tests. It does not establish soundness, and finite tests do not establish it either.

## Verdict

| part | registered threshold | result | verdict |
|---|---|---|---|
| Inventory | >= 40 rows, every row has a site, every site resolves, four kinds only, every `prover_only` / `not_enforced` row in an open gap | 64 rows, 106 sites, checker exit 0, 0 faults | **PASS** |
| Checker self-test (not a registered threshold, recorded per the Runs section) | a changed symbol must make the checker fail | real inventory 0 faults; 4 of 4 mutations (renamed symbol, moved file, row dropped from gaps, unknown kind) each give 1 fault | as expected |
| N1 commitment substitution | 5 of 5 attacks rejected for the intended check, 5 of 5 controls accept | 5 of 5 `NO: model-statement` with the `id:` line; 5 of 5 controls `WITHIN LIMITS` | **PASS** |
| N2 policy substitution (a: no `-policy`, b: `-policy exact-match`) | 5 of 5 per sub-arm, controls 5 of 5 | 10 of 10 `NO: policy` with the expected `policy:` reason (5 a, 5 b); 5 of 5 controls `WITHIN LIMITS` | **PASS** |
| N3 coverage substitution | 5 of 5 attacks rejected for the intended check, 5 of 5 controls accept | 5 of 5 `check_proof: rejected: the request file's checked range is 60:64, but you expect 59:64`; 5 of 5 controls `verified`; `cp_verify` alone on the same files 5 of 5 `YES` | **PASS** |

No attack arm was accepted (0 of 20). Raw: [runs/negative-registered.json](runs/negative-registered.json) (commands, exit codes, last 8 lines, the reason line, input SHA-256s). Inventory counts: [runs/inventory-check.json](runs/inventory-check.json). Self-test: [runs/checker-selftest.json](runs/checker-selftest.json).

## Inventory counts

From `python3 research/coverage/check_inventory.py` on this branch ([research/coverage/inventory.yaml](../../research/coverage/inventory.yaml)):

| | proof_constraint | verifier_validation | prover_only | not_enforced | total |
|---|---|---|---|---|---|
| shipped | 28 | 12 | 4 | 10 | 54 |
| research (fork prototypes, not in cp_verify) | 3 | 3 | 0 | 4 | 10 |
| total | 31 | 15 | 4 | 14 | 64 |

By category: 21 operator, 14 range/rounding, 22 committed input/state, 7 output position. 10 open gaps (7 plain-language gaps G-01 to G-07, 3 open obligations G-OB1 to G-OB3) cover all 18 `prover_only` and `not_enforced` rows (28 rows are named in some gap). The classification is by reading source and docs at the base commit; a row's site says where its enforcement lives, not that the enforcement is correct.

## What the negative tests show, and what they do not

Each test hands a **complete, honestly made proof** (the stored synthetic examples, unaltered) to a caller who wants a different statement than the proof is about. That is the attack this class of row must stop: no bit is flipped, so the proof part of the verifier has nothing to reject.

- **N1** The clipped-gap example's own key, leaf, configuration, request and proof, under the exact-match example's commitment ID. The key stage recomputes the ID from the files and compares it with `-id`; it ends `NO: model-statement` with the line "id: these are not the files of the commitment that you named". With its own ID the same files end `WITHIN LIMITS`. So the commitment binding a client gets is exactly as good as the ID it brings itself (row IS-01).
- **N2** The same files under their own, correct ID, called by a client that expects exact match: (a) without `-policy`, `NO: policy` with "the request covers more than the output token, the parameter file sets another policy than exact-match, and the call has no -policy"; (b) with `-policy exact-match,256,256,0,16,8`, `NO: policy` with "the option -policy names another kind of policy". The proof is valid; it is a proof of a weaker claim (row IS-08). In 5 of 5 (a) and (b) runs the rejection came before any stage started (median 0.005 s).
- **N3** The exact-match example (range 60:64, 3 checked tokens and y) given to `integrations/check_proof.py` with `--range 59:64`. `check_proof.py` rejects it on its range comparison. `cp_verify` alone on the same files says `YES` 5 of 5: a coverage truncation is invisible to the proof and visible only to a client that compares the range with its own (row OUT-05).

Not shown: anything about a cheating prover that forges a proof (none was built), any other fixture or model, the full-size example, or any claim beyond "these three checks fire on these inputs". The times in the raw file are diagnostic only (shared, loaded host).

## Deviations from the PREREG

- The checker self-test writes its JSON with `--json`; the first call failed because `runs/` did not exist yet (no result lost; rerun after the negative run created it). Not a registered arm.
- `research/coverage/selftest_checker.py` was added after registration as the means for the self-test the Runs section asks for; the PREREG names only its output file.
- No other deviation. Debug before the registered run was `negative.py --dry-run` only, which calls no verifier. The registered run took 34.9 s of its 900 s budget.

## Reproduce

```
verifier/build.sh
python3 research/coverage/check_inventory.py
python3 research/coverage/selftest_checker.py
python3 experiments/20261110-6-coverage-inventory/negative.py --out runs/negative-rerun.json
```

The last command refuses to overwrite an existing output file; give a new name.
