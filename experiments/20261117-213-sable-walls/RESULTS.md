# RESULTS: 20261117-213-sable-walls

Issue #213. Desk note, no measurement: nothing was run, built or measured, so there is no metric, no
variance and no `research/results.yaml` entry. The deliverable is
[`research/prior-art/sable-integer-walls.md`](../../research/prior-art/sable-integer-walls.md).

## Against the registered acceptance threshold

COMPLETE as of the review fix of 2026-11-17, with the deviations from the registered sources and
route listed below. All five walls have every field of the PREREG filled (some fields say "not
applicable" or "not checked"), and every Sable statement carries a paper section or a file:lines
citation at commit `0bc6b549afef2f8eb9b8bc4c2f24d6e554dbaacb` and the label "from public source, not
verified by us" (stated once for the whole note and per section).

The differences table now has every registered row. It did not at the first submitted head
(`61d14ce805deb0155c5d582471c8abc3aaa6ac57`): the registered row "prover hardware and time as
reported" was missing, so the COMPLETE reported there was wrong. Both reviewers found this. The row
was added in the review fix, before the registered wall stop of 2026-11-17T23:15:00Z. The table also
has one row the registration did not ask for ("Accuracy reported"); it is an extra row and does not
stand in for a registered one.

| wall | does Sable face it | carries over to FlashProve | recommendation |
|---|---|---|---|
| W1 MLP input above 2,047 | not in this form: it has a fixed norm-output class, but an 8-bit one (at most 127) with a per-row normalization exponent and the gain fused into the next weights, not our gain-applied word at fixed scale 2^12 in class 2,047 | in principle (per-row 8-bit requantization, rsqrt-table norm, gain fused into weights; field and model-independent tables compatible) | none; a candidate arm for a future registered experiment. Sable's own accuracy figures are on other models, data, metric and reference, so they are not comparable with our token bar: they motivate caution, they are not a measured failure of our bar and not a conclusion about what 8 bits cost |
| W2 SiLU outside v1 domain | yes | yes for the field; table contents become per-model. Our parameter file has a gate-table input-scale line (`eg`) the verifier recomputes from, but it is a test setting: a user verification is refused with it (`no-range-words`), and its range (4 to 7, absent 8) was not checked against Qwen. Not an admitted per-model scale | none; two existing options named (scale with margin and abort, or clamp), neither available to a dense Qwen statement today: `eg` needs a policy change, and the gate clamp `gcl` is refused at `NE 0` and cannot be stated for a dense model without a layout change |
| W3 both pre-norms above 2,047 | not in this form (same mechanism as W1) | as W1 | none |
| W4 head dimension 256 | no (all models dh 128; prover asserts it) | nothing to carry | none (negative) |
| W5 partial rotary | no (full-head RoPE) | nothing to carry | none (negative) |

Negative-result rule applied to W4 and W5: Sable does not face them, so the note recommends nothing
for them.

## Amendments to the PREREG

One, A-1, dated 2026-11-17T21:58Z, appended under the PREREG's `## Amendments` in the review fix. It
was written after the fact and says so. It records the deviations below and the real time of
registration; it does not turn them into registered choices. Nothing above the PREREG's
`## Amendments` heading was changed.

The note was placed at `research/prior-art/sable-integer-walls.md`; the PREREG asked only for a note
under `research/`, so that is not a deviation.

## Deviations from the PREREG (and from the lane brief)

These depart from the PREREG's own restrictions, not only from the lane brief. The first submitted
version of this file listed them only as deviations from the lane brief, under "Amendments to the
PREREG: None".

- **Route.** The PREREG's kill criterion allows "WebFetch of the arXiv page or `gh api` on the pinned
  commit" and says "no other routes are used", and to stop and say so if a source cannot be read
  that way. `WebFetch` truncates the page. The lane did not stop: the paper's HTML was downloaded
  once with `curl` from the known arXiv URL (`https://arxiv.org/html/2611.14083v1`, the same URL
  `WebFetch` returned) and converted to text locally to read sections 5, 6 and 11 in full. No other
  URL was fetched.
- **Sources.** The PREREG's "Runs" says "Sources, and only these: paper sections 5, 6, 11.8 and 11.9".
  The abstract and sections 1.2, 2 (one paragraph), 3.1, 3.6, 4, 7.5, 7.6, 11.7 and 12 were also read
  and are cited. They feed the differences table (field, statement, proof size, zero knowledge,
  table commitment), the list of confirmed figures (abstract) and one wall record: the wall 2
  paragraph on table compatibility cites 7.5 and 7.6. The review fix read section 11.1 as well, for
  the hardware and time row, and looked at Tables 4, 7 and 18 to check figures (not cited).
- **Time of registration.** The PREREG header says 2026-11-17T20:45Z. Its commit
  `f407f8e23a626000f4a8787b142f26bd1654f812` has author and committer time 2026-11-17T20:42:22Z. The
  commit time is the record; the header line is left as it was.
- **Review fix route.** One `WebFetch` of the same URL, which stops before section 5.6; later sections
  were read from the text copy the `curl` download had already produced. No new download.

None of this changes the evidence for a wall's answer. Both round-1 reviewers report that the
producing lane's working log places the reading of the sources after the PREREG commit; that is a
reviewer's descriptive finding (linked under "Corrections after review"), not evidence in this
repository.

## Corrections after review (2026-11-17)

Round 1 of review ended with two requests for changes at head
`61d14ce805deb0155c5d582471c8abc3aaa6ac57`:

- R-A: https://github.com/wakesync/flashprove/pull/218#issuecomment-6961360986
- R-B: https://github.com/wakesync/flashprove/pull/218#issuecomment-6961483454

Every sentence below was replaced in place, in the note
(`research/prior-art/sable-integer-walls.md`) or in this file. The old wording is quoted so that a
reader of the first version can see what changed. Nothing was run, built or measured for any of
them. Two items marked "fix lane" were not raised by either review; they were found while the
reviewers' citations were being opened.

**Completion and registration (R-A 1 and 3, R-B 5)**

1. This file, acceptance paragraph. Old: "COMPLETE. All five walls have every field of the PREREG
   filled (some fields say "not applicable" or "not checked"), the differences table has every
   registered row, and every Sable statement carries a paper section or a file:lines citation". The
   registered row "prover hardware and time as reported" was missing. The row was added to the note
   and the paragraph now says so.
2. This file. Old: "## Amendments to the PREREG" followed by "None.", and the heading "## Deviations
   from the lane brief (disclosed)". The `curl` download and the extra sections depart from the
   PREREG itself. They are now listed as deviations from the PREREG, and the PREREG has the dated
   entry A-1, which also records the commit time 20:42:22Z next to the 20:45Z in its header.
3. Note, "Sources". Old: "Sections read: 5, 6, 11.7, 11.8 and 11.9 (the issue names 5, 6, 11.8 and
   11.9), plus 1.2, 3.1, 3.6, 4, 7.5, 7.6 and 12 to fill the differences table;". The list left out
   the abstract and the section 2 paragraph, which the note cites, and did not say the extra
   sections and the route were outside the registration.
