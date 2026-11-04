# PREREG: 20261104-43-h200-memory-lever
Issue: #43. Lane: efficiency v2. Date (UTC): 2026-11-04 01:20. Base commit: 29907e5f.

## Hypothesis
At full size on synthetic weights, the larger GPU memory of an H200 (141 GB) raises steady proving
throughput over an H100 80 GB control by at least 15% when it is used to prove more requests per pass
over the weights (`-in-step 12`, batch 24), and by less than 10% at the identical configuration
(`-batch 24 -in-step 6 -memory lean,tensor-rooms=8`). Secondary: whether `-in-step 12` fits on 80 GB at all.

## Metric
Steady rate in tokens/second as printed by `driver/measure_rate.py` (STEADY RATE line: B x 1,024 tokens
over the mean interval between successive batch releases; only if every proof is accepted by
`cp_verify` and cp_prove exits 0). Also per-interval seconds (the intervals behind the rate), GPU memory
peak (nvidia-smi, 1 s samples by the script), host cgroup memory peak. Unit of comparison:
median of per-batch intervals per arm, converted to tok/s. Cost metric: $/Mtok = instance $/h / (rate x 3600 / 1e6).

Arms (same repo commit, same build recipe, same `target_full_f2` configuration, synthetic weights
`made-up-blocks`, one commitment per machine, `-M 1`):
- C-A: H100 SXM 80 GB, batch 24, in-step 6, `-memory lean,tensor-rooms=8` (measure_rate.py defaults).
- C-B: H100 SXM 80 GB, batch 24, in-step 12 (fit probe: does it run at all on 80 GB).
- T-A: H200 141 GB, batch 24, in-step 6, same memory words as C-A.
- T-B: H200, batch 24, in-step 12.
- T-C: H200, batch 48, in-step 16 (exploratory, only if time remains).
- Fallback fixed now: if in-step 12 fails (no STEADY RATE, CUDA fault) on a machine, that machine's
  next B-arm session uses in-step 8 instead, and the result is labelled in-step 8.

Machines chosen from a live read-only Vast quote at 01:14 UTC: control = one GPU of a 2x H100 SXM 80 GB
offer (Xeon 8462Y+, 32 cores, 516 GB host RAM, driver 580.159.03, $1.219/h for the pair, unverified);
treatment = 1x H200 SXM 141 GB (Xeon 8568Y+, 24 cores, 350 GB host RAM, driver 580.178.04, the
upstream timed runs' driver, $5.54/h, verified). The cheaper H200 NVL offers were excluded: one has
driver 570 (CUDA 12.8, the build needs 13.2) and NVL is a different, lower-power card.

## Acceptance threshold
Fixed now.
- "Same-config hardware gain" = median T-A rate / median C-A rate. Reported as is; no pass bar (it is the price-performance input).
- PASS for the lever: median T-B rate >= 1.15 x median C-A rate AND the min of T-B's batch intervals,
  converted to tok/s, is above the max of C-A's (non-overlapping ranges).
- PASS on cost: T-B $/Mtok (at the rented $/h of each instance) < C-A $/Mtok.
- FAIL: T-B < 1.15 x C-A, or ranges overlap.
- Sanity: C-A must land within 10% of upstream `rate-24-synthetic` 109.09 tok/s; if not, the comparison
  is reported but flagged as an off-baseline control.

## Kill criterion
Hard caps from Shadow (2026-11-03 19:44 EST): $100 all-in across all instances, 6 billable hours total.
Provider-side: teardown timers armed before create (H100 2.5 h, H200 3.5 h; sum 6.0 h). Any build
failure, commit failure, or rate not printed in an arm: stop that instance, keep logs, report.
If the H200 offer cannot be created, try the next H200 offer once; if none, report the control only.

## Runs
n is limited by budget and is below the standards' >= 10 sessions; it is stated, not hidden.
- Each session: 5 batches (4 intervals) at batch 24; 4 batches (3 intervals) at batch 48.
- H100 order: C-A, C-B, C-A. H200 order: T-A, T-B, T-A, T-B, then T-C if the timer allows (AB/AB).
- n per arm: 2 sessions = 8 batch intervals (C-A, T-A, T-B); 1 session for C-B and T-C.
- Warmup: the first batch of each session is the start-up and is excluded by the measure_rate rule.
- Seeds: measure_rate.py `--seed` = session index (1, 2, 3...) on both machines, so both arms prove the
  same windows in the same order.
- Excluded: nothing after the fact. A session that ends without a STEADY RATE line is reported as failed.
- Cold/warm: every session is a fresh cp_prove start on a warm machine (commitment made earlier).
- Confounds stated now: different hosts and CPUs (control Xeon 8462Y+, treatment Xeon 8568Y+ for H200
  SXM), unverified vs verified hosts, no CPU binding by the script. Upstream showed up to 9% between
  machines of one kind; a gain under ~10% cannot be told from host variation with this n.

## Prior art
Upstream timed runs (guide/performance.md, docs/figures.tsv): H100 only; rate 109.09 ± 0.22 synthetic,
111.23 ± 0.92 public at 24/6; 120.94 at 48 (†), 123.31 at 64; batch 64 fails on synthetic weights.
The teardown gist (0xOsprey) ranks "more GPU memory" as the largest lever; paper section 7 contains no
H200/B200 data. Weight streaming as in ZeRO-Inference and FlexGen (cited in prover/prover/weight_stream.cuh).
No published H200 measurement of this prover is known. B200 is excluded: binaries target sm_90a only.

## Amendments
- 2026-11-04 02:40 UTC. C-B (H100, batch 24, in-step 12) ended at start-up with `p258 end 1 cuda-call`, 0 of 120 proofs, before any batch. Per the fallback fixed at registration, the H100 gets one more B-arm session at in-step 8 (CB4, seed 4) after CA3. No other change.
