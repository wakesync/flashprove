# RESULTS: 20261104-43-h200-memory-lever

Issue #43. Measured, unreplicated, synthetic weights (`made-up-blocks`, target_full_f2, `-M 1`), pinned
build 29907e5f. Two rentals. Rental 2's raw session logs are in `rental2/`. Each was pulled and sha256-checked
before its box was destroyed. Rental 1's later data is lost (below).

## Verdict

| bar (PREREG + amendment 2026-11-04 15:02) | computed | verdict |
|---|---|---|
| lever: median T-B >= 1.15 x median C-A, and min T-B interval rate > max C-A interval rate | median interval rates 146.09 / 93.91 = **1.556**; T-B min 145.80 > C-A max 94.12 tok/s | **met as computed, NOT supported** (see below) |
| cost: T-B $/Mtok < C-A $/Mtok | T-B **$10.53** vs C-A **$7.13** /Mtok (H200 $5.54/h; one H100 GPU = half of the $4.82/h box) | **FAIL** |
| sanity: C-A within 10% of upstream 109.09 | 93.84, **-14%** | **off-baseline control** |
| runs: 2 sessions per primary arm | 1 session per arm (C-A, T-B), 4 intervals each | **below registered n** |

The lever bar is met only on paper. Two facts already in this file explain the 1.556 without any GPU memory
effect:
1. The rental-2 H100 host is slow. Its C-A is 14% *below* upstream, and its full-size commit took 2.1x as long as the
   H200 host's (below). Rental 1's H100 (another host) gave C-A 146.67 tok/s.
2. TB1 (H200, in-step 12) at 146.05 tok/s is +2.2% over rental 1's TA1 (H200, in-step 6, 142.97) and equal to rental 1's
   C-A on a faster H100 host (146.67). Across the two rentals, then, "in-step 12 on H200" is within host
   variation of "in-step 6 on either GPU".

So the honest reading is **no evidence that the H200's extra memory raises the steady rate**. The bar is
nominally met because the control box was slow. Neither direction is established: n = 1 session per arm, and the
two arms ran on different hosts whose CPU speed differs by about 2x on CPU-bound phases.

## Mechanism result (measured, n = 1, unreplicated)

`-in-step 12` at batch 24 **runs on the H200**. In TB1 cp_verify accepted all 120 proofs, and the GPU memory peak was
**87,237 MiB** (nvidia-smi, 1 s samples, during TB1). That is above the H100's 81,559 MiB total, consistent with rental
1's CB2 failing at start-up on the H100 (`p258 end 1 cuda-call`). The extra memory buys a configuration that the H100
cannot hold. On this evidence, though, it does not buy throughput.

## What ran

