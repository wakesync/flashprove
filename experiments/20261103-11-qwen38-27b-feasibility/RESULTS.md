# RESULTS: 20261103-11-qwen38-27b-feasibility

Verdict against the pre-registered threshold: **PASS**, with a caveat on (a): (b) is a
pre-registered test and holds; (a) holds only under a counting rule written after registration and
against GLM/DeepSeek lists from unmerged notes (PREREG.md Amendments A1, A2).
Write-up: [research/ports/qwen3.8-27b/FEASIBILITY.md](../../research/ports/qwen3.8-27b/FEASIBILITY.md).

## Kill criterion

Not triggered. The pinned config has no routed experts (dense FFN in every layer), the pinned
Transformers reference is available and cited by line, and no file over 5 GB was fetched (only
config/index/README and the JSON headers of the 18 shards).

## Runs

`run5.sh` ran `count_params.py` 5 times against revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`.
All 5 outputs are byte-identical: SHA-256 `7da1aee23c99128b13fca59c4415eca8b787fdf0fc1975e427689876c527b68c`
(`runs/SHA256SUMS`). These are the re-runs after Amendment A3 (MAC key rename); the original 5 runs
(SHA-256 `bd6e4556d9a2bb1508a7e0f25424c33a4aaafceb38315af5878815137f8898e1`, commit `a6a6b811`) gave the
same parameter counts. Deterministic count, so variance is zero by construction; the 5 runs check that
the remote headers did not change during the lane.

## Numbers (from `runs/run1.json`)

| quantity | value |
|---|---|
| shards / tensors / dtype | 18 / 1,199 / all BF16 |
| total parameters (incl. vision and MTP) | 27,781,427,952 |
| text decoder (48 Gated DeltaNet + 16 full-attention layers, 64 dense FFNs, norms) | 24,353,201,664 |
| of which: FFN / DeltaNet mixers / full-attention mixers / norms | 17,112,760,320 / 5,562,051,072 / 1,677,729,792 / 660,480 |
| embedding / output head (untied) | 1,271,398,400 / 1,271,398,400 |
| MTP head (excluded from a first port) | 424,699,392 |
| vision encoder (excluded from a first port) | 460,730,096 |
| committed set as in docs/model.md section 3 (decoder + embedding + head) | 26,895,998,464 |
| Maverick committed set, from docs/model.md section 2 shape numbers | 400,711,352,320 |
| **ratio committed Qwen / Maverick** | **0.0671** (threshold <= 0.25) |
| per-token matrix MACs, Qwen (2-D decoder matrices + head; `per_token_matrix_macs_text`) | 25,621,954,560 |
| same incl. norm gains, A_log/dt_bias, conv1d taps (`per_token_macs_text_incl_gains_and_conv_taps`) | 25,624,600,064 |
| per-token matrix MACs, Maverick (top-1 routed + shared on MoE layers) | 16,149,708,800 |
| ratio per-token matrix MACs Qwen / Maverick | 1.587 (1.586527; not part of the threshold) |

## New operator families (from FEASIBILITY.md sections 2 and 4)

| model | new families with no counterpart in docs/model.md sections 5-8 |
|---|---|
| Qwen3.8-27B | **7** |
| GLM-5.3-Flash | 11 |
| DeepSeek-V4.1-Flash | 12 |

Condition (a) 7 < 11: holds, **judged under a post-registration counting rule, against unmerged
notes** (not a pre-registered test). Condition (b) 0.0671 <= 0.25: holds (pre-registered metric).
**PASS**, with that caveat on (a).

Counting rule: one family = one new kind of constraint or table in the integer relation; a new shape
of an existing gadget (e.g. a matmul of a new size, SwiGLU of a new width) is not a family. This rule
was written in FEASIBILITY.md section 4 in the results commit, after registration and after the
counting script; PREREG.md Amendment A1 records this. The GLM and DeepSeek pinned configs are in
`sources/` (SHA-256 as in ENV.json) and back the architecture facts; the family lists (11, 12) come
from the prior feasibility notes, which are not on main, so those counts are a judgement against
unmerged notes (Amendment A2). They are a lower bound (each of those families may split further),
which would only strengthen (a) if the notes hold.

## What this does not show

No proof was run. No model-support, speedup or fidelity claim is made. The prove-cost and host-memory figures in FEASIBILITY.md section 3 are estimates by
scaling the Maverick timed runs, labelled as such; the tok/s figure is a single-assumption point
estimate, not a bound, and the host-memory figure for a committed per-token state holds at batch 1
only (section 3 lists the assumptions). The integer approximation's fidelity to the BF16
model is not measured (no weights downloaded).
