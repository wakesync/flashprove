# RESULTS: bounded Qwen operator relations

Five scoped operator profiles now have real product-oracle proofs, not just witness checks.
Their nonlinear and rotary tables are deterministic integer artifacts, with no runtime float evaluation.
All final honest batches and sampled local-relation attacks meet their registered criteria.
A consistent replacement of convolution history still verifies, because external history identity is not bound.
Issue #35 therefore remains PARTIAL: this is research operator machinery, not a Qwen model proof.

## Verdict and final proof measurements

CPU-only, shared AMD EPYC-Rome KVM host, affinity 0-5, all proof batches through the shared heavy-job gate. Research target 10 bits. Each performance row is n=10, F=12, seeds1..10; no warmup excluded. Times are seconds, proof sizes bytes. Brackets are min/max; SD is sample SD. Verifier time includes witness-free circuit construction and sizing. Prove time excludes circuit lowering, sizing and witness-table assembly, so it is not end-to-end prover latency. No speedup comparison or model-scale extrapolation.

| Profile | Honest | Local hostile rejected (complete proofs) | Prove median [range], SD | Verify median [range], SD | Bytes median [range], SD | Columns / relations |
|---|---|---|---|---|---|---|
| nonlinear | 10/10 | 16/16 (5) | 0.0854971 [0.083231, 0.135206], SD 0.0157545098 | 0.036877 [0.0355306, 0.043383], SD 0.00251521166 | 117984 [117792, 118464], SD 188.893386 | 4392 / 8499 |
| conv | 10/10 | 16/16 (5) | 0.00590543 [0.00548054, 0.0178157], SD 0.00420962598 | 0.0243123 [0.0218463, 0.0564424], SD 0.0127453565 | 22160 [21920, 22400], SD 165.352687 | 294 / 573 |
| l2 | 10/10 | 17/17 (6) | 0.1707685 [0.16704, 0.182022], SD 0.00576339834 | 0.0529065 [0.0496414, 0.0601491], SD 0.00329672765 | 223392 [223088, 223632], SD 180.893584 | 9991 / 19742 |
| rms | 10/10 | 17/17 (6) | 0.191691 [0.180383, 0.209283], SD 0.0101109517 | 0.06858455 [0.0645433, 0.104293], SD 0.0115578233 | 223440 [223152, 223728], SD 176.209976 | 15753 / 31137 |
| rotary | 10/10 | 19/19 (6) | 0.08809985 [0.0798018, 0.104492], SD 0.00751997102 | 0.0342126 [0.0316884, 0.0507315], SD 0.00563565634 | 118144 [117792, 118240], SD 140.054593 | 5504 / 10880 |

- **Nonlinear PASS, bounded relation:** one proof jointly covers six functions on one committed scalar, not six independent input positions. General learned decay parameters and downstream gate multiplication are absent.
- **Convolution local PASS, carried-history PARTIAL/FAIL:** four tokens of one depthwise channel use the same canonical three-word history and four taps. The explicit history substitution control accepts the replacement, 1/1, against the SAME public outputs. Both its original and modified tuple proofs are valid. This is a negative result for externally fixed history identity, not a failure of the stated existential relation or a hostile rejection.
- **Norm PASS under registered bounded semantics:** D128 L2 and D256 RMS, unit gain, no epsilon, no extra query scaling. These are not M2 isqrt semantics or full Qwen norms.
- **Rotary PASS under A1:** public position, first64of256, rotate-half, theta10^7, context1024. No private/multimodal position or YaRN.

## Fidelity against float reference

Absolute real-valued errors on the same dequantized integer inputs. Input quantization error versus a separately sampled float tensor is NOT included. Nonlinear n=8197 per row: 4096 random, every4096grid point, five boundaries/zero points. Conv n=40 outputs from10chunks. L2/RMS n=1280/2560 correlated components from10heads. Rotary n=640 rotated coordinates from10positions/vectors; 1920 other coordinates per F are exactly unchanged, excluded from error quantiles. These are synthetic distributions, not real-weight fidelity.

