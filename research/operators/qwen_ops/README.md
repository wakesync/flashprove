# Bounded Qwen operator relations (research only)

This directory is an isolated CPU product-oracle experiment for issue #35, not Qwen support in `cp_verify`. See the pre-registration and receipts in `experiments/20261109-35-qwen-operators/`. No production security, zero knowledge, BF16 fidelity, full-layer proof, independent replication or Lean theorem is claimed.

## Statement and verifier boundary

The public statement is operator kind, F in {12,14,16}, public position for rotary (zero for other operators), and an exactly sized vector of claimed integer outputs. Inputs, selector bits, history and intermediates live in the same Merkle-committed product oracle. They are NOT public input words. The verifier rebuilds every affine relation from its own fixed operator definition, pinned table constants and the public outputs; it does not read a witness, evaluate float nonlinearities, or accept a prover-chosen constraint list. The test compares the witness builder's serialized relation list to the witness-free verifier's list. The research API receives C++ i64 values and proof bytes; it does not implement a production network/statement-file decoder. A future decoder must enforce canonical encodings, allocation bounds and the same shape/class checks before this entry.

**Important limitation:** the statement establishes a relation over an existential committed tuple. It does not authenticate that tuple as the output of a particular model matmul or a prior chunk. Replacing all inputs and recomputing all outputs consistently is another valid statement, not a detected attack. A production composition must put these wires in the existing model oracle or bind openings of the prior commitments. In particular, an internally committed history is not a carried cross-proof history commitment. This lane does not solve issue #34.

The backend is the existing wide affine product oracle (PSC, Merkle commitments and IOPP), with a distinct family string in its configuration digest. All equality and range constraints address the same committed cells as the product relations. Research target is **10 bits**, using the backend's plan accounting. Fixed test coins make runs reproducible, not suitable for hiding deployed witnesses. Hostile cases are sampled complete proofs that preserve all product equations while lying about affine targets inside the prover. The verifier is unchanged and keeps its own targets. Byte and statement mutations are separately identified.

## Integer tables and format

`tables/manifest.json` is the canonical directory manifest, format `flashprove-qwen-integer-tables-v1`. Each `.i64le` is exactly 4096 headerless signed 64-bit little-endian output words, row-major, output scale 2^F. F is 12, 14 or 16. The table's name, F, row count, domain, input rational grid, rounding and SHA-256 are in the manifest. `tables/pinned.h` is a generated C++ copy. Regeneration checks both the binary artifacts and every C++ constant. The manifest SHA-256 identifies the entire set of binary table hashes; SHA-256 is an artifact identifier here, not an in-circuit hash gadget.

- `silu`, `sigmoid`, `softplus`, `decay-half`, `decay-one`, `decay-two`: row i is evaluated at x=(i-2048)/256, for i in [0,4096). Decay means exp(-c softplus(x)), c=1/2,1,2. Integer input X maps to i=floor(X/2^(F-8))+2048. Domain [-8,8), fail closed outside. **No clamping** and no learned A_log/dt_bias support.
- `rsqrt`: row i approximates 1/sqrt((i+256)/1024).
- `l2-128`: row i approximates 1/sqrt(128*(i+256)/1024).
- Norm domain [1/4,17/4); key=floor(1024*sum X_j^2/(D*2^(2F)))-256. This is a deliberately bounded approximation, not the M2 isqrt/epsilon norm. Zero and low-energy vectors have no witness.

### Generation, deterministic but not a transcendental rounding theorem

`tables.py` contains no floating-point arithmetic. Q256 exp reduces |x| by 16, uses 128 positive Taylor terms and four squarings, floors at each integer division, and uses an integer reciprocal for negative arguments. Log normalizes to [1,2) and uses 256 odd atanh-series terms plus the same series for log(2), again with integer floors. The final output rounds this **integer approximation** to nearest, ties to even. No proof of correctly rounded real exp/log is claimed. Reciprocal-root entries instead use exact integer square root and an exact rational midpoint comparison, so their nearest-even rounding is exact. Formula/algorithm changes require new hashes and a new configuration; a manifest is not a licence to select arbitrary values.

Runtime prover and verifier only access pinned integer constants. Float64 is used exclusively in `fidelity.py` as an independent numerical reference, not table generation or witness generation.

## Lookup relation and no-wrap argument

A 4096-way one-hot selector has Boolean entries b_i, sum b_i=1, key=sum i*b_i, y=sum table[i]*b_i. All sums use fan-in at most 120 and equality-linked intermediate cells. The nonlinear gadget shares one input/key across six output functions. The input quotient is tied to X with an exactly bit-decomposed remainder in [0,2^(F-8)). Therefore the key interval enforces the original input domain, including the negative floor convention; there is no unproved host-side clamp.

There are at most 4096 Boolean values, so sum=1 cannot wrap Goldilocks. Selected keys are at most 4095, table coefficients are below 2^20 in magnitude, and all sums are below 2^32 in magnitude even before the one-hot constraint reduces them. Intermediate equalities pin unique field elements. Once selectors are one-hot, reconstruction and remainder bounds pin the intended signed integer X. This is O(table size) per selector group, not the efficient batched LKP backend; table membership itself is proved, not recomputed from disclosed inputs.

## Gadget boundaries

- [Nonlinear](nonlinear/README.md): six functions on one shared committed scalar/key.
- [Convolution](conv/README.md): four tokens, one channel, shared committed three-word history and four taps. External carried-history identity is missing.
- [Norm](norm/README.md): one D128 L2 or D256 RMS head, bounded mean-square table, unit gain and no epsilon.
- [Rotary](rotary/README.md): public position 0..1023, first 64 of 256 coordinates, theta 10^7, rotate-half pairs and exact copy of the rest. Separate manifest `tables/rotary-manifest.json`.

## Reproduce

From the repository root, Python standard library and g++ with C++17, no downloads:

```
python3 research/operators/qwen_ops/check_tables.py
python3 research/operators/qwen_ops/check_rotary_tables.py
python3 research/operators/qwen_ops/crosscheck.py
python3 research/operators/qwen_ops/fidelity.py nonlinear
python3 research/operators/qwen_ops/fidelity.py conv
python3 research/operators/qwen_ops/fidelity.py l2
python3 research/operators/qwen_ops/fidelity.py rms
python3 research/operators/qwen_ops/fidelity.py rotary
python3 research/operators/qwen_ops/record.py final
python3 research/operators/qwen_ops/record.py ubsan-all
```

On a shared lane host, prefix every prove/verify batch with the coordinator's `fp-heavy.sh taskset -c 0-5` wrapper. No absolute host path is part of a repository command. `record.py` writes raw JSONL under the experiment's `runs/`, summarized seconds/bytes with n, median, sample SD and min/max. Timing includes no excluded warmup; verifier time includes witness-free circuit derivation and sizing. `crosscheck.py` exports the actual C++ fixtures at all three scales and checks them against independently written Python integer lowering using the binary tables rather than the C++ header. Table generation, compiler time and shell scheduling are not included in prove/verify times. F=12 is the performance arm; F=14/16 smoke proofs are not ten-run timing estimates.

## What remains outside issue #35 coverage

External commitment identity and prior-history authentication, matmul composition, learned decay constants, norm epsilon and learned gains, DeltaNet q scaling, arbitrary low-energy vectors, full-context/multimodal rotary, the hybrid layer planner, production hash/security accounting, upstream limits, and model fidelity all remain separate obligations. These tables are an experimental interface and must not silently replace M2 or production arithmetic.
