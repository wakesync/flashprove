# RESULTS: 20261113-170-decay-e2e

**Verdict vs the pre-registered bar: XS18 KILLED, XS18+U4 KILLED, XS18+U3 KILLED. The logits were not produced before the registered hard stop, so H is not tested and issue #170 has no answer here.** CPU, no proof. Every number below is descriptive (no threshold), from a run stopped after 21 of 64 layers.

## Plain-language summary

- The question was whether PR #159's table decays (U4, which passed its per-head bar, and U3, which did not) change the abliterated model's next-token predictions when they replace XS18's float decay in all 48 DeltaNet layers, using PR #124's harness and bar.
- The run needs the shared big-memory CPU slot. Another lane (#150 part B) held it from before this PREREG until 15:23:28Z. The PREREG fixed a hard stop of 2026-11-13T15:50:00Z before any code was written, so 26.5 minutes were left against about 75 minutes of work at the rate this run reached (about 70 s per layer). The watchdog stopped the run at 15:50:04Z after layer 20, as registered.
- What was checked: the harness was debugged on a non-suite fixture, and it works: the control path is bit-identical to PR #124's XS18 heads (fixture) and its per-layer residual drift equals PR #124's committed numbers exactly for all 21 finished layers and 10 prompts. Inside the model, the decay the U4 path used was at most 0.00071 from float64 per token (U3: 0.0027), as PR #159 measured on recorded inputs.
- What was not checked: any logit, any top-1, any KL. Through layer 20 the three integer paths drift from REF by almost the same amount (see section 3), but that is not a token result, and the residual is not the output.
- A respawn can run it unchanged: `decay_e2e.py run` resumes from the scratch checkpoint, but a new registration with a new hard stop is needed (see section 5).

## 1. Run record

- PREREG `PREREG.md`: first commit `ec71c8d523679036c36d7599b7e239c92231f1d3`, alone, before any code. No amendments.
- Code: `decay_e2e.py` committed in `b674bdb2d1cb75d19d9a2469ffe5de1bdca69dce` before the run (the run used that commit's file). `summarise.py`, `env.py`, `add_results_row.py`, `partial_report.py`, `partial_control.py` were written while waiting or after the stop and do not touch the forward.
- Fine exp table for U3 (`decay_r2.py fine20`, PR #159's generator): 1,048,576 rows, sha256 `58935f414d1075654248b3bea38f3af9a82bdca41fa95ef0a7c0a158e407a95c`, 0 rows differ from float64 round-to-nearest, as PR #159. All table hashes are in `runs/progress.log.jsonl` (`start` line) and `ENV.json`.
- Before the registered run, outside the heavy gate: one synthetic head check on random inputs (no model data, light): the control head equals `scaled_head.Head.run` bit for bit. Not committed (helper outside the repo); the fixture below repeats the check on real weights.
- `runs/progress.log`: slot granted 15:23:28Z (shared lock plus `fp-heavy.sh`, cores 10 to 15), hard stop 15:50:00Z (the registered lane stop, earlier than grant + 100 min), MemAvailable 13.8 GB at start. Debug fixture 15:23:28Z to 15:25:08Z, rc 0, process-tree RSS peak 3.45 GB. Registered run from 15:25:08Z; `HARD STOP run kill` at 15:50:04Z, rc -15 (SIGTERM, by pid), process-tree RSS peak 8.25 GB (under the 14 GB stop; `time -v` printed no summary because its child was signalled and it was the one killed: `runs/run.time` has only the resource tracker warning).
- Layers finished: 0 to 20 (`runs/progress.log.jsonl`, `runs/run.log`). Per layer: DeltaNet about 68 to 75 s, attention about 53 to 58 s, first-layer fetch wait 20.3 s, later fetches overlapped (`runs/divergence-abl.jsonl` `seconds`). Host shared and loaded.
- Guard errors: none (no `errors-abl.jsonl`). U4 never rejected a lookup in layers 0 to 20.

## 2. Debug fixture (`runs/debug-fixture/fixture.json`, "The capital of Italy is", stock layers 0 to 3, not a suite prompt)

- Control: the substituted head with XS18's own decay is bit-identical to `scaled_head.Head.run` (`q1_forward.head_out(.., "INT", XS18)`) in layers 0, 1, 2.
- The decay value read inside the head for U4 and U3 equals `floor((a20 + 2) / 4)` of PR #159's `arm_decay` output at every token, layers 0 to 2.
- Save / load and resume after layer 1: bit-equal. REF#2 and XS18+U4#2: bit-equal to REF and XS18+U4. Streaming logit metrics on synthetic logits: KL within 1.1e-14 of a dense computation, top-1 equal. `all_ok: true`.

## 3. Partial, descriptive (no threshold, no verdict): layers 0 to 20

Source `runs/partial.json`, `runs/partial.md` (`partial_report.py`), `runs/partial-control.json` (`partial_control.py`).

**Harness agrees with PR #124 so far.** XS18's residual relative difference from REF, per (layer, prompt), equals PR #124's committed `runs/divergence-abl.jsonl` exactly for all 210 (layer, prompt) pairs of layers 0 to 20 (max difference 0.0). This is not the registered control (that needs the logits) but says the forward and the XS18 path reproduce PR #124 up to layer 20.

**Determinism.** REF#2 and XS18+U4#2 (p01, p09) are bit-identical to REF and XS18+U4 after every finished layer.

**Decay error the paths actually used** (max over prompts, tokens and V heads, per DeltaNet layer, |a_path / 2^18 - a_float64(ar)|): XS18 3.7e-6 to 1.3e-5; XS18+U4 1.4e-4 (layer 0) then 5.8e-4 to 7.1e-4; XS18+U3 1.4e-3 (layer 0) then 1.9e-3 to 2.7e-3. These match PR #159's U4 and U3 per-token maxima on recorded inputs (0.00071 and 0.0028) to within the added 2^-19 conversion. The bar PR #159 used is 0.00195 per token: U3 exceeds it inside the model too, U4 does not.

**Residual drift after layer 20** (relative L2 difference from REF):

| prompt | XS18 | XS18+U4 | XS18+U3 |
|---|---|---|---|
| p01-ordinary-short | 0.00165 | 0.00170 | 0.00155 |
| p02-ordinary-paragraph | 0.00179 | 0.00178 | 0.00182 |
| **p03-repeat-word** | 0.00797 | 0.00800 | 0.00810 |
| p04-repeat-punct | 0.00139 | 0.00140 | 0.00143 |
| p05-code | 0.00183 | 0.00184 | 0.00184 |
| p06a-digits-256 | 0.00213 | 0.00215 | 0.00214 |
| p07-chat-ordinary | 0.000857 | 0.000869 | 0.000858 |
| p08-chat-refusal | 0.000925 | 0.000928 | 0.000923 |
| p09-multilingual | 0.00173 | 0.00175 | 0.00175 |
| p11-chat-long | 0.00146 | 0.00147 | 0.00148 |

Closed-loop heads over rel_y 0.05 in layers 0 to 20 are nearly the same in the three paths (p03: 273 / 272 / 271; p04: 41 / 39 / 41; p06a: 6 / 6 / 6; none elsewhere). Reading, descriptive only: through layer 20 the table decay adds little to the drift XS18 already has, and p03 is the prompt that drifts most in every path. Over 64 layers in PR #124, XS18's drift on p03 reached 6.1% to 6.5%; whether the U paths stay with it to the output, and whether any top-1 changes, was not measured.

## 4. Registered cells vs the bar

| arm | top-1 | KL median | KL max | verdict |
|---|---|---|---|---|
| XS18 (control) | not measured | not measured | not measured | **KILLED** |
| XS18+U4 | not measured | not measured | not measured | **KILLED** |
| XS18+U3 | not measured | not measured | not measured | **KILLED** |

H: not tested. Source `runs/summary.json`, `runs/summary.md` (`summarise.py`, which computes the full verdicts and the control check once `runs/e2e-abl.json` exists).

## 5. What a continuation needs

- The scratch checkpoint after layer 20 exists outside the repo, and `decay_e2e.py run <scratch> <runs>` resumes at layer 21 with every path. About 43 layers x about 70 s plus logits = about 55 minutes in the slot.
- That continuation must be registered as an amendment or a new PREREG with its own hard stop, and it must say that layers 0 to 20 were run (and their divergence looked at) before it was registered. The divergence through layer 20 is not a verdict, so the bar can stay as registered.
- Whoever runs it should serialise against the #150 lane on the shared lock and give the stop from the slot grant, not from a wall-clock cap set before the slot was known. That cap is what killed this run.

## 6. What is not established

- No token agreement, top-1, KL or flip for any arm. No answer to issue #170. H untested.
- The registered control (XS18 reproduces PR #124's logit numbers) is not checked. Only its per-layer residual drift through layer 20 is.
- Layers 21 to 63, the abliterated layers that differ from stock (PR #68: 17 to 51), are mostly not run (only 17 to 20 are).
- Everything PR #124 and PR #159 list as not established still holds: no proof, float64 in_proj / out_proj / attention / MLP / norms / lm_head, teacher forcing only, 10 prompts of at most 512 tokens, U4's domain chosen in sample, U4 rows generated in float64, U4 output at 2^-20 shifted to 2^-18 here (one registered rounding), the stock leg not run.
- The descriptive XS18 + exact decay at 2^-20 check from issue #170: not run (PREREG).
- Replication: none.

## 7. Deviations and disclosures

- The registered run stopped at the hard stop, as the Kill criterion says. Not a deviation, but the result is KILLED for every arm.
- `time -v` gave no resource summary (it was the signalled process); peak RSS comes from the job's own 5 s watchdog over the process tree (8.25 GB) instead.
- `partial_report.py` and `partial_control.py` were written after the stop. They compute descriptive numbers from the committed per-layer files; no verdict depends on them.
- The synthetic head check before the run was a helper outside the repo, not committed; the committed fixture repeats the same equality on real weights.
- The core set (10 to 15) differs from PR #124's (0 to 5); residual drift still matched bit for bit through layer 20.

## 8. Raw data

`runs/progress.log`, `runs/progress.log.jsonl`, `runs/run.log`, `runs/run.time`, `runs/divergence-abl.jsonl`, `runs/decay-err-abl.jsonl`, `runs/heads-abl.jsonl`, `runs/manifest-stock.json`, `runs/manifest-abl.json` (layers 17 to 20 only), `runs/debug-fixture/`, `runs/partial.json`, `runs/partial.md`, `runs/partial-control.json`, `runs/summary.json`, `runs/summary.md`.
