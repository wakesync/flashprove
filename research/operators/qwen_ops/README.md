# Bounded Qwen operator relations (research only)

This directory is an isolated CPU product-oracle experiment for issue #35, not Qwen support in `cp_verify`. See the pre-registration and receipts in `experiments/20261109-35-qwen-operators/`. No production security, zero knowledge, BF16 fidelity, full-layer proof, independent replication or Lean theorem is claimed.

## Statement and verifier boundary

The public statement is operator kind, F in {12,14,16}, public position for rotary (zero for other operators), and an exactly sized vector of claimed integer outputs. Inputs, the convolution taps, selector bits, history and intermediates live in the same Merkle-committed product oracle. They are NOT public input words. The verifier rebuilds every affine relation from its own fixed operator definition, pinned table constants and the public outputs; it does not read a witness, evaluate float nonlinearities, or accept a prover-chosen constraint list. The test compares the witness builder's serialized relation list to the witness-free verifier's list. The research API receives C++ i64 values and proof bytes; it does not implement a production network/statement-file decoder. A future decoder must enforce canonical encodings, allocation bounds and the same shape/class checks before this entry.

**Important limitation, the statements bind much less than a reader may expect.** The only public values are the operator, F, the rotary position and the outputs. The convolution taps (the kernel), the history and every input of every operator are committed cells that the **prover chooses freely**; nothing outside the proof fixes them. A proof therefore shows "there exist inputs (and, for the convolution, a kernel and a history) in range for which this relation gives these outputs", and nothing about a particular model's weights or a particular earlier chunk.

| Operator | Public | Committed, chosen freely by the prover |
|---|---|---|
| Nonlinear | operator, F, six outputs | scalar X, quotient/remainder, selector |
| Convolution | operator, F, four outputs | four taps (kernel), three history words, four inputs, remainders |
| L2 / RMS | operator, F, 128 / 256 outputs | input vector, energy, key, coefficient, remainders |
| Rotary | operator, F, position, 256 outputs | 256 inputs, remainders (coefficients fixed by the public position) |