| Function | F | n | Median | p95 | Max | SD | Threshold | Verdict |
|---|---|---|---|---|---|---|---|---|
| silu | 12 | 8197 | 8.83987457e-05 | 0.00302625749 | 0.00412596313 | 0.000963394009 | 0.006 | PASS |
| sigmoid | 12 | 8197 | 7.24773908e-05 | 0.000404697649 | 0.000990238514 | 0.00013672069 | 0.006 | PASS |
| softplus | 12 | 8197 | 8.87329949e-05 | 0.00275705603 | 0.0037807131 | 0.000881888198 | 0.006 | PASS |
| decay-half | 12 | 8197 | 7.09654968e-05 | 0.000355796621 | 0.000772024348 | 0.000113956028 | 0.006 | PASS |
| decay-one | 12 | 8197 | 7.24773908e-05 | 0.000404697649 | 0.000990238514 | 0.00013672069 | 0.006 | PASS |
| decay-two | 12 | 8197 | 5.69520433e-05 | 0.000433748126 | 0.00120172401 | 0.000155939337 | 0.006 | PASS |
| silu | 14 | 8197 | 2.55278162e-05 | 0.0031056664 | 0.00422463101 | 0.00100816689 | 0.006 | PASS |
| sigmoid | 14 | 8197 | 2.00995038e-05 | 0.000410609047 | 0.000962963244 | 0.000147105246 | 0.006 | PASS |
| softplus | 14 | 8197 | 2.409684e-05 | 0.00284902994 | 0.00386765583 | 0.000925313761 | 0.006 | PASS |
| decay-half | 14 | 8197 | 2.11666065e-05 | 0.000363080418 | 0.000756443202 | 0.000124597063 | 0.006 | PASS |
| decay-one | 14 | 8197 | 2.00995038e-05 | 0.000410609047 | 0.000962963244 | 0.000147105246 | 0.006 | PASS |
| decay-two | 14 | 8197 | 1.692292e-05 | 0.000448312102 | 0.0011561442 | 0.000164186164 | 0.006 | PASS |
| silu | 16 | 8197 | 7.10912096e-06 | 0.0031396224 | 0.00427492679 | 0.00101981989 | 0.006 | PASS |
| sigmoid | 16 | 8197 | 5.6763339e-06 | 0.000417314844 | 0.000972747803 | 0.000151637944 | 0.006 | PASS |
| softplus | 16 | 8197 | 6.49842777e-06 | 0.00288299439 | 0.00389070934 | 0.000936575433 | 0.006 | PASS |
| decay-half | 16 | 8197 | 6.0211362e-06 | 0.000367415289 | 0.000749965543 | 0.000128299267 | 0.006 | PASS |
| decay-one | 16 | 8197 | 5.6763339e-06 | 0.000417314844 | 0.000972747803 | 0.000151637944 | 0.006 | PASS |
| decay-two | 16 | 8197 | 5.0540605e-06 | 0.000457187205 | 0.00114285118 | 0.000167749353 | 0.006 | PASS |
| conv | 12 | 40 | 8.53836536e-05 | 0.000218451023 | 0.000239431858 | 6.87017108e-05 | 0.000244140625 | PASS |
| conv | 14 | 40 | 2.23498791e-05 | 5.69969416e-05 | 5.97722828e-05 | 1.64157604e-05 | 6.10351562e-05 | PASS |
| conv | 16 | 40 | 9.37469304e-06 | 1.45074446e-05 | 1.52536668e-05 | 4.3472092e-06 | 1.52587891e-05 | PASS |
| l2 | 12 | 1280 | 0.000126022306 | 0.000268754268 | 0.00040795279 | 8.11355574e-05 | 0.01 | PASS |
| l2 | 14 | 1280 | 5.01741811e-05 | 0.000137655909 | 0.000206969884 | 4.26543787e-05 | 0.01 | PASS |
| l2 | 16 | 1280 | 4.23497699e-05 | 0.000116665533 | 0.00016410029 | 3.66506754e-05 | 0.01 | PASS |
| rms | 12 | 2560 | 0.000380042952 | 0.00153203346 | 0.0023106225 | 0.000490864937 | 0.01 | PASS |
| rms | 14 | 2560 | 0.000379314467 | 0.00150219779 | 0.00220387401 | 0.000474214442 | 0.01 | PASS |
| rms | 16 | 2560 | 0.000377930806 | 0.00152371182 | 0.00219242967 | 0.000480251863 | 0.01 | PASS |
| rotary | 12 | 640 | 0.000114066542 | 0.000244862658 | 0.000387720289 | 7.8287871e-05 | 0.00048828125 | PASS |
| rotary | 14 | 640 | 3.14226273e-05 | 6.7882887e-05 | 9.36475943e-05 | 2.01558944e-05 | 0.000122070312 | PASS |
| rotary | 16 | 640 | 7.62295462e-06 | 1.61560338e-05 | 2.31792128e-05 | 4.93418956e-06 | 3.05175781e-05 | PASS |

