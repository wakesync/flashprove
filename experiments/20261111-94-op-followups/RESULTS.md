# RESULTS: 20261111-94-op-followups

Issue #94 (part of #35). Items 1, 2, 3, 5. Item 4 (grinding) is #95, not done. Measured, unreplicated. Research setting, not a security level, not Qwen model support.

**Verdict: PASS against the registered threshold (with amendment A1).** Registered suite: seeds 1..5, one run per seed, commit `33df862`, O2 binary `eee99d62...` and UBSan binary `f4996f69...` (`runs/build.json`, `runs/build-ubsan.json`), `taskset -c 12-13` on a shared loaded host.

## Numbers (per build; O2 and UBSan identical)

Source: `runs/summary.json` (from `runs/suite.jsonl`, `runs/suite-ubsan.jsonl`).

| Kind | Named cases (case x profile) | Decisions | Outcome |
|---|---|---|---|
| Hostile, expected reject | 65 | 325 | **325/325 rejected, 0 accepted** |
| Documented-gap controls, expected accept | 8 | 38 | **38/38 accepted** |
| Positive (honest v1 and v2, five operators) | 10 | 50 | 50/50 accepted |
| Not applicable | 2 | 2 | `C-conv-other-kernel`, seed 1, v1 and v2: no witness with taps all -S exists (outputs (1010,-6917,3551,407)) |

UBSan: 0 bytes of sanitizer output in every run. Every hostile witness violated at least one relation (minimum 1) and kept every product equation (the harness aborts otherwise). Every run record has `started_utc` and `finished_utc`.

### Item 1: table digest (`runs/digests.jsonl`)

- 27/27 per-table SHA-256 values computed by the verifier from its compiled-in arrays equal the manifest entries; the two manifest constants equal the SHA-256 of `research/operators/qwen_ops/tables/manifest.json` (`13eacc50...79dd`) and `rotary-manifest.json` (`48fc90bb...55a1`).
- v2 digest differs from v1 for 15/15 profiles (5 operators x F12/14/16); 15 distinct v2 digests.
- `T-manifest-hash-only-{5 ops}`: same tables and relations, claimed manifest hash with one hex digit changed: rejected by the v2 verifier 25/25 per build.
- `T-nonlinear-other-table`: one silu row the fixture does not select changed by +1 (same public outputs). Under v2: digest differs (5/5) and the proof is rejected 5/5. Under v1: rejected 5/5 as well, because the changed row is a coefficient of a relation that the verifier rebuilds from its own table; v1 has no digest line for tables.
- Cross-profile replay: v1 proofs under v2 and v2 proofs under v1 rejected, 25 + 25 per build.

**Committed receipts are not affected.** v2 is a new profile; v1 text, relations, prover and verifier are unchanged (`git diff 7c40dd9 -- research/operators/qwen_ops experiments/20261109-35-qwen-operators` is empty). PR #67's run files were produced under v1 and stay valid for v1. A v2 proof is not a v1 proof and vice versa. No existing results.yaml metric changed (see "Ledger" below).

### Item 2: named reviewer cases

Per case, under v1 and v2, both builds:
- `C-conv-chosen-outputs` (opus #1): accepted 5/5. Outputs (S,-S+1,1234,-77) of our choosing, taps (0,0,0,-S).
- `C-conv-other-kernel` (opus #2): accepted 4/4 where a witness exists (seeds 2..5, including the opus seed 3); seed 1 not applicable (A1).
- `C-conv-negate-all` (astra): accepted 5/5.
- `C-rotary-near-target` (opus #4): accepted 5/5. Pairs hit exactly before moving: 32, 30, 30, 32, 30 of 32; output units moved: 0, 2, 2, 0, 2 (`suite.jsonl`, fields `pairs_exact`, `word_units_moved`). The opus run moved 3.
- Rejected 5/5 each (v1 and v2): selector non-Boolean (2,-1) and two-hot on nonlinear and RMS; rotary cos/sin swap; rotary position +7; F12 as F16; permuted nonlinear outputs; conv cross-seed statement; empty proof; L2 salt splice (splice differs from both sources); RMS first/last byte; RMS as L2; impossible output for all five operators; last target +3 for all five.

These gap acceptances are the documented limitation of PR #67 (kernel, history and inputs are prover-chosen), now committed as live controls; they are not new findings and not counted as rejections. The hostile rejections show each constraint exists and is wired; they are equation-level rejections, not a measurement of the 10-bit rounds.

### Item 5: per-round accounting (`receipts/accounting/`)

Fixture seed 7, plan of `qwen_ops/proof.cpp` `run_for()` (shared by v1 and v2). `diagnostic sum` = `account().sum`, the "all rounds' errors added, with the work" line, which the accounting code says decides nothing and is not a union bound.

| Profile | F12 rounds | F12 diagnostic sum (-log2) | weakest round without work (bits) | F14 | F16 |
|---|---|---|---|---|---|
| nonlinear | 31 | 7.38248870 | 4.48733243 | same | same |
| conv | 27 | 7.32588914 | 4.30022646 | same | same |
| l2 | 32 | 7.38432457 | 4.49366312 | same | same |
| rms | 32 | 7.38432457 | 4.49366312 | 33 rounds, 7.38524126, 4.49683079 | as F14 |
| rotary | 31 | 7.38248870 | 4.48733243 | same | same |

All plans hold at the 10-bit per-round target (work counted). The F12 values equal the astra re-review's scratch figures (7.32588914210152, 7.38248869620164, 7.38432456607488; weakest 4.3002264622, 4.4873324288, 4.4936631241) to the printed precision; the round counts match. The F14/F16 RMS plan has one more round (larger table). Prose that cites these numbers should point to these files instead of the reviewers' scratch programs.

## Ledger

`research/results.yaml`: one new entry (`qwen-ops-followups-94`), no existing metric value changed. Checked by a script comparing every metric of base `7c40dd9` against head (all identical); `update-results.py --check` and `check-claims.py` pass (see PR body).

## Deviations

- A1 (before the registered run, after debug on seeds 101..103): `C-conv-other-kernel` solved directly and recorded `not-applicable` when no in-range witness exists; rotary move cap 2 per pair recorded.
- PR #67's `RESULTS.md` follow-up list and README prose are not edited here (committed text of another experiment); this RESULTS and the operator follow-up README are the pointer.

## Not established

- Not a security level; the diagnostic sums are not whole-proof soundness. No grinding attack (#95).
- v2 binds the verifier's table bytes into the transcript; it does not bind inputs, kernel, history or model weights (the gap controls still pass, by design).
- Reachable fraction of the rotary output space not measured; only seeded targets in [-S/2,S/2).
- Unreplicated; one shared loaded host.
