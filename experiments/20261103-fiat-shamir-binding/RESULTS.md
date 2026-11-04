# RESULTS: 20261103-fiat-shamir-binding

Issue #37. Verdict against the pre-registered threshold: **FAIL for the universal early-binding clause; PASS for fixed-ID rejection.** Zero semantic mutations accepted at the original ID. The separate next-token `y` is a counterexample to the literal early-binding clause: its mutation leaves the first request challenge unchanged and is rejected only later. Reporting the exception does not make that clause pass. This corrects the initial PASS-only interpretation without changing the registered threshold; it is not a demonstrated forgery.

This is a binding probe on one shipped fixture. It is not a soundness proof, not an audit, and says nothing about mutations that were not tried. The companion analysis of the two published attacks is `research/security/fiat-shamir-attacks.md`.

## What was run

- Fixture: `examples/accepted-proof` (synthetic small model, ID `79a5a2bc...2183`), unmodified. Mutated copies of the config directory, request and reply live under `bin/fs-binding-inputs/<case>/`; tracked fixture files are never written.
- Two verifier builds on every arm: the production `bin/cp_verify` (gives the verdict) and a diagnostic build with a read-only `FS_TRACE` overlay on `blocks/chain/rounds.h` that prints each chain's first-query digest, the digest after its first prover message, and the first challenge drawn on a copy of the chain (`build_trace.py`). The diagnostic build never decides anything; `build_verdict_agreement` checks it gives the same exit code and last line as production on every run.
- 11 cases, 5 paired repetitions each (baseline/mutation order alternated), n = 55 paired runs, 277.9 s wall. Raw records: `measurements.json`; per-case stats: `summary.json`.
- Labels: the request's first chain is `LABEL_FIRST_CHAIN = 0x46524d01` (blocks/frame/heads.h:112); the trace rows below are for that chain unless stated.

## Per-case results (n = 5 each; all counts had SD 0, min = max)

