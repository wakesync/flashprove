# RESULTS: 20261117-213-sable-walls

Issue #213. Desk note, no measurement: nothing was run, built or measured, so there is no metric, no
variance and no `research/results.yaml` entry. The deliverable is
[`research/prior-art/sable-integer-walls.md`](../../research/prior-art/sable-integer-walls.md).

## Against the registered acceptance threshold

COMPLETE. All five walls have every field of the PREREG filled (some fields say "not applicable"
or "not checked"), the differences table has every registered row, and every Sable statement carries
a paper section or a file:lines citation at commit `0bc6b549afef2f8eb9b8bc4c2f24d6e554dbaacb` and the
label "from public source, not verified by us" (stated once for the whole note and per section).

| wall | does Sable face it | carries over to FlashProve | recommendation |
|---|---|---|---|
| W1 MLP input above 2,047 | not in this form (no fixed norm-output class) | in principle (per-row 8-bit requantization, rsqrt-table norm, gain fused into weights; field and model-independent tables compatible) | none; a candidate arm for a future registered experiment, with Sable's own accuracy figures as a caution |
| W2 SiLU outside v1 domain | yes | yes for the field; table contents become per-model (our verifier already recomputes from a parameter) | none; two existing options named (scale with margin and abort, or clamp) |
| W3 both pre-norms above 2,047 | not in this form (same mechanism as W1) | as W1 | none |
| W4 head dimension 256 | no (all models dh 128; prover asserts it) | nothing to carry | none (negative) |
| W5 partial rotary | no (full-head RoPE) | nothing to carry | none (negative) |

Negative-result rule applied to W4 and W5: Sable does not face them, so the note recommends nothing
for them.

## Amendments to the PREREG

None. The note was placed at `research/prior-art/sable-integer-walls.md`; the PREREG asked only for a
note under `research/`, so this is not a deviation.

## Deviations from the lane brief (disclosed)

- The paper's HTML was downloaded once with `curl` from the known arXiv URL
  (`https://arxiv.org/html/2611.14083v1`, the same URL `WebFetch` returned) and converted to text
  locally to read sections 5, 6 and 11 in full; `WebFetch` truncates. No other URL was fetched.
- Besides the issue's sections 5, 6, 11.8 and 11.9, sections 1.2, 2 (one paragraph), 3.1, 3.6, 4, 7.5,
  7.6, 11.7 and 12 were read, only to fill the differences table (field, statement, proof size, zero
  knowledge, table commitment).