### Rental 1 (2026-11-04 01:22 to 04:45 UTC). Data after 02:33 UTC LOST
These numbers were recorded in the README section 5 run log at the time and never pulled as files:
- CA1 (H100, 24/6, unbound, 30.7-core cgroup): 146.67 tok/s, intervals 168.18 / 167.53 / 167.24 / 167.27 s. +34% over
  upstream 109.09: off-baseline (unbound, more CPU than upstream's 24 bound CPUs).
- TA1 (H200, 24/6, unbound, 23.0-core cgroup): 142.97 tok/s, intervals 171.13 / 172.28 / 172.16 / 172.01 s.
- Same configuration (24/6) on the two boxes: TA1 / CA1 = 142.97 / 146.67 = 0.975, from the two run-log rates above
  (n = 1 session each, 4 intervals each, unbound, different CPU quotas). Stated as recorded at the time. No claim rests
  on it.
- CB2 (H100, 24/12): `p258 end 1 cuda-call` at start-up, 0 of 120 proofs.
- CA3, CB4, CX5, TA2, TB, TC ran or were queued after 02:33 UTC. **Their outputs were never copied off the boxes before
  the 04:45 UTC backstop destroyed them. They are lost and are not reconstructed here.**
- About 6.77 instance-hours (2 boxes x ~3.38 h), above the 6-hour cap. Dollars were inside the $100 cap: about $23 at
  the `offers.json` prices (~3.38 h x $1.219/h plus ~3.38 h x $5.540/h; calculated from the quoted prices, not an
  invoice; no spend receipt for rental 1 is committed). The per-box deadline timers were not anchored at create as the
  PREREG said, and only the all-instances backstop at 04:45 UTC enforced anything (PREREG amendment 2026-11-10, which
  describes the timers as run; the lost data is declared in amendment 2026-11-04 15:02).

### Rental 2 (2026-11-04 15:00:56 to 17:07:27 UTC). Every session bound with taskset to 23 CPUs of the GPU's NUMA node

| session | box | B / in-step | seed | steady tok/s | intervals, s | proofs accepted |
|---|---|---|---:|---:|---|---:|
| TB1 | H200 SXM 141 GB (Xeon 8568Y+, verified, GA US) | 24 / 12 | 1 | **146.05** | 168.04 / 168.56 / 168.30 / 168.15 | 120 / 120 |
| CA1 | H100 SXM 80 GB, GPU 0 of 2 (Xeon 8480+, unverified, JP) | 24 / 6 | 1 | **93.84** | 262.95 / 261.12 / 261.82 / 261.59 | 120 / 120 |

Interval rates (24 x 1,024 tokens / interval), n = 4 each: TB1 median 146.09, SD 0.19, min 145.80, max 146.25. CA1 median
93.91, SD 0.28, min 93.46, max 94.12. Steady rates (B x T / mean interval, as printed): 146.05 and 93.84. Intervals within a session are successive batches of one process, not
independent runs.

Not run in rental 2, against the amendment's plan: CA2, CB8 (H100) and TB2, TA3 (H200). The H100 box's full-size commit
took 60 minutes instead of about 30. To stay under 6 GPU-hours (the H100 box bills 2 GPUs), the H200 was destroyed after
TB1 and the H100 after CA1.

Full-size cp_commit, n = 1 per box (wall, then phases check / anchor-table / key-file / leaf-0-table, s):
H200 28:33 (340 / 463 / 242 / 462). H100 1:00:19 (674 / 1,192 / 417 / 1,202). Rental 1's H100 took about 31 min.
The H100 host reported its CPUs at 24% of maximum frequency (`lscpu`), with a 53.8-core cgroup on 224 threads.

## Confounds, stated

- Host CPU speed differs about 2x between the two rental-2 boxes on CPU-bound phases. Binding both to 23 CPUs equalizes
  the count of CPUs, not their speed. A C-A vs T-B difference mixes GPU memory with host speed, and this design cannot
  separate them. A fair rerun needs the same host type for both arms. One option is an H200 box running both C-A-style
  (in-step 6) and T-B sessions, which isolates the in-step effect on one machine.
- n = 1 session per arm. Upstream reports up to 9% between machines of one kind. Rental 1 and rental 2 C-A differ by 56%
  across hosts.

## Costs and spend (rental 2)

- Vast credit 52.0047 before the first create, 33.6452 after the last destroy: **$18.36** (cap $60). The invoices endpoint
  showed no new invoice rows (charges come out of prepaid credit). The credit delta is the receipt.
- Billed time: H200 1.455 h (1 GPU), H100 2.105 h (2 GPUs): **5.67 GPU-hours** (cap 6), 3.56 instance-hours.
- The two small #36 / #38 workloads shared the H100 box (GPU 1), so this experiment's share of the H100 cost is lower
  than the box total.
- Offers (price, hardware) for both rentals: `offers.json`.

## Files

- `rental2/{h100,h200}-session-*.log`, `-report-*.txt`, `-figures-*.json`: measure_rate.py output per session.
- `rental2/{h100,h200}-stages.log`, `-gpu-summary.csv`, `-host.txt`, `-commit.time`, `-cp_commit-phases.txt`.
- `offers.json`: the four Vast offers used.
- `analyze_r2.py` computes the bars; `numbers.json` is its output.
