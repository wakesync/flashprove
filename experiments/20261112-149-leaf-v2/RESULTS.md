# RESULTS: 20261112-149-leaf-v2 (issue #149, part of #36)

Conversion leaf v2 on real bytes for a registered subset: the 70 tensors PR #68 found different between the stock and abliterated Qwen3.8-27B pins, plus 8 byte-identical controls. CPU only, hash level, **not a proof**. Measured, unreplicated.

Code: `research/weight-binding/wb_leafv2.py` (runner, leaf v2, subset tree, `verify_opening_v2`), `test_wb_leafv2.py` (hostile suite), `run_leafv2.sh` (the run), all at e59442b, committed before any registered tensor was fetched. Reused unchanged by import: `wb_int.py` (`fetch`, `bf16_to_f32`, `to_int`: the matrix rule), `wb_conv.py` (`Conversion`, `leaf_obj` via `leaf_objs`, `_canon`, `leaf_well_formed`, `STEP_MATRIX`, `RULE_VERSION`), `wb_manifest.py` (`_h`, `_lp`, `_is_hex32`, `canonical_opening`, `tensors_from_stream`). What is added: the two leaf fields `e` and `int_sha256`, new domain tags `fp-wb-conv-leaf-v2` / `fp-wb-conv-node-v2` / `fp-wb-conv-subset-v2`, a v2 well-formedness check (`e` a plain int in [-64, 64], `int_sha256` 64 lowercase hex, then the v1 check on the rest), the opening verifier, and the 38-check suite. Summary: `experiments/20261112-149-leaf-v2/summarise.py` -> `runs/summary.json`.

## Verdict per hypothesis

| H | threshold | result | file |
|---|---|---|---|
| H1 inputs | 156 / 156 fetched tensors match #68's per-tensor sha256 | **PASS**: 156 / 156 in run 1; 16 / 16 in run 2; 156 / 156 in run 3 | `runs/run1/blocks.jsonl`, `runs/summary.json` (`h1_sha_matches_68`) |
| H2 pin separation | controls 8 / 8 identical in e_b and int_sha256_b; changed 70 / 70 differ in int_sha256_b | **PASS**: controls 8 / 8 identical (0 differing integers each); changed 70 / 70 differ; e_b equal across pins for all 70 changed tensors | `runs/summary.json` (`h2_*`), `runs/run1/blocks.jsonl` |
| H3 determinism | run 2 byte-identical on every block it covers; all 78 blocks (or at least 10 per pin incl. 2 controls and 5 changed) | **PASS** (via the registered run 3, PREREG A-1 / A-2): run 3 (fresh process, fresh fetch, reversed order) covered 78 / 78 blocks of both pins and all 78 are byte-identical to run 1 (8 controls, 70 changed); subset roots and subset ids equal for both pins; `leaves-v2.json` sha256 equal. Union of run 2 and run 3 = 78 / 78 blocks, all identical (run 2 alone: 8 / 8, below coverage, stopped at the 21 GB disk floor). See "Run 3" below | `runs/compare-run1-run3.json`, `runs/compare-run1-run2.json`, `runs/summary.json` (`h3`), PREREG A-1, A-2 |
| H4 hostile leaves | 100% hostile refused, >= 10 kinds on the new fields; 78 / 78 honest; 70 / 70 abliterated leaves refused under the stock id | **PASS**: 38 / 38 checks: 78 / 78 honest stock openings verify (and 78 / 78 abliterated under the abliterated id); 70 / 70 abliterated leaves refused under the stock subset id; 8 / 8 control leaves identical across pins and accepted; 15 kinds on the new fields (13 on all 78 blocks, 2 on the 70 changed), 8 #100 mutation kinds on all 78 v2 leaves, 10 opening-level cases including a v1 leaf and a v1 conversion-id opening under the v2 id; the suite ran twice with byte-identical JSON | `runs/run1/tests-1.json`, `tests-2.json`, `sha256.txt` |