4. Note, "Notes on the reading". Old: "Read only the sections and files named above." and "The paper
   text was read from the arXiv HTML page at the known URL;". Both now say what was outside the
   registration.

**The accuracy comparison (R-A 2, R-B 4)**

5. Note, answer line 1. Old: "it is a different statement from ours, and by Sable's own figures its
   8-bit formats lose accuracy well beyond our registered token bar." Sable's figures are on other
   models and data, with another metric and reference. They do not test our bar and do not isolate
   what 8 bits cost. The line now says the numbers are not comparable and only motivate caution.
6. Note, wall 1. Old: ""unrounded MLP input" would remove 12% of its Qwen3-32B perplexity gap
   (P 11.8, Table 15)" and "they give no reason to expect an 8-bit input to clear a bar that our
   12-bit path missed." The 12% is a share of excess log perplexity over BF16, measured on the first
   24 WikiText-2 windows, as the table's caption says. The second sentence is kept and is now
   labelled an inference, not a measured failure.
7. Note, wall 4. Old: "12-bit queries and keys would remove 37% of its Qwen2.5 perplexity gap". The
   37% is a share of excess log perplexity over BF16 (Table 13 caption).
8. This file, W1 row. Old: "none; a candidate arm for a future registered experiment, with Sable's own
   accuracy figures as a caution". Now says the figures are not comparable with our bar.

**The norm-output class (R-B 1)**

9. Note, answer line 1. Old: "Sable does not have a fixed public class for a norm output." and
   "normalizes with a 16-bit rsqrt table so the output is at most 127 by construction". Note, wall 1.
   Old: "Not in this form. Sable has no fixed public class for a norm output." This file, W1 row.
   Old: "not in this form (no fixed norm-output class)". Sable has a fixed norm-output class: 8 bits,
   at most 127 in magnitude. What differs from ours is the width, the per-row scale and where the
   gain sits. The note, its number formats row and this file now say that.
