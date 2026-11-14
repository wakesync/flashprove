# RESULTS: 20261114-203-leafv2-registered-pin

Issue #203 (part of #189 and #36). HASH LEVEL, NOT A PROOF. Measured, unreplicated.

## Verdict against the PREREG: PASS (registered mode), with the limits below

In `--registered` mode, all 23 stop-rule cases of PR #191 are refused (none gives `PASS`). The committed honest runs still give H3 `PASS` with basis `single-run`, in both default and registered mode. All 213 existing expectations that were not named as switches keep their outcome. The pin is a committed list. It is **not authentication**, and the default mode is unchanged, so the #189 stop rule is answered **only for evidence read in registered mode against the registered runs**, not in general.

## Round 2, 2026-11-14: registered mode reads each pinned file once (PREREG amendments A-1 to A-3)

Added after review round 1 of PR #205 (opus family, REQUEST CHANGES at `ed50eb617aa97f2cbce9b038845dfbc93320196e`: https://github.com/wakesync/flashprove/pull/205#issuecomment-6873645981). Measured, unreplicated. Hash level, not a proof. The verdict above is unchanged; the sections below this one describe the reviewed head and are kept, with their numbers, as they were.

**What the review found (a reviewer's descriptive finding, see the link; not evidence of this PR).** At the reviewed head, registered mode hashed each consumed file and then opened the same path again to parse it. The reviewer's probe P6 replaced run 3 between the check and the read and reports `PASS`, basis `single-run`, on the altered files. None of D1 to D12 covered that.

**What changed.** In registered mode each pinned file is now read exactly once. The SHA-256 is taken over those bytes and the same bytes are parsed. After that read, registered mode does not open, stat or list a pinned path again; whether a consumed file is present is decided by the checked set. The pin file is read once per invocation and the reported `pin_sha256` is the hash of the bytes that were parsed. Every place where a pinned path was opened, and what it does now:

| place (reviewed head) | pinned path | now, in registered mode |
|---|---|---|
| `wb_leafv2._pinned_file` | each pinned run file and compare file | the ONE read (`_read_once`); returns the bytes it hashed |
| `wb_leafv2._load` | `blocks.jsonl` (read), `run-meta.json` (exists, read) | parses the checked bytes; presence from the checked set |
| `wb_leafv2.load_leaves` | `leaves-v2.json` (read) | parses the checked bytes |
| `wb_leafv2._compare_runs` | `leaves-v2.json` (exists) | presence from the checked set |
| `wb_leafv2.compare_runs(registered=True)` | both runs, checked and then read again | `read_registered` once per run, then the comparison on those bytes |
| `summarise.load` | run directory and `leaves-v2.json` (exists), then the two loaders | the checked bytes of that run |
| `summarise.h3_block` | compare files (exists, read to parse, read to hash) | the checked bytes for all three |
| `summarise.h3_block` | each run pair checked again through `compare_runs` | `compare_registered` on the bytes already checked |
| `wb_leafv2.load_pin` + `pin_sha256` | the pin file, read twice | `read_pin`: one read, parsed and hashed |

Functions changed: `_load`, `load_leaves`, `_compare_runs`, `compare_runs`, `load_pin`, `_pinned_file`, `check_registered`, `check_registered_compare_files` and the `compare` command line in `wb_leafv2.py`; `load`, `h3_block`, `build`, `main` in `summarise.py`. New: `RegisteredRun`, `_read_once`, `read_pin`, `read_registered`, `read_registered_compare_files`, `compare_registered`, `summarise.usage_error`. `_load`, `load_leaves`, `_compare_runs`, `summarise.load` and `summarise.h3_block` are shared by both modes and now carry a branch for a registered read, so the default code path is no longer untouched text as it was at the reviewed head. That the default mode still behaves as on main is shown by measurement (the last row of the table below), not by the code being unchanged.

**Which receipts belong to which head.**

| head | files |
|---|---|
| reviewed head `ed50eb61` (code `6d13d303`) | `runs/evidence-tests-1.json`, `runs/evidence-tests-2.json`, `runs/analysis.json`, `runs/pin-repro.json`, `ENV.json`. Kept unchanged. |
| round 2 (amendments `5c1da10d`, code `e807e0ab`) | `runs/evidence-tests-r2-1.json`, `runs/evidence-tests-r2-2.json`, `runs/analysis-r2.json` (from `analyse_r2.py`), `runs/default-mode-main-suite-r2.json`, `ENV-r2.json`. |

The pin (`runs/registered-pins.json`) and `runs/summary-registered.json` are unchanged; `summarise.py --registered --check` exits 0 on the changed code, so the changed code reproduces the committed registered summary byte for byte.

**Numbers of round 2 (all from committed files).**

| what | value | file |
|---|---|---|
| suite expectations passed, run 1 | 361 of 361 over 145 cases | `runs/evidence-tests-r2-1.json` |
| suite expectations passed, run 2 | 361 of 361 over 145 cases, byte-identical to run 1 | `runs/evidence-tests-r2-2.json` |
| expectations of the reviewed head's receipt present unchanged, every field | 346 of 346 | `runs/analysis-r2.json` |
| new expectations | 15 (11 read-once, 4 command line) in 9 new cases | `runs/analysis-r2.json` |
| a pinned file changed just before its one read: refused | 7 of 7 | `runs/analysis-r2.json` (`read_once_changed_before_read`) |
| P6 as a case (run 3 swapped after the last read) | 4 of 4 expectations hold | `runs/analysis-r2.json` (`read_once_swapped_after_check`) |
| command-line refusals | 4 of 4, exit 2, nothing written | `runs/analysis-r2.json` |
| #191 cases refused by `summarise --registered` | 23 of 23, 0 `PASS` | `runs/analysis-r2.json` |
| main's non-switched expectations kept | 213 of 213 | `runs/analysis-r2.json` |
| defeat cases the suite holds | 11 (D1, D2, D4 to D12; D3 is the default-mode limit expectations) | `runs/analysis-r2.json` (`defeat_cases_in_suite`) |
| of those, full `PASS` on altered evidence in registered mode | 2 (D2, D4) | `runs/analysis-r2.json` |
| **default mode: main's own test file against the changed code** | 231 of 231, receipt **byte-identical** to main's committed receipt | `runs/default-mode-main-suite-r2.json` |

No spread: deterministic file reads, seeds none, two full runs in place of variance.

**The new cases.**
- R1 `pin203-r2-changed-before-read-*` (run 3 `blocks.jsonl`, `run-meta.json`, `leaves-v2.json`, and `compare-run1-run3.json`). Through the in-process seam `wb_leafv2._read_once`, the file is changed on disk after its file-type check and immediately before its single read. The changes are small: one timing field of one record, one metadata field the reader does not use, the same tree document in other formatting, one field dropped from the compare file. All 7 expectations are refused, and the reason recorded in the receipt is a `registered pin` hash mismatch that names the file, so the refusal comes from the hash of the bytes that were read. What the default mode does with these four changes is not in the receipts and is not claimed here.
- R2 `pin203-r2-P6-swapped-after-check`. After the last pinned file has been read, run 3 is replaced by forward-78-whole and its metadata, tree and cached compare file are removed. The registered summariser gives `PASS`, basis `single-run`, with output bytes equal to the committed `runs/summary-registered.json`, and each of the 10 pinned paths was read once; `compare --registered` gives `identical-complete`, equal field by field to the comparison of the committed files, with 6 reads. The altered directory read again from the start is refused by both.
- `pin203-r2-cli-*`: `compare A B --registered` with no output path, `compare A B out.json --registred`, `summarise.py --registred --runs DIR`, `summarise.py --runs --registered`: each exits 2 with a `USAGE:` message and writes no file.

**What this does and does not establish.** A registered result is now a statement about bytes that have the pinned SHA-256. It is a statement about the bytes at the moment they were read, not about what the directory holds afterwards: in R2 the directory is altered by the time the result is written, and the result is still the result of the registered bytes. The checks made by path before the read (run directory is not a symlink, file is a regular file and not a symlink) can still be raced; what cannot happen any more is parsing bytes that were not hashed. D2 (the pin is not authentication), D3 (default mode unchanged, answered only in registered mode, not in general) and D4 (unconsumed files are not checked) stand exactly as below. The read-once cases use an in-process seam; no test here uses a second process or a filesystem that returns different bytes per read.

## What was built

- `experiments/20261112-149-leaf-v2/runs/registered-pins.json` (new file, sha256 `1e15957a...`, 1,505 bytes). It holds the SHA-256 of `blocks.jsonl`, `run-meta.json` and `leaves-v2.json` for run 1 and run 3, `blocks.jsonl` and `run-meta.json` for run 2 (which has no stored tree), and both committed compare files. It is generated by `make_pins.py` from the committed files. `runs/pin-repro.json`: two separate runs of `make_pins.py --stdout` are byte-identical to each other and to the committed file.
- `research/weight-binding/wb_leafv2.py`: `load_pin`, `check_registered`, `check_registered_compare_files`, `compare_runs(a, b, registered=False)`, CLI `compare A B out.json --registered`. The pin is always read from the committed path. The only override is the module attribute `PIN_PATH`, a test seam with no command-line or environment form. The default code path is the main code, renamed `_compare_runs`, and nothing in it changed.
- `experiments/20261112-149-leaf-v2/summarise.py --registered`: checks all three runs and both compare files against the pin first, then adds `h3.overall.basis` and the `PASS-UNION` status, and writes the new file `runs/summary-registered.json`. Without the flag the output is byte-identical to main (`summarise.py --check` exit 0 against the unchanged committed `runs/summary.json`).
- `runs/summary-registered.json` on the committed files: H3 `PASS`, basis `single-run`, union 78 (8 controls, 70 changed), run 3 `identical-complete`, run 2 `identical-partial` 8 of 8.

## Numbers (all from committed files)

| what | value | file |
|---|---|---|
| suite expectations passed, run 1 | 346 of 346 over 136 cases | `runs/evidence-tests-1.json` |
| suite expectations passed, run 2 | 346 of 346 over 136 cases, byte-identical to run 1 | `runs/evidence-tests-2.json` |
| main's receipt (#191) | 231 of 231 over 82 cases | `experiments/20261113-189-missing-metadata/runs/evidence-tests-stoprule-20261114.json` |
| non-switched existing expectations kept unchanged | 213 of 213 | `runs/analysis.json` |
| switched expectations (named in the PREREG) | 18, all now `summarise-registered` refused | `runs/analysis.json` |
| #191 cases refused by `summarise --registered` | 23 of 23 | `runs/analysis.json` |
| #191 cases giving `PASS` in registered mode | 0 of 23 | `runs/analysis.json` |
| default-mode full `PASS` on the 13 altered inputs (unchanged, limit) | 13 of 13 | `runs/analysis.json` (`default_mode_full_pass_cases`) |
| defeat cases giving full `PASS` on altered evidence | 2 (D2, D4) | `runs/analysis.json` |

Variance: every check is a deterministic file read. There is no spread to report. In its place the suite was run twice end to end: identical outcomes, and the two receipts are byte-identical. Seeds: none.

New expectations: 115 (346 - 231). They are 18 `pin203-default-mode-limit-*`, 8 honest-registered, 70 for the 23 #191 cases (summarise, compare and CLI each, plus one extra for the run-2 control), and 19 for the defeat and `PASS-UNION` cases.

## Per case, registered mode (PREREG table A)

Every one of the 23 is refused by `summarise.py --registered` with a reason containing `registered pin`. `compare --registered` (in-process and command line, exit 2) refuses run 3 in 22 of them. In `control-run2-forward-meta-kept` run 3 is untouched: compare run 1 vs run 3 is `identical-complete` (exit 0) and compare run 1 vs run 2 is refused. All of these match the PREREG table: forward 77, 76, 71, 70, 69, 60, 39, 10, 1; forward-78-whole; run1-records-as-run3; run1-dir-as-run3-meta-kept; run1-dir-as-run3-no-meta; run1-first-70-as-run3; alternate-run1-run3-by-name; splice-run1-39-forward-run3-39-69; forward-77-meta-consistent; forward-70-meta-consistent; control-original-order-cut-last; control-original-cut-then-reversed; control-run2-records-as-run3; control-alternate-run1-run3-by-index; control-run2-forward-meta-kept. **PASS.**

B (switches): the 18 named `stop-rule-189-*` summarise expectations are now `summarise-registered` refused. Their compare and suite expectations (36) are unchanged in outcome and source text. **PASS.**

C (honest controls): 213 of 213 unchanged. These include `baseline` (default summary bytes equal the committed `summary.json`, `summarise.py --check` exit 0), `missing-meta-complete`, `compare-files-removed`, `run2-only` and `consistent-partial-77`. Test source: the only changed line in an existing case is the switched summarise call inside `stoprule_189.pin()`. Everything else is inserted (`git diff -U0` shows one removed line). **PASS.**

D (committed files, registered): `PASS`, basis `single-run`, union 78; compare run 3 `identical-complete`, run 2 `identical-partial`. **PASS.**

E (`PASS-UNION` reachable and not `PASS`): forward 77 with a seam pin of the altered fixture gives `PASS-UNION`, basis `union`, run 3 common 77, run 2 common 8, union 78. **PASS.**

F (pin reproducible): two runs byte-identical to the committed pin. **PASS.**

## Defeat cases (beyond #191's 23)

| case | outcome | as registered | reading |
|---|---|---|---|
| D1 pin in the fixture's runs dir regenerated together with a reordered run 3 | refused | yes | the reader uses the committed pin, not a file next to the runs |
| **D2 pin in the repository edited together with run 3 (seam)** | **`PASS`, single-run** | yes | **LIMIT: the pin is only as good as the repository history. Not authentication.** |
| **D3 the 13 altered inputs through the default mode** | **`PASS` (13 of 13)** | yes | **LIMIT: the default mode is unchanged by design. A reader that omits `--registered` gets main's behaviour** |
| **D4 extra unpinned files in run 3 (`notes.txt`, `blocks.jsonl.orig`)** | **`PASS`, single-run** | yes | **LIMIT (scope): files the readers do not consume are not checked. The consumed files are byte-identical, so the result is right for what is read** |
| D5 `blocks.jsonl` a symlink to identical bytes | refused (`symlink`) | yes | |
| D6 run 3 directory a symlink to an honest copy | refused (`symlink`) | yes | |
| D7 run 3 renamed `run4` | refused (summary: run3 missing; compare: `not a registered run`) | yes | |
| D8 run 1 and run 3 swapped by name | refused | yes | |
| D9 pin file absent (seam) | refused (`cannot read`) | yes | |
| D10 pinned compare files removed | registered refused; default `PASS` | yes | default unchanged |
| D11 `leaves-v2.json` added to run 2 (consumed, not pinned for run 2) | refused (`not pinned`) | yes | |
| D12 honest runs copied to another directory unchanged | `PASS`, single-run | yes | correct: identical bytes; the pin binds content, not location |

D2 and D4 are the defeat cases that still give a full `PASS` in registered mode. D3 gives `PASS` in default mode. All three were expected and registered as limits.

## What is NOT established

- **Not authentication.** The pin binds "registered run" to what the repository holds. Whoever can change the repository can change the pin together with a run (D2). The pin says nothing about how or when the runs were produced. Signatures, timestamps and attested runners are out of scope.
- **Not a general answer to the #189 stop rule.** The default mode still gives a full `PASS` to all 13 altered inputs, exactly as on main. The stop rule is answered only for evidence read with `--registered` against the three registered runs. Any new run is not in the pin and is refused in registered mode until a reviewed change adds it.
- Not exhaustive: 23 + 12 cases do not cover every input. Only consumed file names are checked (D4).
- No change to the conversion, the leaf, the tree, the opening verifier, or H1, H2, H4. No new run of the registered experiment, no weights, no model.
- The tests exercise readers, not conversion. They are run by hand; the missing leaf-v2 CI job is still a separate item.
- One implementation. The debug runs (honest copy and forward 50) are not part of the receipts.
- Measured, unreplicated. No public headline.

## Deviations from the PREREG

- PREREG Runs says "`summarise.py --registered` and `--check` once each". In practice `summarise.py --registered` was run once before the recorded suite runs, to generate the committed `runs/summary-registered.json` that the suite compares against. That run was on the honest committed files, which the PREREG lists as a debug fixture, not a registered case. `--check` (default) was run once before the code commit, as a debug check of the default path.
- `PIN_PATH` as a test seam and the in-process summariser reader (`summarise-registered (in-process, pin seam)`) are used for D2, D9 and E, as the PREREG says. D3 is not a separate case: it is the 18 `pin203-default-mode-limit-*` expectations.
- `analysis.json`'s `defeat_cases` map keeps one reader per case (the last one recorded). The full per-reader outcomes are in the receipts.

Added in round 2 (review round 1 of PR #205, link above):
- **18 limit expectations kept, 13 registered.** PREREG B says the 13 full-`PASS` default-mode outcomes stay visible as `pin203-default-mode-limit-*`. The suite keeps all 18 switched default-mode outcomes under that name: 13 `PASS`, 4 `PASS-SUBSET`, 1 `BELOW-COVERAGE` (`runs/analysis-r2.json`, `default_mode_limit_by_outcome`). Nothing main asserted is dropped, but 18 is not the registered 13.
- **D12 was in effect run during debugging.** A reviewer's descriptive finding (link above, item 6), not evidence of this PR: a debug run at 05:18:58Z, before the first recorded suite run, copied the committed runs into a temporary directory and ran `summarise --registered` on the copy ("honest copy registered"), which is in substance listed case D12. The PREREG's debugging clause allowed the honest committed files in place and a forward-50 fixture, not a listed case. The check is deterministic and the expected outcome was registered, so the reviewer does not see an effect on validity; it is a deviation all the same. The note above about the honest committed files in place does not cover it.
- **Defeat-case count.** The reviewed head's ledger row gave 2 of 12 defeat cases. The suite holds 11 defeat cases (D3 is not a case of its own). `runs/analysis-r2.json` writes the list and the count out, and the row now says 2 of 11.
- **PREREG header time.** Corrected by amendment A-3, not in the header.
- **Round 2 itself.** The code was changed after results existed, under amendments A-1 and A-2, written and committed before the change. Two names beyond those the amendment lists were added (`read_pin`, `compare_registered`). Debugging before the first recorded round-2 run was limited to syntax checks and the honest committed files in place (`summarise.py --check`, `summarise.py --registered --check`, in-process `compare_runs(..., registered=True)` on the committed run directories), as the amendment says; the forward-50 fixture was not used. The round-2 runs were not timed: `ENV-r2.json` gives bounds from log lines written before and after each run. Round 2 ran on cores 10-11, the reviewed head's runs on 14-15. After both recorded runs this lane also ran the default mode on the four R1 changes, on temporary copies, to check a sentence of its own draft; that result is in no committed file and nothing here rests on it.

## Raw data

Reviewed head: `runs/evidence-tests-1.json`, `runs/evidence-tests-2.json` (receipts), `runs/analysis.json` (from `analyse.py`), `runs/pin-repro.json` (from `repro_pins.py`), `../20261112-149-leaf-v2/runs/registered-pins.json`, `../20261112-149-leaf-v2/runs/summary-registered.json`.

Round 2: `runs/evidence-tests-r2-1.json`, `runs/evidence-tests-r2-2.json` (receipts), `runs/analysis-r2.json` (from `analyse_r2.py`), `runs/default-mode-main-suite-r2.json`, `ENV-r2.json`.

## Reproduce

The suite at the current code gives the round-2 receipt (361 expectations). `analyse.py` reads the reviewed head's committed receipts and still exits 0 on them.

```sh
taskset -c 10-11 python3 research/weight-binding/test_wb_leafv2_evidence.py "$(mktemp -d)/e.json"   # 361 / 361
python3 experiments/20261114-203-leafv2-registered-pin/analyse_r2.py                               # exit 0 (round 2)
python3 experiments/20261114-203-leafv2-registered-pin/analyse.py                                  # exit 0 (reviewed head's receipts)
python3 experiments/20261114-203-leafv2-registered-pin/repro_pins.py                               # exit 0
python3 experiments/20261112-149-leaf-v2/summarise.py --registered --check                          # exit 0
python3 experiments/20261112-149-leaf-v2/summarise.py --check                                       # exit 0
```
