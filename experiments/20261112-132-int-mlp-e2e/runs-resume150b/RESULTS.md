# Amendment A-3 (issue #150 part B): resume of PR #138's registered run, abliterated layers 31 to 63, logits and the bar. Results

**Outcome vs the registered bar: FAIL.** XM18 (XS18 DeltaNet heads + the M3 integer MLP in every layer) on the abliterated checkpoint, all 10 frozen prompts of PR #124 (1,461 positions):

| criterion | bar | measured | pass |
|---|---|---|---|
| top-1 agreement with float64 | >= 99.0% | 1,423 of 1,461 (97.40%) | no |
| KL(REF \|\| XM18) median | <= 1e-4 nats | 1.59e-3 nats | no |
| KL max | <= 0.1 nats | 1.92 nats (p11-chat-long, position 9) | no |
| no guard error | none | none (no `errors-abl.jsonl`) | yes |

REF sanity passes (p01 last position " Tokyo", 25358). Determinism: XM18#2 bit-equal to XM18 after every layer 31 to 63 and in every logit metric (`deterministic` true in `runs/summary.json`). H (numerical) is false on abl. Range verdict on layers 31 to 63: OUT-OF-BOUND.

Measured, unreplicated. One deterministic run is the registered run (PREREG A-3 "Runs").

## Plain-language summary
PR #138 put integer arithmetic (the M3 design's MLP lowering) into every layer of the abliterated Qwen3.8-27B and stopped half way. PR #167 regenerated its half-way state bit for bit. This run continued from that state through the last 33 layers and computed the next-token predictions. The integer model picks the same next token as float64 on 97.4% of positions; the registered bar asks for 99% and much smaller probability differences, so it fails on all three numbers. The float-heads variant FM (integer MLP only, float64 heads) fails the same way (97.33%), and the XS18 heads on their own pass (PR #124: 1,460 of 1,461). That points at the integer MLP lowering rather than the heads; it is a comparison of two distances to float64, not a measured decomposition.

## 1. Token agreement (registered metric, PR #124's code)
Source: `runs/summary.json` `legs.abl.cells`, `runs/summary.md`, `runs/e2e-abl.json`; extra descriptive aggregates in `numbers.json` (`resume150br2_numbers.py` style reader of the same files, see section 6).

