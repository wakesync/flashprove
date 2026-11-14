# RESULTS: 20261112-149-leaf-v2 (issue #149, part of #36)

Conversion leaf v2 on real bytes for a registered subset: the 70 tensors PR #68 found different between the stock and abliterated Qwen3.8-27B pins, plus 8 byte-identical controls. CPU only, hash level, **not a proof**. Measured, unreplicated.

Code: `research/weight-binding/wb_leafv2.py` (runner, leaf v2, subset tree, `verify_opening_v2`), `test_wb_leafv2.py` (hostile suite), `run_leafv2.sh` (the run), all at e59442b, committed before any registered tensor was fetched. Reused unchanged by import: `wb_int.py` (`fetch`, `bf16_to_f32`, `to_int`: the matrix rule), `wb_conv.py` (`Conversion`, `leaf_obj` via `leaf_objs`, `_canon`, `leaf_well_formed`, `STEP_MATRIX`, `RULE_VERSION`), `wb_manifest.py` (`_h`, `_lp`, `_is_hex32`, `canonical_opening`, `tensors_from_stream`). What is added: the two leaf fields `e` and `int_sha256`, new domain tags `fp-wb-conv-leaf-v2` / `fp-wb-conv-node-v2` / `fp-wb-conv-subset-v2`, a v2 well-formedness check (`e` a plain int in [-64, 64], `int_sha256` 64 lowercase hex, then the v1 check on the rest), the opening verifier, and the 38-check suite. Summary: `experiments/20261112-149-leaf-v2/summarise.py` -> `runs/summary.json`.

After review round 1 of PR #151 (2026-11-13, PREREG A-3) the code that reads the committed run files was changed: one validated loader, the H3 comparison on canonical leaf JSON and rebuilt trees, an explicit overall H3 status, and regression tests. The conversion, the leaf, the tree and the verifier are as at e59442b, no run file was modified and no number below changed, except three unit statements the reviewers showed wrong. See "Review round 1" at the end.

## Verdict per hypothesis

| H | threshold | result | file |
|---|---|---|---|
| H1 inputs | 156 / 156 fetched tensors match #68's per-tensor sha256 | **PASS**: 156 / 156 in run 1; 16 / 16 in run 2; 156 / 156 in run 3 | `runs/run1/blocks.jsonl`, `runs/summary.json` (`h1_sha_matches_68`) |
| H2 pin separation | controls 8 / 8 identical in e_b and int_sha256_b; changed 70 / 70 differ in int_sha256_b | **PASS**: controls 8 / 8 identical (0 differing integers each); changed 70 / 70 differ; e_b equal across pins for all 70 changed tensors | `runs/summary.json` (`h2_*`), `runs/run1/blocks.jsonl` |
| H3 determinism | run 2 byte-identical on every block it covers; all 78 blocks (or at least 10 per pin incl. 2 controls and 5 changed) | **PASS** (via the registered run 3, PREREG A-1 / A-2): run 3 (fresh process, fresh fetch, reversed order) covered 78 / 78 blocks of both pins and all 78 are byte-identical to run 1 (8 controls, 70 changed); subset roots and subset ids equal for both pins; `leaves-v2.json` sha256 equal. Union of run 2 and run 3 = 78 / 78 blocks, all identical (run 2 alone: 8 / 8, below coverage, stopped at the 21 GB disk floor). See "Run 3" below | `runs/compare-run1-run3.json`, `runs/compare-run1-run2.json`, `runs/summary.json` (`h3`, with the explicit result in `h3.overall.status`), PREREG A-1, A-2 |
| H4 hostile leaves | 100% hostile refused, >= 10 kinds on the new fields; 78 / 78 honest; 70 / 70 abliterated leaves refused under the stock id | **PASS**: 38 / 38 checks: 78 / 78 honest stock openings verify (and 78 / 78 abliterated under the abliterated id); 70 / 70 abliterated leaves refused under the stock subset id; 8 / 8 control leaves identical across pins and accepted; 15 kinds on the new fields (13 on all 78 blocks, 2 on the 70 changed), 8 #100 mutation kinds on all 78 v2 leaves, 10 opening-level cases including a v1 leaf and a v1 conversion-id opening under the v2 id; the suite ran twice with byte-identical JSON | `runs/run1/tests-1.json`, `tests-2.json`, `sha256.txt` |

