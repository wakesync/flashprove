# Unprivileged CPU profile and bounded accounting experiment

Follow-up to issue #7 and draft PR18. **No demonstrated end-to-end speedup.** The implementation candidate is preserved as a patch, not adopted into production source. No GPU or full-suite runs, permissions changes, merges or spend.

## Scope and exact inputs

Same stored synthetic-model complete key+leaf+request verification and allocation as the parent README: upstream `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`, fork/evidence base `6851f4221fd29f3184853f9a160c837552b4b2df` (implementation equal to PR4 `133da749937115883c95edfc4b6e372c16209449`), AMD EPYC-Rome KVM, g++ 13.3, stock O2 and all build hardening, CPU15 affinity, -j1, one warmup per arm, alternating AB/BA measured pairs. Source changes are fully identified by patches, not hidden behind the base SHA:

- `cpu-profile-instrumentation.patch`: SHA256 `b3c57702bddadd2edecb8409532d2d028577f3048c84a9aa2b28a61c1f0b4923`. Apply only its `verifier/src/*` hunks for the initial five-pair profile; apply the entire patch for the deeper three-pair profile.
- `cpu-account-reuse.patch`: SHA256 `938db051f84aced6bdd2a44b9fd5c5c2b638006a6817cfa2cf7a1cd39e667a8a`. Apply alone, with **no instrumentation**, for the candidate comparison.

Every comparison's results.json retains binary hashes, fixture hashes, dirty-file inventory, host/toolchain, pressure, wall/user/system time, max-process RSS and faults. Build source digests and warnings are retained. Paths alone are redacted. Request proof remains 4,145,300 bytes; key 1,096,408 and leaf 536,952 bytes. No checkpoint/model inference or GPU outcome is implied.

## What the instrumentation establishes

Research-only `CLOCK_PROCESS_CPUTIME_ID` laps isolate each stage's CPU consumption from competing children. Initial markers identify stage 0=request, 1=key, 2=leaf. The deeper markers are nested inside those regions, not additive; they identify scope but not stage/PID, so do not assign an interleaved deep line to a particular child. Neither profile is a hardware sampling profile. Logging overhead, output and build digest differ, and a profile's wall-time ratio is not a speedup.

Five measured calls' per-stage CPU medians (seconds; all regions in `region-medians.json`):

| Region | Request | Key | Leaf |
| --- | ---: | ---: | ---: |
| first sizing + validation | .10982 | .11130 | .11071 |
| configure | .30021 | .29392 | .29548 |
| request form + accounting | .10751 | n/a | n/a |
| actual proof checking | 1.03637 | .09015 | .07869 |

Policy scan/layout, public-table work and individual layer/head plan construction are small here. The previous coarse ~1.54s pre-proof wall measurement was **not** 1.54s of request CPU. Request setup consumes about .53s CPU, and all three stages repeat significant sizing/configuration work.

The deeper run separates `configure`: approximately .109s sizing, .048s file planning, .062-.064s accounting, .070-.072s hiding checks in representative repetition 1. Sizing is itself distributed across derive (~.016s), batch (~.045s), once/ranges (~.035s), and link (~.011s). The first sizing and configure's sizing are separately executed. Sharing across processes or bypassing the first validation is NOT implemented: doing so safely needs a design preserving validation/failure order, process-global parsing isolation, and input binding.

Initial instrumented comparison medians: upstream 2.62s, instrumented 2.65s (five each). Deep comparison: 2.66s, 2.60s (three each). All honest calls accept and middle-byte altered proofs reject. These are instrumentation controls, not optimization results.

## Bounded experiment selected after the profile

Accounting was an identified nontrivial cost. `account()` already computes `whole_error(r, unit)` once per round, then `Data::holds(r, unit)` repeats that exact calculation three times. The experimental patch reuses the existing error in the exact same comparison against `Real::two_to(work_bits - target)`, storing the boolean for those three uses. No precision, directed rounding, security target, validation, proof parsing, round list or transcript changes. Zero-error rounds retain the existing early continue. It does not cache across calls or processes.

Uninstrumented complete verification results, all five warm repetitions:

| Arm | Wall seconds | Median | Sample SD |
| --- | --- | ---: | ---: |
| Upstream | 2.56, 2.66, 2.63, 2.59, 2.64 | 2.63 | .04037 |
| Candidate | 2.57, 2.64, 2.59, 2.46, 2.71 | 2.59 | .09236 |

Ranges overlap heavily. The 0.04s median difference is smaller than dispersion; **not evidence of a meaningful improvement**, and no speedup claim. The predeclared gross instability screen passes (3.80% versus 9.65% range/median), which is not a confidence test. RSS maximum per process: upstream 157776-157904 KiB, candidate 157232-157360 KiB, not simultaneous process-tree peak and not a claimed memory improvement. Zero major faults in these warm measurements. Shared host, no exclusive physical core.

## Correctness and targeted adversarial evidence

All timing warmups and measured complete verifications exit 0, last line `YES`, with covered r=60 e=64 T=64 and retained commitment, proof-of-work and result-v1 lines. Same ID as the parent README. Timing-run proof mutations exit 1, `NO: proof-refused`.

Additional differential run compares all accounting, commitment, proof-of-work, coverage, result-v1 and final verdict lines (only build digest removed):

- Honest: both YES/0, matching semantic records.
- Full-length proof middle-byte flip and one-byte truncation: both `NO: proof-refused`/1.
- Key middle-byte flip: both `NO: key-refused`/1.
- Leaf middle-byte flip: both `NO: entry-refused`/1.
- Request mutation: both `NO: proof-refused`/1.
- Reply mutation: both `NO: token-range`/1 (tests range rejection, not an in-range reply-binding case).
- Wrong commitment ID: both `NO: model-statement`/1.
- Invalid appended policy line: both `NO: policy-call-line`/1.

These eight negatives are targeted regressions, not comprehensive adversarial/soundness certification. Raw stdout/stderr and semantic comparisons are in `cpu-account-adversarial`. Reconstruct fixtures with `cpu_adversarial.py UPSTREAM CANDIDATE NEW_OUTPUT --cpu 15`. The published script uses explicit validity checks; the executed copy used equivalent enabled assertions. Proof bytes are not duplicated in git.

Targeted numbers/accounting unit test details are in the accompanying test receipt. No full suite was rerun. Existing CPU coverage HOLD is unchanged; this does not authorize adopting the patch or merging PR4/PR18.

## Reproduce and next step

In separate clean base worktrees apply the appropriate patch, run `bash verifier/build.sh`, then the parent `compare_cpu.py` runner with 5 repetitions (3 for the deep profile). Do not compare instrumented to uninstrumented timings as an optimization. Build warnings about the group-writable workspace ancestor were retained; no chmod was performed.

**Next actionable step:** profile `lin_sized`/`derive` exact arithmetic further, or design a validation-preserving single-process reuse of the first computed `Sized` with differential parameter-rejection tests. Avoid sharing stage globals or silently removing checks. The accounting reuse candidate is bounded and correctness-tested on this fixture, but should remain experimental absent stronger performance evidence and independent review. The broader meaningful speed/GPU/real-model outcome is still unmet.
