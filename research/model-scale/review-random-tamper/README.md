# Random-site hostile provers (review-pr42b harness), committed as evidence

These files are the review-only harness and raw output from the PR #42 review at head `b610ae2f`
(review comment on PR #42, "Random-site hostile provers"). They were not pushed with that review.
They are committed here unchanged so that the results.yaml metric `random_site_attacks_rejected`
has a file receipt. Nothing was rerun for this commit.

- `tamper.cpp`: includes `../run.cpp` (same loader and hostile `prove()`), adds random-site attacks.
  Built with the `ENV.json` flags, run single-threaded on one pinned core.
- `tamper_drive.py`: driver. Generates 4 small fixtures (seed 7) with `gen.py`, runs the honest
  prover, the tamper binary, and two fixture-corruption checks. Its `ms` path points at the review
  clone's `research/model-scale/` (sibling checkout at `b610ae2f`), not at this directory.
- `tamper-results.json`, `tamper-n100.log`: N = 100 attacks per kind per point.
- `tamper-results-n20.json`: an earlier N = 20 pass.

Points: d4 T4 4-bit (L=12), d8 T2 8-bit (L=13), d8 T1 12-bit (L=13), d16 T1 12-bit (L=15).
Attack kinds per iteration: (a) complete hostile proof over a table with one random used column's
a or b cell shifted (c recomputed, product relation still holds); (b) honest proof against one
random affine target +1; (c) honest proof against one random wire redirected; (d) honest proof with
the output coordinate moved. Moves of (d) that land on an equal value are skipped, so a point can
count fewer than 400.

Result (sum of `rejected` and `accepted_*` over the 4 points in `tamper-results.json`):
1,564 rejected (398 + 366 + 400 + 400), 0 accepted. N = 20 pass: 315 rejected, 0 accepted.
Fixture corruption (a0 bit, mid c-cell bit) is refused by the host reference check before proving.

Scope: measured, unreplicated, small points only (L = 12..15), toy target 10 bits. Evidence that the
constraints bind at random positions at small sizes. Not a soundness argument, and it does not
cover d = 128.