## Numbers (run 1, measured, unreplicated)

- Subset ids (78 blocks): stock `d502ce1133396fafed2606c306de67c75c3c33de9101155d3444e6e94d7b5230`, abliterated `2808edc948f4b81cfb96b1a9b0201ab84d617ef83731e83cc0c4b12357311887` (`runs/run1/leaves-v2.json`, roots `82a9f1b2...` and `b8af6e0a...`). These are not model conversion ids.
- Exponents: e_b in {11, 12, 13, 14}; equal across pins for all 78 blocks. Changed: 51 at e = 12, 9 at 13, 8 at 11, 2 at 14.
- Fraction of int16 entries differing, changed tensors (n = 70): median 0.458, SD 0.080, min 0.304 (L38 linear_attn.out_proj), max 0.679 (L17 mlp.down_proj). Per family: down_proj (n = 35) median 0.399, min 0.381, max 0.679; linear_attn.out_proj (n = 26) median 0.467, min 0.304, max 0.497; self_attn.o_proj (n = 9) median 0.480, min 0.319, max 0.618.
- Differing entries per changed tensor (n = 70): median 26,717,020, min 9,548,760, max 60,499,880.
- Max |integer delta| at the same index: down_proj median 36 (min 20, max 155); out_proj median 37 (18 to 115); o_proj median 36 (15 to 76). The integer range is [-4095, 4095].
- No changed tensor has identical integers (the negative result the issue names did not occur for any of the 70).
- Cost: run 1 fetched and converted 156 tensors (9,405,726,720 BF16 bytes per pin: 9.41 GB, 8.76 GiB) in 891 s wall; fetch per tensor median 0.885 s (min 0.48, max 1.77, n = 156), conversion + hash median 4.13 s (min 0.94, max 18.87, n = 156); peak RSS 2,176,528 KiB (2.08 GiB, 2.23 GB); nothing written to disk except the run files (KB). Shared host, timings are not a benchmark. Runs 1 and 2 were pinned with `taskset -c 12-15` (PREREG Runs, ENV.json); that pin is not recorded in a run file (`run.time` shows only the inner python command).
- Cross-check (not registered, descriptive): PR #87's committed `runs/h2h3-int.json` has e, int_sha256 and differing-entry counts for 7 of these tensors (6 changed + L16 down_proj); all 7 equal run 1's (`runs/summary.json` `crosscheck_pr87`). Same code path, different process and day, so it is a third run on those 7, not an independent implementation.

## Run 3

First lane (to 22:43Z): not run. PREREG A-1's start condition (free disk at least 22 GB before 2026-11-13T00:00Z) was not met while that lane watched: free disk went 21.6 GB (22:28Z), 18.2 GB (22:32Z), 16.3 GB (22:36Z), 12.9 GB (22:40Z), 11.5 GB (22:43Z), from other work on the shared host.

Successor lane (leafv2149r3): **run, complete**. Disk was freed on the host; free disk 36.6 GB at run start (A-1 condition met, before 00:00Z). Amendment A-2 (commit 482a6fc, pushed before the run) records the only difference: CPU pin `taskset -c 2-7` instead of `12-15`. Code under `research/weight-binding/` unchanged since e59442b.

- Command: `fp-heavy.sh taskset -c 2-7 bash research/weight-binding/run_leafv2.sh experiments/20261112-149-leaf-v2/runs/run3 --reverse --budget-s 2400`; slot granted 22:56:48Z, finished 23:15:45Z; 78 / 78 blocks, not stopped; 1,134.7 s wall (budget 2,400 s); peak RSS 2,176,316 KiB (2.08 GiB, 2.23 GB); free disk 36.6 GB at start, 34.8 GB at end, minimum 35.0 GB at a per-tensor check (decimal GB; `runs/run3/run-meta.json`, `runs/summary.json` `run3`).
- H1 on run 3: 156 / 156 fetched tensors match #68. H2 reproduced: controls 8 / 8 identical, changed 70 / 70 differ in int_sha256_b, e_b equal 70 / 70; fraction differing median 0.458, SD 0.080, min 0.304, max 0.679 (n = 70), identical to run 1.
- Compare (`python3 research/weight-binding/wb_leafv2.py compare .../run1 .../run3 .../compare-run1-run3.json`): 78 common blocks, 78 identical (8 controls, 70 changed); roots equal (stock, abl); ids equal (stock `d502ce11...`, abl `2808edc9...`); `leaves-v2.json` file sha256 equal (`11eb2f98...`).
- The hostile suite also ran twice on run 3's output (run_leafv2.sh does this when 78 blocks complete): 38 / 38 both times, and both JSONs have the same sha256 as run 1's (`bf509cf3...`, `runs/run3/sha256.txt`).
- Timing (shared host, not a benchmark): fetch median 0.875 s per tensor (min 0.48, max 2.35, n = 156), conversion + hash median 4.29 s (min 1.79, max 13.45, n = 156).
- Union per A-1: run 2 (8 blocks) and run 3 (78 blocks) each vs run 1: 78 / 78 blocks covered, all identical. Run 2's 8 blocks have three passes.

