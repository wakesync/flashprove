# RESULTS addendum 2026-11-10: 20261104-43-h200-memory-lever

Written 2026-11-10 while finishing PR #44, in answer to the reviews at `521f9664`
(https://github.com/wakesync/flashprove/pull/44#issuecomment-6777784260 and
https://github.com/wakesync/flashprove/pull/44#issuecomment-6778032151). Text only: no new run, no new
measurement, no number changed.

`RESULTS.md` and `ENV.json` are kept exactly as committed at `d6ef23dd` (the run record). Additions to the environment
record are in `ENV-ADDENDUM-2026-11-10.json`. **Where this addendum and `RESULTS.md` differ in reading, this addendum
is the current reading.** Every number below comes from a committed file of this PR (`rental2/`, `numbers.json`,
`offers.json`), from upstream's committed `docs/figures.tsv`, or is labelled as run-log text without a surviving file.

## Corrected verdict

| bar (PREREG + amendment 2026-11-04 15:02) | computed from committed files | verdict |
|---|---|---|
| lever: median T-B >= 1.15 x median C-A, and min T-B interval rate > max C-A interval rate | 24,576 / median interval: 146.09 (TB1) / 93.91 (CA1) = **1.556**; per-interval rates TB1 min 145.80 > CA1 max 94.12 tok/s | **bar met as computed; lever NOT supported** (effect not identifiable in this design, below) |
| cost: T-B $/Mtok < C-A $/Mtok | T-B **$10.53** vs C-A **$7.13** /Mtok at the rented prices | **FAIL** |
| sanity: C-A within 10% of upstream 109.09 | 93.84 (printed STEADY RATE), **-14%** | **off-baseline control** |
| runs: 2 sessions per primary arm | 1 session per arm, 4 intervals each | **below registered n** |

**Reading.** The registered comparison clears its bar, but the two arms ran on two different hosts, one session each,
and the control is off baseline: CA1 is 14% below upstream's 109.09 (`docs/figures.tsv`, `rate-24-synthetic`), and the
H100 box's full-size commit took 3,619 s against 1,712.65 s on the H200 box (2.11x; `rental2/*-commit.time`). GPU
memory and host speed are confounded, and this design cannot say how much of the 1.556 comes from either. It might be
all host, some host, or none. The supported conclusion is: **no supported throughput improvement from the extra
memory; the effect is not identifiable in this design.** This is not evidence that extra memory has no effect on
throughput, and not evidence that it has one. "Negative" in the ledger refers to the failed cost criterion and the
unsupported lever hypothesis.

This replaces, as a reading, `RESULTS.md` lines 16 to 26 ("Two facts ... explain the 1.556 without any GPU memory
effect" and the rental-1 comparison used for it) and line 33 ("it does not buy throughput").

## GPU memory: what is observed and what is inferred

- **Observed** (rental 2, n = 1 session each): TB1 (H200, in-step 12, batch 24) ran, cp_verify accepted 120 of 120
  proofs, and the largest of 863 one-second nvidia-smi samples was **87,237 MiB**. One sample got no answer and sampling
  stopped 889.5 s after cp_prove's start, so a later, higher value is not seen. CA1 (H100, in-step 6): largest of 1,291
  samples 74,643 MiB, same caveat at 1,348.5 s. The H100's reported total is **81,559 MiB**
  (`rental2/h100-gpu-summary.csv`).
- **Inferred, not measured:** the TB1 sampled peak is above the H100 total, so in-step 12 at batch 24 in this
  configuration probably does not fit an 80 GB H100. A sampled allocation on one GPU is not a measured minimum footprint
  of that configuration, and no committed file shows in-step 12 run, or fail, on an H100.
- **Historical run-log text, no surviving file:** rental 1's CB2 (H100, 24/12) ended at start-up with
  `p258 end 1 cuda-call`, 0 of 120 proofs. That line was recorded in the run log at the time; no session file of it
  survives. A failing CUDA call is not by itself shown to be an out-of-memory error. It is consistent with the
  inference above and is not a measurement of it.

This replaces, as a reading, `RESULTS.md` lines 28 to 33 ("The extra memory buys a configuration that the H100 cannot
hold").

## Rental 1: historical text only

Every rental-1 figure is run-log text written at the time; none of its session, report or timing files survives
(lost before the 04:45 UTC backstop, declared in PREREG amendment 2026-11-04 15:02). That covers CA1 146.67 tok/s, TA1
142.97 tok/s, their ratio TA1 / CA1 = 142.97 / 146.67 = 0.975 (n = 1 session each, unbound, different CPU quotas),
CB2's start-up failure, the early commit observation (452.7 s vs 576.3 s), the full-size commits (1,698 s vs 1,871 s;
"about 31 min" for the H100) and the "56% across hosts" between the two rentals' C-A. They are kept as history. **No
conclusion in this addendum rests on them**, and they are not used to explain the rental-2 ratio. This replaces, as
support, `RESULTS.md` lines 18 to 22, 65 ("Rental 1's H100 took about 31 min") and 74 to 75.

The seeds of rental 1 (CA1 1, TA1 1, CB2 2) are inferred from the registered rule, not observed; see
`ENV-ADDENDUM-2026-11-10.json`.

## Statistics, named precisely

- **Registered comparison rate** = 24,576 / median(interval seconds), the four intervals between successive batch
  releases of one session: TB1 146.0888, CA1 93.9055 tok/s. Their ratio is the ledger's 1.5557.
- **Printed STEADY RATE** = 24,576 / mean(interval seconds), cut after two places by measure_rate.py: 146.05 and 93.84.
- **Median of the four per-interval rates** (24,576 / each interval) is a different statistic: 146.0889 and 93.9056,
  equal to the registered rate at two places here, not in general.
- SD, min and max in `RESULTS.md` are over the four per-interval rates of one session (TB1 SD 0.19, 145.80 to 146.25;
  CA1 SD 0.28, 93.46 to 94.12). They are successive batches of one process, not independent runs, and no
  between-session spread can be estimated with n = 1.

`RESULTS.md` line 11 says "median interval rates"; read it as the registered comparison rate above.

## Clock warnings

Both session logs carry measure_rate.py's warning that the three clock readings at a release (RELEASE, stamp, seen)
disagree by more than 2 s, followed by "find out why they differ before you rely on a figure of this run": 3 NOTE lines
in TB1, 10 in CA1. `clock_notes_r2.py` (reads the committed logs, writes nothing) shows RELEASE - stamp is a near-constant
offset per session (TB1 1.962 to 1.966 s, CA1 2.056 to 2.081 s), and that the median interval computed from the stamp
column instead of RELEASE changes the comparison rates by under 0.01 tok/s (TB1 146.0896, CA1 93.9094). The cause of the
offset was not investigated. This is a limitation of both figures. It does not support either throughput reading.

## Spend

- **Rental 1:** about $23, **calculated** from the `offers.json` quotes (about 3.38 h x $1.219/h plus about 3.38 h x
  $5.540/h, about $22.8), not an invoice. No receipt is committed. About 6.77 instance-hours, above the 6-hour cap.
  The timers are described in PREREG amendment 2026-11-10; `RESULTS.md` line 47 cites amendment 2026-11-04 15:02 for
  them, which declares the lost data but does not describe the timers.
- **Rental 2:** $18.36 is the difference of two prepaid-credit balances (52.0047 before the first create, 33.6452 after
  the last destroy) as read and recorded in the report text during the run. **No receipt, invoice or balance file is
  committed**, so this figure is reported text, not file-backed evidence. `RESULTS.md` line 80 ("The credit delta is the
  receipt") is withdrawn. The billed times (H200 1.455 h, H100 box 2.105 h with 2 GPUs, 5.67 GPU-hours) are likewise
  reported text, not file-backed. No provider call was made to recover either.

## Reproduction

`analyze_r2.py` (unchanged) expects basenames `session-<NAME>.log`; the committed logs are `h100-session-CA1.log` and
`h200-session-TB1.log`, so called on the committed paths it fails. `reproduce_r2.sh` copies the two logs unchanged to
the expected names in a temporary directory outside the run directory, runs the analyzer with the rounded box prices
4.8185 (H100 2-GPU box) and 5.5402 (H200), and compares with the committed `numbers.json`:

```
bash experiments/20261104-43-h200-memory-lever/reproduce_r2.sh
# reproduce_r2: numbers.json reproduced byte for byte
python3 experiments/20261104-43-h200-memory-lever/clock_notes_r2.py
```

With the full-precision quotes instead of the rounded prices the costs are 10.534314 and 7.126723 $/Mtok (both reviews
computed this), the same at the ledger's four places, and the cost bar still fails.

## Public identifiers

`offers.json` carries marketplace offer ids and coarse geolocation; the `rental2/` GPU summaries, session logs, reports
and figures carry GPU UUIDs. Both reviews found no credential or access identifier. These are frozen run files and are
left byte-identical; minimizing them (sanitized copies, or removing fields from the head tree) is left to the
maintainer.
