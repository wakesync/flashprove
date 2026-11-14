# RESULTS: 20261114-195-dq-ne-d-admission

Issue #195 (part of #163, #35). PREREG: [PREREG.md](PREREG.md), first commit `4aa4d2605415f87470f3e4c8d7830a5dda60b098`, with Amendments 1 to 3 (each committed before the runs it covers). Environment and hashes: [ENV.json](ENV.json). Base `2583aca969bb9f33afc92d553dcbd2e2a69fcedc`.

## Verdict

**The registered threshold is met, so the candidate is adopted on this branch. Measured, unreplicated, CPU planning only.** No stop rule of `DQ-NE-D.md` section 5 fired. Several registered items are weaker than planned or still open; they are listed below and are part of the result.

No proof with dq != d exists or was checked. Both prover gates are closed and untouched. This result says nothing about an honest unequal-width proof, about reverse-direction T3, about dh = 256, rotary, or Qwen admission.

## Read this first: one open risk found late, not tested

Found by reading the source 25 minutes before the lane's stop; **not tested, not measured**.

On the base verifier a file reaches the rotary table (`cp_verify.cpp`, the loop over `T * dh / 2` pairs, after `no-wrap-ledger`) only with dh <= d, and `no-wrap-ledger` keeps d below 2^15. So the table has at most about 2^16 * 2^15 words there. With the equality gone, dh is bounded only by `shape-heads` at 2^20 while d can stay small, so a file that passes the tests in between could ask for a rotary table of up to 2^16 * 2^20 words. The design note's N1 says the 2^20 bound "restores" the bound dh had; that holds for the `shape-heads` test, but the effective bound on dh before the table came through d.

What was measured that bears on it: the two at-bound files of T7b (dh = 32,768 and 2^20, lt = 6) are refused `forest-trees` in `layout()`, before the table, with peaks of 40 MB and 97 MB. Whether another file (other `nmin`, `lidb`, `lt`) gets past `forest-trees`, the no-overflow conditions and `w-shape-mW` to the table with a large dh was not examined. `cp_verify` sets itself no memory limit today, so this would be a larger allocation or an out-of-memory end, not an accepted false statement. A reviewer should decide whether N1 needs a tighter bound on dh or the table needs its own size test before this is merged.

## What changed

- `verifier/src/cp_verify.cpp` (`layout()`, `shape-heads`): `H * dh != d` is replaced by `!queryWidthWithinBound(H, dh)`. The name stays `shape-heads`.
- `verifier/src/vf_widths_and_bounds.h`: `QUERY_WIDTH_MOST = 2^20` and `queryWidthWithinBound(H, dh)`, the product in 128 bits, called before dq is formed.
- No other verifier source line. `vf_rejection_names.txt` unchanged. No prover file changed.
- Docs: `verifier/docs/parameter-file.md` (row H, G, dh), `docs/format/FORMAT.md` (rows `shape-heads`, `plan-tensor-layout-fill-<arr>`, `shape-words`), `docs/format/11-2-feed-forward-segment.md` (two rows).
- Tests: new `verifier/tests/query_width_bound_test.cpp`; `weights_twin_test.cpp` two shapes with dq above d; `SUITE.md` expected line of that row; `parameter_walk.py` keeps d in about half of its copies.

## Registered cases

Planning cases: 5 rounds, both binaries, base and patched alternating first. 70 records, 0 not as registered; each kit was the same bytes in every round. Source: `runs/planning/planning-summary.json`, raw output in `runs/planning/raw/`, kits in `runs/planning/kits/`.

