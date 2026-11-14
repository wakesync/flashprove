# RESULTS: 20261114-201-mlp-stage (issue #201)

Measured, unreplicated. One deterministic CPU run, the registered run. No proof, no soundness claim. This result chooses no fix and no design; it is an input for #35 and #32.

## Answer
- **H-S HOLDS.** Replacing only the SiLU table lookup (step 2^-8, index clipped to [-8, 8)) by s = RNE(2^12 silu(gw / 2^12)) moves the late-layer KL median from 1.466e-3 (M31) to 1.83e-6 nats: ratio 0.00125, registered threshold <= 0.5.
- **H-W DOES NOT HOLD.** Replacing only the 13-bit weights by the float64 weights leaves the KL median at 1.454e-3: ratio 0.992.
- In abliterated layers 31 to 63, the token error of PR #138's integer MLP is carried by the SiLU stage, not by the weight conversion. M31-S also meets PR #124's bar descriptively (1,460 of 1,461 top-1, KL median 1.83e-6, max 1.57e-3); M31 and M31-W do not.

## Validity
- G1 REF top-1 equals PR #173's committed `runs-resume150b/runs/e2e-abl.json` on all 10 prompts: true.
- G2 M31#2 bit-equal to M31: residual after every layer 31 to 63 and every logit metric on p01 and p09: true.
- G3 no guard error in M31 or M31-S (and none anywhere): true. REF sanity (p01 last token Tokyo): true.
- Start state: `ckpt.npz` sha256 `22dff8b92107511838e50e4b26d6e91a2b55d09064711c638042c4c18fb80009` (PR #167), re-hashed by the lane before the run, again inside the job on its copy (`runs/progress.log`, match true, meta next_layer 31), and the source again after the run (unchanged). Layers 0 to 30 were not regenerated.
- Weights: all 437 abliterated tensors fetched (layers 31 to 63, final norm, lm_head) and the 25 stock tensors of the timing probe have the sha256 of PR #124's committed manifests (`run-record.json` manifests_vs_pr124, 0 mismatches).
- Unit checks (committed with their output in `unit_checks.json` before the run, commit 7cbc472): (1a) all 4,096 table rows equal RNE(2^12 silu((i - 2048) / 256)) in float64; (1b) M31-S equals `mlp_int` bit for bit with gw on the 2^4 grid inside the domain; (1c) they differ off the grid / outside; (2) M31-W equals `mlp_int` bit for bit with weights exact at their exponent, and differs with inexact weights.
- Timing rule (PREREG): probe t_lin 53.0 s, t_full 54.2 s (512 synthetic tokens); projected 5,171 s for 10 prompts vs 5,851 s available, so the full 10-prompt set ran (the six-prompt fallback was not needed). The run ended by the registered abl-done rule 90 min 34 s after the slot grant, inside the 100-minute cap.

## Token metrics vs REF (1,461 positions, 10 prompts; `runs/summary.json`, `runs/summary.md`)

| path | top-1 agree | KL median | KL p99 | KL max | KL SD (positions) | flips | PR #124 bar (descriptive) |
|---|---|---|---|---|---|---|---|
| M31 (PR #138 `mlp_int`) | 1,423 (97.40%) | 1.466e-3 | 0.103 | 1.93 | 0.0706 | 38 | fails all three |
| M31-S (exact SiLU) | 1,460 (99.93%) | 1.83e-6 | 3.54e-4 | 1.57e-3 | 8.47e-5 | 1 | meets all three |
| M31-W (float weights) | 1,422 (97.33%) | 1.454e-3 | 0.0998 | 1.94 | 0.0699 | 39 | fails all three |
| FM, PR #173 (integer MLP in all 64 layers, cited) | 1,422 | 1.60e-3 | - | 1.92 | - | 39 | fails |

Spread over prompts (per-prompt KL median): M31 2.75e-4 to 2.67e-2; M31-S 1.09e-7 to 3.23e-5; M31-W 2.71e-4 to 2.65e-2 (per-prompt table in `runs/summary.md`).

Flips: M31's 38 flips have REF margins 0.00077 to 2.90 logits (median 0.0775), the largest KL at p11-chat-long position 9 (REF margin 2.90, KL 1.93) and p08-chat-refusal position 35 (REF margin 0.787, KL 1.63). M31-W flips all 38 of M31's positions plus p11-chat-long position 165. M31-S has one flip: p11-chat-long position 161 (REF margin 0.0631, KL 8.8e-4), which M31 does not flip.

Descriptive: M31 (integer MLP only in layers 31 to 63) is already at 92% of PR #173's whole-model FM KL median (1.466e-3 vs 1.60e-3) with almost the same flip set, so most of FM's token error comes from the late layers; the "most error from layers 0 to 30" outcome of the issue is not what was seen.

## Range counters, layers 31 to 63 (totals over 10 prompts; `runs/ranges-abl.jsonl`)

| path | SiLU domain exits (lo + hi) | h >= 2^18 | h >= 2^23 | m > 2,047 | max h | max acc_down | max out |
|---|---|---|---|---|---|---|---|
| M31 | 182,274 (28,918 + 153,356), saturated | 632 | 0 | 101,635,217 | 2^20.15 | 2^33.03 | 2^21.03 |
| M31-S | 180,798 (27,801 + 152,997), counted, not saturated | 2,541 | 0 | 101,661,026 | 2^20.77 | 2^33.59 | 2^21.59 |
| M31-W | 182,303 (28,946 + 153,357), saturated | 631 | 0 | 101,630,159 | 2^20.15 | 2^33.03 | 2^21.03 |

M31's counters reproduce PR #173's FM counters to within the path difference (FM: 181,833 exits, 634 h >= 2^18). Removing the clip lets s, h and out grow (M31-S has 4x the h >= 2^18 entries), so the arm that keeps the tokens has larger, not smaller, intermediate ranges.

Per layer (median residual rel L2 vs REF over prompts, `runs/summary.md`): M31 and M31-W track each other from layer 42 on and jump at the layers with the most SiLU exits (layer 54: 2,178 exits, rel 0.0828; layer 58: 2,378, 0.122; layer 63: 143,833, 0.151); M31-S stays between 0.00095 and 0.0063 through layer 63. Before layer 42 (few exits), M31-W is below M31-S (layer 41: 0.00213 vs 0.00290), i.e. in-domain the weight conversion contributes more to the residual than the table step, but that is small next to the saturation-driven jumps. Descriptive only.

## Run
- Slot granted 2026-11-14T04:48:46Z (cores 8-13, MemAvailable 18.6 GB). Stop: abl_done 06:19:21Z (SIGTERM to the lane's own pid after `e2e-abl.json` was written; `/usr/bin/time` reports signal 15). Elapsed 1:30:34.
- Per-layer wall clock median 157.5 s (90.3 to 195.2), logits 121.6 s; shared loaded host.
- Peak RSS: 8,527,588 kB (time -v, largest process); process tree max 8,748,640 kB at the 2 s polls. Disk free at least 42.6 GB throughout.

## What is NOT established
- M31-S combines two changes: no table step (rounding of gw to the 2^4 grid and the table's own rounding) and no domain clip. The run does not separate them. The per-layer residual pattern points at the clip (jumps where exits concentrate; on-grid the table equals exact SiLU), but that is descriptive, not a registered measurement.
- M31-S is not an admissible M3 operator: its SiLU input exits the v1 table domain on 180,798 entries and h exceeds the 2^18 honest contract on 2,541 entries; m exceeds the 2,047 class on 101.7M entries in every path (m is not clamped, as in PR #138). No repair (wider domain, clamp semantics, different table) was tested.
- Only layers 31 to 63, abliterated leg, PR #124's 10 prompts, float64 heads/attention/norms. Not the stock leg, not XS18 heads, not layers 0 to 30, not other prompts or hardware.
- One deterministic run; no independent replication. No proof.

## Files
- `PREREG.md` (first commit, alone), `mlp_stage.py`, `unit_checks.py` + `unit_checks.json`, `debug/fixture-debug.json` (PR #88 fixture prompt only), `summarise.py`.
- `runs/e2e-abl.json` (per-position metrics), `runs/divergence-abl.jsonl`, `runs/ranges-abl.jsonl`, `runs/progress.log(.jsonl)`, `runs/manifest-abl.json`, `runs/probe/manifest-stock.json`, `runs/summary.{json,md}`.
- `watchdog.log`, `run.time`, `progress.log`, `run.log`, `run.stderr`, `run-record.json`, `ENV.json`.

Reproduce: `python3 mlp_stage.py run <copy of ckpt.npz> runs <grant unix>` (OMP/OpenBLAS threads 6), then `python3 summarise.py runs`; unit checks `python3 unit_checks.py`.

## Amendments
None. The PREREG was not changed after registration.
