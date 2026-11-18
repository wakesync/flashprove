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

- **A-1 (2026-11-17T21:58Z, review fix of PR #218. Written after the fact: the note, RESULTS.md and both round-1 reviews already existed when this entry was written. It records how the work departed from this registration. It does not make those departures registered, and nothing above this section is changed.)**
  - **Time of registration.** The header above says 2026-11-17T20:45Z. The commit that contains this file, `f407f8e23a626000f4a8787b142f26bd1654f812`, has author time and committer time 2026-11-17T20:42:22Z. The header time is about three minutes after the commit that carries it, so it is not the time of writing; the commit time is the record. The header line is left as it was.
  - **Sources (deviation from "Runs").** "Runs" says "Sources, and only these: paper sections 5, 6, 11.8 and 11.9". The note also read and cites the abstract and sections 1.2, 2 (the "Concurrent work" paragraph), 3.1, 3.6, 4, 7.5, 7.6, 11.7 and 12. They feed the differences table, the list of confirmed figures (abstract) and one wall record: the wall 2 paragraph on table compatibility cites 7.5 and 7.6. This is a departure from this registration's own source restriction, not only from the lane brief.
  - **Route (deviation from "Kill criterion").** "Kill criterion" allows "WebFetch of the arXiv page or `gh api` on the pinned commit" and says "no other routes are used", and to stop and say so if a source cannot be read that way. WebFetch returned a truncated page. The lane did not stop: it downloaded the paper's HTML once with `curl` from `https://arxiv.org/html/2611.14083v1` and converted it to text locally. This is a departure from this registration's own route restriction. The four repository files were read through `gh api` as registered.
  - **Order.** Both round-1 reviewers report that the producing lane's working log places the reading of the sources after the registration commit; the second says it did not audit that log independently (https://github.com/wakesync/flashprove/pull/218#issuecomment-6961360986, https://github.com/wakesync/flashprove/pull/218#issuecomment-6961483454). That is a reviewer's descriptive finding, not evidence in this repository.
  - **Missing registered row.** At the first submitted head `61d14ce805deb0155c5d582471c8abc3aaa6ac57` the differences table had no row "prover hardware and time as reported", and RESULTS.md reported COMPLETE. The review fix added the row before the wall stop of 2026-11-17T23:15:00Z. To fill it, section 11.1 was read and is cited, which is one more section outside the registered list. Tables 4 and 7 (sections 11.2 and 11.3) and Table 18 (appendix A.6) were looked at to check figures and are not cited.
  - **Route of the review fix.** One WebFetch of the same arXiv URL (a registered route); it stops before section 5.6. Later sections were read from the text copy that the `curl` download above had already produced. No new download was made, and the four repository files were read again through `gh api` at the pinned commit.
  - **Edit of this entry.** The "Order" and "Missing registered row" items above were reworded at 2026-11-17T22:05Z, in the same review fix and before it was pushed: the first wording said neither reviewer audited the log, which the first reviewer's comment does not say, and it did not name the tables looked at.
  - **What this does not change.** No wall's yes / no answer, no hypothesis, metric, threshold or kill criterion. The statements corrected in the review fix are listed in RESULTS.md, "Corrections after review".
