# RESULTS: 20261111-7-cpu-phase-cost

Issue #7. Registration: [PREREG.md](PREREG.md) (commit 069c0d27, alone). Environment and frozen manifest: [ENV.json](ENV.json). Raw data: `runs/runs.jsonl` (one line per process, 80 processes), statistics `runs/summary.json` (from `analyze.py`), artifact hashes `runs/artifact-hashes.json`.

## In plain words

- This measures where the time goes when one of this repository's two CPU-runnable proof programs makes a proof and a separate program checks it. It is the first phase-by-phase cost table on main for either program. Both are small research programs. Neither is the GPU prover and neither is a real model.
- **Profile B (one Qwen DeltaNet attention head, 4 positions, made-up inputs): PASS.** Proving is 79% of the time from "start the prover" to "the independent checker said yes" (13.40 s of 16.91 s, medians of 10). Checking is second (3.26 s). Everything else together is under 0.3 s. Proofs are 6.76 MB; the prover peaks at 1,229.1 MiB of memory (about 1.29 GB), the checker at 698.1 MiB (about 0.73 GB). Making several proofs in one process does not make each one cheaper: there is no shared setup to spread out.
- **Profile A (the toy protocol test of PR #40): FAIL, by a hair.** The ordering part of the prediction held: proving a batch of 3 requests (0.74 s) and making the commitment (0.52 s) are the two biggest phases, clearly separated from the rest. But the registered amortization threshold was "a batch on an existing commitment costs below 50% of a cold run", and it came out at **50.02%** (0.823 s vs 1.645 s). That is a FAIL under the registration and is reported as one; it is not rounded into a pass. It is also not robust to how the registration is read: the PREREG words this metric two ways, and the other wording gives 49.99% (see the note under the verdict table).
- On a single core of this shared virtual machine, these programs are not fast: profile B proves 0.30 head positions per second, 0.24 counting the independent check.
- **Not measured here:** anything on a GPU, Qwen3.8-27B or any whole model, generated-tokens/s, overhead compared to plain inference (no plain-inference baseline was run), and money.

## Verdicts against the registration

| profile | registered threshold | result | verdict |
|---|---|---|---|
| B | prove / e2e >= 0.60, prove range not overlapping the next phase, verification second | 0.792; prove 13.270..13.673 vs verification 3.144..3.386; order prove > verification > witness > startup > write > read | **PASS** |
| A (i) | commit and prove the two largest phases, each range separate from every smaller phase | order prove > commit > verification > setup > write > witness; commit 0.503..0.535 and prove 0.726..0.784 vs the next, verification 0.238..0.325 | holds |
| A (ii) | amortized per-batch verified median < 50% of cold e2e median, and amortized max < cold min | 0.8229 / 1.6452 = **0.5002**; max 0.856 < min 1.584 | **does not hold** (ratio) |
| A | (i) and (ii) | | **FAIL** |

**Note (2026-11-11, after review of PR #106): two registered wordings of A (ii).** The PREREG defines the amortized number twice. Its "Metric" section says the per-batch cost is the median of prove over batches 2..K and the median of check_proof over those batches, i.e. two separate medians, summed. Its "Acceptance threshold" says "the amortized per-batch verified latency median (prove + check_proof x3 of one batch)", i.e. the median of per-batch sums. `analyze.py` implements the threshold wording; it was written after the registered run (commit f70ff0c, not the harness commit 499694a). From the committed `runs/runs.jsonl` (cold e2e median 1.645225 s), median over processes of each process's median per-batch sum: 0.822946 s, ratio **0.500203, FAIL** (this table, the analyzer). Median over processes of [median prove + median check] per process, the literal Metric wording: 0.822399 s, ratio **0.499870**, which would pass (its max 0.847541 s is also below the cold min 1.584263 s). The verdict stays FAIL: the threshold sentence is the one that defines PASS/FAIL, it says "of one batch", and it is the more conservative reading. The honest summary is that A (ii) sits on the threshold and its sign depends on the aggregation, not only on rounding. Both numbers were recomputed from the raw log by a reviewer of PR #106 and again, with separate code, before this note was written. PREREG Amendments (2026-11-11) records the same.

Every one of the 80 processes exited 0; every proof was accepted by its independent verifier (A: 330 proofs, B: 50 statements). No run was excluded, retried or replaced. Registered run: slot granted 04:26:07Z, done 04:42:02Z (955 s of a 2,700 s budget).

## Profile A: CPU reference protocol fixture (PR #40), cold, n = 10

Seconds, sample SD, min..max. One prover process (configure, commit, prove one batch of 3, write files) then one verifier process (configure, read files, check key, entry and 3 proofs). Seeds 0..9.

| phase | median | SD | min..max |
|---|---:|---:|---:|
| process startup (prover) | 0.0120 | 0.0015 | 0.0096..0.0133 |
| configure (parse and size public files) | 0.1130 | 0.0057 | 0.1058..0.1234 |
| **setup** (startup + configure) | **0.1260** | 0.0062 | 0.1157..0.1359 |
| witness (toy matrix and table rows) | 0.0001 | 0.0000 | 0.0000..0.0001 |
| commit: two tables (encode + salted Merkle) | 0.0342 | 0.0007 | 0.0332..0.0352 |
| commit: key file (range / one-time proof) | 0.3814 | 0.0072 | 0.3674..0.3927 |
| commit: entry file (LINK proof) | 0.1035 | 0.0036 | 0.1021..0.1139 |
| **commit, total** | **0.5199** | 0.0093 | 0.5030..0.5345 |
| **prove** (one batch of 3 requests) | **0.7375** | 0.0228 | 0.7258..0.7835 |
| write files (key, entry, 3 proofs) | 0.0015 | 0.0002 | 0.0013..0.0020 |
| prover process wall | 1.3840 | 0.0291 | 1.3459..1.4409 |
| verifier: startup | 0.0051 | 0.0007 | 0.0045..0.0064 |
| verifier: configure | 0.1108 | 0.0182 | 0.1080..0.1672 |
| verifier: read files | 0.0065 | 0.0005 | 0.0058..0.0076 |
| verifier: check key | 0.0245 | 0.0019 | 0.0225..0.0284 |
| verifier: check entry | 0.0149 | 0.0013 | 0.0140..0.0178 |
| verifier: check 3 proofs | 0.0873 | 0.0072 | 0.0825..0.1008 |
| **independent verification** (verifier process wall) | **0.2500** | 0.0260 | 0.2384..0.3253 |
| **end-to-end verified-before-release** | **1.6452** | 0.0443 | 1.5843..1.7420 |

Bytes (n = 10): key 500,884 (SD 1,215, 499,432..502,728); entry 131,928 (893, 130,352..133,008); each proof about 576 to 577 KB (577,092 / 576,340 / 576,864 medians for requests 1..3, range 571,716..580,116). Peak RSS (kernel high-water mark per process): prover 110.6 MiB (110.1..111.0), verifier 10.2 MiB (10.1..10.4). The verifier figure is an upper bound: `ru_maxrss` of a child forked from the Python runner carries the high-water mark of the pre-exec fork image, so much of the 10.2 MiB may be the runner's image rather than the verifier (profile B's hundreds of MiB are not materially affected). Process CPU time is within 0.1% of wall for both (single-threaded).

Positions/s: **not applicable.** Toy requests are byte strings and the toy segments do not prove model inference or the replies (see `blocks/frame/tests/seam_world.h`). Notable: the verifier spends 44% of its time re-parsing and sizing the public files (configure), more than on checking the three proofs.

## Profile A, amortized: K = 10 batches on one commitment, n = 10 processes

| quantity | median | SD | min..max |
|---|---:|---:|---:|
| commit, once | 0.5263 | 0.0140 | 0.5143..0.5638 |
| prove, first batch | 0.7428 | 0.0155 | 0.7228..0.7731 |
| prove, per later batch (median of batches 2..10 per process) | 0.7349 | 0.0138 | 0.7168..0.7592 |
| check 3 proofs, per later batch | 0.0875 | 0.0024 | 0.0833..0.0908 |
| **per-batch verified latency** (prove + check, batches 2..10) | **0.8229** | 0.0169 | 0.8015..0.8561 |
| same plus file write and read | 0.8282 | 0.0168 | 0.8071..0.8614 |
| prover + verifier process wall, all 10 batches | 9.1497 | 0.2002 | 8.9362..9.5584 |
| that divided by K (fixed costs spread over 10) | 0.9150 | 0.0200 | 0.8936..0.9558 |

Amortization count K = 10 batches of 3 requests (30 proofs) per commitment, in every process; after 10 batches the table had 155 columns left, so K was not limited by the column budget. Peak RSS: prover 111.6 MiB, verifier 10.6 MiB. Batch proving does not get cheaper with repetition (0.735 vs 0.743 s first batch); the saving is entirely the commitment and the configure steps not repeated.

## Profile B: Qwen DeltaNet head, two lookups (stage 1), cold, n = 10

One prover process (read input, build and check the witness, prove, write statement words and proof) then one verifier process (read the two files, `verify_stage1`). Fixture seeds 1..10. No commitment phase exists in this statement: every input is public (directory README); that is "not applicable", not a zero-cost commitment.

| phase | median | SD | min..max |
|---|---:|---:|---:|
| process startup (prover) | 0.0687 | 0.0052 | 0.0662..0.0826 |
| read input | 0.0034 | 0.0006 | 0.0023..0.0040 |
| witness (build, checks against reference, sizing, table) | 0.1998 | 0.0103 | 0.1883..0.2250 |
| **prove** | **13.4016** | 0.1361 | 13.2702..13.6726 |
| write files (words + proof) | 0.0039 | 0.0006 | 0.0036..0.0055 |
| prover process wall | 13.6739 | 0.1369 | 13.5365..13.9648 |
| verifier: startup | 0.0319 | 0.0030 | 0.0269..0.0359 |
| verifier: read files | 0.0202 | 0.0036 | 0.0181..0.0299 |
| verifier: decode + derive relations | 0.1156 | 0.0065 | 0.1099..0.1298 |
| verifier: proof verifier | 3.0707 | 0.0655 | 2.9447..3.1814 |
| **independent verification** (verifier process wall) | **3.2605** | 0.0674 | 3.1442..3.3857 |
| **end-to-end verified-before-release** | **16.9118** | 0.1817 | 16.7979..17.3505 |

Proof 6,756,752 B (SD 270, 6,756,144..6,756,944); statement words 278,616 B (fixed). Peak RSS: prover 1,229.1 MiB, verifier 698.1 MiB. Process CPU time equals wall to within 0.03%.

Positions/s (T = 4 head positions per statement, each with a proved output o_t; there is no prompt/generation split, so prompt positions/s and proved output positions/s are the same number here): **0.2985 positions/s** proving (0.2926..0.3014), **0.2365 positions/s** end-to-end verified (0.2305..0.2381). One head of one layer; not a model rate.

Consistency with the earlier in-process measurement of the same binary code (`experiments/20261109-32-qwen-deltanet-lookup-build/`, prove 13.667 s, verify 2.990 s, 1,258,566 KiB, same fixtures by SHA-256): close (prove 13.40 here), with this run's verifier in its own process (698 MiB) instead of after the prover in one process. Different days on a shared host; not an A/B.

## Profile B, amortized: 4 statements per process, n = 10 processes

| quantity | median | SD | min..max |
|---|---:|---:|---:|
| prove, first statement | 13.8604 | 0.3286 | 13.2555..14.3136 |
| witness + prove, per later statement (statements 2..4) | 13.4932 | 0.3069 | 13.1972..14.0345 |
| verify_stage1, per later statement | 3.0663 | 0.0590 | 3.0147..3.1986 |
| **per-statement verified latency** | **16.5543** | 0.3281 | 16.2219..17.1179 |
| per-statement verified positions/s | 0.2416 | 0.0047 | 0.2337..0.2466 |
| process pair wall / 4 | 16.9436 | 0.3057 | 16.5298..17.3879 |

Amortization count 4 statements per prover process and per verifier process. The only shared cost is process startup (about 0.1 s), so amortized and cold per-statement latencies overlap; there is nothing in this statement to amortize. Peak RSS: prover 1,254.8 MiB, verifier 727.0 MiB.

## Byte identity cross-check

The split harness for profile A reproduces PR #40's published seed-0 artifacts byte for byte: key, entry and all three proofs of `A-cold-0` and the first batch of `A-amort-0` have the SHA-256 values in `experiments/20261103-7-cpu-commit/RESULTS.md` (`runs/artifact-hashes.json`, field `pr40_seed0_equal_*`). So the split into processes did not change what is proved. Profile B fixtures equal the stage 1 evidence fixtures by SHA-256 (`runs/fixtures.json` vs `research/operators/qwen_deltanet_m2_build/evidence.json`).

## What is new compared with `cpu-commit-profile` (PR #40)

PR #40 timed profile A's stages inside one process as the baseline arm of a hashing A/B (configure 0.119, two tables 0.037, make_key 0.411, make_entry 0.113, prove_batch 0.800 s, medians, CPU 13). This run adds: a frozen manifest; verification in an independent process that reads only files, with its own phase split; process startup; end-to-end verified-before-release latency; an amortized cell with K stated; per-process peak RSS; proof and commitment sizes; and the same treatment for profile B. Stage medians here are 3 to 8% lower than PR #40's (different day, different cores, shared host). That is not a speedup claim.

## Deviations from PREREG

- **Raw log path scrub.** The runner wrote absolute paths of the lane's clone into each child's argv. Before committing, `scrub.py` replaced that one prefix with "." (210 occurrences) and nothing else; the first line of `runs/runs.jsonl` records the SHA-256 of the unscrubbed file. Analysis was run on both and gives identical statistics.
- **Artifacts not committed.** The 470 proof/commitment files (0.5 GB) are not in the repository; their SHA-256 values are (`runs/artifact-hashes.json`). Rerunning the suite with the replay command (`run.py replay`, README) regenerates them deterministically (test coins).
- The PREREG "Metric" section said profile A witness generation was `toy_matrix_in_range` and `lin_table_rows`. Both are timed; at 0.1 ms the matrix is trivial. The per-request vectors drawn inside `prove_batch` are, as registered, counted in prove.
- **Two wordings of the A amortized metric (added 2026-11-11, after review).** See the note under the verdict table: the analyzer (written after the run, f70ff0c) implements the threshold wording (0.500203, FAIL); the literal Metric wording gives 0.499870. Verdict unchanged, FAIL.
- **Replay mode (added 2026-11-11, after review).** `run.py registered` keeps the registered hard stop 2026-11-11T06:30Z and after it runs nothing. To reproduce later, `run.py replay` runs the same suite and order with a budget relative to its own start (`--budget-min`, default 45) and optionally the first N repetitions (`--reps`); it never writes under `runs/`. `test_replay.py` with the clock set after the cutoff shows `registered` still stops and `replay` runs its child processes; receipt `runs/replay-check.json` (a new file, 1 repetition per cell, a smoke test, not a replication). PREREG Amendments (2026-11-11).
- **Replay exit status (added 2026-11-11, second review round).** `run.py replay` now ends with one final event and a matching exit status: `done` / 0 only if every requested cell ran, every child exited 0 and no child printed a reject or refused line; `stopped` with `reason: budget` / 2 if its budget fired first; `failed` / 1 otherwise; the final event carries the child, nonzero-exit and reject/refused counts. Malformed or missing option values and a `--budget-min` that overflows to infinity in seconds give a usage message. `registered` and `debug` are unchanged. Subprocess tests in `test_replay_status.py` (budget stop before any child and after 2 real children, missing binaries, a stub that prints a reject line, a real 1-repetition completion, `registered` after the cutoff, option errors); receipt `runs/replay-check-2.json`, a new file. PREREG Amendments item 3. No number or verdict changes.
- Thresholds, n, seeds, cores, ordering and the budget of the registered run were as registered.

## Not established

- Anything about the GPU prover (`cp_commit` / `cp_prove`), which needs CUDA and was not run. The profile A fixture is the CPU reference protocol, not the serving path; profile B is a research operator.
- Any Qwen3.8-27B or whole-model cost. Profile B is one head of one layer, at research security (10-bit target, toy coins), on synthetic inputs, with a lowering that failed fidelity on real weights (PR #68). Multiplying 0.30 positions/s up to a model is an extrapolation and is not made here.
- Generated tokens/s and any overhead vs plain inference: no matched plain-inference baseline was measured.
- Money: no unit price is applied.
- Replication: one lane, one shared host, one day. Times are indicative; the phase ordering is robust (ranges far apart), the A amortization ratio is not (0.5002 vs 0.50 under the analyzer, 0.4999 under the literal Metric wording).
- `ENV.json` `binary_sha256` values reproduce only from a build in the same directory: the binaries embed the absolute source path (`__FILE__` in check messages), so a build elsewhere gives different bytes with identical outputs.

## Reproduce

From the repository root, CPU only (g++ 13, Python 3 with numpy):

```
python3 experiments/20261111-7-cpu-phase-cost/build.py scratch/bin
python3 experiments/20261111-7-cpu-phase-cost/fixtures.py registered scratch/fx
# on a shared host, inside its heavy-job gate; cores via COST7_CORES (default 6-11); the output dir must not exist
# `replay` = the registered suite and order with a relative budget (the `registered` mode stops at its 2026-11-11T06:30Z cutoff)
python3 experiments/20261111-7-cpu-phase-cost/run.py replay scratch/bin scratch/fx <new_out_dir> --budget-min 45
python3 experiments/20261111-7-cpu-phase-cost/analyze.py <new_out_dir>/runs.jsonl <new_out_dir>/summary.json
# with no arguments, analyze.py regenerates runs/summary.json from the committed runs/runs.jsonl
# hashes.py needs a run's artifacts under runs/artifacts/ (not committed)
```
