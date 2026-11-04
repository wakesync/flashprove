# Efficiency levers (research lane, work in progress)

Tracking issue #43. Related: #7 (cost), #39 (prover speedup). Base: main 29907e5f (VERSION 0.16.0).
Nothing here is a claim until merged and reviewed. Upstream figures are quoted from
`guide/performance.md`, `docs/figures.tsv` (row ids in backquotes) and `paper/paper.pdf` section 7.
All upstream timings: one H100 80 GB of an 8-GPU host, 24 CPUs, public 4-bit Maverick files unless
marked synthetic, n = 3 runs.

## 1. Fact-check of the public cost teardown

Source: 0xOsprey, "FlashProve economics, raw vs proven inference" (GitHub gist 52fd0803...).
Headline: ~$0.017 per proven 1,024-token request, ~$15/Mtok proven vs ~$0.11 raw, ~165x all-in.

Legend. UP = upstream-measured, matches the repo. CONV = the author's own conversion or assumption
(arithmetic checked). WRONG = does not match the repo or the arithmetic. NUANCE = number right,
framing loses a caveat the repo states.

| Teardown number | Verdict | Evidence / correction |
|---|---|---|
| 111.23 tok/s at batch 24 ("400k tok/hr") | UP | `rate-24` 111.23 ± 0.92, n = 3. 111.23 x 3600 = 400,428 tok/h. |
| 17.4 / 76.3 / 123.3 tok/s at batch 1 / 8 / 64 | UP | `rate-1`, `rate-8`, `rate-64`. |
| Waits ~59 / ~107 / ~222 / ~536 s | UP for 24 and 64, CONV for 1 and 8 | `latency-24` 220.7 to 225.9, `latency-64` 533.3 to 537.9. 1 and 8 are seconds-per-request x batch (58.8; 13.41 x 8 = 107.3); no measured wait exists for them. |
| batch 64: 80,629 of 81,559 MiB; synthetic attempts at 64 all fail at a CUDA call | UP | `gpu-mem-64`, `failed-batch`, `service-at-64-synthetic` (0 of 320). Public weights at 64: 960 of 960 accepted. Cause of the synthetic failure is "not known" upstream: OOM is the teardown's inference, not a finding. |
| 18.78 MB proof, 6.24 MB client download, 2.15 GB provider secret dir | UP | `proof-size-mean`, `client-download`, `secret-dir-size`. |
| Commit 38.7 min | UP | `commit-time-drawn` 38:43.77. |
| 688k batches per leaf table | UP | `batches-per-leaf-table` 688,127. |
| cp_verify ~21 s (1 thread), ~17 s (8-24 threads), <= 3.53 GB | UP | `verify-time` 21.14, `verify-time-8-threads` 16.84, `verify-time-24-threads` 17.07, `verify-memory` 3.53 GB. |
| Lean verify ~24 min, <= 14.13 GB | UP, not released programs | `lean-verify-time` 1,414 s; marked † (not the released programs). |
| Middleware check ~94 s per batch of 24 | UP, n = 1 | `serving-check-24`, one run, synthetic, not a timed run. |
| "~280 GB host RAM" | UP, rounded | `container-mem-no-cache` 269.7 GB public / 278.3 GB synthetic; `host-mem` 257.1 GB (process). |
| 93x (max load), 71.4x (same batch), 20.1x (vs decode) | UP (calculated upstream) | `overhead-prefill-max`, `overhead-prefill-24`, `overhead-decode`. Baseline: vLLM FP8 on 8x H100, separate days; upstream says baseline is a lower bound. |
| Unproven ~37.2M tok/GPU-h, ~$0.094/Mtok GPU-only | CONV, arithmetic OK | 111.23 x 93.0 x 3600 = 37.24M tok/h; $3.50 / 37.24 = $0.094/Mtok. |
| Proven ~$15/Mtok | CONV, arithmetic OK given his inputs | ($3.50 GPU + $3.00 host) / 0.4004 Mtok/h = $16.2/Mtok; GPU only $8.74. "~$15" is mildly low for his own $6.5/h. |
| $/Mtok ~$96 / ~$22 / ~$15 / ~$13.5 at batch 1 / 8 / 24 / 64 | CONV, slightly low | At $6.5/h: $103.7 / $23.7 / $16.2 / $14.6. His column looks computed at ~$6.0/h. |
| ~$0.017 per request | CONV, OK | 9.206 s x $6.5/h = $0.0166. |
| ~165x all-in | CONV, depends on two assumptions | 93 x (6.5 / 3.5) = 172.7x if the raw side pays no host share; with his $0.016/Mtok host share on the raw side, ~147x. Headline sits inside his own 100-170x range; it is not an upstream number. |
| Host ~$3/h for 24 vCPU + ~280 GB | CONV, unsourced | No upstream price. It is the largest single assumption after GPU $/h. Upstream ratios are "per GPU" and explicitly exclude CPUs and host memory (performance.md "Cost"). |
| Middleware ~23 s of 1 CPU per request | CONV | 94.0 s x 6 parallel checks / 24 = 23.5 CPU-s. OK. |
| "Proving costs ~the same whether 1 or ~360 tokens are checked" / "~26x per attested token" | NUANCE | Upstream: 108.67 vs 108.73 tok/s with every reply token checked vs last token only (`rate-replies-all`, `rate-replies-control`), "the difference shows nothing". Stored replies of 31-500 tokens, chosen to meet limits. The 26x is his division, not upstream. |
| 6.81% integer vs FP16 top-token divergence; 0/96 exact match | UP | `integer-vs-float`, `gap-honest-replies-exact-match`. Python implementation, not released programs. |
| 0.58-1.46 s/token through the integer-exact vLLM plug-in | UP, † | performance.md "Proving, not serving", 48 of 48 short replies, not released programs. |
| Run-to-run spread "up to 9%" | UP, † | performance.md "How far the figures repeat". |
| "6 passes over ~200 GB of weights: 4 waves + 2 walks; ~37 s/pass" | MOSTLY RIGHT on structure, WRONG on cost split | 4 waves = 24 / `-in-step 6` (measure_rate.py default); 2 walks = `hf_side_walks()` "one pass for u, one for all opened columns" (prover/hash_commitment/hf_keeper.cu:362). But passes are not equal cost: see section 2. Weight files are 232.13 GB (`weight-files`), not ~200 GB. |
| "Binding constraint: the 80 GB card holds ~29% of ~280 GB working set; weights stream from pinned host RAM every pass" | HALF RIGHT | Streaming from pinned host memory is real (prover/prover/weight_stream.cuh header: ZeRO-Inference / FlexGen style). "Binding" is not supported: upstream numbers decompose to ~58% per-request compute (section 2). 80/280 is his ratio. |
| "Main gain is single-request latency" attributed to "report section 7"; "meaningful optimizations we did not incorporate" quote | NOT FOUND | `pdftotext paper/paper.pdf` has no "incorporat" string and no H200/B200 mention; section 7 is Evaluation. The quote may come from a technical report the repo calls "not public". Treat as unsourced. |
| "Opening more columns past the mask budget (44,040,191) fails ZK: this IS the batch-size ceiling" | NUANCE | The mask budget limits columns per leaf table over its life (688,127 batches); the per-batch ceiling in code is `SLOTS_MOST = 64` (prover/prover/slot.h) and the parameter file's `slots`. |
| Anthropic launch-post corroboration, VerInf/Attestable/DeepProve comparison | OUT OF SCOPE | Not checkable from this repo. paper Table 8 lists the same systems "without ratios, because the machines, models and proved statements differ"; the gist computes ratios anyway. |