For the convolution and the rotary the consequence is strongest. **The statements do not bind the inputs or the kernel, and a reviewer's constructions show that outputs picked by the reviewer (chosen for the convolution; drawn at random and then adjusted in 3 of 256 words for the rotary), not computed from any model's weights or inputs, can be proved, and that the same public convolution outputs can be proved with a different kernel.** How much of the in-range output space can be reached was not measured, and the range checks alone do not describe it. What was demonstrated: the opus reviewer built three complete proofs with the unmodified prover that the unchanged verifier accepted (https://github.com/wakesync/flashprove/pull/67#issuecomment-6757161440; the reviewer's runs, not committed run files of this PR): a convolution with four outputs of the reviewer's choosing, (S,-S+1,1234,-77), via taps (0,0,0,-S); a convolution reproducing the seed-3 public outputs with a different kernel (all taps -S) and freshly solved history and inputs; and a rotary proof at position 517 for one random 256-word target, whose words were sampled in [-S/2,S/2), after moving 3 of the 256 words by 1. Before that move the reviewer's search hit 29 of the 32 rotated pairs exactly and no proof was attempted, so an exact arbitrary rotary target was not reached. The rotary relation does not reach every in-range output (astra re-review, https://github.com/wakesync/flashprove/pull/67#issuecomment-6757637207: at F12, position 517, pair 0, the target pair (4095,4095) would need an input below -4852, outside [-S,S)). The nonlinear outputs must be one consistent table row and the norm outputs the floored scaled values of some in-range vector at a table coefficient, so those are more constrained, but their inputs are equally unbound. The hostile `public-output`/`wrong-output` rejections cannot stop a prover who simply picks a different witness. A production composition must put these wires in the existing model oracle or bind openings of the prior commitments. In particular, an internally committed history is not a carried cross-proof history commitment. Binding the kernel and inputs to committed weights and to the previous chunk is the job of the M3 statement (PR #70, draft) and the state-commitment work (#34), not of this PR.

The backend is the existing wide affine product oracle (PSC, Merkle commitments and IOPP), with a distinct family string in its configuration digest. All equality and range constraints address the same committed cells as the product relations. Research target is **10 bits**, using the backend's plan accounting. This is a **per-round** target that includes 6 bits of proof-of-work on the query rounds (`Plan::holds`: a round's error times 2^-work is at most 2^-10). The weakest query rounds are about 4.3 to 4.5 bits before the work factor. **No whole-proof soundness figure has been established for these profiles at this research setting.** The reviewers added up the per-round errors as the plan charges them; that sum is a diagnostic only. The repository's own accounting code (`blocks/numbers/accounting.h`, the lines it prints under "FOR INFORMATION") says such sums decide nothing, that in some rounds the charge is the largest of several events' chances and not their sum, "so none is a union bound over all events", and that "no figure here is a security level". A whole-proof soundness figure would also depend on the attacker's hash-query budget, which the sum does not include. The reviewers' diagnostic sums (their own scratch calculations, not committed run files of this PR): about 2^-7.3 over the 27 rounds of the convolution profile in the first opus review (link above); 2^-7.326 for the convolution, 2^-7.382 for nonlinear and rotary (31 rounds) and 2^-7.384 for L2 and RMS (32 rounds) in the astra re-review (link above) and in the opus re-review (https://github.com/wakesync/flashprove/pull/67#issuecomment-6757721363). The two opus comments call the sum a union bound and a 1-in-N chance for one proof; that reading is not supported and is not claimed here. This is a research setting; the rejection counts do not show production security.

Fixed test coins (`ToyCoins(seed)`) are the prover's own randomness, the salt and the masks. Every verifier challenge is derived from the transcript by hashing. Fixed coins make runs reproducible and remove hiding; they do not weaken soundness, and are not suitable for hiding deployed witnesses.

Hostile cases are sampled complete proofs that preserve all product equations while lying about affine targets inside the prover. The verifier is unchanged and keeps its own targets. Byte and statement mutations are separately identified. These hostile proofs are rejected by an equation check with a large margin, not by a low-probability query round, so they show that each constraint exists and is wired to the right cell; they do not show that the protocol reaches its target. No grinding attack against the weakest query rounds was attempted by anyone.

## Integer tables and format

`tables/manifest.json` is the canonical directory manifest, format `flashprove-qwen-integer-tables-v1`. Each `.i64le` is exactly 4096 headerless signed 64-bit little-endian output words, row-major, output scale 2^F. F is 12, 14 or 16. The table's name, F, row count, domain, input rational grid, rounding and SHA-256 are in the manifest. `tables/pinned.h` is a generated C++ copy. Regeneration checks both the binary artifacts and every C++ constant. The manifest SHA-256 identifies the entire set of binary table hashes; SHA-256 is an artifact identifier here, not an in-circuit hash gadget.

- `silu`, `sigmoid`, `softplus`, `decay-half`, `decay-one`, `decay-two`: row i is evaluated at x=(i-2048)/256, for i in [0,4096). Decay means exp(-c softplus(x)), c=1/2,1,2. Integer input X maps to i=floor(X/2^(F-8))+2048. Domain [-8,8), fail closed outside. **No clamping** and no learned A_log/dt_bias support.
- `rsqrt`: row i approximates 1/sqrt((i+256)/1024).
- `l2-128`: row i approximates 1/sqrt(128*(i+256)/1024).
- Norm domain [1/4,17/4); key=floor(1024*sum X_j^2/(D*2^(2F)))-256. This is a deliberately bounded approximation, **not the M2 design's integer-square-root (isqrt/epsilon) norm (#66)**. Zero and low-energy vectors have no witness.

### Generation, deterministic but not a transcendental rounding theorem

`tables.py` contains no floating-point arithmetic. Q256 exp reduces |x| by 16, uses 128 positive Taylor terms and four squarings, floors at each integer division, and uses an integer reciprocal for negative arguments. Log normalizes to [1,2) and uses 256 odd atanh-series terms plus the same series for log(2), again with integer floors. The final output rounds this **integer approximation** to nearest, ties to even. No proof of correctly rounded real exp/log is claimed. Reciprocal-root entries instead use exact integer square root and an exact rational midpoint comparison, so their nearest-even rounding is exact. Formula/algorithm changes require new hashes and a new configuration; a manifest is not a licence to select arbitrary values.

Runtime prover and verifier only access pinned integer constants. Float64 is used exclusively in `fidelity.py` as an independent numerical reference, not table generation or witness generation.

## Lookup relation and no-wrap argument

A 4096-way one-hot selector has Boolean entries b_i, sum b_i=1, key=sum i*b_i, y=sum table[i]*b_i. All sums use fan-in at most 120 and equality-linked intermediate cells. The nonlinear gadget shares one input/key across six output functions. The input quotient is tied to X with an exactly bit-decomposed remainder in [0,2^(F-8)). Therefore the key interval enforces the original input domain, including the negative floor convention; there is no unproved host-side clamp.

There are at most 4096 Boolean values, so sum=1 cannot wrap Goldilocks. Selected keys are at most 4095, table coefficients are below 2^20 in magnitude, and all sums are below 2^32 in magnitude even before the one-hot constraint reduces them. Intermediate equalities pin unique field elements. Once selectors are one-hot, reconstruction and remainder bounds pin the intended signed integer X. This is O(table size) per selector group, not the efficient batched LKP backend; table membership itself is proved, not recomputed from disclosed inputs.

## Gadget boundaries

- [Nonlinear](nonlinear/README.md): six functions on one shared committed scalar/key.
- [Convolution](conv/README.md): four tokens, one channel, shared committed three-word history and four taps. Kernel, history and inputs are all prover-chosen; external identity of any of them is missing.
- [Norm](norm/README.md): one D128 L2 or D256 RMS head, bounded mean-square table, unit gain and no epsilon. Not the M2 isqrt norm (#66).
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

On a shared lane host, prefix every prove/verify batch with the coordinator's `fp-heavy.sh taskset -c 0-5` wrapper. No absolute host path is part of a repository command. `record.py` writes raw JSONL under the experiment's `runs/`, summarized seconds/bytes with n, median, sample SD and min/max. Timing includes no excluded warmup; verifier time includes witness-free circuit derivation and sizing. `crosscheck.py` exports the actual C++ fixtures at all three scales and checks them against independently written Python integer lowering using the binary tables rather than the C++ header. Prove timing starts after circuit lowering, sizing and witness-table assembly, so it is NOT end-to-end prover latency. Table generation, compiler time and shell scheduling are not included in prove/verify times. F=12 is the performance arm; F=14/16 smoke proofs are not ten-run timing estimates.

`report.py` (run after all receipts exist; it assembles RESULTS.md and `runs/aggregate.json`) also **rewrites `experiments/20261109-35-qwen-operators/ENV.json`** with the current host data and the current SHA-256 of every file in this directory. The committed ENV.json is the receipt of commit `6bb270a`: its hashes of the five README files here and of `report.py` predate the later wording-only review fixes and were intentionally not regenerated. A reproducer who runs `report.py` will therefore see those six hashes change (and the host fields, on another machine); proof.cpp and the table hashes should not change.

## What remains outside issue #35 coverage

External commitment identity and prior-history authentication, matmul composition, learned decay constants, norm epsilon and learned gains, DeltaNet q scaling, arbitrary low-energy vectors, full-context/multimodal rotary, the hybrid layer planner, production hash/security accounting, upstream limits, and model fidelity all remain separate obligations. These tables are an experimental interface and must not silently replace M2 or production arithmetic.
