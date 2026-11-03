# CPU reproduction baseline

Upstream: [anthropics/FlashProve](https://github.com/anthropics/FlashProve), pinned at `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c` (initial public release, 0.16.0-rc.26 commit title). This is an independent fork's reproduction, not an upstream endorsement. Upstream sources, LICENSE, NOTICE and third-party notices are unchanged.

## Independent review

[The independent review](REVIEW.md) reproduces this PR in a separate clone, audits the meaning of every original negative case, adds 19 negative cases, and retains full per-call logs, source/binary/proof hashes and exact commands. The original evidence below is unchanged. Fresh receipts are in `independent-original/`, `independent-hardened/`, `audit-final/` and `RECEIPTS.json`; `audit-probe/` retains exploratory expected-reason mismatches. Verify the new evidence with `sha256sum -c research/reproduction/REVIEW-SHA256SUMS` from the repository root.

## Results

All selected checks completed. These are **synthetic examples**, not real model inference or a reproduction of the H100 throughput claim.

| Check | Exit | Full final verdict / summary | Wall seconds |
|---|---:|---|---:|
| Build | 0 | `THE VERIFIER IS BUILT: <REPO>/bin/cp_verify` | 80.786 |
| Stored exact-match | 0 | `YES` | 1.572 |
| Exact-match negative table | 0 | `10 altered sets: all rejected` | 13.185 |
| Stored clipped-gap | 0 | `WITHIN LIMITS: clipped-gap C=9244130 theta=323343 cap=1 s=16 sh=8` | 1.571 |
| Clipped-gap negative table | 0 | `10 altered sets: all rejected` | 12.140 |
| Toy build + generation + checks | 0 | `<WORK>/look/bent.proof: 577340 bytes: an opening does not lead to its root` | 50.547 |

Toy honest judge: exit **0**, last line `./honest.proof: 577340 bytes: ACCEPTED`.
Toy altered judge: exit **1**, last line `./bent.proof: 577340 bytes: an opening does not lead to its root`.
The script's third-last line was exactly:
`AS EXPECTED: the honest copy was accepted, and the copy with one bit flipped was rejected. The last line of each check:`
Both stored example SHA256SUMS checks passed.

### Accepted claims

- Exact-match ID: `79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183`. `r=60 e=64 T=64 tokens=61..63 y=yes`: three in-request reply tokens plus the token after the request.
- Clipped-gap ID: `8df714349b76202d6f302bb80b33d6d0798bd81d987b9e387038b7fd24c55ae6`. `r=15 e=47 T=64 tokens=16..47 y=no`, policy `clipped-gap,9244130,323343,1,16,8`. `WITHIN LIMITS` is policy compliance, not exact-match generation.
- Both acceptances print 49 commitment-assumed rounds, proof of work up to 32 bits in 38 rounds, least round 128.00 bits with work and 96.23 without. **These are not security levels.**
- Source build digest: `93afdaf592393a54ebd17b681d1c03295eb883f0161ff0e6ab872a3b39939595`.

Complete `covered:`, `commitment:`, `proof of work:` and `result-v1` lines are in [the exact-match log](evidence/verify-accepted-proof.log) and [the clipped-gap log](evidence/verify-accepted-proof-clipped-gap.log).
IDs were taken from stored fixtures, the explicitly permitted exception for examples, not an acceptable trust source for real verification.

### Negative cases

Both upstream ten-case tables passed with every modified set exiting **1**, a rejection rather than a no-verdict exit: proof bit flip, truncation, trailing byte, key bit flip, leaf bit flip, prompt token, checked reply token, `.y` word, quantization scale and commitment ID. Some rejections are early format or statement checks, not cryptographic proof rejection. Exact per-case final lines are retained in `evidence/negative-*.log`. In the clipped-gap example e<T, so `.y` is a mandatory zero sentinel, NOT an after-request generated token; its mutation gives `NO: statement-range`. Only the exact-match example reaches T and checks the after-request token, giving `NO: reply-differs`. These are mutations of honest fixtures, not malicious proof synthesis or a soundness audit. The toy also runs its upstream altered-proof checks.

## Build warning

The build succeeded but printed this warning (only its local path is redacted):

> build.sh: note: another account may be able to change <CHECKOUT_ANCESTOR> (its group or others can write in it, and it has no sticky bit), under which this checkout lies, and so could change what is built, and this script itself; for a build that no other account can touch, keep the checkout below directories that only you can write in; if <CHECKOUT_ANCESTOR> is yours, close it with chmod go-w

No permission was changed, safeguard bypassed, or source patched. The upstream default build explicitly allows this case with a warning. This reduces confidence in isolation from other local accounts: this run is not an independently secured build attestation. Future isolated reruns should start in a checkout below private directories. Toy and mutation outputs used a fresh private temporary directory. The README describes a silent build; this version also prints the build digest and compilation notice before compiling.

## Reproduce and inspect

Prerequisites already present: non-root Linux account, bash, g++ 13+, make, Python 3 and GNU coreutils. No dependencies installed, no sudo/root, no GPU access or spending. Environment: Ubuntu 24.04.4 LTS, x86-64, Linux 6.8.0-100-generic, AMD EPYC-Rome, g++ 13.3.0, Python 3.12.3, GNU Make 4.3.
Build concurrency is bounded by `MAKEFLAGS=-j4`; the verifier build is one compiler invocation. `OMP_NUM_THREADS=4` is set, but does not promise to bound the verifier's own worker threads; 16 logical CPUs were available. Timings are single observations on a shared host, not benchmark distributions.

From this branch's repository root:

```sh
python3 research/reproduction/run.py research/reproduction/evidence-rerun
```

The output directory must not exist. The runner rebuilds `bin/cp_verify`, sequentially runs selected upstream commands, records exits and wall times, and stops on an unexpected top-level exit. Check stored-proof verdicts and toy judge statuses as well as script exit codes.
`evidence/results.json` records exact argv rendered as shell commands, working directories, exits and full final lines. `<REPO>` is the checkout and `<WORK>` the fresh `tempfile.mkdtemp` directory, preserved after the run. Local path prefixes alone are sanitized before publication.
The executed top-level command was `python3 research/reproduction/run.py` (exit 0). A subsequent sanitization-only refinement replaces ancestor paths with the generic placeholder above.
The upstream negative script prints per-case verdicts but does not retain full internal verifier output; its unabridged summary is saved. Full outputs are saved for both direct accepting calls and toy judges. No full CPU suite was run: it rebuilds binaries and is a separate broader lane.

## Limits

No new model proof was made by the CUDA prover. Stored proofs were supplied upstream; upstream docs say those files came from other programs, not the released prover. The toy generates library proofs for a synthetic matrix, not transformer inference; its randomness is not intended to hide weights.
This run does not establish weight privacy, full-size performance, real Maverick equivalence, or implementation soundness. The Lean soundness theorem concerns its Lean verifier, at its stated full-size/exact-match scope, not this C++ binary or these small fixtures. See [known limits](../../guide/known-limits.md), [what is proved](../../guide/what-is-proved.md) and [weight hiding](../../guide/weight-hiding.md).