Net: every upstream-measured number he uses is quoted correctly. The dollar figures are his
conversions on two unsourced prices ($3.50 GPU, $3.00 host); his batch cost row is computed at
about $6.0/h, not the $6.5/h he states. The weakest part is the bottleneck story, below.

## 2. Bottleneck anatomy

Claim under test (teardown): GPU memory is the binding constraint.

What the code says:
- Weights live in pinned host memory and are copied to a few GPU buffers ("rooms") group by group
  (prover/prover/weight_stream.cuh, header comment). `-memory lean` = `late-on-keys,tensor-rooms=10`
  (prover/prover/arguments.h `presets()`); the service default is `lean,tensor-rooms=8`
  (driver/measure_rate.py, integrations/vllm/REFERENCE.md).
- A batch of B requests runs ceil(B / in-step) batch passes ("waves"), each one read of the weights,
  then the opening's 2 walks (hf_keeper.cu:362). `-in-step` takes 1 to 16 (arguments.h); "whether
  more than six requests in step fit is not known" (integrations/vllm/REFERENCE.md).
- `-overlap` / `-overlap-two` fold a batch's walks into the next batch's waves, at the cost of a second
  / third weight-table keeper and engine in GPU memory; refused on a model's files (synthetic only).
- One code comment gives a single untimed run at full size, `-in-step 6`: batch passes 73-90.5 s, the
  opening's passes 34.6-38.2 s (weight_stream.cuh, comment above `load()`).
- Build targets sm_90a only (prover/build.sh line 617, `-arch=sm_90a`). B200 (sm_100) cannot run these
  binaries without a port. H200 is sm_90 and runs them.