| path | n | top-1 agree | KL median | KL p99 | KL max | KL SD | bar |
|---|---|---|---|---|---|---|---|
| XM18 | 1,461 | 1,423 (0.9740) | 0.00159 | 0.101 | 1.92 | 0.0707 | FAIL |
| FM (float heads, integer MLP; descriptive) | 1,461 | 1,422 (0.9733) | 0.00160 | 0.101 | 1.92 | 0.0705 | (would fail) |
| XS18 only (PR #124 committed run, cited) | 1,461 | 1,460 | 2.95e-06 | - | 0.00566 | - | PASS in PR #124 |

REF top-1 equals PR #124's committed REF on every prompt (post hoc consistency check, `ref_top1_equal_pr124`).

Per prompt (XM18; FM within one flip on every prompt, see `runs/summary.md`):

| prompt | T | agree | KL median | KL max | residual rel L2 vs REF after layer 63 |
|---|---|---|---|---|---|
| p01-ordinary-short | 13 | 12 | 0.0268 | 0.353 | 0.158 |
| p07-chat-ordinary | 23 | 22 | 0.00033 | 0.035 | 0.242 |
| p08-chat-refusal | 39 | 37 | 0.000357 | 1.66 | 0.175 |
| p09-multilingual | 21 | 19 | 0.0177 | 0.128 | 0.127 |
| p02-ordinary-paragraph | 107 | 96 | 0.00614 | 0.0808 | 0.140 |
| p04-repeat-punct | 64 | 64 | 0.0111 | 0.238 | 0.232 |
| p05-code | 144 | 143 | 0.000479 | 0.101 | 0.143 |
| p03-repeat-word | 512 | 511 | 0.000306 | 0.264 | 0.182 |
| p06a-digits-256 | 256 | 247 | 0.00836 | 0.0931 | 0.185 |
| p11-chat-long | 282 | 272 | 0.00232 | 1.92 | 0.123 |

Spread over the 10 per-prompt values (XM18): top-1 fraction median 0.9605, SD 0.0372, min 0.8972 (p02), max 1.0 (p04); per-prompt KL median: median 0.00423, min 0.000306, max 0.0268; per-prompt KL max: median 0.183, min 0.0350, max 1.92. 7 of 10 prompts have a KL max over 0.1 nats; 15 of 1,461 positions are over 0.1 nats; 1,347 of 1,461 positions are over 1e-4 nats.

**Called out (as registered by issue #150):**
- **p03-repeat-word** (512 positions): 511 agree, one flip at position 1 (ref 271 -> 198, REF margin 0.144, KL 0.155). Its KL median 3.1e-4 is among the lowest; the drift that PR #138 saw on p03 by layer 29 did not turn into many flips.
- **p06a-digits-256** (256 positions): 9 flips, mostly digit-to-digit with small REF margins (0.00077 to 0.478; median 0.0160): positions 8, 114, 145, 161, 168, 172, 181, 192, 207. PR #124's XS18-only run had 1 flip here (position 81).
- The largest flips by KL are not on these two: p11-chat-long position 9 (REF 248046 -> 220, REF margin 2.90, KL 1.92) and p08-chat-refusal position 35 (REF 198 -> 248068, REF margin 0.787, KL 1.66). Token ids 248046 and 248068 are near the top of the 248,320-id vocabulary (not decoded here; descriptive).
- p02-ordinary-paragraph has the most flips (11 of 107) and the lowest agreement (89.7%).

**All 38 XM18 flips with REF's top-1 margin** (logit units) are listed in `runs/summary.md` and `runs/summary.json` (`cells.XM18.flips`). REF margin over the 38 flips: median 0.0883, min 0.00077, max 2.90. 3 of the flips (p07, p08 and p11, position 2) are the same chat-template context (ref 2523 -> 1, margin 0.0775).

## 2. Ranges (registered, descriptive, no threshold), XM18, layers 31 to 63
Source: `runs/summary.md` "ranges", `runs/ranges-abl.jsonl`, `numbers.json`. Pooled over the 33 layers of this resume only; layers 0 to 30 are PR #138's (RESULTS section 2) and PR #167's reproduction, cited, not recomputed.

| quantity | max abs | log2 | where | bound | events |
|---|---|---|---|---|---|
| m | 235,253 | 17.84 | layer 63, p03 | \|m\| <= 2,047 | 101,566,552 of 246,850,560 entries (41.1%) |
| gw | 236,620 | 17.85 | layer 62, p11 | honest < 2^18, rng < 2^23; SiLU domain [-2^15, 2^15) | 0 over 2^18; SiLU saturated: 28,771 low + 153,193 high = 181,964 of 839,291,904 hidden entries |
| u | 248,495 | 17.92 | layer 63, p06a | honest < 2^18 | 0 |
| h | 1,167,750 | 20.16 | layer 62, p11 | honest < 2^18, rng < 2^23 | 622 entries >= 2^18 (layers 52 to 62), 0 >= 2^23 |
| down accumulator | 8.75e9 | 33.03 | layer 63, p06a | ledger 2^55.02 | 0 |
| out | 2,136,640 | 21.03 | layer 63, p06a | < 2^31 | 0 |

Weight exponents 11 to 14, all in 1..24; all \|W_int\| <= 4,095. Range verdict: OUT-OF-BOUND (XM18 class events 101,748,516: m over class plus SiLU saturations). New against PR #138's layers 0 to 30: the h honest contract 2^18 is exceeded (622 entries, PR #138: none, max 145,770), and SiLU saturations grow from 6 (PR #138, layers 21 to 26) to 181,964. The m share per layer rises from 26.0% at layer 31 to 59.8% at layer 62 (57.2% at 63).

## 3. Drift (descriptive)
Residual relative L2 vs REF, XM18, median over 10 prompts (`runs/divergence-abl.jsonl`, `numbers.json` `XM18_resid_rel_median_by_layer`): 0.0064 after layer 31, 0.0143 after layer 53, then a step to 0.0905 at layer 54, 0.132 at layer 58, 0.167 after layer 63 (SD over prompts 0.041, min 0.123, max 0.242). FM: 0.167 after layer 63. FM and XM18 are two distances to float64, not a decomposition (no XS18-only arm in this run; PR #124's XS18-only arm is cited).

## 4. Run record
- Code at the run: `1960ec5f81b4ad9fd092bed7bbaa7571a56fb4cf`, unchanged, from a checkout of that commit: `mlp_e2e.py run <state> <runs> full`. The code loaded the state, logged `resume` with meta `{leg abl, next_layer 31, legs_done [], prompt_set full}` and ran layers 31 to 63 and `finish_leg("abl")`. Summariser: `summarise_mlp.py` at `1960ec5`, unchanged, run on `runs/`.
- Starting state: copy of PR #167's `ckpt.npz`, sha256 `22dff8b92107511838e50e4b26d6e91a2b55d09064711c638042c4c18fb80009` for the source and the copy (`state-start-sha256.json`); x16.npz `67dde0e8...53d5` likewise. Source re-hashed before the copy; it is not modified.
- Gate: `flock bigmem.lock fp-heavy.sh taskset -c 6-11 /usr/bin/time -v -o run.time python3 <entry> ...` under a systemd user unit. Slot granted 2026-11-13T13:55:55Z, MemAvailable 13,319,468 kB (KiB; 12.70 GiB, above the 12 GiB floor as implemented), no queue wait.
- Stop: rule (1), abl done. The `logits_done` line for abl was written 15:23:26Z; the watchdog sent SIGTERM at 15:23:28Z; `time -v`: "Command terminated by signal 15", elapsed 1:27:33. No stock-leg layer line was written before the signal (`run-record.json` `stock_progress_lines_after_abl` empty). No other stop rule fired: 120-min budget would have ended 15:55:55Z, hard stop 16:45Z.
- Per-layer seconds (33 layers, `layer_s`): median 155.0, min 109.3, max 194.5 (host shared and loaded, load average about 6.5). Logits 103.6 s.
- Peak RSS (`time -v`, largest single process): 8,152,664 kB (7.78 GiB). Watchdog process-tree VmRSS at logged events: max 4,681,760 kB. Free disk min 54.0 GiB at logged events. User 8,895 s, system 3,736 s, 240% CPU.
- Weights: 437 abliterated tensors fetched (layers 31 to 63, final norm, lm_head); sha256 of every one equals PR #124's committed `manifest-abl.json` (`run-record.json` `manifests_vs_pr124`). No stock tensor fetched.
- End state: `ckpt.npz` sha256 `521dd9e937bd17c59b55d209a994c610de656286067e69f8279eafcc9402d211` (meta `legs_done [abl]`), outside the repository (`state-end-sha256.json`).
- `run.stderr`: one multiprocessing resource_tracker warning (6 leaked semaphores), a consequence of the SIGTERM stop.

## 5. What this establishes, and what it does not
- Establishes (measured, unreplicated, one deterministic run): with PR #138's code and lowering, starting from PR #167's hashed layer-30 state, the abliterated XM18 path fails PR #124's bar on all three numeric criteria; FM fails it the same way; the integer MLP values leave the design's classes in more places in layers 31 to 63 than in 0 to 30.
- Does not establish: the stock leg (out of scope, not run); anything about a changed m arithmetic (DRAFT-1, clamp or smaller scale; out of scope); any proof; a second prompt set; behaviour on other hardware or BLAS. It is not an independent replication. It does not move PR #138's cutoff: layer 30 is this run's input and stays post-cutoff evidence for PR #138. Which component of the integer MLP (m over class, SiLU saturation, h rounding) causes the flips is not separated here; FM vs XM18 only says the XS18 heads add little on top.

## 6. Deviations
- None from amendment A-3. Disclosed: the watchdog was tested on a dummy process before the run (no forward). `numbers.json` is a post-run descriptive reader of the committed run files (no new measurement); it is generated by a helper script kept in the planning directory, outside the repository, and every number in it can be recomputed from `runs/`.

## 7. Files (this directory)
`runs/` (the job's own output: `divergence-abl.jsonl`, `ranges-abl.jsonl`, `heads-abl.jsonl`, `e2e-abl.json`, `manifest-abl.json`, `progress.log.jsonl`; summariser output `summary.json`, `summary.md`), `numbers.json`, `run-record.json`, `watchdog.log`, `run.time`, `progress.log`, `run.log`, `run.stderr`, `state-start-sha256.json`, `state-end-sha256.json`, `ENV.json`. Host paths replaced by placeholders. PR #138's `runs/` and PR #167's `runs-resume164/` are not modified.

Next arm (proposal, not run): the m class question (DRAFT-1 / PR #152's arms) judged end to end against this bar; a registered run that changes the m arithmetic needs its own PREREG.
