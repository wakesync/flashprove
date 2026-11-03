# Independent review of CPU baseline PR #1

Reviewed PR head: `848815f4cdb0b6dda2b25e9cd6ec4ffb2f03777b`.
Upstream source: `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`.
Review date: 2026-11-03. Separate clone, fresh verifier build and toy build, same CPU host class as the initial reproduction. This is independent execution and inspection, not independent hardware or a third-party security audit.

## Verdict

**PASS for the narrowly stated synthetic CPU baseline; not evidence of model support, GPU performance, weight privacy or implementation soundness.** No protocol source was changed. Original evidence remains untouched. Upstream LICENSE, NOTICE and attribution remain unchanged.

The original runner was rerun unmodified into `independent-original/`, exit 0. The hardened runner was rerun into `independent-hardened/`, exit 0. Exact argv, wall times, exits, compiler/OS/CPU metadata and full accepting output live in those directories. Both stored proof manifest checks passed. The original build took 85.617 seconds, exact acceptance 1.619 seconds, clipped-gap acceptance 1.569 seconds, negative tables 13.257 and 12.609 seconds, and toy build/generation/checks 52.504 seconds. These are single observations, not benchmark measurements.

## Findings and repairs

1. **Pin check did not check the executed source.** `git rev-parse PIN` only establishes that an object exists. The reviewed checkout really did match upstream outside `research/`, but future edited checkouts could have been misleadingly called pinned. The runner now requires `git diff --exit-code PIN -- . ':(exclude)research'`, records HEAD and working-tree status, and hashes the built verifier. This checks tracked upstream files, not host integrity or untracked include-path injection; the build warning still matters.
2. **Incomplete artifact provenance.** The original run checked stored SHA256SUMS but did not hash its new toy proofs or binary, record the checkout revision, or retain the toy rejection tables. The runner now retains generated toy artifact hashes and both 27-row rejection tables. The toy program really runs **54 altered copies/calls**, plus the shell's extra middle-byte mutation. Six honest generated library proofs are checked. These are not model inference proofs.
3. **The 20 negative cases are real, but do not establish 20 independent cryptographic properties.** Source inspection confirms the upstream harness requires both exit 1 and the exact expected `NO:` line, first checks an honest control, changes bytes in fresh copies, and selects the altered file paths. The original runner only retained the table summary, not each invocation's log. `audit_cases.py` reruns all 20 with individual logs, commands, times and changed-file SHA256 values, plus new range, header, length, vocabulary and trusted-policy cases.
4. **Clipped-gap output-token wording needs care.** Its `example.y` is a required zero sentinel because `e < T`. Flipping it tests `statement-range`, not binding of an actual after-request generated token. Exact-match's `y` mutation reaches `reply-differs`. Likewise reducing exact-match `e` alone fails the sentinel precondition. An additional test changes `e` and sets `y=0`, reaching `proof-refused` instead. Do not count precondition failures as cryptographic corruption detection.
5. **No source-level vulnerability found in this bounded inspection.** Header, empty-file, policy and token-range cases intentionally test early rejection. They do not test a malicious prover. Root rejection, safe temporary-path checks and build warnings were not bypassed.

## What each original table checks

Each fixture runs these ten mutations (20 calls total):

| Mutation | Exact-match final line | Clipped-gap final line | Actual scope |
|---|---|---|---|
| Proof middle bit | `NO: proof-refused` | same | One sampled proof byte, not every field |
| Proof last byte removed | `NO: proof-refused` | same | One truncation point |
| Proof trailing zero | `NO: proof-refused` | same | Exact-consumption check |
| Key middle bit | `NO: key-refused` | same | One key mutation |
| Leaf middle bit | `NO: entry-refused` | same | One leaf mutation |
| Prompt token 0 low bit | `NO: proof-refused` | same | Request binding on these fixtures |
| First checked reply low bit | `NO: proof-refused` | same | Checked request-token binding |
| `example.y` low bit | `NO: reply-differs` | `NO: statement-range` | Actual output vs required sentinel |
| KL scale middle bit | `NO: model-statement` | same | Model/config commitment consistency |
| ID final hex digit | `NO: model-statement` | same | Caller-supplied ID consistency |

Both accepted IDs, `covered:`, `commitment:`, `proof of work:` and `result-v1` are in the full `verify-*.log` files. Exact-match covers `r=60 e=64 T=64 tokens=61..63 y=yes`; clipped-gap covers `r=15 e=47 T=64 tokens=16..47 y=no`. Accounting bit counts are not security levels.

## New tests and reproduction

From a non-root Linux checkout, with g++ 13+, GNU make, Python 3, bash and coreutils:

```sh
python3 research/reproduction/run.py research/reproduction/my-baseline
python3 research/reproduction/audit_cases.py research/reproduction/my-audit
```

Each output directory must be new. No downloads, package installation, GPU, rental or full CPU suite is involved. The audit uses the already-built binary, so run the baseline first. Audit calls have a 120-second per-call timeout. Inputs are fixed, not randomized. `audit-probe/` preserves the initial exploratory run: all corruptions were rejected, but 11 *expected reason strings* were initially incorrect. The probe exited 1. Expected reasons were reconciled against `vf_input_files.h`, `cp_verify.cpp` and observed output, not silently treated as passes. Final `audit-final/` uses explicit exact verdict assertions.

The audit has 41 calls: two honest controls, the original 20 rejections, 16 new one-input corruptions (eight per fixture), two wrong trusted-policy calls, and one exact-match range-end mutation with a matching zero sentinel. All 39 negative calls must exit 1 with the expected exact final line. New cases are range start/end changes, empty proof/key/leaf, proof header bit, token 512 outside vocabulary, inverted range, wrong CLI policy and the joint end/sentinel mutation. Empty leaf is `entry-refused`; empty proof/key and changed header are format checks; token and range errors are statement checks; wrong policy is `NO: policy`. Only the valid changed-range cases reach `proof-refused`.

Toy seeds are source constants, not secret randomness: matrix `TestCoins(3)`, commitment/index coins 24 and 25, key/leaf proof coins 44 and 45, batch seeds 51 and 62 with first/second-chain offsets `100+n` and `200+n` for `n=0..2`. See `blocks/frame/handover_proof.cpp`. The fixture policy has `seed_lo=31`, `seed_hi=0`; this is not a claim to reconstruct the stored fixtures' original generation process. No random fuzzing was performed.

## Remaining limits

The existing permissive-ancestor build warning recurred, with sanitized path only. No permissions were changed. Thus these are not secured build attestations. The hardened runner excludes research-only modifications from the upstream source check and records those modifications separately. Published logs replace checkout/home/work paths; hashes of raw toy logs may differ across paths even when proof bytes match. Generated proof files stay in the private temporary work directory; their hashes are published, not large binaries.

Stored proofs are upstream fixtures, not proofs made by the released CUDA prover. The C++ verifier is not the formally proved Lean verifier. No new Lean theorem, malicious-witness synthesis, floating-point equivalence, checkpoint provenance, production architecture support, TEE attestation or H100 result follows from these checks. GPU replication remains budget-gated; real-model proof generation and broader suite coverage remain separate work.
