# PREREG: 20261121-229-qwen-m3a1-weight-side

Issue: #229. Lane: qwenm3a1. Date (UTC): 2026-11-21 06:05. Base commit: 4c6ae1254860873a832981fd0d56eb7376e77389.

Research harness only, CPU only. Design followed: `experiments/20261109-32-qwen-m3-design/DESIGN.md` (r3) sections 3.2, 4, 5.0, 6.2, 9.

## What this step builds (decided from the source before any code)

The smallest composition found in the source that binds trace cells to a committed weight table without changing any existing file:

1. **Weight table.** One committed table (`blocks/iop/index_cpu.h`, `IndexCpu`; Merkle root over encoded columns, record of out-of-domain answers) holding all 3,288,706 integer weights of V head 0 of layer 0 as a matrix M with 2^13 columns and 595 rows: row 0 = the 1,666 trace-read weights (1,536 conv taps of the head's q, k, v channels, 128 gated-norm gains, cA, dt_bias) at fixed public addresses 0..1,665, then zeros; rows 1..514 = the head's in_proj rows (q 128, k 128, v 128, z 128, a 1, b 1; 5,120 entries each, then zeros); rows 515..594 = the head's 128 columns of out_proj (5,120 x 128 values, 8,192 per row). The verifier holds the table's key (root and record) and nothing else of the weights.
2. **Trace side.** The 1,666 weight cells as cells of the harness's wide affine product oracle (`research/operators/qwen_deltanet/product.h`, toy PSC plus IOPP, as used by every Qwen head proof on main), each with its in-trace class of DESIGN 6.2 step 1. Class lowering: exact bits (arm A, DESIGN 7.2), not lookup keys: w + 4,096 = sum of 13 boolean cells for taps, gains and cA (class [-4,096, 4,095]); dt + 2^17 = sum of 18 boolean cells for dt_bias (class [-2^17, 2^17)). Each bit is a product column (b, b, b) with two 2-term relations, so b * b = b. These are the same classes the design states; bits instead of keys change the cost, not the class.
3. **Tie (DESIGN 6.2 step 2).** On the trace chain, after the product oracle's root and with the table's name (root and record) bound in the chain's first query, the verifier draws a point psi (13 elements of E). The prover sends v. One linear claim on the product oracle: sum_i eq(psi, i) w_i = v over the 1,666 cells. One LIN claim (`blocks/iop/lin.h`) on the table: row 0 of M at psi equals v, i.e. sum_j eq(psi, j) M[0][j] = v over all 8,192 columns of row 0. The verifier builds the LIN claim itself from psi and v read off the trace chain. A trace cell that differs from its table entry, or a non-zero table entry in row 0 past address 1,665, makes the two sides differ except with probability at most 13 / |E| over psi (both vectors are fixed before psi is drawn). This is the random linear combination of 6.2 with eq(psi, i) in place of rho^i.
4. **LIN is run with `TableTest::ONE_TIME`**, the committer's own proximity test of the table, so no earlier key-file test is assumed or vouched for. Its chains follow `blocks/iop/tests/lin_world.h` (first, shared, second chain, binding tree of one leaf), with this lane's own first-chain binding (psi, v, the trace chain's seal).

T = 1 is implicit: weights do not depend on T, and this step proves no token computation.

## Hypothesis

On the CPU research harness, a proof that (a) holds the 1,666 trace-read weights of V head 0, layer 0 of the pinned stock Qwen3.8-27B as product-oracle cells in their DESIGN 6.2 classes and (b) ties them to a committed table of all 3,288,706 head weights by one LIN claim at a transcript point, verifies for the honest prover, and is rejected for every registered hostile case below.

## Statement (exactly)

- **Public:** the run configuration (codes, plan, sizes, setting: target 10 bits, query work 6, the harness's research setting), the 1,666 public addresses and class widths (13 or 18 bits), the layout of M above, and the table's key (root and record).
- **Committed, not shown:** the table (all 3,288,706 integers, as field elements); the trace cells and their bits.
- **Proved:** every trace weight cell is an integer in its class; the trace cells equal the table entries at their addresses (row 0, columns 0..1,665); row 0 of the table is zero at columns 1,666..8,191; the table is close to a codeword (LIN's one-time test).
- **Verifier recomputes:** the relations from the public layout; psi from its own transcript; the LIN claim from psi and v. It reads no weight.
- **Not proved:** any bound on table entries in rows 1..594 (the matrix weights); that the table is the advertised checkpoint (the root is what the committer published; the manifest's job, #59); any computation on the weights.

## Weights

Fetched by HTTP range from the pinned stock revision (`Qwen/Qwen3.8-27B` at 37561816e66b5b9153b1b64c10968c18c1e6f4a0) with the merged `experiments/20261109-8-qwen-real-weights/fetch.py` `get()`, layer 0 linear_attn tensors only (A_log, conv1d, dt_bias, in_proj_a, in_proj_b, in_proj_qkv, in_proj_z, norm, out_proj), into a directory outside the clone. Each tensor's SHA-256 must equal the merged `runs/stream-stock.json` hash before use; a mismatch stops the lane. Conversion: DESIGN 5.0 with `research/weight-binding/wb_int.py` `exponent_of` (per tensor, max |int| <= 4,095): matrices and conv taps as is; gain_int = RNE(2^e sqrt(128) gain); cA_int = RNE(2^e exp(A_log)); dt_int = RNE(2^12 dt_bias). Committed: shapes, exponents, SHA-256 of the integers; never values.

## Metric

Verifier verdict (accept / reject with its reason string) per case; columns of the product oracle, relations, table shape, proof bytes (trace and LIN), prove and verify wall time, peak RSS (getrusage), all labelled measured, unreplicated, one host.

## Acceptance threshold

PASS for (a)+(b) iff: honest proof accepted in 5 of 5 runs, AND every hostile case H1-H6 rejected, AND completeness cases C1-C3 accepted, AND the C++ check that the trace cells equal the converted integers at their addresses holds.

Hostile cases (each one complete proof by a prover that knows the honest witness, unchanged verifier):
- H1 other root: an honest proof checked against the key of a second table that differs from the honest one in one entry of row 0 (one tap, +1). Also H1b: the same proof against a second commitment of the same weights with other randomness (another root).
- H2 one tap changed: trace tap cell +1 (in class, bits re-derived honestly), table honest; two variants: v computed from the trace (LIN claim false) and v computed from the table (trace tie row false).
- H3 trace gain out of class: gain cell = 2^50 in trace AND in the table (so the tie holds); bits from an honest decomposition of the old value; relation targets replaced by their local values on the tampered table (as `research/operators/qwen_deltanet/test.cpp`'s hostile prover).
- H4 trace gain in class but not the table's: gain cell +1 in trace, table honest.
- H5 dt_bias at 2^17 (trace and table both 2^17, tie holds): must be refused by the class.
- H6 table row 0 non-zero past address 1,665 (one padding entry = 1), trace honest.

Completeness cases (must be ACCEPTED; head 0's own dt_bias is replaced in trace and table by the value, everything else honest): C1 dt_int = 78,848; C2 dt_int = -23,424; C3 dt_int = 2^17 - 1.

Sub-step (c) (in_proj as a linear claim): only after (a)+(b) pass and are committed and if more than 50 minutes remain; if started, registered here by amendment before its run.

## Kill criterion

Hard stop 2026-11-21T08:15Z. Stop and report if: the composition needs a change to an existing file under `blocks/`, `prover/`, `verifier/` or the existing harness; the table exceeds 2^23 columns of the product oracle or a run's peak RSS passes 12 GB; a hostile case is accepted (report as a soundness finding, fix nothing in this step); no honest proof verifies by the deadline. No widening of the statement after a failure.

## Runs

Honest: 5 runs, same inputs, different prover coin seeds (1..5). What varies: the prover's randomness (masks, tails, so roots, transcript challenges and proof bytes); the verdict is expected to be the same. Hostile and completeness: 1 run each, prover seed 1. Debug fixture (never registered, used for all development): synthetic integers from numpy seed 9101, laid as "head 1" of the same layout, with no real weights. No registered case runs before this registration. Cores 2-7, through fp-heavy.sh if over 2 min CPU or 4 GB.

## Prior art

DESIGN.md (r3) designs and counts this tie; it is not built on main. LIN, FOLDEQ and the committed table are upstream blocks (Greyhound-style row/column claims, Brakedown-style table test; see lin.h and foldeq.h headers), used here unchanged. Upstream's WF range proof bounds table entries for the Maverick layout only; not used here. zkML systems that commit weights (zkLLM, EZKL, Jolt-based) bind weights by a commitment and prove matmuls against it; the new piece here is only the composition of a committed weight table with this fork's research product oracle and the in-trace class of the trace-read cells.

## Not in this step (M3a-1 parts left out)

No head computation: no in_proj products (unless (c) is reached), no conv, no gates, no q/k norm, no recurrence, no gated norm, no out_proj product, no state or history; T = 16 is not touched. The matrix weights' range is NOT proved: no Qwen layout of WF exists and none is built here, so table rows 1..594 are bounded by nothing in this proof (field elements under a root). The table test's error bounds are those of the hand-made LIN plan of `lin_world.h` (rounds priced NOTHING): no soundness figure is claimed for the LIN part; the trace part uses the harness's research setting (target 10 bits). No hiding claim: v reveals one linear combination of public weights. No accuracy claim of any kind.

## Amendments

### A1 (2026-11-21 06:58 UTC, after code and synthetic debug, BEFORE any registered run)
Concrete choices the code makes that the registration did not fix. None changes the statement, a threshold or a case.
- Tie point: drawn in a round named JOIN (13 elements of E), after the product oracle's root and PSC; v is one scalar sent after it; one tie row on the product oracle. Transcript label 0x46504d31, run text `research-qwen-m3a1-weight-cells-v1`.
- LIN parameters (`LinCase` of `blocks/iop/tests/lin_world.h`): table 2^7 rows, 2^6 matrix columns per table row (so k_col = 13), 1 record answer, 24 drawn table columns, rate at most 1/4, message lengths 4,096 for G_u, Omega and W, rows high, one request, 12 draws per proximity stage. The LIN claim's row weight is the indicator of row 0. The claim's target is v itself: the request's mask entry is joined with coefficient 0, so v is not masked (no hiding claim, as registered).
- Hostile prover form, as registered: H2b, H3 and H5 set each linear claim's target to its local value on the tampered trace (the qwen_deltanet test's hostile prover). H2a, H4 and H6 run the honest code on tampered inputs. H1 and H1b prove honestly and are checked against another table's key.
- Measured RSS is getrusage of the process plus /usr/bin/time's maximum; H1 and H1b commit two tables in one process.
- Debug: all 5 kinds of run were exercised on the synthetic fixture only (seed 9101, head 1). Outputs not kept as evidence.
