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
- 2026-11-04 03:00 UTC. Exploratory, added after seeing data, labelled exploratory everywhere, enters no pass/fail: the boxes' CPU quotas differ (H100 cgroup 30.7 cores, H200 23.0 cores; upstream bound 24 CPUs of the GPU's NUMA node). After CB4 the H100 runs one session (CX5, seed 5, 24/6) bound with taskset to 23 CPUs of the GPU's NUMA node, to match the H200's quota. It tests whether the CPU budget, not the GPU, sets the rate.
- 2026-11-04 15:02 UTC. Rental 2 (before any rental-2 instance exists; Shadow GO 07:07 EST, caps $60 all-in
  and 6 GPU-hours for the whole rental, shared with two other workloads). Rental 1's data after 02:33 UTC
  was not pulled before its boxes were destroyed and is declared lost (CA3, CB4, CX5, TA2, TB, TC never
  reported); rental 1 enters RESULTS.md as CA1, TA1 and CB2 only. Rental 2 re-runs the arms with the same
  configuration, metric and pass bar, with these changes, fixed now:
  - CPU confound: every rental-2 session on both boxes is bound with taskset to the same count of CPUs of the
    GPU's NUMA node, N = min(23, CPUs of that node allowed by the box's cgroup) on both boxes (remote/bound.sh
    rule), and N is recorded. Rental 1's unbound CA1/TA1 stay reported but enter no pass/fail.
  - Order and seeds. H100: CA seeds 1, 2 (24/6), then CB8 seed 3 (24/8, the registered fallback, since CB2
    failed at in-step 12). H200: TB seeds 1, 2 (24/12), then TA seed 3 (24/6). T-C dropped.
  - n per primary arm: 2 sessions x 4 intervals (C-A, T-B), as registered; below the standards' n, stated.
  - Pass bar unchanged: median T-B >= 1.15 x median C-A, min T-B interval rate > max C-A interval rate, and
    T-B $/Mtok < C-A $/Mtok at each box's rented $/h.
  - Kill: a box's sessions stop when the rental's 6-hour or $60 cap, or 17:18 UTC, is near; artifacts are
    pulled and pushed after every session, before the next.
- 2026-11-04 17:15 UTC (after rental-2 data). Deviations from the 15:02 plan, as run: the H100 box's full-size commit took
  60 min (about 30 expected), so with the 6 GPU-hour cap (the H100 box bills 2 GPUs) only one session per primary arm
  ran: TB1 (H200, 24/12, seed 1) and CA1 (H100, 24/6, seed 1). CA2, CB8, TB2 and TA3 were not run. The H200 was destroyed
  after TB1 was pulled (16:28 UTC), the H100 after CA1 was pulled (17:07 UTC). The hard-stop timer moved four times
  (16:48, 16:53, 16:58, 17:06, finally 17:13 UTC), each time within the 6 GPU-hour cap and logged before the move. The pass
  bar, the metric and the cost rule (one H100 GPU = half of the 2-GPU box price) are unchanged.
