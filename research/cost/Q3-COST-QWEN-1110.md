# Q3: what a Qwen3.8-27B proof costs, from numbers on main (desk, 2026-11-10)

Part of #7. Question Q3 of the coordinator's research agenda for 2026-11-10 (the agenda itself is
not in this repository; issue #7 is the tracking issue): proof time, memory and USD per 1,000
tokens for Qwen3.8-27B at full size on one GPU, as a multiple of plain inference. Desk lane: no
run, no GPU, no provider call, no new measurement. Drafted on main `14bc10e3`; citations re-checked
and line numbers given on main `5e964019`.

## Plain answer

- **No cost figure for a full-model Qwen proof is established.** Nothing for Qwen has run on a
  GPU. Every per-token figure below is the extrapolation that PR #70 (merged) made from another
  model's rates, or arithmetic on it. The three rates it uses differ by about 60 times, and nobody
  has measured which one a Qwen DeltaNet segment follows.
- **On those extrapolations**, proving every token of a 1,024-token window costs 42 to 86
  GPU-seconds per 1,000 window tokens at the two rates taken from upstream (about 0.03 to 0.07 USD
  at 2.16 to 3.00 USD per GPU-hour), and 2,559 GPU-seconds (1.5 to 2.1 USD) at the only GPU rate
  this fork has measured itself. Largest-segment memory is 41 GB central, 82 GB high, and 393 GB at
  the fork's own rate: the last does not fit one H200, and "fits one H200" is **not established**
  (PR #70 reviews).
- **The multiple of plain inference cannot be computed from main**: no plain-inference rate for
  Qwen3.8-27B is on main. Section 4 gives the formula only.
- **Use cases.** U2 (sampled audit) is the only one whose cost could become small by construction:
  it scales with the proved fraction. All three are blocked before cost matters, by fidelity (Q1)
  and by a DeltaNet GPU sub-proof that does not exist. U3 is also blocked on the Tinfoil H200 by
  the confidential-computing mode.
- **Next measurement to register:** one GPU calibration of the existing prover's bytes and seconds
  per committed entry at four or more segment sizes, with a plain-inference baseline on the same
  card (section 7). For the **dense family only**, it can tell whether the 23 or the 220
  bytes-per-entry reading applies (or neither); a DeltaNet segment may differ, so it does not by
  itself settle whether the Qwen model fits.

Labels used: **measured** (a run on main), **counted** (an exact size from a model on main),
**extrapolated** (a count times a rate from another model), **assumed** (a number chosen, not
derived), **not established** (no evidence on main).

## 1 Inputs and where each comes from

Line numbers are on main `5e964019`.

| # | input | value | label | source |
|---|---|---|---|---|
| I1 | committed entries per window token, all 64 layers, packed per-token state (plan of record) | 95,057,841; DeltaNet mixer 88% | counted, the DeltaNet part for a lowering that is not built | `experiments/20261109-32-qwen-m3-design/RESULTS.md` 150-157; `runs/model-r2.json` 662-671 |
| I2 | prove time per window, one DeltaNet segment per layer: T = 64 / 256 / 1,024 | central 6.15 / 13.63 / 43.54 s; high 8.95 / 24.84 / 88.40 s; small-example rate 163.8 / 655.1 / 2,620.5 s | extrapolated; "high" and "small-example" are labels of a range, not bounds (RESULTS.md 170-171) | RESULTS.md 182-185; model-r2.json 694-698, 814-818, 934-938 |
| I3 | how I2 is made | 18.16 s x 3 passes x 0.067 + 4.33 s per 10.57e9 entries, a fit to upstream's four Maverick H100 rates (records not in this repository); small-example rate from the fork's 2.35 s for 87M entries, "mostly start-up" | extrapolated; upstream inputs unreproduced | RESULTS.md 205-211 |
| I4 | largest-segment GPU memory, same case, T = 1,024 | low 28.6, central 41.0, high 82.0 GB; 97.4 GB with weights resident (central) | extrapolated, 22.97 bytes per entry from one upstream point | RESULTS.md 182, 212-213; model-r2.json 926-933 |
| I5 | same at this fork's own measured memory rate | 220 bytes per entry: 24.5 / 98.2 / 392.8 GB at T = 64 / 256 / 1,024; largest window under 127 GB is 256 | extrapolated from a measured small synthetic example of another model | RESULTS.md 213-221; model-r2.json 2143-2155 |
| I6 | the measurement behind I5 | 5,227 to 5,293 MiB GPU while proving, **500 ms samples, so not true peaks**; `cp_prove` 2.35 s mean (n = 3) | measured, small synthetic example, H100 | `guide/performance.md` 45, 48; `research/results.yaml` 167 |
| I7 | proof size, T = 1,024 window | 172.9 MB | extrapolated | RESULTS.md 182; model-r2.json 942 |
| I8 | committing the weights | about 2.6 min | extrapolated linearly from upstream's 39 min for Maverick, fixed costs ignored | RESULTS.md 198-199; model-r2.json 337-340 |
| I9 | committed weights | 26,895,337,984 integers, 56.3 GB | counted | RESULTS.md 141-144 |
| I10 | GPU price | 2.16 USD per H100-hour (replication-1 invoice); 3.00 USD per GPU-hour assumed by PR #70. The 2.40 column below is **not an invoice**: it is the listed rate in a pre-billing reading that `research/gpu/README.md` itself corrects (final invoice 1.186 USD all-in for about 25.5 min of instance life, about 2.78 USD per hour, not broken down by the file); kept as a sensitivity point inside 2.16 to 3.00 | 2.16 measured invoice (H100, not H200); 2.40 corrected reading; 3.00 assumed | `research/gpu/replication-1/README.md` 70; `research/gpu/README.md` 22; RESULTS.md 195 |
| I11 | segments per window, per-layer cut | 81, over `cp_verify`'s cap of 64 | counted | RESULTS.md 182, 242-243; model-r2.json 2181-2188 |
| I12 | upstream's proving-vs-serving multiple, Maverick | 93.0x slower than stock vLLM prefill per GPU at the highest load tried; one pass 20.1x slower than decoding at 512 streams | calculated upstream; records not in this repository | `guide/performance.md` 27 (both multiples); 37 (records not here) |
| I13 | upstream start-up per service, Maverick | 68.1 to 79.0 s | measured upstream; records not in this repository | `guide/performance.md` 19 |
| I14 | measured Qwen sub-proofs (none is a full-model proof, none on a GPU) | one DeltaNet head at T = 4: M1 prove 51.4 s median, M1b 39.2 s median (n = 10 each); #71 SA chunk proofs of one head at D = 32 over 64-token windows, window prove medians 153.2 s (C = 1), 39.3 s (C = 16), 40.3 s (C = 64), n = 5 windows; plus standalone operator proofs (#67). All CPU research harness, synthetic inputs, research security (10-bit target) | measured; CPU, not used as a rate in this note | `research/results.yaml` 340 (M1), 358 (M1b), 394, 403, 412 (#71); 657 onward (#67) |

`model-r2.json` is read rather than `model-r3.json` (the merged head's): for every field this note
uses they are identical, except the resident-weights figures (`weights_resident_gb`,
`vram_with_resident_weights_gb_central`), which r3 raises by about 5e-6 GB (the dt_bias bytes).

## 2 Gaps (each one is a reason the figures above are not a cost)

| gap | status on main | which inputs it voids | source |
|---|---|---|---|
| G1 GPU prover for a DeltaNet segment | **does not exist**; no GPU measurement of any DeltaNet work | I2, I4, I5, I7 (88% of entries, I1) | RESULTS.md 202-204; `docs/qwen-port.md` 94 |
| G2 which memory rate a DeltaNet segment follows (23 vs 220 bytes per entry) | **not measured**; upstream's full-size dense point contradicts 220 for the dense family, nothing decides it for DeltaNet | I4 vs I5, the H200 fit | RESULTS.md 212-221; `docs/qwen-port.md` 68-74 |
| G3 "fits one H200" | **not established**, said so by the merged design and its reviews (PR #70 round-3 approval, https://github.com/wakesync/flashprove/pull/70#issuecomment-6769339230: "No surface reads as 'fits one H200'") | every memory row | RESULTS.md 38, 231-243 |
| G4 state witness volume | counted only for the packed lowering, which is not built; the built wide-oracle lowering is 6,250 GB of aggregate trace for a 1,024 window; the cheaper low-rank form is **not established** | I1, and every low-rank figure, which this note does not use | RESULTS.md 179, 279-289 |
| G5 state handoff bound in a proof | in the merged SA harness the boundary state and token inputs are public words; no hidden-state handoff is tested | cost of chunked windows over 1,024 tokens (Q6) | `research/results.yaml` 385 |
| G6 fidelity of the integer model | **fails** on layer 0: median rel_y 0.659 at F = 12 (#68); no registered candidate passes (#74, under a protocol deviation); deeper layers unmeasured | all: a proof of an integer model far from Qwen is not a U1 proof; a wider format costs more (+17% entries per token if the recurrence widens, a lower bound) | `research/results.yaml` 526, 534, 556; RESULTS.md 270-276 |
| G7 attention layers, head dimension 256 | not admitted by the planner; modelled as a quarter of a Maverick attention link | the 16 attention layers in I1, I2 | RESULTS.md 225-226; `docs/qwen-port.md` 99-101 |
| G8 segment cap | per-layer cut needs 81 segments, `cp_verify` refuses over 64 | the per-layer case used here; the per-block case (49 segments) needs 123 GB central and 1,178 GB at the own rate at T = 1,024 | RESULTS.md 181-182 |
| G9 H200 speed | assumed equal to H100 | I2 on the target card | RESULTS.md 222 |
| G10 plain-inference baseline for Qwen3.8-27B | **none on main** (no vLLM or other rate on any card) | the multiple Q3 asks for | search of main; `research/ports/qwen3.8-27b/FEASIBILITY.md` 145-160 has only a prove-rate estimate |
| G11 serving the integer model | at exact match a reply passes only if every token is the integer model's own choice; upstream needed a vLLM plug-in at 0.58 to 1.46 s per token (Maverick, records not here); nothing for Qwen | the cost of producing a provable reply, on top of proving it | `guide/performance.md` 35 |
| G12 verify cost for a **full-model** Qwen proof | no full-model estimate on main (head- and chunk-level CPU verify times exist, e.g. M1b 7.1 s median, `research/results.yaml` 359) | the verifier side of every use case | FEASIBILITY.md 162-163 |
| G13 production security | every Qwen proof used a 10-bit research target | I14 | `docs/qwen-port.md` 104-105 |
| G14 PR #44 (larger-memory GPU test, cost teardown) | merged after this note was drafted; its rows are the Maverick-shaped synthetic configuration (`target_full_f2`), not Qwen, one session per arm, lever not supported | nothing is taken from it as a Qwen input | `research/results.yaml` 621-646 |

## 3 Cost per 1,000 tokens (extrapolated)

Case: packed, per-token state, one DeltaNet segment per layer, one request per pass, weights
streamed. It is the cheapest **plan-of-record** lowering (state committed, handed on at chunk
boundaries), and it is post hoc and exploratory in PR #70 (RESULTS.md 182). A variant that keeps
the floor remainder as a lookup key instead of committing it (RESULTS.md 154, not built) comes out
lower: 30.1 s per window and 25.4 GB central at T = 1,024 (`model-r2.json`, packed
`per_token_layer_segments_remainder_as_key`, T1024); it is not used here. Per 1,000 **window**
tokens (prompt plus reply); the cost per reply token is the window's cost divided by the reply
length (RESULTS.md 196-197). Fixed costs (start-up, committing) are excluded. Produced by
`research/cost/q3_cost_from_main.py`.

| window T | rate | GPU-s per 1K | USD per 1K at 2.16 / 2.40 (corrected reading, I10) / 3.00 per GPU-h | largest segment GB | proof |
|---|---|---|---|---|---|
| 64 | central | 96.1 | 0.058 / 0.064 / 0.080 | 2.6 | 10.8 MB |
| 64 | high | 139.9 | 0.084 / 0.093 / 0.117 | 5.1 | |
| 64 | small-example | 2,559 | 1.54 / 1.71 / 2.13 | 24.5 (own rate) | |
| 256 | central | 53.2 | 0.032 / 0.035 / 0.044 | 10.3 | 43.2 MB |
| 256 | high | 97.0 | 0.058 / 0.065 / 0.081 | 20.5 | |
| 256 | small-example | 2,559 | 1.54 / 1.71 / 2.13 | 98.2 (own rate) | |
| 1,024 | central | 42.5 | 0.026 / 0.028 / 0.035 | 41.0 | 172.9 MB |
| 1,024 | high | 86.3 | 0.052 / 0.058 / 0.072 | 82.0 | |
| 1,024 | small-example | 2,559 | 1.54 / 1.71 / 2.13 | **392.8** (own rate, does not fit) | |

The 3.00 USD column at T = 1,024 central reproduces PR #70's 0.035 (RESULTS.md 195-196). The
small-example rate is flat in T because it is a per-entry rate; PR #70 notes it is mostly start-up
on a tiny model (RESULTS.md 209-210), so it is a pessimistic reading, not a bound (the script's
source key is still named `upper_bound_small_example`, a legacy r1 name; the script prints it as
"small-example"). The central and high rates assume a DeltaNet entry costs what a dense entry
costs, which "could be off in either direction" (RESULTS.md 202-204). No row is a measurement.

Fixed costs not in the table: committing about 2.6 min once per commitment (I8, extrapolated);
upstream's start-up of 68 to 79 s per service for Maverick (I13). For a long-lived prover these
amortise; for U2 at low fractions they may not (section 5).

## 4 As a multiple of plain inference

multiple = (prove GPU-seconds per token) x (plain-inference tokens per GPU-second), on the same
card and the same token kind (prefill or decode).

The second factor is not on main for Qwen3.8-27B (G10), so **the multiple is not established**.
At T = 1,024 the multiple would be 0.0425 / 0.0863 / 2.559 times the plain rate in tokens per
GPU-second (central / high / small-example), all extrapolated.

The only measured-against-serving multiple anywhere in the repository is upstream's for Maverick:
93.0x per GPU against stock vLLM prefill at the highest load tried, and 20.1x for one pass against
decoding at 512 streams, where a pass checks one token (I12; upstream's records are not here). It
is not a Qwen number. Two lanes agreeing with it would still be one calculation.

## 5 Per use case

### U1 Model substitution (priority 1)

What it needs: a proof of the whole forward pass against a commitment to the claimed checkpoint.
Stock and abliterated differ only in layers 17 to 51, so a partial proof of early layers cannot
tell them apart; the smallest statement that can is a block inside 17 to 51 (DESIGN.md 681-684).
So U1 pays the full-model cost of section 3 on every proved token, plus serving the integer model
(G11).

Cost on main: 0.03 to 0.07 USD per 1,000 window tokens (central to high, T = 1,024), 1.5 to 2.1
USD at the small-example rate; 42 to 2,559 GPU-seconds per 1,000 tokens. All extrapolated.

Verdict: **blocked, before cost is the question**, on G6 (no integer format passes fidelity, so a
proof would not be about Qwen), G1 (no DeltaNet GPU sub-proof), G2/G3 (memory fit unknown, and at
the own rate a 1,024 window does not fit), G7 and G8 (verifier limits). If the central rate held,
the per-token cost would be modest; if the small-example rate held, it would be about 60 times
higher, and at the own memory rate windows would be capped at 256 tokens on one card. The time
rate and the memory rate are separate unknowns: a memory calibration (G2) speaks to the memory
column only; the time rates need their own fit (section 7), and for DeltaNet neither is settled
without G1.

### U2 Sampled audit (priority 2)

Cost model only; detection probability is Q4. Proving a fraction f of whole 1,024-token windows
costs f times the U1 figure per served token, plus fixed costs. The denominator is **variable
proving work per served prompt-plus-reply window token**; it is not total audit or serving cost:
start-up, committing, keeping receipts, retaining the requests and serving the integer model are
all excluded.

| f | proving GPU-s per 1K served window tokens: central / high / small-example | proving USD per 1K served window tokens at 3.00 per GPU-h: central / high / small-example |
|---|---|---|
| 1 | 42.5 / 86.3 / 2,559 | 0.035 / 0.072 / 2.13 |
| 0.1 | 4.25 / 8.63 / 256 | 0.0035 / 0.0072 / 0.21 |
| 0.01 | 0.43 / 0.86 / 25.6 | 0.00035 / 0.00072 / 0.021 |
| 0.001 | 0.043 / 0.086 / 2.56 | 0.000035 / 0.000072 / 0.0021 |

Caveats that move this table: (a) fixed costs. If a prover is started per audited request,
upstream's Maverick start-up of 68 to 79 s (I13) exceeds the central per-window proof of 44 s, so
at low f the cost is start-up bound unless a prover stays warm; a warm prover holds a GPU. (b) At
exact match only a recorded response that already satisfies the integer model's relation can be
proved (G11). Re-running the request does not help: a different response is not the one that was
served. So U2 audits only a service that already serves the integer model. (c) Sampling layers
instead of requests is not costed: a layer sample still needs that layer's input, which ties to G5
(no hidden-state handoff in a proof). (d) The memory question (G2/G3) is unchanged by sampling:
each audited window still has to fit.

Verdict: **the most cost-robust use case**: even at the pessimistic rate, f = 0.01 gives about 0.02
USD of proving per 1,000 served tokens before fixed costs. **Blocked on the same G1, G2, G6** as
U1, and its value depends on Q4 (whether sampling detects cheating at a given f).

### U3 Proof alongside a TEE (priority 3)

Cost = TEE serving overhead + proof cost (section 3, or section 5 U2 if sampled). The TEE serving
overhead is **not on main** (no H200 inference run). On the Tinfoil H200 two blockers come before
cost: the unmodified prover calls `cudaHostRegister`, which NVIDIA lists as not allowed in CC mode,
and the live instance runs CC-On (`research/gpu/tinfoil-h200/README.md` 21;
`experiments/20261110-43-h200-bringup/RESULTS.md` 38, predicted from sources, untested); and the
live instance uses about 94% of GPU memory while `cp_commit` / `cp_prove` refuse a GPU with more
than 2 GiB in use (same RESULTS 36-37). The host's GPU count is not established (README 15).

Verdict: **blocked** on a prover code change (`cudaHostAlloc`) or a CC-off mode whose wording and
entitlement are unverified, and on a free GPU, in addition to G1, G2, G6. What a proof adds over
attestation is Q5; its price is the U1 or U2 figure above.

## 6 What is established vs not

Established (on main): the counts I1, I9, I11; the fork's small-example GPU readings I6 (sampled,
not true peaks); one H100 marketplace invoice rate (I10, 2.16 USD per hour); the measured Qwen
sub-proofs of I14 (CPU, one head or chunk, synthetic inputs, research security), none of them a
full-model or GPU proof; the CC-On and memory blockers as source readings.

Not established: any Qwen GPU time, memory or USD; any full-model Qwen proof or verify cost; which
memory rate applies; that the model fits one H200; the multiple of plain inference; the low-rank
state form; a fidelity-passing integer format; TEE serving overhead.

## 7 Next measurement to register

**Cost calibration on one GPU, existing prover, no Qwen code needed. Dense family only.** Prove
the dense-family planner proxy (or the existing small examples) on one 80 GB card and record per
run: committed entries of the largest segment (from `cp_verify -plan arrays`), the CUDA
allocator's peak if the prover exposes one plus GPU memory sampled at 100 ms or faster, `cp_prove`
wall split into start-up and proving, and host memory.

Design, folding in both reviews of PR #85:
- **Four or more sizes**, spanning at least two orders of magnitude of committed entries, with
  registered repeats and an uncertainty on each fitted coefficient.
- **Vary T at fixed weights** (one proxy), so weight-streaming buffers and the CUDA context stay
  in the intercept and only the request's entries move. Hold shapes, security settings and the
  streaming mode fixed.
- **Above the padding floor.** The planner pads lookups to minimum sizes (RESULTS.md 223-224) and
  allocators round up; drop sizes below the floor, report residuals, and check for jumps at
  allocation or padding thresholds (a change of allocation regime breaks a single line).
- **Largest size chosen so both hypotheses read out on an 80 GB card**: a largest segment of about
  3e8 to 5e8 entries is 7 to 12 GB at 23 B/entry and 66 to 110 GB at 220 B/entry, so neither
  hypothesis ends in an out-of-memory crash with no reading (or the crash is itself the reading,
  registered beforehand).
- **Separate fits for memory and time.** Memory = a + b x (largest simultaneously resident
  segment entries). Time = c + d x (total processed entries), plus the pass and weight work. A
  memory slope says nothing about which time rate holds, and the reverse.
- **Registered decision, with an "inconclusive" outcome.** If b is in [11.5, 46] bytes per entry,
  PR #70's central memory column is supported for the dense family; if in [110, 440], the own-rate
  column is; if in (46, 110), or if the residuals do not support a line, neither is, and the
  result is reported as inconclusive. A slope near 23 with a large intercept a does not validate a
  zero-intercept 23 x entries column; report a and b together.

In the same session, measure plain Qwen3.8-27B BF16 inference (prefill and decode tokens per
second, vLLM, same card) as the denominator of section 4. The calibration does not settle G1
(DeltaNet entries may cost differently in both time and memory), but it removes G10 and narrows
the dense-family memory and time rates. It is the step named in `docs/qwen-port.md` 81-82 and in
the PR #70 review (comment 6758415494, item iii). On the Tinfoil H200 it needs the CC-On fix or a
CC-off instance and a free GPU first (section 5 U3); otherwise it is a rented-card run, which the
2026-11-09 rules route through the coordinator.

Calibration points from the reviews of PR #85, not yet addressed by any measurement and left open
here: the intercepts (CUDA context, fixed buffers) are unknown; whether allocation is one regime
across the size range is unknown; and how a DeltaNet segment's memory and time per entry compare
with the dense family's is unknown.

## Reproduce

```
python3 research/cost/q3_cost_from_main.py
```

Reads only `experiments/20261109-32-qwen-m3-design/runs/model-r2.json`; standard library;
deterministic. Every other number in this note is quoted with its file and line on main.
