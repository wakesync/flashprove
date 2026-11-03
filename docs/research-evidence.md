# Fork evidence ledger

Snapshot: 2026-11-03. This ledger distinguishes public reproducibility evidence from summarized local research receipts. It does not promote open PRs into merged functionality. Documentation publication ran no builds, suites or GPU experiments.

## Public CPU baseline

[PR #1](https://github.com/wakesync/flashprove/pull/1), `848815f4cdb0b6dda2b25e9cd6ec4ffb2f03777b`, adds the original CPU baseline. [PR #3](https://github.com/wakesync/flashprove/pull/3), `bf66eecdac3f5329d2f8e53867c867318720d1dd`, independently reproduces and strengthens it.

At the latter commit, see [review](https://github.com/wakesync/flashprove/blob/bf66eecdac3f5329d2f8e53867c867318720d1dd/research/reproduction/REVIEW.md), [receipt index](https://github.com/wakesync/flashprove/blob/bf66eecdac3f5329d2f8e53867c867318720d1dd/research/reproduction/RECEIPTS.json) and [hash manifest](https://github.com/wakesync/flashprove/blob/bf66eecdac3f5329d2f8e53867c867318720d1dd/research/reproduction/REVIEW-SHA256SUMS).

Reported independent executions:

- `python3 research/reproduction/run.py research/reproduction/independent-hardened`: exit 0; fresh verifier build, exact fixture `YES`, clipped fixture `WITHIN LIMITS`, two ten-case rejection tables, six honest toy library proofs and 54 internal altered calls/copies rejected.
- `python3 research/reproduction/audit_cases.py research/reproduction/audit-final`: exit 0; 41 calls, zero assertion failures (two controls, original 20 negatives, 19 additional negatives). Earlier probe exit 1 due to incorrect expected reason strings is retained, not erased.
- `sha256sum -c research/reproduction/REVIEW-SHA256SUMS`: exit 0 in the baseline lane.
- Exact fixture: `r=60 e=64 T=64 tokens=61..63 y=yes`. Clipped fixture: `r=15 e=47 T=64 tokens=16..47 y=no`. These are synthetic fixtures, not real-checkpoint generation.

This is independent rerunning on the same host class, not independent hardware or a second cryptographic verifier. Mutation tests include early parser/statement/policy rejection; not all are malicious-witness proof synthesis. No new Lean theorem, GPU inference or full CPU-suite pass follows.

## Extension and integration

[PR #2](https://github.com/wakesync/flashprove/pull/2), `ffc55fa00839a3758433f93fd6c4aef7f4db92bc`: [extension documentation](https://github.com/wakesync/flashprove/tree/ffc55fa00839a3758433f93fd6c4aef7f4db92bc/research/extensions) and [recorded checks](https://github.com/wakesync/flashprove/blob/ffc55fa00839a3758433f93fd6c4aef7f4db92bc/research/extensions/evidence/results.json). Eight harness tests and the admitted synthetic fixture passed in that lane. Unsupported architectures, policies, shapes, state and metadata fail closed. The manifest digest is application metadata, not a new Fiat-Shamir binding or checkpoint provenance proof.

[PR #4](https://github.com/wakesync/flashprove/pull/4), `133da749937115883c95edfc4b6e372c16209449`, integrates reviewed fixture/output-bound fixes. The single confined full CPU run has now completed with durable **aggregate exit 77**, not exit 0: **89 passed, 2 partial, 0 failed, 1 not run**, across 92 selected rows. Zero status-3 rows or alarm lines were reported. Duration was 4370.89 seconds. The runner table contains 173 rows; CPU mode explicitly excluded 13 GPU-dependent rows. These counts do not claim coverage of every table row.

The [CPU owner's public closeout](https://github.com/wakesync/flashprove/pull/4#issuecomment-6613832649) and [issue evidence anchor](https://github.com/wakesync/flashprove/issues/5#issuecomment-6613833083) summarize the retained aggregate, row exits and 92 original screens. The newly completed raw full-run receipts are not committed at the tested SHA; those public summaries are not a complete independently reproducible artifact bundle. Independent source/receipt review found no blocking defect in the scoped repairs, but explicitly retained HOLD.

Remaining coverage gaps:

- Clang build not run (exit 77).
- Weight sums partial: 13 Python substeps skipped because the required numpy / gguf-py 0.19.0 combination was unavailable.
- Confinement partial: 29 checks as expected, but actual signal confinement, second-level kernel-answer-5 and root-only mount/proc/account-file cases were not established. Stand-ins do not establish real root coverage.
- Integration units: 1961 passed, three unidentified pytest skips and 20 root-only deselections. Those omissions are not passes.
- Kernel ordinary-signal confinement and a group-writable source ancestor remain disclosed limitations. CPU mode establishes no GPU/long-mode, real Lean, TEE or production-model end-to-end coverage.

The completed full run includes 68 middleware tests and 346 expected fake-Lean launcher calls. Prior focused aggregate exit 0, nine adapter tests and the 41-call mutation audit remain prior evidence, not new coordinator executions. An earlier pre-V2 full run lacked a recoverable aggregate and had failing outputs; it has not been relabeled. **PR #4 remains held under the full-pass gate.** Missing aggregate is no longer the blocker; actual scoped coverage closure or an explicit authorized bounded-scope gate decision is required. Do not rerun the full suite merely to recover evidence, merge stacked PRs #1-3 separately to evade this gate, or report real Lean validation.

## Operator experiments: narrow review, publication still a gate

These exact-commit results were read from builder and independent-review receipts, not rerun by the documentation lane. Full source and raw review artifacts are not linked as public reproducibility bundles here, so they remain provisional for public reproduction:

- Public-coordinate prototype `65ada28ab3303a5daa1117ece5ed10759040b416`: independent focused compile/test exit 0; 7,776-byte honest proof and three complete malicious proofs rejected. Review evidence JSON SHA-256: `19031eb8bfbf2cc8fe226af5efaa35ed0ad7b356e1ee21daeff3de69963eab5f`.
- Same-oracle cell equalities `ba3c98459c2aae732fedeb9742db4deb5fcedfa8`, parent above: independent review narrowly approved its supported constructor composition, with no merge or model approval. Focused aggregate exit 0; 7,936-byte honest proof, two complete malicious one-edge proofs rejected, topology/public mutations and V3 regression checked. Review evidence JSON SHA-256: `f861e1fb92f6cfb052d71785808276e8d02dfc4aa4e6c0368847cc69d48c64d0`.
- Reviewer boundary proofs succeeded at lengths 16/32 and counts 1/64. Length 8 was refused by the unchanged sizing planner; the initial reviewer aggregate exit 1 is retained. Thirteen invalid constructors aborted as expected. Those trusted-configuration guards are not graceful untrusted-input handling.

A hash identifies a receipt but does not make unavailable contents independently reproducible. Publication of source plus sanitized raw evidence is required before treating this ledger as sufficient reproduction material. These experiments do not prove affine/range/Boolean/top-k/permutation/normalization relations, a router, an architecture, hiding or a new security bound. Mutable trusted constructors, incomplete adversarial coverage and absence of an independent cryptographic verifier remain limitations.

## GPU, fidelity, ports and attestation

No completed fresh GPU commit/prove/verify receipt was available for this snapshot. A prior local image build and negative no-GPU startup test do not establish GPU runtime correctness, benchmark performance or current allocation state. No fork real-checkpoint fidelity benchmark, GLM/DeepSeek model proof, long-context proof or real hardware TEE attestation is claimed.

Pinned source inspection found model metadata and implementation descriptions, not verified tensor shards or tokenizer artifacts:

- [GLM-5.3-Flash](https://huggingface.co/zai-org/GLM-5.3-Flash/tree/46a050bec13002ad29ee795c16e61cf4fa3c4a9c), reference [Transformers implementation](https://github.com/huggingface/transformers/blob/f90e93c4f83974f634860e246cdfd2c68666d605/src/transformers/models/glm5_next/modeling_glm5_next.py). Reference code is not established equivalent to publisher fused serving kernels.
- [DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/tree/314113f8a7dadb388215396ba5fbee2c610a04d6).
- [Separately named GLM BF16 artifact](https://huggingface.co/zai-org/GLM-5.3-Flash-BF16/tree/f9fed3bbc82291073373d67452e9f25317ef7577), not a silent replacement for the requested FP8 release.

Small reference-only integer experiments compared 300 staged-rounding recurrence cases, 300 top-k cases and 13 state segment boundaries. Agreement between reference evaluators is not floating-point fidelity or cryptographic proof coverage. These results are motivation for [operator feasibility](https://github.com/wakesync/flashprove/issues/11), not support declarations.

## Source accuracy check for this publication

The [roadmap](research-roadmap.md#what-the-upstream-numbers-actually-say) quotes the pinned upstream performance/model/limits documents. `guide/performance.md` at `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c` has SHA-256 `d32577a48991cd972de98eb74a8fb8daeaa03acfac5599f12aeb004dd043aede`. Its prefill denominators, eight-GPU FP8 baseline, unavailable historical records and other-programs fidelity caveats are preserved. No cited upstream performance or divergence figure is labeled reproduced by this fork.
