# Constraint coverage inventory (issue #6)

`inventory.yaml` maps every admitted operator, range/rounding rule, committed input or state and output position of the relation that a FlashProve proof is about to the place in this repository that enforces it, and says which of four kinds that enforcement is:

- **proof_constraint**: inside the proof (a sub-proof's sumcheck, lookup, range check, or the hash chain). A cheating prover must break the proof system.
- **verifier_validation**: the verifier program or the client's integration checks public values outside the proof's relation (parameter conditions, ID comparison, policy or range comparison with what the caller states). A complete proof of another statement passes the proof part and is stopped only here, and only if the caller states the right value.
- **prover_only**: only the honest committer or prover does it. Nothing in a proof shows a verifier that it happened.
- **not_enforced**: nothing does. The proof says nothing about it.

`open_gaps` lists every `prover_only` and `not_enforced` row in plain language, plus three open proof obligations.

## What is proved, what is recomputed, what is not covered

- **Proved here:** nothing. The inventory is descriptive: it was made by reading source and docs at main `ba1e3067`. A site says where a check lives; it does not show the check is right or sufficient.
- **What the checker recomputes:** `check_inventory.py` opens every cited file and fails if the cited symbol (a literal string) is gone, if a row has an unknown kind, or if a `prover_only` / `not_enforced` row is in no gap. So the inventory cannot silently rot when the code moves. `selftest_checker.py` shows that it fails on four kinds of alteration.
- **Run:** three negative tests for `verifier_validation` rows (commitment, policy and coverage substitution with complete honest proofs): [experiments/20261110-6-coverage-inventory/](../../experiments/20261110-6-coverage-inventory/RESULTS.md).
- **Not covered:** a malicious-proof test for any `proof_constraint` row (none built in this lane), the Lean theorem's own assumptions row by row, the CUDA prover's internals, hiding. The research rows describe prototypes outside `cp_verify`, not model support.

## Commands

```
python3 research/coverage/check_inventory.py            # exit 0 and counts; --json OUT to save them
python3 research/coverage/selftest_checker.py           # exit 0 if the checker catches 4 of 4 mutations
```

Needs Python 3 and PyYAML (as `scripts/update-results.py`). When you move or rename a cited symbol, update its row in the same change.
