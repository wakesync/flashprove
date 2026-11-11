# Constraint coverage inventory (issue #6)

`inventory.yaml` is an inventory, not a complete map, of the relation that a FlashProve proof is about. Each row maps one element (an operator, a range or rounding rule, a committed input or state, an output position) to the place in this repository that enforces it, and says which of four kinds that enforcement is:

- **proof_constraint**: intended to be enforced inside the proof (a sub-proof's sumcheck, lookup, range check, or the hash chain). That the constraint is correct or sufficient is not established here.
- **verifier_validation**: the verifier program or the client's integration checks public values outside the proof's relation (parameter conditions, ID comparison, policy, range or next-token comparison with what the caller states). A complete proof of another statement passes the proof part and is stopped only here, and only if the caller states the right value.
- **prover_only**: only the honest committer or prover does it. Nothing in a proof shows a verifier that it happened.
- **not_enforced**: nothing does. The proof says nothing about it.

`open_gaps` lists every `prover_only` and `not_enforced` row in plain language, plus three open proof obligations (G-OB1 to G-OB3). `excluded` lists the research directories under `research/operators/` that no row covers, with the reason.

## How complete it is

- **Shipped verifier** (`cp_verify`, `cp_commit`, `cp_prove`, `integrations/`): the rows were made by reading source and docs. Review of PR #97 found missing rows (the embedding lookup, the stream links between segments, range conditions 1 to 6 and 8, the unchecked tokens after e, the caller's y); they were added. Others may still be missing. Nothing checks completeness for the shipped verifier except review.
- **Research prototypes** (`research/operators/`): every directory is either cited by a row or listed under `excluded`; the checker fails otherwise. Being cited does not mean every relation of the directory has a row: the Qwen operator and GLM rows describe each prototype's relations at the level of one operator, not constraint by constraint.
- Not covered at all: a malicious-proof test for any `proof_constraint` row (none built in this lane), the Lean theorem's own assumptions row by row, the CUDA prover's internals, hiding. Research rows describe prototypes outside `cp_verify`, not model support.

## What is proved, what is recomputed, what is not covered

- **Proved here:** nothing. The inventory is descriptive. A site says where a check lives; it does not show the check is right or sufficient.
- **What the checker recomputes:** `check_inventory.py` opens every cited file and fails if a cited symbol (a literal string of at least 12 characters) is gone, if the inventory declares other kinds or categories than the four of each fixed in the checker, if a row has an unknown kind, category or scope, if a `prover_only` / `not_enforced` row is in no gap, if a plain gap (G-01 to G-07) names a row of another kind, if an open obligation G-OB1 to G-OB3 is deleted or loses one of the rows the checker fixes for it (for G-OB2: IS-01, IS-08, OUT-05, OUT-06, OUT-09) or one of those rows changes kind, or if a research directory is neither cited nor excluded. CI runs it and its self-test on every pull request and push to main (`.github/workflows/claims-check.yml`), so a rename or deletion of a cited site is noticed.
- **What the checker does not see:** a row moved to another valid kind (for example `verifier_validation` to `proof_constraint`) outside a plain gap and outside the rows fixed for G-OB1 to G-OB3, a new caller-stated check that is never added to G-OB2, a check disabled behind unchanged text, or a row that loses one of two sites. The kind of a row is a reader's judgement; review must challenge it.
- **Run:** three negative tests for `verifier_validation` rows (commitment, policy and coverage substitution with complete honest proofs): [experiments/20261110-6-coverage-inventory/](../../experiments/20261110-6-coverage-inventory/RESULTS.md).

## Commands

```
python3 research/coverage/check_inventory.py            # exit 0 and counts; --json OUT to save them (refuses to overwrite)
python3 research/coverage/selftest_checker.py           # exit 0 if the checker catches every mutation it lists
```

Needs Python 3 and PyYAML (as `scripts/update-results.py`). When you move or rename a cited symbol, or add a directory under `research/operators/`, update the inventory in the same change.