## What is and is not established

Established (measured, unreplicated, hash level): for the 70 changed tensors and 8 controls, the executable matrix rule on the pinned bytes gives an exponent and an integer hash per block; the pins separate exactly where #68's per-tensor diff says (70 / 70 changed differ in integers, 8 / 8 controls identical); a leaf v2 carrying both fields is bound into a subset tree whose opening verifier refuses every constructed hostile opening, including wrong or swapped e_b / int_sha256_b and the other pin's values; the rule gave byte-identical results across two full runs of all 78 blocks of both pins (run 1 and run 3, opposite orders, separate processes and fetches), a third pass on 8 of them (run 2), and on PR #87's 7.

Not established:
1. **Determinism beyond this host and stack.** Run 1 and run 3 used the same host type, Python 3.12.3 and numpy 2.4.3, and the same code. Agreement on another CPU, numpy version or operating system is not measured. n = 2 runs per block (3 on 8 blocks).
2. **The other block classes.** Norm-folded matrices (368 blocks, including q/k/v, in_proj and gate/up), lm_head with the final norm, the embedding, and the 224 weight cells have no e_b / int_sha256_b. Their rule steps (`STEP_FOLDED`, `STEP_CA`, ...) are still text only.
3. **The full tree.** The subset id is not a conversion id for the model; the 722-block leaf-v2 tree for a pin (55.6 GB per pin) is not built.
4. **Binding to a proof.** Nothing here ties a commitment or proof to these integers (no `cp_commit`, no key-file change). int_sha256_b tells a verifier which integers the rule produces from the public pin; it does not show which integers a prover used.
5. **U1 margin.** That the two pins differ in 30% to 68% of integers per changed tensor says nothing yet about whether the output difference exceeds the integer lowering error (PR #139's U1 margin is the relevant result there).
6. **Implementation independence.** One implementation (wb_int's rule); no second implementation or language has reproduced the hashes.

## Deviations
- Run 2 stopped at 8 blocks (registered disk floor), below the H3 subset minimum of 10. Disclosed above and in PREREG amendment A-1 (committed after run 2, before any further fetch).
- The run 2 files were committed (371f80e, 22:28:26Z) before amendment A-1 existed in the tree: that commit's message names A-1, but PREREG.md was not staged in it, and A-1 landed alone in 48025d0 (22:32:16Z). Run 2 is governed by the original Runs line, not by A-1. A-1 registers run 3 and the union rule, and it was committed and pushed before run 3's slot (22:56:48Z) and before any fetch after run 2. ENV.json `commits.run2` said until this fix that 371f80e carried A-1; that was wrong and is corrected, with the A-1 commit recorded as `prereg_amendment_a1`.
- Run 3 was executed by a successor lane on cores 2-7 instead of the registered 12-15 (PREREG amendment A-2, committed and pushed before run 3 started). Nothing else differs from A-1.
- The first pushes of this branch (e59442b, 502d77b) ran the host-path guard before push but ran `update-results.py --check` and `check-claims.py` only after the 502d77b push (both exit 0; results.yaml was unchanged at that point).
- (Review fix) PREREG amendment A-3 was written after the reader changes had been drafted in the fix lane's working tree, and says so; it is committed alone (79e3eea) before them (00378cb). No registered run depends on it.
- (Review fix) The first complete run of the new regression tests gave 156 / 162. All six misses were refusals: the loader refused the altered copy, but with the record-field message instead of the `e_equal` message the test names. The two checks in the loader were reordered so the more specific message comes first; the test expectations were not edited. The three runs after that gave 162 / 162 with byte-identical JSON.

## Review round 1 (2026-11-13, PREREG A-3)

Both reviewers reproduced every number above from the committed files and found no mismatch between the honest runs. They asked for changes to how the run files are read, and to some statements. No tensor was fetched or converted again and no registered run was repeated.

What was wrong in the readers at 738ec96 (found by the reviewers on altered copies; the committed files have no such defect):
- `load_records` kept the last record per block name. A duplicated record, identical or contradictory, disappeared silently: `compare` reported 78 / 78 and the hostile suite 38 / 38.
- `compare` compared three record fields and the stored root and id strings. A stored `leaves-v2.json` with one changed leaf, or two swapped leaves, changed only the file-hash flag, and `summarise.py` did not read that flag, so its H3 union still said all identical.
- `summarise.py` read the committed compare files as a cache. With a truncated stored tree `compare` refused, but the summary still reported the earlier successful H3.

What changed (commit 00378cb; `research/weight-binding/README.md` has the details):
- One validated loader for `blocks.jsonl`, used by `tree`, `compare`, the hostile suite and `summarise.py`. It refuses duplicates (identical ones too), names outside the registered 78, wrong kinds, malformed fields, derived flags that do not follow from the record or from #68's hash and shape, a record order that is not a prefix of the registered order or its reverse, and a count or order that disagrees with `run-meta.json`.
- A stored `leaves-v2.json` is accepted only if it is byte for byte the tree rebuilt from the validated records.
- `compare` compares the canonical leaf-v2 JSON per block and pin (the H3 metric as registered) and the fetched-bytes hash, and computes root and id equality on rebuilt trees.
- `summarise.py` recomputes H3 from the run files. Each committed compare file must agree with the recomputation on every field it has. `h3.overall.status` is the explicit result: PASS, PASS-SUBSET, BELOW-COVERAGE or FAIL.
- Run 2 stays what it was: a legitimate partial run, 8 / 8 identical, below coverage on its own.

Effect on the committed evidence:
- `runs/run1`, `runs/run2`, `runs/run3` and both `runs/compare-run1-*.json`: not modified. The new `compare` reproduces every field of both committed compare files; `tree` rebuilds both committed `leaves-v2.json` files byte-equal; the hostile suite's JSON keeps its sha256 (`bf509cf3...`).
- `runs/summary.json` was regenerated. No value it had changed and nothing was removed. Added: `h3.overall` (status PASS), and `inputs` and `status` under `h3.run2` (identical-partial) and `h3.run3` (identical-complete). `summarise.py --check` compares the committed file with a fresh recomputation.

Regression tests (`research/weight-binding/test_wb_leafv2_evidence.py`, receipt `runs-fix151/evidence-tests.json`): 162 / 162 expectations over 59 cases, three runs with byte-identical JSON. Each case alters a temporary copy of the committed run files and asks `compare`, the hostile suite and `summarise.py` what they make of it; an altered copy that any of them accepts as the passing result is a failure. Covered: both reviewers' cases (identical duplicate, conflicting duplicate before and after the honest record, stored leaf hash flip, stored leaves swapped, stored leaf e + 1, block dropped, payloads swapped, record hash flip, control e + 1, truncated tree file, truncated records, line order changed) and related ones (edited compare files, a compare file without its run, wrong kinds, unknown names, flipped flags, an edited `run-meta.json`). Where an altered run is made self-consistent again (tree and compare file rebuilt from the altered records), the readers accept it as evidence and report the difference from run 1: `compare` status mismatch with 77 / 78, summary status FAIL.

Statements corrected (the measurements are unchanged):
- "about 8.8 GB per pin" was GiB: the 78 tensors are 9,405,726,720 bytes per pin, 9.41 GB or 8.76 GiB.
- "peak RSS 2.18 GB" read a KiB counter as decimal kB: 2,176,528 KiB is 2.08 GiB or 2.23 GB (run 3: 2,176,316 KiB). Corrected here, in the `run3_wall_seconds` note in results.yaml and in ENV.json.
- The ledger summary said the tree "refuses 38 of 38 hostile and honest checks". Honest openings are accepted. It now says the suite passes 38 of 38 checks, hostile openings refused and honest ones accepted.
- ENV.json `commits.run2` (see Deviations).

Limits of the fix:
- The loader checks what the committed files determine. It cannot check `e` or `int_sha256` against the weights; that needs the bytes. A record altered consistently (its flags, its stored tree and its compare file all rebuilt) is accepted as a record, and is caught only because it then differs from run 1. Someone who rewrites every run the same way is not caught by any of this; the defence there is a re-run from the public pins.
- The order check is stricter than the reviewers asked: a `blocks.jsonl` whose lines are reordered with their content unchanged is now refused, where one reviewer expected it to compare as identical.
- The new tests exercise the readers, not the conversion. They are not a second implementation of the rule and add nothing to H1, H2 or H4.
- Not done, left as follow-up: binding the CPU pin of runs 1 and 2 into a run file (it cannot be added to committed run files; it is in the PREREG and ENV.json), and a continuous-integration job for the two leaf-v2 test files (they are run by hand; the commands are in `research/weight-binding/README.md`).

## Limits addendum, 2026-11-13: missing metadata (issue #189)

This append-only clarification does not change any text, registered result, or run file above. The reader's behavior is unchanged. The motivating finding is the [PR #151 after-merge auditor's observation](https://github.com/wakesync/flashprove/pull/151#issuecomment-6863785743); the following measurements are this follow-up's independent fixture reproduction, not numbers borrowed from the audit.

**Corrected 2026-11-14, before merge.** As first written, this addendum said the metadata-free cut was "never full `PASS`" and recommended requiring metadata as the remedy. Review of PR #191 found inputs for which a truncated, reordered or substituted run 3 does get a full H3 `PASS`. The bullets below are true for the inputs they name and are now worded that way; the finding, and the updated recommendation, are in the next addendum.

`run-meta.json` is optional in `wb_leafv2._load`. When absent, recorded completion (`done`, `n_registered`, `stopped`) and direction (`reverse`) are unchecked. The reader still validates block identities, fields, uniqueness, and that file order is a prefix of the registered order or its reverse. Accepting an ordered prefix therefore does **not** show that it came from a registered stopped run. Removing metadata from an otherwise complete run can still give H3 `PASS`; that status checks coverage and agreement of the supplied records, not provenance or the existence of completion metadata.

Independent scratch-copy fixtures, registered before code in `experiments/20261113-189-missing-metadata/PREREG.md`, give the following in each of five deterministic replays (measured, unreplicated):
- Run 3 with its final complete line cut and its metadata, stored tree and cached comparison removed: `identical-partial`, 77 common and identical blocks; recomputed H3 `PASS-SUBSET`, not a full `PASS`, for this input: the cut is taken in run 3's original (reverse) order, and the block it drops is one that run 2 does not hold. A cut taken in forward order behaves differently (next addendum).
- The same cut with original metadata retained (tree/cache removed): both readers refuse on the metadata count. With original stored tree retained instead (metadata/cache removed): both refuse an incomplete run next to a stored tree.
- Noncanonical line reordering without metadata/tree/cache: both refuse record order.
- Complete run 3 with only metadata removed: `identical-complete` and H3 `PASS`, like the unchanged baseline.

Receipts: `experiments/20261113-189-missing-metadata/runs/registered/summary.json` and its per-repetition JSON files, with before/after source hashes. The extended evidence suite receipt is `experiments/20261113-189-missing-metadata/runs/evidence-tests.json`. The missing-metadata cases document a boundary, not a new proof, new conversion, or independent validation of integer hashes against weights.

**Recommendation (not implemented; updated in the next addendum, which finds it necessary but not sufficient): require metadata by default for evidence presented as a registered run.** Its small compatibility cost is preferable to silently losing the completion/direction checks while retaining a success-like label. If metadata-free exploratory comparison remains useful, it should be explicit and visibly distinct from registered evidence, not an implicit fallback. Requiring metadata would check consistency, not authenticate metadata or prove provenance: an attacker can rewrite metadata too. Any behavior change needs its own dated PREREG amendment and review. The CI-job and historical CPU-pin follow-ups remain outside this issue.

## Limits addendum, 2026-11-14: the issue #189 stop rule fired (blocking finding)

Appended; nothing above the 2026-11-13 addendum changes, and that addendum changes only as its own correction note says. No registered result, run file, reader or summariser changes. H1 to H4 above are not re-opened: on the committed files run 3 alone is `identical-complete` against run 1 on all 78 blocks, so the committed H3 result does not depend on what follows.

**Finding (measured, unreplicated).** Issue #189's stop rule says: if any truncated or reordered run reports a full PASS, stop and report. Both reviewers of PR #191 found such inputs ([first review](https://github.com/wakesync/flashprove/pull/191#issuecomment-6866086584), [second review](https://github.com/wakesync/flashprove/pull/191#issuecomment-6867478542)), and the follow-up lane reproduced every one with its own script, registered beforehand in amendment A-1 of `experiments/20261113-189-missing-metadata/PREREG.md`: 23 cases, five replays each, 115 of 115 as registered. With run 3's metadata, stored tree and cached comparison removed, each of these gives H3 `PASS` from the unchanged reader and summariser, in every replay:

- Run 3's lines put into forward registered order and cut to 77, 76, 71 or 70 lines (comparator `identical-partial`; union 78). At 69 lines the union is 77 and the status is `PASS-SUBSET`.
- The whole of run 3 put into forward order (`identical-complete`).
- Run 1's records in place of run 3's, or run 1's whole directory in place of run 3's with its own metadata kept or removed (`identical-complete`); run 1's first 70 lines in place of run 3's (`identical-partial`, union 78).
- Records taken alternately from run 1 and run 3 by block name; run 1's first 39 lines followed by forward run 3 lines 39 to 69.
- The forward 77 and forward 70 cuts **with** a `run-meta.json` edited to agree (`done`, `reverse` false, `stopped` set).

**Why.** Two properties of the readers described above combine. Without `run-meta.json` the loader accepts a prefix of either canonical order. And `h3.overall` is computed on the union of run 2 and run 3 (amendment A-1 of this experiment's PREREG): run 2 is a legitimate stopped run holding the last 8 blocks of the forward order, so any run 3 holding the first 70 or more is completed to 78. Separately, no record says which run produced it, so run 1's records are accepted as run 3 and H3 then compares run 1 with itself.

**What it is and is not.** Three notions need to be kept apart: per-comparison coverage (the comparator reports the cut inputs correctly, as `identical-partial` with their true counts), union coverage (what `h3.overall` reports), and registered-run provenance (that `run3/` is a complete, independent run executed as registered). The finding is real union coverage from run 2 plus provenance that cannot be checked. It is not invented block coverage and not a false hash match: the lane's own cross-check of the fixture files found, in all 115 replays, that every block counted is present in the supplied files and that every block reported identical has equal `e`, `int_sha256` and fetched-bytes `sha256`.

**Limit, stated plainly.** H3 `PASS` from these readers means: the supplied record files agree with run 1 on every block they cover, and together they cover all 78. It does not mean that a second complete run took place, that the files are the registered runs, or that they were not cut, reordered or copied from run 1. The H3 result above rests on the committed files and their history, not on the label.

Receipts: `experiments/20261113-189-missing-metadata/runs/stoprule-20261114/summary.json` and its per-replay files; the evidence suite with 18 cases that pin this current behaviour as a known finding, not as a contract (231 of 231 expectations over 82 cases), `experiments/20261113-189-missing-metadata/runs/evidence-tests-stoprule-20261114.json`. Full table and limits: `experiments/20261113-189-missing-metadata/RESULTS.md`.

**Recommendation, updated (nothing implemented; each item needs its own dated registration and review).** Refusing a missing `run-meta.json` for registered evidence is still recommended, because the either-direction ambiguity is what lets a forward cut line up with run 2. It is not sufficient: metadata edited to agree, and run 1's directory with its own untouched metadata, still give a full `PASS`, so requiring metadata checks consistency and does not authenticate provenance. Two further changes address what metadata cannot: make a `PASS` assembled from the union visibly different from one where a single compared run covers all 78 blocks, and bind run identity to something outside the run directory (for example a committed pin of each registered run's file hashes, which every case above would fail). None of these is cryptographic authentication. The stop rule remains open until such a change is registered, reviewed and measured.