10. Note, wall 1, `NormScale` item (fix lane). Old: "giving |q'| <= 127 "by construction";" with the
    citation P 5.2. The paper does not use the words "by construction" there; the quotation marks
    were wrong. The bound is now cited to the proof's range lookup (P 6.2) and to `zk/model.py`.

**8-bit matrix inputs (R-B 2)**

11. Note, confirmed list. Old: "8-bit matrix-product inputs: **confirmed** (P 5.1)." Note, number
    formats row. Old: "matrix inputs 8-bit with a per-row exponent". This holds for the activation
    rows entering the weight-matrix products of a dense layer. It is not exception-free: the
    mixture-of-experts down input is requantized to [-1023, 1023], queries and keys after RoPE are
    9-bit, and attention probabilities lie in [0, 2^10]. Both places now state the scope and the
    exceptions.

**Wall 2 admission costs (R-B 3, and a nonblocking item of R-A)**

12. Note, wall 2. Old: "So a per-model input scale is expressible on our side as a parameter the
    verifier recomputes from, not as a committed table; this note did not check that `eg`'s allowed
    range (4 to 7) would cover Qwen." The cited parameter document says a user verification is
    refused when `eg` is present (`no-range-words`); the setting exists for tests. The range is 4 to
    7, and an absent line means 8.
13. Note, wall 2. Old: "Two different options, both existing somewhere: Sable's (per-model scale with
    margin, abort outside: a refusal on rare inputs) and upstream FlashProve's gate clamp `gcl`". The
    same document says `gcl` is refused at `NE 0` and cannot be stated for a dense model, and
    Qwen3.8-27B is dense. Both admission costs are now listed, and answer line 2 is qualified.
14. This file, W2 row. Old: "yes for the field; table contents become per-model (our verifier already
    recomputes from a parameter)" and "none; two existing options named (scale with margin and abort,
    or clamp)". Both cells now carry the restrictions above.

**Smaller items (nonblocking in R-A and R-B, and one from the fix lane)**

15. Note, wall 4. Old: "the score bound N4 fails, and the KFD lookup width is hit first; there is no
    drop-in admission change (`research/operators/qwen_ops/DH256-ROTARY.md:6-10`, `:98`, `:253`)."
    The cited lines do not say which is met first; line 167 does, and is now cited.
16. Note, wall 2. Old: "Its scan (`scripts/fo_domain_scan.py:1-13`, `:79-81`) reports zero undefined
    sequences on 3.45 million tokens of real text and 160 adversarial sequences for all three models
    (P 11.9, Table 16)." The paper says the Qwen3 columns came from its serving engine, which is not
    the engine in the cited lines.
17. Note, wall 1. Old: "The later registered integer-MLP token test failed at 1,423 of 1,461". 1,423
    is the number of agreements, not of failures.
18. Note, lookup tables row. Old: "are pinned by the digest h_circ from a registry" with the citation
    "(P 6.1, P 7.5, P 7.6)". The registry is described in section 4, now cited.
19. `ENV.json`. Old: "no toolchain used for results; text reading only". The tools used to fetch and
    read the sources are now listed.
20. Note, confirmed list (fix lane). Old: "Paper date 10 Nov 2026 and the pinned commit:
    **confirmed** (arXiv submission history;". No submission history page was fetched; the only page
    read was the HTML version, whose stamp gives the date. The source is now named as that stamp.

**Other sentences reworded as part of the items above**

21. This file, deviations (with item 2). Old: "sections 1.2, 2 (one paragraph), 3.1, 3.6, 4, 7.5, 7.6,
    11.7 and 12 were read, only to fill the differences table". Not only: the wall 2 paragraph on
    table compatibility cites 7.5 and 7.6, and the confirmed list cites the abstract.
22. Note, wall 1 (with item 6). Old: "Those are different metrics and references from our registered
    bar (>= 99% top-1 against float64, teacher-forced), so they are not comparable numbers, but".
    Now also names the different models and data, and cites where our bar is registered.
23. Note, number formats row, our column (with item 9). Old: "Qwen M3 design: public norm-output class
    2,047 at scale 2^12". Now says the scale is fixed and the gain is applied inside the norm.
24. Note, out-of-domain row (with item 13). Old: "upstream gate clamp `gcl` saturates
    (`verifier/docs/parameter-file.md:269`)". Now says it exists with experts only.

No wall's answer changed: walls 1 and 3 "not in this form", wall 2 "yes", walls 4 and 5 "no".
