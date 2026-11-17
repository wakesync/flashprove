# PREREG: 20261117-213-sable-walls

Issue: #213. Lane: sable213. Date (UTC): 2026-11-17T20:45Z. Base commit: 37576f43d3eeeca7fcfe7543b2e3e87add450b47 (origin/main when the branch was cut).

This is a desk note, not a measurement. Nothing is run, built or measured. This file registers the bounded deliverable before any content is written.

## Hypothesis

For each of the five walls our Qwen integer lowering hit, the public Sable prover (moonmath-ai/Sable at commit 0bc6b549afef, paper arXiv 2611.14083) either (a) faces the same wall and gets past it with a design choice that is compatible with FlashProve's Goldilocks field and fixed public tables, or (b) does not face it, or gets past it only with a choice FlashProve cannot make. The note decides (a) or (b) per wall from public text only.

## Metric

None numeric. Per wall, a filled record with these fields:

1. Our side: what the wall is, cited on main by path and line (starting from `docs/qwen-port.md`, section "Integer MLP and norm classes").
2. Does Sable's integer function face it (yes / no / not stated).
3. What Sable does, quoted or paraphrased, labelled "from public source, not verified by us".
4. Citation: paper section number, and repository file path at 0bc6b549afef with line range.
5. Compatible with FlashProve's Goldilocks field and fixed public tables: yes / no / unclear, with the reason.
6. What it would cost in our statement (what changes in what FlashProve proves or how big the tables are), qualitative, no new numbers.
7. Confirmed from source vs only quoted from the issue.

The five walls:

- W1. MLP input above the 2,047 class (in every measured layer).
- W2. SiLU inputs outside the v1 table domain.
- W3. Both pre-norms (attention and MLP RMSNorm inputs) above 2,047.
- W4. Head dimension 256.
- W5. Partial rotary (rotary applied to only part of each head).

## Acceptance threshold

The note is complete when all five walls have every field filled (a field may say "not stated in the sources read"), the differences table below is filled, and every Sable statement carries a section or file citation and the label "from public source, not verified by us".

Differences table, rows fixed now: what is proved (whole reply and stopping rule against one token), zero knowledge, field, lookup tables (fixed public vs committed or per-model), number formats (activation and matrix-input widths), proof size, prover hardware and time as reported, models covered, what is undefined or out of domain. Columns: FlashProve (cited on main) and Sable (cited, theirs).

Negative-result rule (from the issue): if Sable's formats only work because of choices FlashProve cannot make (for example a different field width or committed tables), the note says so per wall and recommends nothing for that wall.

## Kill criterion

Wall stop: the lane deadline is 2026-11-17T23:15:00Z. At that time the note is committed as it stands, marked PARTIAL, with the unfilled fields listed. Also stop (and say so) if a source cannot be read through the allowed routes (WebFetch of the arXiv page or `gh api` on the pinned commit); no other routes are used.

## Runs

None. Desk read only. Sources, and only these: paper sections 5, 6, 11.8 and 11.9; repository files `zk/model.py`, `zk/tables.py`, `zk/llm.py`, `scripts/fo_domain_scan.py` at 0bc6b549afef via the GitHub API. Nothing from Sable is cloned, built, installed, imported or run, and no Sable code is copied beyond short cited excerpts.

## Prior art

zkML provers that lower transformers to integers and prove them: EZKL, zkLLM, Jolt-based zkML, Expander; the related work of the Sable paper. The prior art under study here is Sable itself. FlashProve's own prior work is on main: `docs/qwen-port.md` and the operator studies under `research/operators/qwen_ops/`. What is new: a per-wall map from our measured walls to a public design, with field and table compatibility stated, before any further measurement is registered.

## Amendments

(empty at registration)