| case | semantic | production verdict | mutation accepted | first-chain first challenge changed | note |
|---|---|---|---|---|---|
| baseline (every pair) | - | `YES`, exit 0 | 55/55 accepted | identical trace in 55/55 runs | determinism confirmed |
| policy-equation (`epsF_lo 1` -> `2`) | yes | `NO: model-statement`, exit 1 | 0/5 | not reached: rejected before any chain | commitment ID recomputed from config differs from `-id` |
| quant-scale (KL.bin first word 29 -> 28) | yes | `NO: model-statement` | 0/5 | not reached | same |
| layout-placement (two rows' `r` swapped) | yes | `NO: model-statement` | 0/5 | not reached | same |
| layout-comment (append `# byte binding control`) | **control** | `NO: model-statement` | 0/5 | not reached | config bytes are bound verbatim, see below |
| prompt-token (token 0 + 1) | yes | `NO: proof-refused` | 0/5 | **changed 5/5** | first-query digest and first SEND challenge differ |
| reply-token-in-request (word 61 + 1) | yes | `NO: proof-refused` | 0/5 | **changed 5/5** | same |
| last-request-token (word 63 + 1) | yes | `NO: proof-refused` | 0/5 | **changed 5/5** | same |
| range-start (r - 1) | yes | `NO: proof-refused` | 0/5 | **changed 5/5** | same |
| range-end (e - 1) | yes | `NO: statement-range` | 0/5 | not reached: rejected by form check | `e - 1 < T` with `y != 0` fails cp_verify.cpp:324 before any chain |
| next-token (y 199 -> 200) | yes | `NO: reply-differs` | 0/5 | **unchanged 5/5** (deferred binding) | see below |
| commitment-id (first hex digit flipped) | yes | `NO: model-statement` | 0/5 | not reached | ID mismatch |

Build agreement: 55/55 (production and diagnostic builds gave the same exit code and last line on every arm).

### Config mutations: a second measurement at the mutated config's own ID

For the four config cases the mutated config has its own commitment ID (`cp_verify -plan id`, printed as `commitment ID:`). Passing that ID instead of the original lets the chains start, so the first-query digest can be compared:

| case | derived ID differs from original | verdict at derived ID | first-chain first challenge changed vs baseline |
|---|---|---|---|
| policy-equation | yes | `NO: key-refused` (proof of work fails in the key stage) | changed 5/5 |
| quant-scale | yes | `NO: key-refused` | changed 5/5 |
| layout-placement | yes | `NO: key-refused` | changed 5/5 |
| layout-comment (control) | yes | `NO: key-refused` | changed 5/5 |

The derived-ID runs are a diagnostic only: they never count as acceptance (the ID is not the published one, and no proof was ever generated for the mutated config). The recorded key-stage rejection is at a proof-of-work check under the altered transcript. The key file's one-time chain (`LABEL_ONE_TIME_CHAIN`) includes the configuration digest. Only the failing check reached in each run is observed; this does not show that every nonce fails, nor that a changed transcript must always fail proof of work.

## Findings

1. **Configuration is bound byte for byte, before any challenge.** `configuration_digest()` (blocks/frame/heads.h:71) hashes the full text of policy.txt, layout.txt and KL.bin, length-prefixed. It enters the commitment ID (heads.h:91, checked at cp_verify.cpp:2252 before the file's proof chains start; offline record seeds are already derived while forming the ID) and the first query of every chain (`Binder::configuration`, blocks/chain/public.h:243, called first in `bind_request_parameters`, blocks/frame/check.h:63). The whitespace/comment **control** therefore also changes the ID and the first challenge. This is the expected consequence of verbatim binding; it was pre-registered as a control and is reported as such, not as a semantic finding. Consequence for operators: a cosmetic edit to a config file is a new commitment.
2. **The request (tokens, range) is in the first query.** `bind_request_statement` (check.h:73) puts `stored copy`, `request` and `the request file's words` into the statement list before `VerifierRounds` starts the chain (check.h:168, 170). All four request-word mutations changed the first-query digest and the first SEND challenge, 5/5 each.
3. **Deferred binding of the next token y (the one exception).** The statement word for y is zeroed before it enters the first query (cp_verify.cpp:2431-2432, `stNoReplyH`). The prover sends y as a plain scalar later on the same chain (`ReqVerifier::first`, blocks/iop/req.h:661-671, round `R_REPLY`), and the verifier compares it with the caller's y only after the links (check.h:176). Measured: changing y leaves the first-query digest, the first SEND challenge and the REPLY-round digest **identical** to baseline (5/5), and the proof is rejected at `reply-differs`. This matches the project's own documentation (docs/limits-further.md SO-50; PUBLISHED-WORKS.md, the Dao et al. row). It is not an accept of a changed statement, but it is exactly the "deferred binding" the prereg asked to report. Whether it opens a 2026/1838-style delayed-statement attack is examined in `research/security/fiat-shamir-attacks.md`.
4. **Range-end is rejected by a form check, not by the hash chain.** `e - 1 < T` with `y != 0` violates the rule at cp_verify.cpp:324. That is correct behaviour, but a mutation that keeps the form legal (for example `e - 1` together with `y = 0`) was not tried.

## Not measured / limits

- Only one fixture, one proof, one configuration. No real model, no GPU, no new proofs generated.
- Mutations were single-field edits. Combined edits, edits that keep the form legal, and prover-side changes were out of scope.
- The diagnostic prints only the first chain's first challenge (and the REPLY round). Later-round challenge differences were not recorded.
- The "changed" rows show a different hash output, which is a limited transcript-binding observation. Both papers can attack concrete hashes even when their stated instance encodings are hashed; a different challenge is not a soundness proof (prereg Metric).

## Raw data

- `measurements.json` (55 records, full stdout lines of interest, stderr, sha256 of stdout per run)
- `summary.json` (per-case n, sum, median, population SD, min, max)
- `ENV.json`

## Follow-up regression and interpretation correction

At test revision `7318acfb`, ran:

```sh
python3 verifier/tests/fiat_shamir_binding_test.py
```

Exit 0, entire last line:

```text
fiat_shamir_binding_test: expected outcomes, 55 pairs; 0/50 semantic mutations accepted; deferred y binding reproduced (5/5)
```

The fresh run uses the same production/diagnostic binaries and exactly the registered
11 cases x 5 pairs. It is same-lane repeatability, not independent review or new attack
coverage. Wall time 222.6 seconds is diagnostic only, not a speed comparison. The fresh
raw records, per-case statistics, full binary hashes and command are in
`regression/measurements.json`, `regression/summary.json`, `regression/ENV.json`.
The prior raw results remain unchanged.

Fresh-run results: 55/55 baselines accept; 0/50 semantic mutations and 0/5 controls
accept. At the fixed published ID, the three semantic config cases reject 15/15;
at the diagnostic changed IDs, the first challenge changes 5/5 for each of those
cases and for the control. Four request-word cases change the challenge 5/5 each.
Caller-y mutation leaves it unchanged 5/5, with later rejection. Production and
trace outcomes agree for all 55 baseline/mutation pairs (110 arm comparisons).
Each per-case Boolean indicator has n=5, population SD=0, median=min=max: acceptance
0; measured challenge change 1 for config/request cases and 0 for y. Values not
reached are null, not successes or zero-valued challenge observations.

The regression test asserts those exact expected observations, including y's
exception. Thus the **regression test passes**, while the registered universal
**early-binding hypothesis fails**. The fixed-ID no-accept clause passes. The
corrected paper analysis also does not infer Fenzi Proposition 5.5 from the plan
hash and explicitly accounts for its prefix-based, rather than all-challenges-only,
attack. These are corrections to interpretation, not new successful forgeries.

Fixture acceptance receipt: ID
`79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183`,
exit 0, last line `YES`, covered `r=60 e=64 T=64`, policy exact-match. Full `covered:`,
`commitment:`, `proof of work:` and `result-v1` lines are preserved in
`regression/baseline-receipt.txt`. These are this synthetic fixture's outcomes only;
the printed bits are not a claimed security level.
