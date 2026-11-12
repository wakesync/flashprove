# PREREG: 20261112-7-h200-dense-calibration
Issue: #140 (part of #7, informs #32 and #43). Lane: h200cal7 (preparation, CPU only). Date (UTC): 2026-11-12T18:05Z. Base commit: d96cdda066f443a9b0c0f481b30eaaf45108ae65.

Nothing in this experiment has run on a GPU. This file registers the protocol of one job for one window on one H200 with confidential computing (CC) mode off, approved by the owner on 2026-11-12 (issue #140). The window is run later by the coordinator with the owner, not by this lane. Everything numeric below that is not cited to a file on main is marked **estimate**.

## Hypothesis
For the dense family of the existing prover (`cp_prove` of the pinned upstream commit `9e2bdd8f`, the build of `research/gpu/tinfoil-h200/Dockerfile`), the peak GPU memory of the prove window on one H200 grows linearly in the committed entries resident at once, x_mem = in-step x (entries of the configuration's largest link), with a slope b that is within 2x of exactly one of the two rates on main: 23 B per entry (upstream's Maverick point, `experiments/20261109-32-qwen-m3-design/RESULTS.md`, H5.3 note 3) or 220 B per entry (this fork's one small-example reading, same place). The registered expectation, taken from that note, is the 23 B rate for the dense family (upstream's full-size point contradicts 220 B there). The falsifier is a slope within 2x of 220 B, or within 2x of neither.

## Metric
Per run, each run being one fresh commitment and one `cp_prove -in` batch:
- **GPU memory (y_mem)**: the largest `memory.used` sample (MiB, converted to bytes as MiB x 2^20) of `nvidia-smi --query-gpu=timestamp,memory.used,... -lms 100` taken between the wall-clock start and end of that run's `cp_prove` (both recorded by the runner as epoch seconds with nanoseconds). Sampled maxima, not true peaks. Sample interval 100 ms. The `cp_commit` window is reported separately and is not used in the fit (cp_commit sizes its buffer to what is free, `research/gpu/README.md`).
- **Time (y_time)**: `cp_prove` wall seconds from `/usr/bin/time` (`%e`), plus `cp_commit` wall seconds, user CPU and max RSS of both (`%U %S %M`).
- **x_mem** (memory fit): in-step x largest-link entries, both fixed per configuration before the run (table below). **x_time** (time fit): requests in the batch x entries of one request (the planner's total over all links).
- Entries are counted by `cp_verify -plan arrays <config> 128`, summing rows x columns over every `array:` line, per link (the method of `research/operators/qwen_m3/planner_proxy.py`).
- `cp_prove`'s own printed GPU memory plan line (`chain_frame.cuh`, `card_plan_print`), recorded as printed, not used in the fit.
- Host memory: max RSS of `cp_commit` and `cp_prove`, and cgroup `memory.peak` of the job.
- Verdict of every proof: on the box (`cp_verify`, duty 6, before any export) and **off the box on CPU** (`cp_verify` built from the pinned commit on a CPU-only machine, run on every exported public bundle). A run counts only if both say `YES` (exit 0) for every proof of its batch.
- Fits, by ordinary least squares over every counted run of every configuration: y_mem = a + b x_mem and y_time = c + d x_time. Reported: a, b, c, d; the standard error of each from the fit; and, as the spread, the minimum and maximum of b (and d) over every choice of one run per configuration (all 3-point fits).

## Configurations (fixed now)
All three run on made-up weights (`-weights made-up-blocks -M 1`), the default (serving) build, the exact-match policy, CC mode off. Entry counts are the planner's, printed by `cp_verify -plan arrays` (CPU, before registration; the arrays files land in `planner/` in the next commit, made with a verifier of a later main commit; the job re-records them on the box with the image's own `cp_verify` and the fit uses the box's counts if they differ, which is then reported).

| id | parameter file | T | requests | -in-step | entries of one request (total) | largest link | x_mem | x_time |
|---|---|---|---|---|---|---|---|---|
| C1 | `prover/examples/target_small_f2_roomy` unchanged (the small synthetic example), its `own_choices.req` | 64 | 1 | 1 | 87,178,558 | 25,235,939 | 25,235,939 | 87,178,558 |
| C2 | C1 with `lt 8`, `la 9`, the eight table-digest blocks (`tsilu*`, `tsig*`, `trope*`, `texp*`) removed (all or none, `policy-tables`), `iota*` recomputed by `verifier/tests/forest_lines.py`, `layout.txt` by `prover/tools/pack_layout.py` (message 17, free 4) | 256 | 8 | 4 | 105,868,606 | 33,247,791 | 132,991,164 | 846,948,848 |
| C3 | C2's recipe with `lt 9`, `la 10`, `f 2048`, `fe 1024` | 512 | 64 | 10 | 147,640,092 | 50,857,541 | 508,575,410 | 9,448,965,888 |

Span: x_time 108x (C1 to C3), x_mem 20.2x. **The memory axis does not reach two orders of magnitude, and that is a registered limitation, not an oversight:** under the 220 B hypothesis a 100x span from C1 would need 2.5e9 resident entries, 555 GB, four times the card. The largest x_mem was chosen so that it fits the card under both hypotheses (below). C2 and C3 requests are made by `prover/tools/make_request.py` from a file of pseudo-random tokens (seed = request index, recorded), r = T - 1, e = T (next token only); the planner's arrays do not depend on r and e (not checked beyond the planner; recorded). C2 and C3 change the window length and C3 the feed-forward width; both stay in the dense family (attention, SwiGLU, norms, head; `NE 4` as in C1, the expert segments unchanged), and neither is a Qwen configuration.

Not included, and why:
- A Maverick-width proxy (`target_full_f2` shapes): its table (`table 11 32 ...`) brings full-size commit cost (28 min on an H200 box, `research/results.yaml` 780 neighbourhood, and the run script's 280 GB host floor), which does not fit the 75-minute job or the 64 GB instance memory of the draft config.
- `-in-step 16` at C3: x_mem 8.1e8, 179 GB at 220 B per entry, over the card's 143,771 MiB (`experiments/20261104-43-h200-memory-lever/rental2/h200-report-TB1.txt`).
- T = 1,024 windows: the planner refuses `lt 10` with this head (`NO: shape-call-H-R16a`).

### Expected GPU memory, host memory and time (estimates unless cited)
| id | GPU memory, 23 B/entry + intercept | GPU memory, 220 B/entry | host memory | cp_prove wall | cp_commit wall |
|---|---|---|---|---|---|
| C1 | 5.55 GB (measured on an H100: 5,293 MiB sampled, `research/gpu/README.md` line 35) | same, by construction | cp_prove RSS about 0.88 GB, cp_commit 0.86 GB (H100, `research/gpu/replication-1/README.md` line 49) | 2.21 to 2.46 s (H100, replication-1 line 38) | 17.2 to 21.3 s (H100, replication-1 line 36) |
| C2 | 8.0 GB (estimate: 4.97 GB intercept + 23 x 1.33e8) | 29.3 GB (estimate) | under 4 GB (estimate; not known) | 2.7 s (central rate 4.1e-10 s/entry + C1 start-up, estimate) to 23 s (C1's per-entry rate, estimate) | about 20 s (estimate: same table as C1) |
| C3 | 16.7 GB (estimate) | 111.9 GB (estimate) | under 16 GB (estimate; not known, the draft config gives 64 GB) | 6 s (estimate) to 255 s (estimate) | about 20 s (estimate) |

The C1 intercept estimate (4.97 GB) assumes the 23 B rate; under the 220 B rate there is no intercept. C3 at 220 B (112 GB) plus a CUDA context is under the card's total; it fits under both hypotheses only if the intercept is below about 30 GB (estimate).

## Acceptance threshold
The calibration is **usable** only if all hold: each of C1, C2, C3 has at least 3 counted runs (both verifiers `YES` on every proof); every sampled prove window has at least 5 samples; and the fit uses all counted runs. Then, for the dense family only, as written in `research/cost/Q3-COST-MODEL-1112.md`, "The next experiment to register":
- b in [11.5, 46] B per entry (within 2x of 23): **the central memory rate is supported for dense segments.**
- b in [110, 440] B per entry (within 2x of 220): **the fork's own rate is supported for dense segments.**
- otherwise: **neither rate is supported**; the cost note's memory ranges widen.
- The same rule for b's minimum and maximum over the 3-point fits: a classification is reported as firm only if every 3-point slope falls in the same class; otherwise "class X by the fit, not firm by the spread".
- d within [2.05e-10, 8.19e-10] s per entry (within 2x of the central 4.33 s / 10,573,982,429 entries, `experiments/20261109-32-qwen-m3-design/PREREG.md` line 87): **the central time rate is supported for dense entries.** Otherwise not.
- **Intercept dominates** (the issue's negative): if a > b x x_mem at every configuration (respectively c > d x x_time), that is reported, and then neither rate is usable for Qwen fit estimates whatever b says.
None of these makes a Qwen memory or USD figure stand: no DeltaNet entry is measured.

C1 also serves #43 phase 2: its runs are the #43 warm repeats (below), judged there by that PREREG's own threshold.

## Kill criterion
- Job: `FP_JOB_TIMEOUT` = 3,300 s from the job's start; the instance gets at most 75 min from boot to finished job (boot, image pull and job start inside the remaining 20 min, unmeasured). Each calibration run has its own step timeout (C2: 300 s, C3: 900 s; C1 as #43: 600 s).
- `FP_ONBOX_BUILD` = 1 (the #43 PREREG's cold run, programs rebuilt on the box, 18 to 20 min on an H100, replication-1 line 34), so no #43 deviation on that point. Budget (estimate): build 20 min, C1 cold + 10 repeats 6 min, C2 3 min, C3 up to 24 min (255 s prove + 64 on-box verifies at about 3 s + 20 s commit, x 3), total about 53 of the 55 min; if the 255 s worst case holds, C3's third run is the one at risk, and it is the one dropped (reported as timed out, not replaced). With `FP_ONBOX_BUILD` = 0 the job would gain 20 min but deviate from #43; not chosen.
- The GPU sampler runs at 100 ms for the whole job (the #43 PREREG says 500 ms; finer sampling is recorded there as a dated amendment, it changes no #43 threshold).
- Order inside the job: `cc_probe`, then #43 phase 2 (cold run, then 10 warm repeats, which are C1), then C2 x 3, then C3 x 3. A timeout loses the largest configuration first.
- If C3's commitment is refused by `cp_commit` (for example the worst-case check, status 7, which cannot be run without a GPU and has not been run at `lt 9`), C3 is **not replaced**: it is reported as refused, and the fit is reported over C1 and C2 only, labelled "two configurations, not the registered three; no classification". Same for C2.
- If `cc_probe` shows `cudaHostRegister` failing (CC mode on despite the request), every later step is expected to fail fast; the job still runs and finalises, and the result is the #43 CC-on negative, no calibration.
- The window's restore cut-off (`research/gpu/tinfoil-h200/RUNBOOK.md`, window sheet) overrides everything here.

## Runs
- C1: n = 10 (the #43 warm repeats), plus the #43 cold run reported separately and not in the fit. C2: n = 3. C3: n = 3. No warmup exclusion. Sequential, one process on the GPU at a time, smallest first, a fresh commitment per run (each `cp_commit` draws its own seed).
- Exclusions only for an infrastructure fault outside the prover (instance restart, lost GPU): reported, not rerun inside this window (no time), never silently dropped. A run whose proofs are rejected by either verifier is reported and not counted.
- No run of any configuration before the window, inside or outside the gate. The job's code is debugged on CPU with mocked GPU programs only (the run_job tests); C2's and C3's parameter files are checked on CPU by the planner only.
- Off-box verification: after the window, on a CPU-only host, `cp_verify` built from the pinned commit, every exported bundle, plus the 5 mutation cases of `research/gpu/local-verify` on one bundle per configuration.

## Prior art
- This repository: the H100 small-example receipts (`research/gpu/`, `research/gpu/replication-1/`), the source of the 220 B per entry reading (one point, one configuration, sampled at 500 ms); the full-size H200 and H100 rows of #44 (`research/efficiency/README.md`, `experiments/20261104-43-h200-memory-lever/`), which give one in-step 12 point (87,237 MiB sampled) but no per-entry fit; upstream's Maverick figures (`guide/performance.md`: 80,629 of 81,559 MiB at 64 per batch with six per pass), the source of the 23 B rate through #70's fit; the planner counts of `research/operators/qwen_m3/planner_proxy.py`.
- zkML provers: zkLLM (Sun et al., 2024) and Expander report proving time against model size on one GPU; EZKL and Jolt report CPU/GPU proving time against circuit size. None of those numbers is for this prover's proof system or its entry count, and none gives a memory-per-entry slope for it. What is new here is only that slope, for this prover, on one card.
- TEE GPU: NVIDIA Hopper CC (H100/H200 CC-On; `cudaHostRegister` not allowed, r580 release notes) is why the window runs CC off. This experiment measures nothing about CC-on or TEE overhead.

## Amendments
(empty at registration)

### Amendment 1 (2026-11-12T18:27Z, before any run; no hypothesis, metric, threshold, configuration or run count changes)
- The entry counts of C1, C2 and C3 were re-printed on CPU by the pinned commit's own `cp_verify` (sha256 `7f9efc1e...04394`, inside the locally built `final` image, `runs/planner-in-image.txt`): identical to the table above (87,178,558 / 25,235,939; 105,868,606 / 33,247,791; 147,640,092 / 50,857,541).
- The job's variables are fixed: `FP_CALIB="C2:8:4:3:300 C3:64:10:3:900"`, `FP_SAMPLE_MS=100`, `FP_JOB_TIMEOUT=3300`, `FP_ONBOX_BUILD=1`, `FP_REPEATS=10` (research/gpu/tinfoil-h200/tinfoil-config.draft.yml). Each calibration run records its `cp_commit` and `cp_prove` start and end in `<run>.windows` (`stamp.sh`); the prove window of the Metric is that pair.
- In C2 and C3 the on-box `cp_verify` runs after `cp_prove` has exited, so its CPU time is outside the prove window and is not in y_time.
- If the image used in the window is the `runtime` stage (public image, no on-box build), `FP_ONBOX_BUILD` is 0; that changes #43, not this experiment.

### Amendment 2 (2026-11-12T20:00Z, before any run; from the two round-1 reviews of PR #141; no hypothesis, metric, threshold, configuration or run count changes)
- **How far the committed-entries axis spans.** The entries of ONE commitment (the planner's total of one request) go from 87,178,558 (C1) to 147,640,092 (C3): **1.69x**. The 108x span of x_time and the 20.2x span of x_mem above come almost entirely from the requests per batch (1, 8, 64) and the in-step (1, 4, 10), not from the size of the committed model. So b and d, whatever their values, are slopes over **resident and batched entries at almost fixed model shape** (the same layer count, the same expert segments, `NE 4`; only the window length and, at C3, the feed-forward width change). Carrying b or d over to larger committed models (a Qwen segment, a Maverick-width layer) is an assumption that this experiment does **not** test. A result in either class of the acceptance rule is reported with that sentence next to it. The cost note's wording "two orders of magnitude of committed entries" is met here only because x is defined as a batch product; it is not met for the model's own size.
- **Run count below STANDARDS 3.** C2 and C3 have n = 3, below the standard's at least 5 runs (at least 10 for performance). That is a **deviation from the standard**, taken for the window's time budget (Kill criterion: C3 x 3 already uses about 24 of the 55 job minutes, estimate). C1 has n = 10. Medians and spreads of C2 and C3 are reported as n = 3 (median, min, max) and no claim rests on non-overlapping ranges of n = 3 alone.
- **Header time.** The header above says 18:05Z; the commit that registered this file (484911f4) is dated 2026-11-12T18:01:09Z. The header time is clerical; the commit time is the registration time.
- **Off-box verification, made concrete.** "Every exported bundle" means every response of every exported run: the calibration runs export `in/rNN.req`, `out/rNN.y`, `out/rNN.proof` for r01 up to the run's request count, the #43 runs `example.*`. `research/gpu/tinfoil-h200/verify_offbox.py` (CPU, tested by `verify_offbox_test.py` with a mocked `cp_verify`) checks every expected response against the run's own commitment ID, counts a missing response or a withheld `out/` as a failure, and passes a run only if every response says YES (exit 0); the whole check passes only if every run does. It also runs the 5 mutation cases of `research/gpu/local-verify` on the first response of every run (a superset of "one bundle per configuration"); each must exit nonzero with a last line starting `NO`. A run that the on-box verifier rejected (out/ withheld) stays not counted, as registered.