What upstream numbers say. Fit batch time t(B) = a + b*ceil(B/6) + c*B to the five measured batch
sizes (B = 1, 8, 24, 48, 64; 48 is † not released programs; t = B*1024/rate):

| term | fitted | meaning |
|---|---|---|
| a | 38.2 s | per-batch fixed: the opening's 2 walks + batch end |
| b | 14.0 s | per wave: one weight stream not hidden behind compute |
| c | 5.32 s | per request: that request's sub-proofs over its 1,024 tokens |

Fit residuals are under 1.5 s at every B (B = 1: 57.5 vs 58.8). At B = 24: 38 s fixed (17%), 56 s
waves (25%), 128 s per-request (58%). Read: three parameters on five points, two of them partly
collinear; this is a decomposition hypothesis, not a measurement. The GPU run in section 5 measures it
directly with `-measure` ("the turns' stream stood still for weights X s").

Consequence: if per-request compute is ~58% of a batch, more GPU memory alone cannot give more than
~1.7x at batch 24, and only if it removes all wave and walk overhead. Memory is a real constraint on
batch size (64 fails on synthetic weights) and on in-step, but not obviously the binding constraint on
throughput.

## 3. Ranked levers

| # | Lever | Expected gain on tok/s (batch 24 basis) | Evidence | Cost / risk |
|---|---|---|---|---|
| 1 | Bigger GPU memory used for fewer waves: H200 141 GB with `-in-step 12..16` and batch 48 | +15 to +35% predicted (fit: B = 48, in-step 16 -> 3 waves instead of 8 -> ~147 tok/s vs 121 at in-step 6) | fit above; `rate-48-steady` 120.94 †; in-step cap 16 in arguments.h | needs H200 (~1.6x H100 $/h on Vast) so $/Mtok gain is the real test; latency rises with B |
| 2 | Batch size alone (24 -> 48/64) on 80 GB | +8.7% (48), +10.9% (64) measured | `rate-48-steady` †, `rate-64` | 64 unreliable on 80 GB; latency 2.4x |
| 3 | Same config on H200 (HBM 4.8 vs 3.35 TB/s, same SM count, same PCIe Gen5 host link) | 0 to +10% predicted | no prover code adapts room count to free memory automatically; compute dominates | pure hardware price question |
| 4 | `-overlap` / `-overlap-two` | up to the 38 s fixed term (~17%) if walks hide fully | arguments.h; synthetic-only (refused on a model's files) | more GPU memory; not usable on real weights today |
| 5 | Fill the window / check whole replies | same tok/s, more attested tokens per proof | `rate-replies-all` vs control | coverage choice, not speed |
| 6 | NUMA binding, huge pages | commit 38% (wrong node), prove ~2% | performance.md last section (†, untimed) | operational, already practice |
| - | CPU micro-tweaks | skip | PR #40: 6.5% | |

B200: excluded from the experiment, the binaries are sm_90a only. 2x H100: the prover pins device 0
(prover/prover/inputs.cuh `cudaSetDevice(0)`); multi-GPU is a code change, not a knob.

## 4. GPU experiment plan

See `experiments/20261104-43-h200-memory-lever/PREREG.md` (written before any GPU code).

## 5. Results

(pending)

### Run log
- 2026-11-04 01:22 UTC: two instances created (control: 1 GPU of a 2x H100 SXM 80 GB box, $1.219/h; treatment: 1x H200 SXM 141 GB, $5.54/h). Teardown timers armed before create. Both boxes started the pinned build at ~01:31 UTC.
- 01:42-01:43 UTC: pinned build + `examples/quickstart-gpu.sh` passed on both boxes (cp_verify YES on the small proof). ~17 min each.
- Early commit observation (n = 1 per box, the commitment's anchor table, from cp_commit's own timing lines): H200 splits the table's tree into 16 parts of 2^28 positions, 452.7 s; H100 into 32 parts of 2^27, 576.3 s (-21%). The committer sizes its parts to free GPU memory: a first direct sign of the memory lever, on commit, not prove.
- Full-size synthetic commitment (`cp_commit -weights made-up-blocks`, target_full_f2, -M 1), n = 1 per box, wall from stage log: H200 1,698 s (01:43:26 to 02:11:44), H100 1,871 s (01:42:32 to 02:13:43): H200 9% faster. Upstream `commit-time-synthetic` 2,312.68 s (other hosts/CPUs). Phase anchor-table 461.4 vs 585.1 s; key-file 240.6 vs 242.6 s. Sessions started 02:11 (H200) and 02:13 (H100).
