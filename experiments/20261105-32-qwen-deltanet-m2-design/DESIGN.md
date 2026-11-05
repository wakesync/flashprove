# Qwen DeltaNet M2: design

Issue #32. PREREG: [PREREG.md](PREREG.md) (first commit 84776893). Results and verdict: [RESULTS.md](RESULTS.md).
This is a design. Nothing in it is proved, and no M2 proof exists.

The numbers are counts from `research/operators/qwen_deltanet_m2/count_model.py`:
- The recurrence part of the model reproduces the measured M1 and M1b statements exactly (RESULTS.md H1).
- The gated-norm part and the arm B layout are design counts. No builder exists to check them against. The norm is about 0.8% of the M2 head's columns (about 780 of about 100,000 per token), so an error there cannot move the verdict.

Timings marked "estimate" are linear interpolations, not measurements.

## 1 What M2 proves

**One V head of one Qwen3.8 Gated DeltaNet layer, end to end, T = 16, F = 12**, on synthetic inputs of the published shapes. The statement runs from that head's in_proj outputs to its gated-norm output. All 48 V heads of a layer have the same statement with different public inputs, so the layer cost is 48 times the head cost (section 6, an extrapolation).

The old M2 line in FEASIBILITY.md ("one full layer at exact shape, d 5,120, SwiGLU 17,408") is out of reach of the research harness. That layer is about 3.8e8 multiply-adds per token in its matrices:
- in_proj_qkv 5,120 x 10,240
- in_proj_z 5,120 x 6,144
- in_proj_a and in_proj_b 5,120 x 48
- out_proj 6,144 x 5,120
- MLP 3 x 5,120 x 17,408

As affine terms with public weights, that is about 70 times the whole M1b statement per token. It is also a dense matmul, an operator family FlashProve already proves in its main prover (docs/model.md sections 5 and 7). M2's job is the part that is new, so the matrices stay out (section 5).

## 2 Statement

Per token t < 16, the head's public inputs (all integers at 2^F unless noted):

| name | count | what | class (verifier-enforced) |
|---|---|---|---|
| xq, xk, xv | 3 x 128 | in_proj_qkv outputs of this head's channels, before the conv | \|x\| < 2^31 |
| ar, br | 2 | in_proj_a and in_proj_b outputs | \|x\| < 2^20 |
| z | 128 | in_proj_z outputs | \|x\| < 2^20 |
| y | 128 | the gated-norm output, the statement's result | \|y\| < 2^31 |

Per head, public and fixed by the shape, not per token:
- conv kernels (3 x 128 x 4 taps, at 2^12)
- A_log and dt_bias (folded into the decay table, section 3)
- the gated-norm gain (128)
- S0 (128 x 128, \|S0\| < 2^18)
- S_T (128 x 128, \|S_T\| < 2^18)

Private, and committed in the product oracle:
- every state S_t
- M, delta (two limbs)
- the head output o
- the norm's scalars and w

In M1/M1b, o was public. In M2 it is private, because the result is now y.

## 3 Gate, conv and norm: which are proved