| case | H, G, dh, d | dq | base (5 of 5) | patched (5 of 5) | peak resident, patched |
|---|---|---|---|---|---|
| T7b above | 3, 1, 2^19, 512 | 1,572,864 | `NO: shape-heads` | `NO: shape-heads` | 11,952 KiB |
| T7b one step above | 33, 1, 32768, 512 | 2^20 + 32,768 | `NO: shape-heads` | `NO: shape-heads` | 11,956 KiB |
| T7b at the bound | 32, 1, 32768, 512 | 2^20 | `NO: shape-heads` | `NO: forest-trees` | 39,552 KiB |
| T7b at the bound (design's) | 1, 1, 2^20, 512 | 2^20 | `NO: shape-heads` | `NO: forest-trees` | 97,280 KiB |
| T2, dq above d | 3, 1, 4, 8 | 12 | `NO: shape-heads` | planned | 37,780 KiB |
| T2, dq below d | 1, 1, 4, 8 | 4 | `NO: shape-heads` | planned | 37,764 KiB |
| T7c | 63, 1, 128, 4096 | 8,064 | `NO: shape-heads` | planned | 38,884 KiB |

"Planned" is the registered meaning: `-plan arrays` status 4, `pack_layout.py` made layout.txt, `-plan accounting` status 4 with one line `THE ROUNDS: HOLD` and no `internal-` line, and `-plan request` with that layout at 0 and at 128 bits both status 4. The base binary's peak is about 12,000 KiB on every file.

- The two above-bound files are refused under `shape-heads` with the base binary's memory: the test comes before any tensor is sized.
- The two at-bound files are **not valid plans**. They get past the new test and are refused later, under `forest-trees`. The design note guessed `af-policy-kF`; the measured name is different and is still not N1's.
- T2 with dq below d planned at the first registered run; the corrected rerun that Amendment 1 allowed was not needed.
- No line `plan: not the standard parameter form` appears in any kept output. `-plan request` ran with `-q`. Whether these test shapes are in the standard form was not examined.

**T7a**, the predicate alone (`runs/compiled/run-t7a-*.json`): plain build and a build with the address and undefined-behaviour sanitizers both end `query_width_bound_test: ok (2043 checks; 959 of 1984 pairs (H, dh) with H in 1..64 and dh = 2^1..2^31 admitted)`, status 0, no sanitizer report.

**T1**, layout twins (`runs/compiled/run-twin-t1-second.json`): `weights_twin_test: ok (48 worlds, 780 units, 979500 cells, 7389952 places without a cell; 5508 checks)`. The 12 new worlds are d = 8, dq = 12 and d = 20, dq = 24 with experts, at 6 column settings. The test at its base text, built against the patched tree, prints the base line (36 worlds, 4152 checks).

**T8**, existing rows, base against patched (`runs/existing/existing-summary.json`): 10 rows counted, each with the same exit status and the same normalised hash on both binaries, **one round** (five were registered).

| row | status | outcome on both |
|---|---|---|
| example_kits | 0 | 7 parameter files, 0 not as expected |
| served_form (has the dense cases) | 0 | all as expected |
| plan_tau | 0 | 13 cases |
| kit_rounds | 0 | 3 kits, 0 not as stored |
| la_equals_lt | 1 | `NO: shape-la` |
| stored proof, accepted-proof | 0 | `YES` |
| stored proof, clipped-gap, with `-policy` | 0 | `WITHIN LIMITS: clipped-gap C=...` |
| call_accounting | 0 | 0 lines not as in the call |
| rejected-proofs, accepted-proof | 0 | 10 altered sets: all rejected |
| rejected-proofs, clipped-gap | 0 | 10 altered sets: all rejected |

`ws_build_fuzz` (sanitizers, 300,000 shapes, seed 1, built against the patched tree): status 0, `20545 built`, `refused w-shape-mW: 9059`, the same six lines as the committed `research/cpu-full-suite/full-screens/verifier.ws_build_fuzz.txt`.

## Weaker than registered, and faults of this experiment's own harness

1. **T8 is one round, not five.** Outputs are deterministic text, and the planning cases did run five rounds; T8's repeat was not done.
2. **Sanitized planning calls: PENDING.** The one registered attempt to build the whole verifier with sanitizers hit its 120 s limit (`runs/compiled/build-cp_verify-sanitized-once.json`). Sanitized coverage is T7a and `ws_build_fuzz` only. The issue asked for the small boundary cases under UBSan: that was done for the predicate, not for the planning calls.
3. **T3: NOT ESTABLISHED.** Not attempted (time). Nothing here shows that a stored proof is rejected under a changed-H statement by proof checking.
4. **Clipped-gap stored proof, first run not counted.** The harness left out the `-policy` option; both binaries answered `NO: policy`. Kept in `runs/existing/raw/whole_clipped_gap.*` (Amendment 2).
5. **Rejected-proofs rows took three attempts.** Twice the test refused to start (its work folder check; the second time through a fault of the lane's wrapper). Receipts in `runs/existing/not-started/` (Amendment 3). These seven files had host paths replaced by placeholders after their hashes were recorded.
6. **T8 order.** Base and patched ran side by side on two cores, not alternating.
7. **Walk harness (N6).** One short smoke run with the patched binary: `33 files; fault 0, unchecked 0, slow 0, large 0`. Whether any of those files had dq != d was not checked. The walk's usual length and the sanitized walk were not run.
8. **`FORMAT.md`, row `shape-words`.** Its "cannot fail" argument for G dh went through d and the equality. For dq != d that step is gone and was not re-derived; the row now says so. If it does fail, the call ends with that refusal by name.
9. **Kits.** The derived lines were worked out on equal-width shapes with the base binary, as registered. The T7c kit needed a line the registration had not listed (`group link`), stated in Amendment 1 before the run.
10. A build of the T1 binary raced the edit of its source and printed the base line; it is kept as `run-twin-t1.json` and is not T1. The counted run is `run-twin-t1-second.json`.

## Not run

The full suite; the `extreme_files`, `clang_build`, sanitized-walk rows; anything with a GPU, a prover, weights or a proof made here; the Lean model (unchanged, and it does not cover this).
