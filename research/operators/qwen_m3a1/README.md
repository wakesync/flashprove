# Qwen M3a-1, weight side: a committed weight table and the trace's weight cells tied to it (issue #229, research only)

Registration and results: [`experiments/20261121-229-qwen-m3a1-weight-side`](../../../experiments/20261121-229-qwen-m3a1-weight-side/). CPU research harness, not a serving protocol. No existing file is changed: the code includes `blocks/` and `research/operators/qwen_deltanet/product.h` as they are on main.

## What is proved

For V head 0 of layer 0 of the pinned stock Qwen3.8-27B (DESIGN.md of `experiments/20261109-32-qwen-m3-design`, sections 3.2, 5.0, 6.2):

1. **A committed table of the head's weights.** All 3,288,706 integers of the head (DESIGN 5.0 conversion) are the 595 x 8,192 matrix M of one committed table (`blocks/iop/index_cpu.h`: encoded rows, Merkle root over columns, record). Row 0 holds the 1,666 weights the trace reads (1,536 conv taps of the head's q, k and v channels, 128 gains times sqrt(128), cA = exp(A_log), dt_bias at 2^12) at addresses 0..1,665 and zeros after them; rows 1..514 the head's in_proj rows (q, k, v, z: 128 each; a, b: 1 each); rows 515..594 the head's 128 columns of out_proj. The verifier holds the table's key (root and record), not the weights.
2. **The 1,666 weight cells in their class (DESIGN 6.2 step 1).** Each cell is a product-oracle cell with an exact class by bits: w + 4,096 is 13 boolean cells for taps, gains and cA, so w is in [-4,096, 4,095]; dt + 2^17 is 18 boolean cells, so dt_bias is in [-2^17, 2^17). Each bit is a column (b, b, b) of the product oracle with two 2-term relations, so b^2 = b. 23,329 product columns, 44,992 relations, table length 2^15.
3. **The tie (DESIGN 6.2 step 2).** After the product oracle's root, on a chain whose first query holds the relations and the table's name, the verifier draws psi (13 elements of E) and the prover sends v. One more linear claim on the product oracle: sum_i eq(psi, i) w_i = v. One LIN claim (`blocks/iop/lin.h`, run as the table's one-time test `TableTest::ONE_TIME`) whose first chain binds psi and v: row 0 of M at psi equals v. Both vectors are fixed before psi, so a cell that differs from its table entry, or a non-zero row-0 entry past address 1,665, makes the two sides differ except for at most 13 / |E| of the points. That is the bound of the idealised argument with both vectors fixed before psi is drawn, not the error of the compiled proof at the research setting.

T = 1 in the sense of the issue: no token computation is proved, and weights do not depend on T.

## What the verifier recomputes

It builds the relations from the public layout, sizes and plans the trace run itself, binds the table key it holds into the trace chain's first query, draws psi from its own transcript, reads v, adds the tie row, checks the proximity test, then builds the LIN claim (row-0 indicator, psi, v) from those values and checks LIN's three chains and the binding path with the same key. It reads no weight.

## What is not covered

- **The matrix weights' range is not proved.** Rows 1..594 (in_proj, out_proj) are field elements under the root, bounded by nothing here. No Qwen layout of the WF range proof (`blocks/iop/wf.h`, `blocks/frame/wf_units.h`, Maverick layout only) exists, and none is built here.
- No head computation: no in_proj products, conv, gates, norms, recurrence or out_proj. Sub-step (c) of #229 (in_proj as a linear claim on the table) was not started.
- The M3a-1 evidence gate of `experiments/20261109-32-qwen-m3-design/DESIGN.md` section 9 (honest 10 of 10 at T = 16, the hostile cases that need the head computation, UBSan clean) is NOT met by this step; this step is the weight side only.
- No soundness level. The trace part uses the harness's research setting (target 10 bits, query work 6). LIN's chains use the hand-made plan of `blocks/iop/tests/lin_world.h` (every round priced NOTHING, compiled with `BLK_PLANS_BY_HAND_FOR_A_TEST`), so the LIN part has no error bound at all. The hostile cases are one complete proof each, not an exhaustive adversary.
- Not hiding: v is sent in the clear (the LIN claim's mask entry has weight 0). The weights are public anyway.
- That the committed table is the advertised checkpoint: the root is whatever the committer made (the manifest's job, #59). The fetched tensors are checked against the merged stream hashes before conversion; that check is outside the proof.
- No accuracy claim (F = 12 is known to miss the fidelity bar on layer 0).

## Files

- `prepare.py`: fetches layer 0's linear_attn tensors of the pinned stock revision by HTTP range (merged `fetch.py` `get()`), checks each tensor's SHA-256 against the merged `runs/stream-stock.json`, converts by DESIGN 5.0 (merged `wb_int.py` `exponent_of`), writes M (int32) to a data directory outside the repository and a summary of shapes, exponents and SHA-256 values. `synthetic` mode writes the debug fixture (numpy seed 9101, "head 1", no real weights). Tap order: taps are stored in the checkpoint's order j, so a head computation must read tau = 3 - j (reviewer's finding, <https://github.com/wakesync/flashprove/pull/231#issuecomment-7059688619>).
- `qm3a1.cpp`: table, trace, tie, LIN, verifier, and the registered hostile and completeness cases.
- `run_registered.py`: the registered runs, each to its own file, never overwritten. `summarise.py`: `runs/summary.json`.

## Reproduce

From the repository root (Python 3 with NumPy, g++ 13; pin cores on a shared host):

```sh
python3 research/operators/qwen_m3a1/prepare.py real <data_dir> <data_dir>/summary.json
g++ -std=c++17 -O2 -Wall -Wextra -fno-ipa-modref -DBLK_FIELD=2 -DBLK_HASH=1 -I blocks research/operators/qwen_m3a1/qm3a1.cpp -o <data_dir>/qm3a1.bin
python3 research/operators/qwen_m3a1/run_registered.py <data_dir>/qm3a1.bin <data_dir>/M.i32 <fresh runs dir>
python3 research/operators/qwen_m3a1/summarise.py <fresh runs dir>
```

`prepare.py real` fetches about 232 MB. The compile took several minutes of one core here (the reviewer's build with the same flags took 30 s, reviewer's finding, <https://github.com/wakesync/flashprove/pull/231#issuecomment-7059688619>); each run takes about 4 to 8 s and 0.45 to 0.82 GB.
