# RESULTS: missing-metadata boundary (issue #189)

**STOP RULE FIRED: blocking finding. Measured, unreplicated.** Issue #189's stop rule and this experiment's kill criterion are met: with run 3's metadata, stored tree and cached comparison removed, truncated, reordered or substituted inputs get a full H3 `PASS` from the unchanged reader and summariser. The milestone stops here. Nothing is fixed in this PR and the stop rule is not resolved.

This replaces the verdict this file carried at `bdc059a4c7302b8787c18c5c038468e89c5415d9` ("PASS against this follow-up's registered contract", "the stop rule did not fire"). That verdict was true only for the six registered arms. Both round-1 reviewers found the inputs below after those arms had run ([first review](https://github.com/wakesync/flashprove/pull/191#issuecomment-6866086584), [second review](https://github.com/wakesync/flashprove/pull/191#issuecomment-6867478542)); this lane then reproduced every one of them with its own script (PREREG amendments A-1 and A-2). The sentence "a cut without metadata gives `PASS-SUBSET` and never a full `PASS`" is withdrawn: it holds for one cut position in one direction.

This is a deterministic reader study on committed files, hash level, not a proof, not a new conversion. `research/weight-binding/wb_leafv2.py` and `experiments/20261112-149-leaf-v2/summarise.py` are unchanged.

## What kind of finding this is

Three things are easy to mix up. The finding is about the third.

1. **Per-comparison coverage**: how many blocks run 1 and run 3 have in common (`wb_leafv2.py compare`). The comparator reports this correctly in every case below: a 77-line run 3 is `identical-partial` with 77 common blocks, never `identical-complete`.
2. **Union coverage**: the summariser's `h3.overall` is computed on the union of the blocks covered by run 2 and by run 3, each compared with run 1 (amendment A-1 of the #149 experiment). Run 2 is a legitimate stopped run holding the last 8 blocks of the registered order. A run 3 that holds the first 70 or more blocks is therefore completed to 78 by run 2, and the label is `PASS`.
3. **Registered-run provenance**: whether the records in `run3/` are a complete, independent run executed as registered. The reader cannot check this. Without `run-meta.json` it accepts a prefix of either canonical order, and no record says which run produced it.

So each full `PASS` below is **real union coverage plus provenance that cannot be checked**. It is not invented block coverage and not a false hash match: the script's own cross-check (it parses the fixture files with the `json` module, without the reader) found, in all 115 replays, that every block the reader counted is present in the supplied files and that every block reported identical has equal `e`, `int_sha256` and fetched-bytes `sha256`. What the label does not show is that run 3 was cut, reordered, or is run 1's own records.

PR #151's committed result does not rest on the union: on the committed files run 3 alone is `identical-complete` with 78 common blocks (the `baseline` arm below). The finding is about what the reader would accept, not about the committed runs.

## Review-driven cases (amendment A-1), 2026-11-14

`stoprule_cases.py`, one recorded invocation, 23 cases, five fresh private copies each: **115 of 115 replays gave the outcome registered in A-1** before the script existed, and every reviewer-reported outcome reproduced. **13 cases (65 replays) are a full H3 `PASS` on an altered run 3.** Receipts: `runs/stoprule-20261114/summary.json` and `runs/stoprule-20261114/rep{1..5}-<case>.json` (return codes, sanitised output, comparator result, the `h3` block, the cross-check), `source-before.json` / `source-after.json` (equal: no committed run file changed), `env.json`.

"Forward k" = run 3's lines put into forward registered order, first k lines kept (the committed run 3 is stored in reverse order). Unless the row says otherwise, run 3's metadata, stored tree and cached comparison are removed; run 1 and run 2 are untouched. "Common" is the comparator's common-block count for run 1 against run 3; "union" is the summariser's union block count; "from run 2 only" is how many union blocks the run 3 file does not contain. Every count has n = 5, sample SD 0, min = max = the value shown: five replays of a deterministic file read are one measurement repeated, not five independent ones.

| Case | Comparator, common | H3 overall, union | From run 2 only | Reported by |
|---|---|---|---|---|
| forward 77 | identical-partial, 77 | **PASS**, 78 | 1 | both reviews |
| forward 76 | identical-partial, 76 | **PASS**, 78 | 2 | first review |
| forward 71 | identical-partial, 71 | **PASS**, 78 | 7 | first review |
| forward 70 | identical-partial, 70 | **PASS**, 78 | 8 | both reviews |
| forward 69 | identical-partial, 69 | PASS-SUBSET, 77 | 8 | this lane (boundary) |
| forward 60 | identical-partial, 60 | PASS-SUBSET, 68 | 8 | second review |
| forward 39 | identical-partial, 39 | PASS-SUBSET, 47 | 8 | first review |
| forward 10 | identical-partial, 10 | PASS-SUBSET, 18 | 8 | second review |
| forward 1 | identical-partial, 1 | BELOW-COVERAGE, 9 | 8 | first review |
| whole of run 3 in forward order | identical-complete, 78 | **PASS**, 78 | 0 | both reviews |
| run 1's records as run 3 | identical-complete, 78 | **PASS**, 78 | 0 | first review |
| run 1's directory as run 3, its own metadata and tree kept | identical-complete, 78 | **PASS**, 78 | 0 | both reviews |
| run 1's directory as run 3, metadata removed | identical-complete, 78 | **PASS**, 78 | 0 | second review |
| run 1's first 70 lines as run 3 | identical-partial, 70 | **PASS**, 78 | 8 | second review |
| records alternately from run 1 and run 3 by block name, forward order | identical-complete, 78 | **PASS**, 78 | 0 | first review |
| run 1's first 39 lines, then forward run 3 lines 39 to 69 | identical-partial, 70 | **PASS**, 78 | 8 | second review |
| forward 77, metadata edited to agree (`done` 77, `reverse` false, `stopped` set) | identical-partial, 77 | **PASS**, 78 | 1 | first review |
| forward 70, metadata edited to agree | identical-partial, 70 | **PASS**, 78 | 8 | second review |
| control: original-order last-line cut (registered arm 3's input) | identical-partial, 77 | PASS-SUBSET, 77 | 0 | both reviews |
| control: original-order last-line cut, then reversed | refused (record order) | refused | n/a | first review |
| control: run 2's records as run 3 | identical-partial, 8 | BELOW-COVERAGE, 8 | 0 | both reviews |
| control: run 1 and run 3 lines alternated by raw line index | refused (duplicate record) | refused | n/a | first review |
| control: run 2 reversed into forward order, its metadata kept (run 3 untouched) | run 3 identical-complete; run 2 refused (record order) | refused | n/a | second review |

What the rows show:

- **The boundary is exactly 70.** Run 2's 8 blocks sit at positions 70 to 77 of the forward order. A forward prefix of run 3 with 70 or more lines is completed to 78; 69 lines gives a union of 77 and `PASS-SUBSET`. The registered arm cut run 3 in its original (reverse) order, where the missing block is one run 2 does not hold, which is why it saw `PASS-SUBSET`.
- **Reordering a whole run into the other canonical order is accepted** when metadata is absent (`identical-complete`, `PASS`). The record content is run 3's; the direction it was executed in is unchecked.
- **Substitution is accepted, with or without metadata.** With run 1's records (or run 1's whole directory, metadata included) in place of run 3, H3 compares run 1 with itself. No metadata rule catches this: the reader has no notion of run identity.
- **Metadata that is edited to agree is accepted.** The forward cuts still give a full `PASS` with a `run-meta.json` that matches them. Requiring the file would not close the finding on its own.
- **Nothing was invented.** No replay reported a block that is absent from the supplied files, or a match between unequal hashes. The second stop rule registered in A-1 (the more serious finding) did not fire.
- None of the 20 accepted fixtures reproduces the committed `runs/summary.json` byte for byte (the recomputed summary records each `blocks.jsonl` hash; `summary_sha256` in every receipt differs from the committed file's hash in `source-before.json`). The status label alone does not tell them apart; a comparison against pinned file hashes would.

## The six registered arms (unchanged, as measured on 2026-11-13)

`runs/registered/summary.json` records all 30 expected outcomes across six arms and five fresh temporary copies per arm; both reviewers reproduced them. Each per-repetition receipt `runs/registered/rep{1..5}-<arm>.json` retains input hashes, return codes, sanitised stdout/stderr, and JSON outputs. These files are not modified.

| Arm | Comparator | Recomputed H3 | Common blocks: median, sample SD, min/max (n=5) |
|---|---|---|---|
| `baseline` | identical-complete | PASS | 78, 0, 78/78 |
| `complete-no-meta` | identical-complete | PASS | 78, 0, 78/78 |
| `cut-no-meta-tree-cache` | identical-partial | PASS-SUBSET | 77, 0, 77/77 |
| `cut-meta-kept` | refused | refused | not reported on refusal |
| `cut-tree-kept` | refused | refused | not reported on refusal |
| `reordered-no-meta-tree-cache` | refused | refused | not reported on refusal |

All cuts in these arms remove the last complete line of run 3 in its original order. The metadata-kept arm is refused on the metadata count (`done=78` against 77 records), the tree-kept arm on an incomplete run next to a stored tree, the reorder (lines 3 and 40 exchanged) on record order. These outcomes stand. They do not support the general statement the earlier text drew from them: the acceptance threshold was met on the registered inputs, and the kill criterion ("any truncated or reordered fixture reports full H3 `PASS`") is met by the inputs in the previous section. The kill criterion governs.

## Regression suite

`research/weight-binding/test_wb_leafv2_evidence.py` gains 18 cases named `stop-rule-189-*` (insertion only: no earlier line of the file changes). They pin the **current** outcome of each altered input above for the three readers, including the 13 full-`PASS` ones, and each also checks that the reported union is exactly the set of blocks present in the run 2 and run 3 files. They are labelled in the file and in the receipt as the stop-rule finding, a record of present behaviour so that a change is noticed. They are not a contract the reader should keep: a separately registered reader change is expected to change them.

One invocation after the reproduction: **231 of 231 expectations over 82 cases**, receipt `runs/evidence-tests-stoprule-20261114.json`. Its first 177 expectation records are identical to those of `runs/evidence-tests.json` (the 2026-11-13 receipt, 177 of 177 over 64 cases, unchanged); 54 are new. The original `experiments/20261112-149-leaf-v2/runs-fix151/evidence-tests.json` is unchanged.

## Recommendation (step 4 of the issue), updated

The earlier text recommended requiring `run-meta.json` for registered evidence. In light of the finding that is still worth doing and is not enough. None of the following is implemented here; each needs its own dated registration and review.

1. **Refuse a missing `run-meta.json` when the input is presented as a registered run.** Reason: with the file absent the loader accepts either canonical direction, and that ambiguity is what lets a forward-ordered cut of a reverse run line up with run 2. By the loader's code (read, not measured in this PR), a forward cut next to run 3's original metadata fails the count check, and would fail the direction check if the count were made to agree. This closes the metadata-absent rows of the table only if the metadata is honest.
2. **Do not treat that as provenance.** Measured above: metadata edited to agree still gives a full `PASS`, and so does run 1's directory with its own untouched metadata. Requiring metadata checks consistency inside one directory. It does not authenticate the metadata, does not show the run was executed, and does not distinguish one run from a copy of another.
3. **Separate the union from the label.** A full `PASS` built from two partial comparisons should be visibly different from one where a single run covers all 78 blocks, for example a distinct status when no single compared run is `identical-complete`. On the committed files this changes nothing (run 3 alone is complete). This is the part of the finding that requiring metadata does not touch at all.
4. **Bind run identity to something outside the run directory.** The cases above all alter `blocks.jsonl`, so its hash changes. A committed pin of each registered run's file hashes, checked by the summariser, would refuse every case in the table. A weaker, heuristic check is to refuse a run 3 whose records are byte-identical to run 1's (independent runs do not share timing fields). Neither is cryptographic authentication: whoever can rewrite the pin can rewrite the runs. The git history of the committed files is the actual record.
5. **State the limit wherever H3 is quoted**: H3 is agreement and coverage of the supplied records, not evidence that an independent, complete second run took place.

## Limits and deviations

- The registration above `## Amendments` in PREREG.md is unchanged. Amendment A-1 was committed alone, before `stoprule_cases.py` existed; A-2 records the outcome. No registered arm, threshold or run file changed; no existing receipt was modified or replaced.
- Debugging, as A-1 allows: `stoprule_cases.py` was run twice on the unregistered forward-50 fixture (once printed, once timed) and syntax-checked. One edit followed (keep the sanitised stdout in the receipt instead of only its hash). No listed case ran before the recorded invocation. The recorded invocation and the suite invocation each ran once, with no failed or discarded attempt.
- After the recorded run, the script was run a second time into a private temporary directory to check that the receipts reproduce byte for byte; that replay is a reproducibility check, not the recorded run, and none of its files is committed. See README.md for what compared equal.
- The review-driven cases were chosen after the reviewers had reported their outcomes, so they confirm a reported finding; they are not a blind test, and "115 of 115 as registered" should be read that way.
- 23 cases do not exhaust the inputs. Other unions, other splices and other metadata edits were not tried. Nothing here says the reader is safe outside these cases; the finding says the opposite for provenance.
- No weights, conversion, model inference, GPU, provider request, attestation, proof generation, or second implementation of the reader. No H1/H2/H4 result is strengthened or weakened. The cross-check is this lane's own parsing of the fixture files, not an independent implementation of the leaf rule: it compares recorded hashes, it cannot check them against weights.
- The existing follow-ups (CI jobs for the two leaf-v2 suites, the CPU pin missing from the original run files) remain separate.
- Shared CPU host. Registered arms on cores 10-11 (`ENV.json`); the 2026-11-14 work on cores 12-13 (`runs/stoprule-20261114/env.json`). No timing or performance claim. Measured, unreplicated, not a public headline.