## Numbers (run 1, measured, unreplicated)

- Subset ids (78 blocks): stock `d502ce1133396fafed2606c306de67c75c3c33de9101155d3444e6e94d7b5230`, abliterated `2808edc948f4b81cfb96b1a9b0201ab84d617ef83731e83cc0c4b12357311887` (`runs/run1/leaves-v2.json`, roots `82a9f1b2...` and `b8af6e0a...`). These are not model conversion ids.
- Exponents: e_b in {11, 12, 13, 14}; equal across pins for all 78 blocks. Changed: 51 at e = 12, 9 at 13, 8 at 11, 2 at 14.
- Fraction of int16 entries differing, changed tensors (n = 70): median 0.458, SD 0.080, min 0.304 (L38 linear_attn.out_proj), max 0.679 (L17 mlp.down_proj). Per family: down_proj (n = 35) median 0.399, min 0.381, max 0.679; linear_attn.out_proj (n = 26) median 0.467, min 0.304, max 0.497; self_attn.o_proj (n = 9) median 0.480, min 0.319, max 0.618.
- Differing entries per changed tensor (n = 70): median 26,717,020, min 9,548,760, max 60,499,880.
- Max |integer delta| at the same index: down_proj median 36 (min 20, max 155); out_proj median 37 (18 to 115); o_proj median 36 (15 to 76). The integer range is [-4095, 4095].
- No changed tensor has identical integers (the negative result the issue names did not occur for any of the 70).
- Cost: run 1 fetched and converted 156 tensors (about 8.8 GB per pin) in 891 s wall; fetch per tensor median 0.885 s (min 0.48, max 1.77, n = 156), conversion + hash median 4.13 s (min 0.94, max 18.87, n = 156); peak RSS 2.18 GB; nothing written to disk except the run files (KB). Shared host, timings are not a benchmark.
- Cross-check (not registered, descriptive): PR #87's committed `runs/h2h3-int.json` has e, int_sha256 and differing-entry counts for 7 of these tensors (6 changed + L16 down_proj); all 7 equal run 1's (`runs/summary.json` `crosscheck_pr87`). Same code path, different process and day, so it is a third run on those 7, not an independent implementation.

## Run 3

First lane (to 22:43Z): not run. PREREG A-1's start condition (free disk at least 22 GB before 2026-11-13T00:00Z) was not met while that lane watched: free disk went 21.6 GB (22:28Z), 18.2 GB (22:32Z), 16.3 GB (22:36Z), 12.9 GB (22:40Z), 11.5 GB (22:43Z), from other work on the shared host.

Successor lane (leafv2149r3): **run, complete**. Disk was freed on the host; free disk 36.6 GB at run start (A-1 condition met, before 00:00Z). Amendment A-2 (commit 482a6fc, pushed before the run) records the only difference: CPU pin `taskset -c 2-7` instead of `12-15`. Code under `research/weight-binding/` unchanged since e59442b.

- Command: `fp-heavy.sh taskset -c 2-7 bash research/weight-binding/run_leafv2.sh experiments/20261112-149-leaf-v2/runs/run3 --reverse --budget-s 2400`; slot granted 22:56:48Z, finished 23:15:45Z; 78 / 78 blocks, not stopped; 1,134.7 s wall (budget 2,400 s); peak RSS 2.18 GB; free disk 36.6 GB at start, 34.8 GB at end, minimum 35.0 GB at a per-tensor check (`runs/run3/run-meta.json`, `runs/summary.json` `run3`).
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
- Run 3 was executed by a successor lane on cores 2-7 instead of the registered 12-15 (PREREG amendment A-2, committed and pushed before run 3 started). Nothing else differs from A-1.
- The first pushes of this branch (e59442b, 502d77b) ran the host-path guard before push but ran `update-results.py --check` and `check-claims.py` only after the 502d77b push (both exit 0; results.yaml was unchanged at that point).