Higher F does not eliminate the fixed input-grid error. SiLU worst maximum is grid-limited, not a claim of convergence with F.

## Hostile scope, smoke checks and sanitizer

All operators sample sign changes, out-of-domain operand, quotient+1 with compensating invalid remainder, changed output, changed scale/type, malformed output count, i64 extreme public outputs, flipped proof byte, truncation and trailing data. Nonlinear/norm add wrong table row; norm adds out-of-domain mean-square; conv adds wrong history reuse; rotary adds wrong pair, changed unrotated coordinate and position attacks. Complete malicious proofs preserve all multiplication equations and replace affine targets ONLY inside the malicious prover; the unchanged verifier derives its own targets. This is sampled coverage, not exhaustive soundness.

- nonlinear: UBSan local hostile 16/16 rejected, one honest accepted, zero sanitizer reports; F14 and F16 smoke PASS (n=1 each, not performance estimates).
- conv: UBSan local hostile 16/16 rejected, one honest accepted, zero sanitizer reports; F14 and F16 smoke PASS (n=1 each, not performance estimates).
- l2: UBSan local hostile 17/17 rejected, one honest accepted, zero sanitizer reports; F14 and F16 smoke PASS (n=1 each, not performance estimates).
- rms: UBSan local hostile 17/17 rejected, one honest accepted, zero sanitizer reports; F14 and F16 smoke PASS (n=1 each, not performance estimates).
- rotary: UBSan local hostile 19/19 rejected, one honest accepted, zero sanitizer reports; F14 and F16 smoke PASS (n=1 each, not performance estimates).

The history substitution control is also repeated under UBSan and again accepts the alternative consistent history. Its status is intentionally separate from local-relation rejection totals.

Independent Python integer lowering matches all 150/150 actual C++ fixture cases (19500 output words), all five operators, F12/14/16, seeds1..10. C++ reads compiled headers while Python reads binary tables. This checks implementation agreement separately from float fidelity.

## Table format, exact identity and regeneration

- `flashprove-qwen-integer-tables-v1`, manifest SHA-256 `13eacc50c87e53bbda5d9dcbb11761c399e430e56eba7ed7877e15d8362c79dd`.
- `flashprove-qwen-rotary-v1`, manifest SHA-256 `48fc90bb5e9c65cb66c21753f36b6da565bd2739c1a5bf057a7d78eeb97455a1`.

Nonlinear: 24 headerless i64LE files,4096rows each, F12/14/16; x=(i-2048)/256 for six nonlinear functions; mean-square=(i+256)/1024 for rsqrt/l2-128. Rotary: three headerless i64LE files,65536words each, flattened[1024position][32pair][cos,sin]. Nearest-even of deterministic Q256 integer approximation; reciprocal-root rounding is exact by integer midpoint comparison. The artifact generator is not a theorem of correctly rounded real exp/log/trig. Both manifest families and generated headers are regenerated bit for bit.

