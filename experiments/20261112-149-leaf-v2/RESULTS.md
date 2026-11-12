# RESULTS: 20261112-149-leaf-v2 (issue #149, part of #36)

Conversion leaf v2 on real bytes for a registered subset: the 70 tensors PR #68 found different between the stock and abliterated Qwen3.8-27B pins, plus 8 byte-identical controls. CPU only, hash level, **not a proof**. Measured, unreplicated.

Code: `research/weight-binding/wb_leafv2.py` (runner, leaf v2, subset tree, `verify_opening_v2`), `test_wb_leafv2.py` (hostile suite), `run_leafv2.sh` (the run), all at e59442b, committed before any registered tensor was fetched. Reused unchanged by import: `wb_int.py` (`fetch`, `bf16_to_f32`, `to_int`: the matrix rule), `wb_conv.py` (`Conversion`, `leaf_obj` via `leaf_objs`, `_canon`, `leaf_well_formed`, `STEP_MATRIX`, `RULE_VERSION`), `wb_manifest.py` (`_h`, `_lp`, `_is_hex32`, `canonical_opening`, `tensors_from_stream`). What is added: the two leaf fields `e` and `int_sha256`, new domain tags `fp-wb-conv-leaf-v2` / `fp-wb-conv-node-v2` / `fp-wb-conv-subset-v2`, a v2 well-formedness check (`e` a plain int in [-64, 64], `int_sha256` 64 lowercase hex, then the v1 check on the rest), the opening verifier, and the 38-check suite. Summary: `experiments/20261112-149-leaf-v2/summarise.py` -> `runs/summary.json`.

## Verdict per hypothesis

| H | threshold | result | file |
|---|---|---|---|
| H1 inputs | 156 / 156 fetched tensors match #68's per-tensor sha256 | **PASS**: 156 / 156 in run 1; 16 / 16 in run 2 | `runs/run1/blocks.jsonl`, `runs/summary.json` (`h1_sha_matches_68`) |
| H2 pin separation | controls 8 / 8 identical in e_b and int_sha256_b; changed 70 / 70 differ in int_sha256_b | **PASS**: controls 8 / 8 identical (0 differing integers each); changed 70 / 70 differ; e_b equal across pins for all 70 changed tensors | `runs/summary.json` (`h2_*`), `runs/run1/blocks.jsonl` |
| H3 determinism | run 2 byte-identical on every block it covers; all 78 blocks (or at least 10 per pin incl. 2 controls and 5 changed) | **BELOW REGISTERED COVERAGE (not PASS)** at the time of writing: run 2 stopped after 8 blocks at the registered 21 GB free-disk floor (host disk consumed by other work); 8 / 8 blocks identical to run 1 (4 controls, 4 changed; sha256, e, int_sha256 for both pins = 16 tensor conversions). Amendment A-1 registers a run 3 if disk recovers; see "Run 3" below | `runs/compare-run1-run2.json`, `runs/run2/run-meta.json`, PREREG A-1 |
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

**Not run.** PREREG A-1's start condition (free disk at least 22 GB before 2026-11-13T00:00Z) was never met while the lane watched: free disk went 21.6 GB (22:28Z), 18.2 GB (22:32Z), 16.3 GB (22:36Z), 12.9 GB (22:40Z), 11.5 GB (22:43Z). Other work on the shared host was using the space. The lane stopped watching at 22:43Z with the disk still falling. H3 therefore stays at run 2's 8 blocks, below the registered coverage, as A-1 says. Running run 3 (`bash research/weight-binding/run_leafv2.sh <fresh dir> --reverse`, then `wb_leafv2.py compare`) on a host with free disk is the cheapest way to close H3 (about 15 minutes, about 2.2 GB RAM, nothing kept on disk).

## What is and is not established

Established (measured, unreplicated, hash level): for the 70 changed tensors and 8 controls, the executable matrix rule on the pinned bytes gives an exponent and an integer hash per block; the pins separate exactly where #68's per-tensor diff says (70 / 70 changed differ in integers, 8 / 8 controls identical); a leaf v2 carrying both fields is bound into a subset tree whose opening verifier refuses every constructed hostile opening, including wrong or swapped e_b / int_sha256_b and the other pin's values; the rule gave byte-identical results on the 8 blocks run twice (and on PR #87's 7).

Not established:
1. **Full determinism coverage.** Only 8 of 78 blocks were converted twice in this lane (H3 below the registered coverage) unless run 3 ran. The rule is plain numpy (`np.rint` on binary64, int16 cast), with no threading or randomness, but that is an argument, not a measurement.
2. **The other block classes.** Norm-folded matrices (368 blocks, including q/k/v, in_proj and gate/up), lm_head with the final norm, the embedding, and the 224 weight cells have no e_b / int_sha256_b. Their rule steps (`STEP_FOLDED`, `STEP_CA`, ...) are still text only.
3. **The full tree.** The subset id is not a conversion id for the model; the 722-block leaf-v2 tree for a pin (55.6 GB per pin) is not built.
4. **Binding to a proof.** Nothing here ties a commitment or proof to these integers (no `cp_commit`, no key-file change). int_sha256_b tells a verifier which integers the rule produces from the public pin; it does not show which integers a prover used.
5. **U1 margin.** That the two pins differ in 30% to 68% of integers per changed tensor says nothing yet about whether the output difference exceeds the integer lowering error (PR #139's U1 margin is the relevant result there).
6. **Implementation independence.** One implementation (wb_int's rule); no second implementation or language has reproduced the hashes.

## Deviations
- Run 2 stopped at 8 blocks (registered disk floor), below the H3 subset minimum of 10. Disclosed above and in PREREG amendment A-1 (committed after run 2, before any further fetch).
- The first pushes of this branch (e59442b, 502d77b) ran the host-path guard before push but ran `update-results.py --check` and `check-claims.py` only after the 502d77b push (both exit 0; results.yaml was unchanged at that point).
