# PR #67 follow-ups (issue #94, research only)

Items 1, 2, 3 and 5 of issue #94. Item 4 (a grinding attack on the weakest query rounds) is issue #95 and is not done here. This is not Qwen model support, not a production verifier and not a security level. Receipts: `experiments/20261111-94-op-followups/` (PREREG, ENV, RESULTS, `runs/`, `receipts/accounting/`).

`follow.cpp` includes `../qwen_ops/proof.cpp` unchanged (its `main` is renamed by a macro), so the v1 relations, fixtures, prover and verifier are byte-for-byte those of PR #67. Nothing under `research/operators/qwen_ops/` that PR #67's receipts hash was changed.

## Item 1: table identity in the configuration digest (profile v2)

PR #67's profile text (v1) is `operator-family qwen-bounded-integer-v1`, `profile <op> F=<F> position=<p>`. The tables entered the proof only as compiled-in constants: a verifier built with other `pinned.h` contents produced the same configuration digest. Profile v2 adds three lines to the configuration text, which enters the configuration digest and so the first query of the transcript:

```
operator-family qwen-bounded-integer-v2
profile <op> F=<F> position=<p>
tables-manifest-sha256 13eacc50...79dd
rotary-manifest-sha256 48fc90bb...55a1
tables-read <name>-f<F>=<SHA-256 of the i64LE bytes of that table, as compiled into this verifier> ...
```

The `tables-read` hashes are computed at run time from the arrays the verifier actually uses, so a different table changes the digest even if someone forgets to update the manifest constant; `run.py digests` checks that each of the 27 computed hashes equals its manifest entry and that the two manifest constants equal the SHA-256 of the committed manifest files. The plan (sizes, rounds) is the same for v1 and v2; only the text differs.

What it does: a proof made under another table, or under another claimed manifest hash, is rejected by the v2 verifier (cases `T-*`). What it does not do: it binds the verifier's own tables into the transcript; it does not make a table correct, and it does not bind inputs, kernel or history (still prover-chosen, see the gap controls). v1 is unchanged and remains what PR #67's committed receipts measured; a v1 verifier still accepts any v1 proof regardless of table identity, except that the proof's relations already carry the table coefficients (case `T-nonlinear-other-table` under v1 is rejected because the changed row changes a relation coefficient, not because of a digest).

## Item 2: reviewer constructions as named cases

All from PR #67's reviews (opus https://github.com/wakesync/flashprove/pull/67#issuecomment-6757161440, astra https://github.com/wakesync/flashprove/pull/67#issuecomment-6756145013). Each case is run under v1 and v2.

- Documented gaps, expected ACCEPT (the statement does not bind inputs, kernel or history): `C-conv-chosen-outputs` (outputs (S,-S+1,1234,-77), taps (0,0,0,-S)), `C-conv-other-kernel` (fixture outputs, all taps -S, history and inputs solved; recorded `not-applicable` when no in-range witness exists), `C-conv-negate-all` (all inputs and taps negated), `C-rotary-near-target` (position 517, random target in [-S/2,S/2), at most 2 units moved per pair).
- Expected REJECT: non-Boolean and two-hot selectors (nonlinear, RMS), rotary cos/sin swap, rotary position +7, F12 proof as F16, permuted nonlinear outputs, conv cross-seed statement, empty proof, L2 salt splice, RMS first/last byte flip, RMS proof as L2, impossible outputs (all five), last target +3 (all five), cross-profile replay (v1 proof under v2 and back), claimed manifest hash changed, nonlinear proof made with a different table.

Complete hostile proofs keep every product equation and change targets inside the prover (PR #67's technique); the harness refuses any hostile witness that violates no relation.

## Item 3: run timestamps

Every record written by `run.py` (build receipts, one `mode: run` line per seed before its cases, digests, accounting receipts) carries `started_utc` and `finished_utc` (ISO-8601, UTC). Committed run files of earlier PRs are not edited.

## Item 5: per-round accounting receipts

`run.py accounting` writes `experiments/20261111-94-op-followups/receipts/accounting/<op>-f<F>.txt` for every profile at F12/14/16 (fixture seed 7): every plan round (name, count, work bits, minus log2 of its whole error), the `account()` summary as JSON, then the repository's own `print_accounting` text. `summary.json` collects the summaries. The "all rounds' errors added" line is a diagnostic: the accounting code itself says it decides nothing, is not a union bound over all events, and that no figure there is a security level.

## Reproduce

From the repository root (Python 3 standard library, g++ C++17, no downloads):

```
python3 research/operators/qwen_ops_followups/run.py build --receipt
python3 research/operators/qwen_ops_followups/run.py build --ubsan --receipt
python3 research/operators/qwen_ops_followups/run.py suite
python3 research/operators/qwen_ops_followups/run.py suite --ubsan
python3 research/operators/qwen_ops_followups/run.py digests
python3 research/operators/qwen_ops_followups/run.py accounting
python3 research/operators/qwen_ops_followups/run.py summary
```

Writers refuse to overwrite an existing receipt; move the committed `runs/` and `receipts/` aside to reproduce. On a shared host pin to a couple of cores (`taskset`).
