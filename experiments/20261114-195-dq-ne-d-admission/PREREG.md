# PREREG: 20261114-195-dq-ne-d-admission

Issue: #195 (part of #163 and #35). Lane: dq195. Date (UTC): 2026-11-14T02:31Z. Base commit: 2583aca969bb9f33afc92d553dcbd2e2a69fcedc.

Design followed: `research/operators/qwen_ops/DQ-NE-D.md` (merged, PR #166). Its file:line numbers are at `184f89b3`; between that commit and the base, `git diff --stat` over `verifier/`, `docs/format/`, `prover/common/parameter_file.h` and `prover/prover/layout.h` shows only `prover/common/parameter_file.h` changed, so the verifier and doc line numbers below are the note's.

What existed when this file was written: the unmodified verifier built once from the base (`verifier/build.sh`, source digest `64abf54f904779731c64f1460d5daa450926f0aec0a0e7110f5a11d65622ac5c`). No test, no planning call and no source edit had been made.

## Hypothesis
Replacing the equality `H dh = d` in `shape-heads` (`verifier/src/cp_verify.cpp:520`) by the bound `H dh <= 2^20`, and changing no other verifier code, lets `cp_verify` complete a planning call on parameter files with dq != d (dq above d and below d, up to the reachable dq = 8,064), while every existing file, test and stored proof gets the outcome it gets today.

## Metric
Deterministic functional outcomes, no timing claim. For each case: exit status, last output line (the refusal name or `PLAN ONLY: no proof was checked`), and for a completed plan the count of lines `accounting: THE ROUNDS: HOLD`. For each existing test (T8): exit status and the SHA-256 of its output after replacing the checkout path and the work folder path by fixed placeholders. Peak resident memory of each planning call (wait4 `ru_maxrss`) is recorded as a resource receipt only.

Two binaries: **base** (unmodified, built before this file) and **patched** (the candidate change below), both by `verifier/build.sh`, g++ 13.

## Frozen site inventory (the only places the candidate may change)
Verifier code:
1. `verifier/src/cp_verify.cpp:520-521`: drop `h.H * h.dh != d`; add the N1 test. The name stays `shape-heads` (its meaning changes; no new name, so `vf_rejection_names.txt` is unchanged).
2. `verifier/src/vf_widths_and_bounds.h`: one new constant (the bound 2^20) and one new function of (H, dh) that returns whether H dh, multiplied in 128 bits, is at most the bound. It exists so that T7a can test the predicate alone. Nothing existing in that header changes.
3. The comment lines next to site 1.

Docs (the note's rows 58 to 62): `verifier/docs/parameter-file.md:106`; `docs/format/FORMAT.md:2152`, `:2162`, `:2183`; `docs/format/11-2-feed-forward-segment.md:294`, `:1035`.

Tests and harness: `verifier/tests/parameter_walk.py` (N6: the walk may leave d alone when it changes H or dh); `verifier/tests/weights_twin_test.cpp` (T1: added shapes) with the matching expected line in `SUITE.md`; new files under `verifier/tests/` and under this experiment's folder.

Not changed under any outcome: `prover/common/parameter_file.h`, `prover/prover/layout.h`, any other prover file, `vf_attention_shape.h`, the clamp and N4 rules, rotary support, any other refusal, `research/operators/qwen_ops/DH256-ROTARY.md`.

If any other verifier source line has to change for a registered case to pass, that is stop rule 3: the lane stops and does not adopt the change.

## The cases and their expected outcomes (fixed now)
Planning call = `cp_verify -plan accounting <folder> 128` unless said otherwise. "Planned" = status 4, last line `PLAN ONLY: no proof was checked`, exactly one line `accounting: THE ROUNDS: HOLD`, and no line containing `internal-`.

**T7a, the predicate alone** (new unit test, compiled plain and with `-fsanitize=address,undefined -fno-sanitize-recover=all`). Expected: true at (H, dh) = (1, 2^20), (32, 32768), (63, 128), (24, 256); false at (33, 32768), (3, 2^19), (1, 2^21), (63, 2^31), (2^32 - 1, 2^32 - 1). And for every H in 1..64 and dh = 2^k, k in 1..31, it equals the independent form `H <= 2^20 / dh` (integer division). No sanitizer report.

**T7b, the bound in planning calls** (the small kit `prover/tests/configurations/pinned_no_proof_of_work`, only the lines d, H, G, dh changed; d = 512, G = 1):

| case | H | dh | dq | base | patched |
|---|---|---|---|---|---|
| above | 3 | 2^19 | 1,572,864 | `NO: shape-heads` | `NO: shape-heads` |
| one-step-above | 33 | 32768 | 2^20 + 32768 | `NO: shape-heads` | `NO: shape-heads` |
| at-exact | 32 | 32768 | 2^20 | `NO: shape-heads` | status 1 under a name that is not `shape-heads`; recorded |
| at-design | 1 | 2^20 | 2^20 | `NO: shape-heads` | status 1 under a name that is not `shape-heads`; recorded |

The two at-bound files are not valid complete plans and are not described as such. For the two above-bound files the refusal must come before qa is sized: the evidence is the name (`shape-heads` is raised before the first tensor is added) and a peak memory in line with a refused small file. Each call runs under an address-space limit of 4 GiB.

**T2, complete plans at the design's small shapes.** dq above d: H = 3, G = 1, dh = 4, d = 8 (dq 12, dkv 4, nqk 16). dq below d: H = 1, G = 1, dh = 4, d = 8 (dq 4, nqk 8). Expected, patched: `-plan arrays` status 4, `prover/tools/pack_layout.py` makes layout.txt, the planning call is Planned, and `-plan request` with that layout at 0 and at 128 asked bits both end with status 4. Expected, base: `NO: shape-heads` for both. Whether the plan prints `plan: not the standard parameter form` is recorded and is not part of the threshold (dh = 4 is a test shape).

**T7c, the reachable control.** H = 63, G = 1, dh = 128, d = 4,096 (dq 8,064, dkv 128, nqk 8,192). Expected, patched: Planned, by the same three steps as T2. Expected, base: `NO: shape-heads`. A kit that lists its arrays but does not finish the accounting plan is not a pass.

**How the T2 and T7c kits get their other lines.** The derived lines (iota_*, iotaA_0, iotaH_*, lmS, kFD, the request-matrix and table lines, the rotary digest, layout.txt) depend on the shape, so a copied kit is refused for reasons that have nothing to do with dq. They are worked out on **debug shapes that the registered suite does not use, with the base binary only**: equal-width twins (dq = d), namely (d, H, G, dh) = (12, 3, 1, 4), (4, 1, 1, 4), (8, 2, 1, 4) for T2 and (8064, 63, 1, 128), (4096, 32, 1, 128) for T7c. The attention sub-proof never reads d, so a twin with the same H, G, dh has the same attention lines. A registered kit is then its same-heads twin's file with the line d replaced, the lines iota_0..7 recomputed by a script whose formula must first reproduce the committed kits' and the twins' own iota lines, the rotary digest lines recomputed by `scales/policy_tables.py`, and layout.txt made by the two-step rule above. No registered shape is run on either binary before its registered run. If a registered kit is refused for a kit line (not for code), one corrected rerun per kit is allowed, written first as a dated Amendment, with the first run kept and reported.

**T1, layout twins.** `weights_twin_test` gains shapes with dq above d, including the note's odd-part example d = 8, dh = 4, dq = 12 (dq = 3 * 2^2). Expected: `weights_twin_test: ok`, 0 failed checks. The existing shape d = 24, dq = 16 (dq below d) stays.

**T8, nothing existing changes.** Run with the base binary and with the patched binary, test files at their base text: `example_kits_test.py`, `served_form_test.py` (it has the dense cases), `plan_tau_test.py`, `kit_rounds_test.py`, the `verifier.la_equals_lt` call, whole verification calls on `examples/accepted-proof` and `examples/accepted-proof-clipped-gap` (the stored proofs), `examples/rejected-proofs/try_altered_copies.py` on both, and `call_accounting_test.py` on `examples/accepted-proof`. Compiled tests, built at base text against the patched tree: `weights_twin_test` (the 36 base worlds), `ws_build_fuzz` (300,000 shapes, seed 1, address and undefined-behaviour sanitizers). Expected: every row passes on both, with the same exit status and the same normalised output hash on base and patched. A row whose one run needs more than 2 minutes of CPU is left out and named (the lane has no heavy slot).

**T3, statement swap (not part of the pass threshold).** Fixture: `examples/accepted-proof` (d = 512, H = 4, G = 2, dh = 128; the patched binary must first say YES on it unchanged). Changed statement: the same files with H = 6 (dq 768 != d; G divides H; dh unchanged), its other lines made by the same twin rule (twin: d = 768, H = 6, G = 2, dh = 128), and it must be Planned by the patched binary on its own. Then the stored key, entry, request, reply and proof are checked under the changed configuration, with the ID that `-plan id` derives for it. Expected: status 1 from checking, not a `shape-*`, `plan-*` or `af-*` name; the name and the stage are recorded. A YES would be a soundness finding: stop, keep the files, report. If the changed statement cannot be Planned inside the time box, or the refusal is a shape or planning name, T3 is reported **NOT ESTABLISHED**; a shape refusal is not counted as proof binding. The reverse direction (an honest dq != d proof under a dq = d statement) needs a prover and is out of scope.

## Acceptance threshold
PASS, and the candidate is adopted on the branch (code, docs, tests), only if all of these hold: T7a as listed, plain and sanitized; T7b all four rows as listed on both binaries; T2 both shapes Planned on patched and `shape-heads` on base; T7c Planned on patched and `shape-heads` on base; T1 ok; T8 identical on every row run; no sanitizer report anywhere; no stop rule.

Anything less is PARTIAL or FAIL, reported as such, and then **the widened admission is not adopted**: `verifier/src`, the docs and the existing tests stay at base on the branch, and the candidate is published only as `candidate.patch` in this folder beside the evidence.

## Kill criterion
Stop rules of the design note, section 5, applied as written: (1) an existing test changes its outcome; (2) T2 is refused under any name or shows an `internal-` name; (3) a place outside the frozen inventory has to change; (4) a `no-wrap-*` verdict changes for an existing configuration; (5) time. No guard is removed or loosened to get a pass.

Time: lane hard stop 2026-11-14T04:15:00Z. Kit work for T2, T7c and T3 ends at 03:25Z; what is not Planned by then is reported not Planned. T3 is attempted only after T2 and T7c are finished. Cores 8 and 9 only; target 3 GiB resident, hard cap 4 GiB per process; no model weights, no GPU, no prover run, no key or proof made, no spend. A sanitized build of the whole `cp_verify` is tried once under `timeout 120`; if it does not finish, the sanitized planning cases are reported PENDING and only T7a and `ws_build_fuzz` count as sanitized.

## Runs
Outcomes are deterministic; repetitions guard against a flaky harness, not against noise. Every registered planning call (T7b, T2, T7c) runs 5 times on each binary, base and patched alternating first by round; all 5 must agree. T8 script rows run 5 rounds on each binary in the same alternation; rounds not finished by 03:25Z are reported as not run, with the count. Compiled tests (T7a, T1, `ws_build_fuzz`, base-text twin test) run once per build mode. No warmup, no seed except `ws_build_fuzz`'s 1, no completed run excluded. A first run with an unexpected outcome stays in the receipts; a rerun is labelled and does not replace it.

## Prior art
This is an admission rule of one verifier, not a new proof technique. The audit it implements is this repository's `DQ-NE-D.md` (PR #166), which classified every use of d, dq, dkv and nqk in six verifier files and found the equality to be a size bound only; a reviewer of that PR tried the one-line substitution exploratively and saw copied kits refused at derived lines (`shape-call-*`, `forest-trees`), which is why the kits here are regenerated. Grouped-query attention with a projection width different from the residual width is standard in served models (Qwen3.8-27B: 24 heads of 256 against d = 5,120). zkML systems that take arbitrary tensor shapes (EZKL, zkLLM, Jolt-based and Expander-based provers) have no such equality because their circuits are compiled per model; they give no evidence about this verifier's planner. No TEE claim is involved. What is new here is only the tested statement that this planner completes at dq != d with one changed condition.

## What a PASS would and would not establish
Would: the CPU verifier admits and fully plans the listed dq != d files, the bound refuses above 2^20 before sizing, and the listed existing outcomes are unchanged. Would not: that an honest dq != d proof exists or verifies (both prover gates stay closed; the design's T4 and T6 need a GPU), reverse-direction T3, anything about dh = 256, partial rotary, q/k norm or Qwen admission, and nothing about the Lean model.

## Amendments

### Amendment 1, 2026-11-14 02:56 UTC (after the candidate was written and built, before any registered case or T8 row was run on either binary)

What had been run when this was written: the two builds; `kits.py selfcheck` (its iota formula gives the lines iota_0..7 and iotaH_0..5 of all 7 committed kits); and planning calls with the **base** binary on equal-width debug shapes only (d = H dh): (8,2,1,4), (12,3,1,4), (4,1,1,4), (8064,63,1,128), (4096,32,1,128). No file with dq != d had been given to either binary, and the patched binary had not been run at all.

1. **Kit lines, fixed by the twins.** Source kit for T2, T7b and T7c: `prover/tests/configurations/pinned_no_proof_of_work`. T2 kits: lmS 10, kFD 12, ranges-part 10, plus the recomputed iota lines and table digests. T7c kit: lmS 10, the line `table 11 32 402653184 44040191 0 18` (that of `prover/examples/target_full_f2`), ranges-part 13, `group link 1 18 17 17 15` (its last number was 13), plus the recomputed iota lines and digests. The line `group link` was not in the registration's list of derived lines; the twin (8064,63,1,128) is refused `plan-mask-row` without it, on the base binary, at dq = d. These are lines of the parameter file, not code.
2. **T2, dq below d, has no same-heads twin that plans.** Its twin would be (4,1,1,4), and d = 4 is refused `shape-product-layer-H` (a rule on d, by the base binary). So that kit is the twin (8,2,1,4)'s file with the line H set to 1, not a same-heads twin's file with d replaced. The attention lines of an H = 1 file have therefore not been seen to plan on any binary before the registered run. If the registered run refuses it for a kit line, the one corrected rerun of the registration applies.
3. **T7b uses plain substitution.** Only the four lines d, H, G, dh are replaced; no iota line or digest is recomputed (recomputing the rotary digest at dh = 2^20 would build a table of 2^26 entries, and the file is expected to be refused anyway).
4. **T8 normalisation, stated before the first T8 run.** Besides the checkout and work folder paths, the hash ignores: the path of the binary; the printed source digest (`build=...`, which differs between the two binaries by construction: `64abf54f...` and `fd3fdeee...`); lines whose text after leading blanks begins `seconds:`; and every `<digits>.<digits> s`, replaced by `<t> s` (wall times; the same rule as normalisation N2 in `experiments/20261112-135-dense-standard-form/PREREG.md`, Amendment 1). The runner writes the list of line shapes it touched.
5. **Memory receipt.** Peak resident memory is read per call with wait4, as registered.
6. **Time.** About 79 minutes remain to the hard stop. T3 will not be attempted unless everything else is finished by 03:40Z; otherwise it is reported NOT ESTABLISHED. T8 rounds: as many of the 5 as finish by 03:25Z, as registered.
7. **Correction to this amendment's own text** (still before any registered run). Its first committed version, `42c0ec83`, was staged a moment before three wording fixes landed, so that commit gives the time as 02:57 (the clock read 02:56), says "78 minutes", and cites "PR #145's Amendment 1" for the wall-time rule. There is no such source: the rule is normalisation N2 of `experiments/20261112-135-dense-standard-form/PREREG.md`, Amendment 1, as item 4 now says. Items 1 to 3, 5 and 6 are otherwise as first committed.

### Amendment 2, 2026-11-14 03:24 UTC (after the registered planning cases, T7a, T1 and T8 round 1 groups A, B, C; before group D, `ws_build_fuzz` and any rerun)

1. **A fault of this experiment's T8 harness, on one row.** The row `whole_clipped_gap` (the stored proof of `examples/accepted-proof-clipped-gap`) was called without the option `-policy clipped-gap,9244130,323343,1,16,8` that the example's README gives. Both binaries answered the same: status 1, `NO: policy`, before reading the proof, with one normalised hash. That is not a pass and not a difference between the binaries; the row has no valid run. Its two receipts stay as run. The row is run again, once per binary, under the new name `whole_clipped_gap_with_policy`, with the README's option and nothing else changed; the threshold for it is the registered one (status 0, a line beginning `WITHIN LIMITS: clipped-gap C=`, same hash on both binaries). The comparison lists the first run as a harness fault and does not count it.
2. **What runs after the registered 03:25Z T8 time.** Group D (`try_altered_copies.py` on both examples), the rerun of item 1, and `ws_build_fuzz` had not started when this was written (03:24Z) and so finish after 03:25Z. Each is run once per binary (the fuzz once, it does not use `cp_verify`) and reported as run after the registered time. T8 rounds 2 to 5 are not run: T8 is one round. The 04:15Z hard stop is unchanged.
3. **Order of the two binaries in T8.** From group A on, base and patched ran at the same time, one on core 8 and one on core 9, instead of one after the other in alternating order. The outcomes are deterministic text; the registered alternation was not kept for T8.
4. **Sanitized whole-verifier build.** Not attempted before this amendment. If it is not attempted by 03:50Z it is reported PENDING, as registered, and only T7a and `ws_build_fuzz` count as sanitized.