| File | SHA-256 |
|---|---|
| decay-half-f12.i64le | `3eb5dc20111b938dfdbdc107f1eee4afe0c3a1ee24395b8b00e1ded747374c73` |
| decay-half-f14.i64le | `1fccba69e53cfc7127aa64faf99b24afca0abe906df21f03eef8dca20920f0c2` |
| decay-half-f16.i64le | `a5df401e15e8b53c19ec6ac9aff29b07f1da4c5fe4da58f442843fcb2b63f048` |
| decay-one-f12.i64le | `ffd373e621ca994094bf876d684498580532286cc28dd005a79524831c3daedb` |
| decay-one-f14.i64le | `9ea248664c13743c7de3a80317aa569a5facd1c6f8201ef0ca09d830810592b8` |
| decay-one-f16.i64le | `0dd2e0c57ba339a8b98b4bd72a1f8952fa4812e5dcdeace47aa78cf3c68b2774` |
| decay-two-f12.i64le | `ffea852d2bce347738db58ecd26779f8250be9b7867e85cac7e1d09dc3109edb` |
| decay-two-f14.i64le | `d8ccd4b32b641f41f3aee45dcfeebf27fb33e03f32b3a0a1ffacd4b0b0c921a5` |
| decay-two-f16.i64le | `1b9497ca353b7757b0569bbf8033cf358c76af9b9e3a221f430a6e575ba280c0` |
| l2-128-f12.i64le | `94f9818f19a0b60472c8b12958eed5b7fe307855484e88cf49953b8d761d1c8d` |
| l2-128-f14.i64le | `c52b3ec802dac19d6c2ee71b33135f5aafdbe7190cded781dcad5ab64625abd8` |
| l2-128-f16.i64le | `4f829f9f91bf19b4249819bfd5f4e353a0cb6c41507308c4d3d93aa10c760040` |
| rsqrt-f12.i64le | `2a64edfa56cac61d60277529f96bb9fe43816f4d4a7e2838e2b03ddd88a2b188` |
| rsqrt-f14.i64le | `de64bf85310e388d44873f316fe65b0863b5a1b6013b2379620650c63309bf33` |
| rsqrt-f16.i64le | `30af43dcd253a6cd355a19cde5eb1d7de10a7a65f037898297e914e88f68d7bf` |
| sigmoid-f12.i64le | `19057d5fd13d67d8895e7b31f9b0d8c55eb75802857f8ae8b5deae67ab9202d5` |
| sigmoid-f14.i64le | `b02295838ed1f1835c4b0dfdac2427e5de51a3c10b866c0db48015d053427b19` |
| sigmoid-f16.i64le | `12687ae0d6622dac904a99a53b37c087c37a0f0a2aa2ed2eda6d3a41a784cf3a` |
| silu-f12.i64le | `cb2ceb05c7a1292a064e8d6d63cf9b63926db1122ea19663faecee21752bf8e9` |
| silu-f14.i64le | `7476abec4eb483ecdf18956c9e8a0e2ed6a5f45ad2b434e131e21ada40313339` |
| silu-f16.i64le | `bce2998ef7693bc5ec209b0e61cf5c5094923a2f36b79a8a95dfe4363bc37948` |
| softplus-f12.i64le | `d2c1a4504ec3a7eca897cd818e7e572e70e3f82835b52f4cf55f9fc61e633b24` |
| softplus-f14.i64le | `06e7b73c704dd531344578d223f74ae9f1b113adb2911e07fba68b775214104e` |
| softplus-f16.i64le | `323b7830d7316d90bbf4722388b6fa27d35cfefcb5c07f1c9e9ce17fe72ba3e8` |
| rotary-f12.i64le | `a82bd980ea903f4723bfc84a5fb96a008854cefe98a1c081a0c9818669204c9a` |
| rotary-f14.i64le | `c3401fd3a60d412ecb13026716c7ff4d8706435190c2f3b2a9ec6036a55c2f84` |
| rotary-f16.i64le | `f2e5684ac918104eac97bd9b2797ac4b69304267b6490127ff819d5ad9bbc04a` |

## Deviations and what remains missing from #35

A1 registered rotary before its code; A2 added typed transcript profiles, expanded malformed-statement tests, and a final unified rerun before measuring that profile. Development batches are preserved under runs/milestones, not pooled with final timings. The conservative O4096 selector backend, restricted norm domain and fixed decay examples were registered before code, not post hoc error-budget changes. No failed sample or warmup was removed.

External commitment identity is the principal gap: no matmul provenance, checkpoint-bound taps/constants or prior-chunk history root. Conv is only one channel/four tokens. Norm lacks learned gains, epsilon, nearzero support and DeltaNet q extra scaling. No sigmoid-times-mixer gate composition, learned A_log/dt_bias, hybrid layer planner, main-prover/CUDA integration, production security/hiding, Lean extension or real-weight fidelity. Upstream no-expert/dq!=d/head256 admission limits are untouched; exact locations and required work are in research/operators/qwen_ops/LIMITS-AND-ROTARY.md. Rotary beyond the public-position text-only1024 profile remains absent.

## Reproduction and evidence provenance

See research/operators/qwen_ops/README.md and each gadget README. Run record.py final and record.py ubsan-all through the host heavy-job gate with taskset-c0-5; run check_tables.py, check_rotary_tables.py, crosscheck.py and fidelity.py for each operator. Run report.py after all receipts exist. All commands require only g++, Python standard library and the repository; no weights, GPU or paid API.

Release proof implementation commit `c8e2a428782bf8a8239e9bea7455a1e0b10129fd`, sanitizer commit `95438aba49383998fce3d2cc5106c7bb34368679`; identical proof.cpp SHA-256 `31f1a723f1bb07015e16fa15337e31e7888f4256d608af8ed2b3ee6361e9aa95`. ENV.json pins toolchain, source hashes and compiled artifacts. Raw lines and distribution summaries are in runs/. research/results.yaml links to the receipt commit, not a future squash commit. Independent replication and review are still required.
