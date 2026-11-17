# RESULTS: 20261117-210-identity-bridge

Issue #210 (part of #36 and #6). PREREG: [PREREG.md](PREREG.md), first commit `fd515f1994aa4930f39b2ef8b5061a2a119397bf`, amendment A-1 in `9e5b37cfd4f328a10e5081a7422b43603fa8271b`. Base: main `5583d7f82b549454cdb6374d2fd347dfd9781976`.

The deliverable is the note [research/weight-binding/IDENTITY-BRIDGE.md](../../research/weight-binding/IDENTITY-BRIDGE.md).

**This is a desk specification. Nothing was run and nothing was measured.** No model, weight, attestation, key, proof or route was touched. There is no number here to replicate, no `research/results.yaml` entry and no proposed claim.

## Verdict against the registration

**The registered acceptance rule is met, by the lane's own reading. Not reviewed.** The hypothesis is not falsified: at least one edge is not a verified relation on main. In fact 14 of 18 are not.

| registered item | result |
|---|---|
| every edge carries all seven fields and exactly one status | 18 edges (after amendment A-1), 7 fields each, one status each (note section 5) |
| every named counterexample has a rejecting obligation or UNRESOLVED | 11 of 11 answered (note section 6) |
| every statement has a source | a `path:line` on main or a `[V1]` / `[V2]` / `[V3]` mark where the statement is made, and a source map (note section 8). The note's own proposals and reasoning are listed as such in 8.3 |
| the same-output physical-engine counterexample stays undetectable by proof alone | yes: counterexample 11 is UNRESOLVED by construction |
| FAIL rule: a signed assertion promoted to proof | not found by the lane in its own text. Every signature is classed as guarantee (c), and no edge of the proof or recomputation groups takes an input from a signer |
| FAIL rule: a subset result promoted to full Qwen support | not found by the lane in its own text. E8b is stated as 78 of 722 blocks; the full tree is a separate edge, E8c, with status PROPOSED |
| new soundness theorem or format: name it and stop | both are needed and both are named, O-1 and O-2 (note section 9.2). Neither is attempted |
| wall stop 2026-11-17T12:00:00Z | this file was written at 11:21Z, with all ten registered sections of the note already committed. Anything done after the stop would be a deviation and is not in this file |

The two FAIL-rule rows are the author checking its own work. An independent reader is the test of them.

## The answer

1. The join goes through one public revision that the client itself authorizes. The client recomputes the package root, the checkpoint id and the conversion id from that revision, and accepts a proof only under a commitment that a key-file claim binds to the conversion id. A package root and a tensor root are never compared with each other.
2. On main the join cannot be made for Qwen. The edge that would make a proof say which weights ran (E9) has a four-tensor research fixture and no security bound.
3. A proof and an attestation answer different questions. A runtime that returns the same acceptable output from another engine is undetectable by proof alone.

## Edges by status

| status | count | edges |
|---|---|---|
| established on main, in a stated scope | 4 | E7 (hash level, open weights), E8a (hash level, rule text), E8b (hash level, 78 of 722 blocks), E11 (token ids, synthetic examples) |
| documented by vendor only | 5 | E1, E2, E3, E4, E5a |
| proposed code | 6 | E6a, E6b, E8c, E10, E12, E13 |
| unsolved cryptographic obligation | 3 | E5b, E9, E14 |

No edge is established on main for the full Qwen model under proof.

## Counterexamples

| # | counterexample | designation |
|---|---|---|
| 1 | unrelated but valid package / proof roots | UNRESOLVED (rests on E9) |
| 2 | wrong config with same tensor names | rejected on main at hash level for the conversion id; equality with the committed configuration not built; runtime use UNRESOLVED |
| 3 | exponent / integer-hash swap | rejected on main at hash level for 78 blocks; other 644 blocks not built; the prover's table UNRESOLVED |
| 4 | subset root presented as full tree | rejected on main in part (distinct tags, hashed count); pinned count and kind not built; claim count under proof UNRESOLVED |
| 5 | authorized root but alternate loader | UNRESOLVED |
| 6 | hot-swapped adapter | UNRESOLVED |
| 7 | rollback to old approved code | obligation, not built; hardware platform version UNRESOLVED |
| 8 | receipt key from another boot | obligation, not built; a key copied out within the same boot UNRESOLVED |
| 9 | output reconstructed from different token IDs | rejected on main on synthetic examples when the route delivers token ids; text-only routes UNRESOLVED |
| 10 | state root without authenticated origin | obligation, not built; proof side UNRESOLVED |
| 11 | a malicious runtime returning the same acceptable output | UNRESOLVED by construction, undetectable by proof alone |

Main rejects one of the eleven inside a stated scope (9), three in part at hash level (2, 3, 4), and seven not at all. "Obligation, not built" is not a rejection: a client running what is on main accepts those cases today.

## What is not established

- No vendor statement was verified. The five vendor-only edges are descriptions from three public pages.
- No Qwen proof exists, so no proof edge holds for Qwen.
- The four edges established on main are hash-level bookkeeping or application checks, measured and unreplicated in their own results. They are not proofs.
- The edge list is not shown to be complete. It comes from the issue's wording and one reading of the evidence. The eleven counterexamples are the issue's list.
- That counterexample 11 cannot be detected by proof alone is an argument from what the statement contains, not a theorem proved here.
- Hidden weights are not treated: every recomputation edge assumes public weights.
- Confidentiality, privacy and zero knowledge are out of scope.
- The schema example is a discussion shape with made-up values. Nothing parses it.

## Deviations and corrections

1. **Two lanes.** The registering lane stopped at 09:20Z on an output-length limit, before writing any of the note. A successor lane (same model, new session) continued from 10:02Z on the same branch. Recorded in amendment A-1 before any note content was committed. The 42 minutes between sessions count against the three-hour stop, which did not move.
2. **Three edges split** (E5, E6, E8 into seven), recorded in amendment A-1 with reasons, before the note. No edge was dropped.
3. **E14 changed status after it was pushed.** Commit `e859e22` gave E14 the status "documented by vendor only". On re-reading, the vendor pages document that a measured program was started, not that it produced the reply, and the edge depends on E5b, which is unsolved. It is now "unsolved". The note says so where the edge is defined. The earlier commit is left in the history.
4. **One vendor page was first read cut short.** The note was drafted from a copy of the attestation-architecture page cut at 16,000 characters by the lane's own fetch limit. The page was then fetched in full and its marked statements checked. The cut part describes a router that admits only enclaves matching the latest release, which the first draft of the rollback rows (E1, counterexample 7) had said the pages did not describe. Those rows were rewritten.
5. **No checker.** The optional checker of the PREREG was not added. A lane-side script, not in this repository, confirmed that the 213 backticked path and line citations in the note name files that exist and ranges inside them (0 problems). It checks nothing about what the cited lines say.
6. **Reading depth.** The seven evidence files the issue names, `research/weight-binding/DESIGN.md`, `research/envelope/SPEC.md` and the key-file README were read in full. Every other cited file was read at the cited lines and their surroundings only.
7. **Prior art.** The PREREG lists RFC 9334, confidential-VM attestation, in-toto / SLSA and zkML systems from general knowledge. None of them was read for this note and none is cited in it.

## Process

- Commits after the registration: amendment A-1 alone, then the note in four content commits and one correction commit, then this file. No amend, no rebase, no force-push.
- Before each push: `scripts/check-no-host-paths.sh` ok, `scripts/update-results.py --check` ok, `scripts/check-claims.py` ok.
- Not reviewed and not replicated. This pull request is a draft.
