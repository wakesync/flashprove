# Combined PR review

Integrated PRs #1, #3 and #2 without textual conflicts, preserving their commits and
all historical evidence. Upstream sources, LICENSE and NOTICE are unchanged from
`9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`.

## Findings fixed

1. The adapter accepted a numeric `next_token` for end<T but silently replaced it
   with `none`. This could mislead an API caller into believing that expectation was
   checked. Interior coverage now requires `None`; coverage reaching T requires a
   vocabulary integer (not bool/float). A new no-launch regression tests rejected
   expectations and the explicit interior `None` command mapping. This is an API
   contract fix, not evidence of an upstream false-proof acceptance.
2. The baseline README called the clipped `.y` mutation an after-request token and
   implied no rejection was a parsing error. Corrected: it is a zero sentinel when
   e<T, and format/statement rejections are distinct from proof rejection.

## Fresh bounded evidence

`python3 research/integration/record.py`, exit 0, source HEAD
`d76da729a064d32bcf8048d40ad3bafaf6e4c4e7`:

- Upstream source diff gate: exit 0.
- Adapter: 9 tests, exit 0, final `OK` (5.441 s).
- Stored exact baseline: exit 0, `outcome=verified` (2.141 s).
- Mutation audit: 41 calls, zero failures, exit 0 (32.875 s).
- Historical review integrity manifest: exit 0.

Commands, full sanitized output, environment and SHA256 hashes are in
`evidence/results.json` and `audit/`. The verifier was freshly built using
`bash verifier/build.sh`, exit 0, source digest
`93afdaf592393a54ebd17b681d1c03295eb883f0161ff0e6ab872a3b39939595`.
The build warns that another account may change a checkout ancestor. No permissions
were changed and no safeguard disabled. This is not a secured build attestation.

Exact fixture ID:
`79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183`.
It checks r=60 e=64, tokens 61..63 and next token 199, not reply termination.
Clipped fixture ID:
`8df714349b76202d6f302bb80b33d6d0798bd81d987b9e387038b7fd24c55ae6`.
It checks r=15 e=47, tokens 16..47 under clipped-gap, not an after-request token.
Complete commitment, coverage, proof-of-work and result lines are in audit logs
001/022 and evidence/2.log. 49 assumed commitment rounds and 32 work bits in 38
rounds, least-round 128.00/96.23 figures, are NOT security levels.

## Broad-suite status at review publication

The upstream full CPU command was started with confinement and eight job slots:
`./run_suite.py cpu /tmp/flashprove-integration-cpu-review --jobs 8`.
It is still running the sanitizer walk at this publication. No aggregate verdict
exists yet. Do not describe this as a full-suite pass. The coordinator must collect
its final exit, summary and screens, investigate failures and preserve receipts
before deciding to merge. No GPU, nvcc mode or long-mode Lean/model suite requested.

## Scope

Manifest equality and reviewer-pinned configs fail closed; the manifest digest is
application metadata, not part of Fiat-Shamir or checkpoint provenance. Trust in the
local Python/checker/binary/filesystem remains necessary. API users must inspect both
exit status and machine outcome. No weights, downloads of tensor shards, rentals,
new production model support, CUDA performance, hardware attestation, new Lean proof,
floating-point equivalence or privacy claim follows. Port experiments remain integer
reference comparisons with zero proof coverage. Merge is held pending broad-suite
results and coordinator review of these fixes.