| step | in M2 | why |
|---|---|---|
| causal conv1d, kernel 4, zero padding (on xq, xk, xv) | **verifier recomputes** | a function of public integers only |
| SiLU on the conv outputs | **verifier recomputes** | a function of public integers only |
| q/k L2 norm, q scale 1/sqrt(128) | **verifier recomputes** | a function of public integers only |
| decay a = exp(-A softplus(ar + dt_bias)), beta = sigmoid(br) | **verifier recomputes** | a function of public integers only |
| recurrence (M, delta, S', o) | **proved** | private state |
| gated RMSNorm of o, times SiLU(z) and gain | **proved** (norm), **verifier recomputes** cg = round(2^F gain SiLU(z) sqrt(128)) | the norm reads private o; cg is public-only |
| in_proj, out_proj, pre-norm RMSNorm, residual, MLP | **not proved in M2** | dense family, proved elsewhere; inputs to M2 are public |

**Why recomputation is enough at this boundary.** At this statement boundary every input to conv, SiLU, L2 norm and the gates is public. A relation over them would prove that the verifier's own computation is right, and the verifier can just do that computation. The cost is O(T x 128 x 4) integer operations, about 0.2 ms at T = 16. The results enter the proof only as relation coefficients and targets (k, q, a, beta), as public values did in M1b.

**What changes at M3.** When the in_proj outputs become private (committed by the matmul sub-proof), these steps must become in-relation gadgets:
- conv: 4 product gates per channel per token
- SiLU: a Ts-style table lookup, as docs/model.md section 7
- L2 norm: isqrt and reciprocal, as in section 4.4 below
- gates: two table lookups per token

By the same counting rules, that is under 10 columns per channel per token, about 4,000 per head per token. That is under 1% of the head's state work (sections 5 and 6). An optional build arm M2-R may prove them in-relation as a rehearsal. It is not needed for the M2 claim.

**Determinism of recomputation.** The prover and verifier must derive identical integers. The design pins:
- **conv**: integer taps at 2^12; acc = sum of w_tau x_(t - tau); c = floor(acc / 2^12)
- **SiLU**: a public table on clamped keys (docs/model.md Ts form), not libm at verify time
- **L2 norm**: integer isqrt with round half up, eps = 17 at 2^2F. For q the divisor is multiplied by round(sqrt(128) x 2^12) and the numerator by 2^12.
- **a and beta**: two public tables keyed by clamp(ar) and clamp(br), built once with correctly rounded exp, as the docs/model.md tables are

The prototype `head_reference.py` uses float64 numpy at the table points. A build lane must replace that with the tables, and add a test that two builds give byte-identical tables.

## 4 Lowering (on the merged M1b machinery)

### 4.1 Unchanged from M1b
- Product oracle a, b, c (toy PSC).
- Wide affine relations.
- RNG (blocks/iop/rng.h) with its LKP digit lookup, in ONE proximity-test group.
- RNG cells laid directly on product row a, so the range-checked integers are the cells the relations read. No wiring relations.
- The staged-floor recurrence (M1 README).
- delta two-limb at 2^18.

### 4.2 RNG cell classes and sizing (hard rule b)

Every RNG cell class has an honest contract |x| < 2^18. Each class sits in a 16-column RNG matrix with window 2D = 2^23 (b0 = 12, b1 = 11). An honest combination is therefore at most 16 x 2^18 = 2^22 = D, which is RNG's completeness condition, and RNG proves |x| < 2^23 (soundness side).

| class | honest contract | why the contract holds | measured max (H4, 20 runs x 1,024 steps) |
|---|---|---|---|
| S' | \|S'\| < 2^18 | builder rejects otherwise (statement refused, never saturated) | 150,189 |
| M | \|M\| < 2^18 | as M1b | 53,294 |
| delta_lo, delta_hi | delta = 2^18 hi + lo, lo in [0, 2^18), \|hi\| < 2^18 | split (registered, D4) | lo 262,143 (its bound), hi 1 |
| o (new, private) | \|o\| < 2^18 | builder rejects otherwise. Nearly provable: \|o\| <= \|S'\|max x \|\|q\|\|_1 / 2^F, and \|\|q\|\|_1 <= sqrt(128) \|\|q\|\|_2 <= 2^F + 64 after rounding, so \|o\| < 2^18 (1 + 2^-6). In practice it is 40x below. | 6,379 |
| w (new) | \|w\| <= 2^12 | provable: \|w\| <= \|o\| Rc / 2^24 <= \|o\| 2^12 / sigma <= 2^12, since \|o\| <= sigma | 4,048 |

No other class needs a split. The registered split rule (H4) did not have to fire. The M2 head has 272,384 RNG cells at T = 16: 17,024 cell rows, laid as two matrices of 16,384 and 1,024 rows. That gives 348,160 digit entries at N = 10.

### 4.3 Remainders (hard rule c): two arms

The M1b result showed remainder bits are 12 of the 17.4 product columns per state cell per token. The design registers two arms:

**Arm A: exact bits** (M1b as is). A width-w remainder costs:
- w columns [x, x, x]
- 2w relations (a = b, c = a)
- w terms in the floor relation

**Arm B: lookup-exact remainders.**
- Each 12-bit remainder (F = 12) is ONE product cell [r, 0, 0] in a key region of row a. It is a direct key of a second LKP instance into the public range table {0, .., 2^12 - 1}: LkpTablePart with empty rows, one function, unshifted.
- A 24-bit remainder (the M floor, 2^2F) is two such cells, r = lo + 2^12 hi. Both terms go directly into the floor relation, so no extra relation is needed.
- An exact interval [0, 2^12) on each limb gives r in [0, 2^24) exactly, so floor uniqueness is unchanged from M1b.

This is an exact range proof, not RNG's approximate one, so the floor-uniqueness argument of M1b goes through as is. The keys come in parts (LkpPublic::parts, allowed for one unshifted function). The key region is laid like RNG's cells, and LKP's key claim becomes a laid_form on message 0, as `rng_key_row` does for the digits. The multiplicities are one extra message with about 20 planes x 2^12 entries.

**Savings (count model, H2 and H3):**

| | arm A | arm B | B / A |
|---|---|---|---|
| M1b shape (T = 4, public o, no norm): product columns per state cell per token | 17.41 | 6.07 | **0.349** |
| same: relations | 2,231,808 | 609,792 | **0.273** |
| same: terms | 5,174,272 | 1,186,816 | 0.229 |
| same: table log-length | 21 | 19 | |
| M2 head (T = 16, private o, norm): gate columns + range cells + keys | 4,649,440 | 1,605,872 | 0.345 |
| same: relations | 9,042,944 | 2,402,432 | 0.266 |
| same: table log-length | **23 (does not fit 2^22)** | **21** | |
| largest T at log-length <= 22 | 14 | 41 | |

Arm B removes, per remainder bit, one gate column and two relations. In their place it adds one key per 12 bits plus a small fixed multiplicity message. That is about 2.9x fewer product columns and about 3.7x fewer relations. **Arm A cannot hold M2 at T = 16 in the 2^22 table. Arm B can, and holds it at the M1b table size (2^21).** Arm B is therefore the primary arm for M2. Arm A at T = 8 is the fallback if arm B's build fails.

### 4.4 Gated RMSNorm (new, proved)

Per token, with Vx = sum of o_j^2 (exact, in the relation) and eps' = round(128 x 1e-6 x 2^2F) = 2,147:

```
sigma = isqrt(Vx + eps')        e1 = Vx + eps' - sigma^2 >= 0,  e2 = sigma^2 + 2 sigma - Vx - eps' >= 0
Rc    = floor(2^36 / sigma)     rr = 2^36 - Rc sigma >= 0,      sigma - 1 - rr >= 0
w_j   = floor(o_j Rc / 2^24)    remainder in [0, 2^24)
y_j   = floor(cg_j w_j / 2^F)   remainder in [0, 2^F); cg_j public (section 3); y_j public
```

The sigma here is the root of the sum, not of the mean. The sqrt(128) goes into cg, as docs/model.md section 5 puts it into the weights.

**Gates per token:**
- sigma x sigma, Rc x sigma
- 128 x (o x o), 128 x (o x Rc)

**Exact limbs per token** (arm B keys / arm A bits): sigma 2, e1 2, e2 2, Rc 3, rr 2, gap 2, and per j: one 24-bit remainder (2) and one 12-bit remainder (1).

**Uniqueness.** The bounds are provable from the cell contracts (|o| < 2^18, so Vx < 2^43, sigma < 2^22, e1, e2 <= 2 sigma < 2^23, Rc < 2^36). e1 >= 0 and e2 >= 0 pin sigma = isqrt. rr in [0, sigma) pins Rc. Each floor has an exact remainder.

**No wrap.** RNG proves |o| < 2^23. The largest magnitudes are then:
- sum of o^2 < 2^53
- o Rc < 2^59
- cg w < 2^47

All are below p.

The H4 range suite found no exact limb outside its interval and no negative exact quantity in 20/20 runs.

### 4.5 Verifier entry point (hard rule a)

`verify_m2(shape_constants, statement_words, proof_bytes)` is the only entry. The prototype is `verify_from_words` in `research/operators/qwen_deltanet_m2/admit_proto.cpp`, on the M1b statement. It runs these steps:
1. Fix the shape from the verifier's own constants. The header words must equal them, and the word count must be exact.
2. Decode every public word as a canonical Goldilocks element (< p), read it as a signed integer (a word above p/2 is negative), and check it against its class bound (section 2). A non-canonical word, a huge element, or an integer outside its class is rejected **here**.
3. Recompute the public-only stage (section 3) from the decoded integers.
4. Derive every relation target and coefficient from those integers with the relation-only builder.
5. Size the run (a pure function of the shape) and run the unchanged proof verifier.

There is no `admissible()` that a caller runs separately, and no entry point that accepts caller-built relations or a caller-built `LookupRun`. The low-level `lookup_verify(run, ...)` stays a library internal. **The M2 build must not export it as a verifier.**

The prototype measured this on the M1b statement (RESULTS.md H5):
- 10/10 honest seeds accepted.
- 34/34 hostile encodings rejected at the expected stage, including a huge field element in each of the 8 public classes and the #63 review's R9.
- For R9, an honest proof of the statement with o' = o - 2^-F mod p is **accepted** by the current path, `lookup_verify` with caller-built relations and `admissible()` skipped. The new entry **rejects** it at decode.

## 5 What stays unproved in M2

- in_proj_qkv, in_proj_z, in_proj_a/b and out_proj (the matmuls)
- the layer's pre-norm RMSNorm and residual
- the SwiGLU MLP
- the full-attention layers
- the link from one layer to the next

In M2 the in_proj outputs are public statement values. Nothing in M2 shows they came from a given x and weights. That is M3's link (a matmul sub-proof whose outputs are the committed inputs of the M2 relation, under the shared-wire or same-oracle tie of research/operators/shared_wires). Conv, SiLU, L2 norm and gates move from "verifier recomputes" to "proved" at that point (section 3).

## 6 Cost (counts exact; time estimates indicative)

| | arm A | arm B |
|---|---|---|
| M2 head, T = 16: product table | 2^23 (over) | 2^21 |
| relations | 9.04M | 2.40M |
| RNG digit entries | 348,160 | 348,160 |
| LKP keys (remainders) | 0 | 276,688 |
| prove, estimate (linear in table length from #47 / #63) | n/a | about 39 s |
| peak RSS, estimate (M1b at 2^21: 4.4 GB) | n/a | about 4.5 GB |
| per token, one layer (48 heads): relations | 27.1M | 7.21M |
| per token, one layer: product columns + cells + keys | 13.9M | 4.82M |
| per token, 48 DeltaNet layers: product columns + cells + keys | 670M | 231M |

The last row is the number M3 must beat with chunked state commitment or streaming. FEASIBILITY.md's per-token state alone is 37.7M cells per token. Arm B's 231M is 6.1 product cells per state cell. That fits no single-host table at T = 1,024 without chunking. M2 does not resolve this, and is not meant to.

## 7 M2 build preregistration sketch (for the build lane, not run here)

The build lane must keep these, and register numbers in its own PREREG before code:
- **H1 honest:** 10/10 at T = 16 (seeds 1..10, the H4 generator, R1).
- **H2 hostile:** M1b's 44 classes ported, plus:
  - o tamper with its floor preserved
  - the norm: sigma +1 with e1/e2 shifted, Rc +1 with rr shifted, w +1 with its remainder shifted
  - one remainder key off-table (arm B: key 2^12, which only a hostile LKP prover can send)
  - the limb re-split
- **H3 range:** H4 of this lane re-run on the build's reference, 20/20.
- **H4 admission:** this lane's H5 suite on the M2 statement words, plus a huge element in xq, ar and z, and the R9 analogue on y. All rejected by `verify_m2` alone.
- **Kill:** no honest T = 16 arm B proof in 6 h, then fall back to arm A at T = 8 and report.
