# Qwen DeltaNet M2: design

Issue #32. PREREG: [PREREG.md](PREREG.md) (first commit 84776893). Results and verdict: [RESULTS.md](RESULTS.md).
This is a design. Nothing in it is proved, and no M2 proof exists.

The numbers are counts from `research/operators/qwen_deltanet_m2/count_model.py`:
- The recurrence part of the model reproduces the measured M1 and M1b statements exactly (RESULTS.md H1).
- The gated-norm part and the arm B layout are design counts. No builder exists to check them against. The norm is about 0.8% of the M2 head's columns (about 780 of about 100,000 per token), so an error there cannot move the verdict.
- The norm's **term** counts are counted for one stated lowering (section 4.4.1). A build that reuses operands differently has a different, equally valid total. They are not checked by a builder.

Timings marked "estimate" are linear interpolations, not measurements.

**Third review (#66, 2026-11-09).** A third review found that section 4.4's no-wraparound argument relied on |cg| < 2^24 while no section made the verifier check the cg it recomputes. It gave 22 modular-alias counterexamples to the stated norm lowering under a large verifier-fixed gain. They are counterexamples to this document's contract, not forged proofs: no M2 builder exists. This revision makes the bound a checked admission rule (section 3.1), audits every other derived value the same way (section 3.1), writes out the norm lowering and the full no-wrap argument (sections 4.4.1 and 4.4.2), and makes the guard and its regression a build requirement (sections 4.5 and 7).

## 0 What M2 is for (post-review, #66 must-fix 1)

**M2 is a rehearsal of the proving machinery for M3. As a standalone statement it is redundant.** At the M2 boundary every input is public (section 2) and every step is a deterministic integer function of those inputs. So a verifier can compute every state S_t, every M and delta, the head output o and the output y itself, in about O(T D^2) integer operations: milliseconds, against a verify of seconds. The argument that moves conv, SiLU, the q/k norm and the gates to verifier recompute (section 3: "proving them would add cost and no soundness") applies to the whole M2 statement. A verifier that only wants to know y for these public inputs should recompute it, not check a proof.

In this document, S_t, M, delta, o and the norm intermediates are **witness values: not in the statement, and computable from public inputs at the M2 boundary**. Nothing in M2 hides them, and M2 makes no hiding or zero-knowledge claim about them. Earlier drafts called them "private". That word was wrong and is gone.

What M2 is worth, as a rehearsal:
- the measured cost of the recurrence and the gated-norm lowering at the real head shape (columns, relations, prove and verify time), which M3 inherits unchanged;
- the arm-B composition (a second LKP instance for remainders, keyed on product-oracle cells, next to RNG's), which has not been built in this repo;
- the verifier entry that admits its own integer inputs (section 4.5), which M3 needs in any case.

What M2 does **not** de-risk: none of the operator families that are new in FEASIBILITY.md. Causal conv1d, the decay and beta tables and the per-head q/k L2 norm all moved to verifier recompute (section 3), so M2 builds no gadget for them. Their in-relation form is first built at M3 (or in the optional rehearsal arm M2-R, section 3).

**What M3 must add so that proving is not redundant.** The proof has a point only when the verifier cannot recompute the result from what it holds. At least one of these must hold for each proved step:
1. **Committed inputs.** The in_proj outputs (xq, xk, xv, ar, br, z) are not public words but committed cells, outputs of a matmul sub-proof on the layer input and the committed weights (docs/model.md), tied to the M2 relation by shared wires or the same oracle (research/operators/shared_wires). Then conv, SiLU, the q/k norm and the gates must be in-relation gadgets (section 3, "What changes at M3"), and the conv history (section 2) is a committed value carried from the previous chunk.
2. **Committed state.** S0 and S_T are commitments carried between chunks (issue #34), not 2 x 16,384 public words. Then the recurrence proves a transition between commitments, which no verifier can recompute without the state.
3. **A statement the verifier does not hold in full.** The verifier receives a commitment to the model and the final output, not every layer's in_proj outputs.

M2 has none of these by design. Every M2 number is reported as rehearsal cost, not as the cost of a useful proof.

## 1 What M2 proves

**One V head of one Qwen3.8 Gated DeltaNet layer, T = 16, F = 12**, on synthetic inputs of the published shapes. The statement runs from that head's in_proj outputs to its gated-norm output. "End to end" means end to end within the head, with all inputs public: by section 0 the whole statement is verifier-computable, and M2 is a rehearsal for M3. All 48 V heads of a layer have the same statement with different public inputs, so the layer cost is 48 times the head cost (section 6, an extrapolation).

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
- the gated-norm gain (128 values, one per channel)
- S0 (128 x 128, \|S0\| < 2^18)
- **H, the conv history (3 x 384): the last 3 pre-conv inputs of each of the head's 384 conv channels (128 q, 128 k, 128 v) before token 0, \|H\| < 2^31, the class of xq, xk, xv**
- S_T (128 x 128, \|S_T\| < 2^18)

**Shape constants are fixed by the verifier, and they are not trusted to be in range.** The kernels, A_log, dt_bias and the gain are the verifier's own configuration, not words an attacker sends. This document puts no bound on them. A bound on a constant would not be enough anyway: what enters a relation is a value the verifier **derives** from the constants and the decoded words. So the requirement is on the derived values:

| derived value (verifier-recomputed, section 3) | count per token | class (verifier-enforced at derive, section 3.1) |
|---|---|---|
| k | 128 | \|k\| <= 2^F |
| q | 128 | \|q\| <= 2^F |
| a, beta | 2 | 0 <= a, beta <= 2^F |
| v | 128 | \|v\| < 2^31 |
| cg | 128 | \|cg\| < 2^24 |

**Requirement.** The verifier checks every derived value against this table before it builds any relation and before any value is converted to a field element. A value outside its class is a reject at the derive stage. Section 3.1 gives the rule, the reasons and the audit.

Witness, laid in the product oracle (not in the statement; computable from the public inputs at this boundary, section 0; no hiding claim):
- every state S_t
- M, delta (two limbs)
- the head output o
- the norm's scalars and w

In M1/M1b, o was a statement value. In M2 it is a witness value, because the statement's result is now y. That is a change of statement boundary, not a privacy property.

**Conv history (post-review, #66 must-fix 2).** The causal conv at token t reads the inputs at t, t - 1, t - 2 and t - 3. At t = 0 the model pads with zeros only when token 0 starts the sequence. The statement allows any S0, and a window with S0 != 0 is a window that does not start the sequence, so its conv needs the 3 inputs before it. Two options were on the table: (a) make H a public, class-bounded input, or (b) restrict the statement to S0 = 0 at sequence start. **M2 takes (a).** Reasons:
- It is cheap. H is 1,152 words against the statement's 16,384 for S0 and 16,384 for S_T, plus 16 x 642 per-token words (xq, xk, xv, ar, br, z, y). Decoding it is a range check per word. The verifier's conv recompute reads it in place of the zero padding, so the conv rule is one rule for every window, with no special first window.
- (b) would make M2 a statement about sequence starts only, and M3's chunking (state committed between chunks, #34) needs exactly the non-zero case. Under (a), M3 changes H from public words to a committed value carried from the previous chunk, like S0. Under (b), M3 would have to add the history then.
- S0 = 0 with H = 0 is the sequence-start case of (a), so (a) loses nothing.

The admission prototype now has H in its wire format and decodes it with its class bound: a huge element, the first value outside the class on both sides and a non-canonical word are rejected at decode (RESULTS.md, post-review rerun). The M1b relations the prototype proves do not read H (M1b has no conv), so a changed but in-class H is accepted there. That is recorded as a control, not a defence. In M2 the verifier's conv recompute reads H, so a changed H changes k, q and v and must fail at the proof verifier. That case is in the build's H4 suite (section 7).

## 3 Gate, conv and norm: which are proved

| step | in M2 | why |
|---|---|---|
| causal conv1d, kernel 4, on xq, xk, xv, with the public history H in place of the padding before token 0 (H = 0 at sequence start) | **verifier recomputes** | a function of public integers only |
| SiLU on the conv outputs | **verifier recomputes** | a function of public integers only |
| q/k L2 norm, q scale 1/sqrt(128) | **verifier recomputes** | a function of public integers only |
| decay a = exp(-A softplus(ar + dt_bias)), beta = sigmoid(br) | **verifier recomputes** | a function of public integers only |
| recurrence (M, delta, S', o) | **proved** (rehearsal, section 0) | witness values; at this boundary also verifier-computable |
| gated RMSNorm of o, times SiLU(z) and gain | **proved** (norm, rehearsal), **verifier recomputes** cg = round(2^F gain SiLU(z) sqrt(128)) **and rejects unless \|cg\| < 2^24** (section 3.1) | the norm reads the witness o; cg is public-only |
| in_proj, out_proj, pre-norm RMSNorm, residual, MLP | **not proved in M2** | dense family, proved elsewhere; inputs to M2 are public |

**Why recomputation is enough at this boundary.** At this statement boundary every input to conv, SiLU, L2 norm and the gates is public. A relation over them would prove that the verifier's own computation is right, and the verifier can just do that computation. The same holds for the recurrence and the norm (section 0); M2 proves those anyway, as the rehearsal for M3, and does not prove conv, SiLU, L2 norm or the gates. The cost is O(T x 128 x 4) integer operations, about 0.2 ms at T = 16. The results enter the proof only as relation coefficients and targets (k, q, a, beta), as public values did in M1b.

**What changes at M3.** When the in_proj outputs become committed values (outputs of the matmul sub-proof, not public words), these steps must become in-relation gadgets:
- conv: 4 product gates per channel per token
- SiLU: a Ts-style table lookup, as docs/model.md section 7
- L2 norm: isqrt and reciprocal, as in section 4.4 below
- gates: two table lookups per token

By the same counting rules, that is under 10 columns per channel per token, about 4,000 per head per token. That is under 1% of the head's state work (sections 5 and 6). An optional build arm M2-R may prove them in-relation as a rehearsal. It is not needed for the M2 claim.

**Determinism of recomputation.** The prover and verifier must derive identical integers. The design pins:
- **conv**: integer taps at 2^12; acc = sum of w_tau x_(t - tau); c = floor(acc / 2^12); x_(-1 - tau) = H[tau] for tau = 0, 1, 2
- **SiLU**: a public table on clamped keys (docs/model.md Ts form), not libm at verify time
- **L2 norm**: integer isqrt with round half up, eps = 17 at 2^2F. For q the divisor is multiplied by round(sqrt(128) x 2^12) and the numerator by 2^12.
- **a and beta**: two public tables keyed by clamp(ar) and clamp(br), built once with correctly rounded exp, as the docs/model.md tables are

The prototype `head_reference.py` uses float64 numpy at the table points. A build lane must replace that with the tables, and add a test that two builds give byte-identical tables.

### 3.1 Derived-value admission (third review, #66 must-fix M1)

**The gap.** Section 4.5 decoded and class-checked every statement word, then recomputed the public-only stage, then derived relations. It did not check what the recompute produced. Section 4.4 then used |cg| < 2^24 as if it were known. It was not: cg = round(2^F gain SiLU(z) sqrt(128)), and the gain had no bound. RESULTS.md H4 measured max |cg| = 230,259 over 20 runs at gain 1. A measured range is not an admission rule.

**What goes wrong without the rule.** The y floor is the relation cg_j w_j - 2^F y_j - r_j = 0 over the Goldilocks field, with r_j in [0, 2^F) exact, w_j a range cell and y_j public with |y_j| < 2^31. If |cg_j w_j| can reach p, the relation has a solution (y_j, r_j) in those ranges that is not the integer floor. The review's example: o = (4096, 0, ..), so sigma = 4096, Rc = 2^24, w_0 = 4096; with cg_0 = 2^62 the true floor is 2^62, outside the y class, and y_0 = 2^30 - 1 with r_0 = 3,072 satisfies the relation mod p. There are 22 such cases (o_0 in {4096, 8192}, cg_0 = 2^52 .. 2^62). `research/operators/qwen_deltanet_m2/norm_alias_regression.py` rebuilds all 22 from the equations of section 4.4 and checks every listed witness range: 22 of 22 are aliases without the rule. Each one also has a complete compatible statement (a 16-token recurrence that produces that o). The gain they need is about 1.3e11 to 1.4e14, a verifier-fixed constant.

**The rule (option a: a verifier check).** After the recompute stage and before any relation is built or any integer is converted to a field element, the verifier checks every derived value against its class in section 2: every k_i and q_i, a, beta, every v_j and every cg_j, for every token. One value outside its class is a reject with verdict "derive". It is never clamped, saturated or reduced mod p, and the process never exits. The check is on the integers the recompute produced, with the same checked arithmetic as section 4.5.

**Why (a) and not (b).** Option (b) was to restrict the admitted shape and constants so that the bound is proved for every admitted z.
- (a) puts the rule on the value that enters the relation. The no-wrap argument (section 4.4.2) then cites a checked fact. It does not depend on the gain, on how SiLU is tabulated, or on a float rounding argument.
- (b) is true at gain 1, by arithmetic: |z| < 2^20 at 2^F means |z| < 256 in real units, |SiLU(z)| < 256, so |cg| <= 2^F x 2^3.5 x 256 x |gain| = 2^23.5 |gain| (plus rounding), which is below 2^24 for |gain| <= 1.41. The regression script (part G) checks this over every in-class z with the float64 formula of `head_reference.py`: max |cg| is 11,863,272 at gain 1 and 16,727,213 at gain 1.41. But real gains are not 1, the argument would have to be redone for every table and every constant, and a later change to the z class would silently break it.
- (a) costs 128 comparisons per token for cg, and 514 for all six derived classes. It is also the form M3 can carry over: there cg is a committed value, and the same bound becomes an in-relation range check (see the last paragraph).

**Completeness cost.** A statement whose gain makes some |cg_j| >= 2^24 for its z is refused, not saturated. By the arithmetic above, the check cannot fire when |gain| <= 1.41. A head with a larger gain can be refused on some inputs, and needs a larger bound. **The real Qwen gains have not been measured in this lane.** The no-wrap argument has room: with every other bound as in section 2, the y floor stays below p for any cg bound up to about 2^41 (section 4.4.2). Raising the bound is a design change with its own review. The y class (|y| < 2^31) then has to be re-derived with it, because the size of y follows the size of cg, and the y class is part of the same no-wrap sum.

**Audit of every verifier-derived value** (the review asked for the others to be checked the same way). "Needs" is the largest bound on that value for which every identity of section 4.4.2 stays below p with all other values at their class maxima (computed by the regression script, part E). "By construction" says whether the class also follows from the recompute rule for every admitted input.

| derived value | multiplies which witness value | no-wrap needs | class admitted | enforced | by construction? |
|---|---|---|---|---|---|
| k_i (L2 norm of SiLU(conv(xk))) | S (memory read), delta (update) | \|k\| <= 4,194,272 (just under 2^22) | \|k\| <= 2^F | derive check | **yes, for every input.** s = isqrt(sum u^2 + 17) >= \|u_i\|, so \|2^F u_i / s\| <= 2^F, and round half up keeps it in [-2^F, 2^F]. The check cannot fire; it guards a build error. |
| q_i (same, with 1/sqrt(128)) | S' (output gate) | \|q\| <= 17,179,871,196 (2^34.0) | \|q\| <= 2^F | derive check | **yes:** \|q\| <= round(2^24 / 46,341) = 362. Sampled 774 vectors up to 2^40: max 362. |
| a (decay table) | S, P = sum S k | a <= 4,194,272 (just under 2^22) | 0 <= a <= 2^F | derive check, and a table-build check that every entry is in [0, 2^F] | yes if the table is built as specified (exp of a non-positive number). **Was not stated as checked.** |
| beta (sigmoid table) | v - M | beta <= 8,552,332,728 (2^32.99) | 0 <= beta <= 2^F | derive check, and the table-build check | yes if the table is built as specified. **Was not stated as checked.** |
| v_j (SiLU(conv(xv))) | enters v - M, which beta multiplies | \|v\| <= 4,501,400,586,551,297 (2^52.0) | \|v\| < 2^31 | derive check | **no. Second gap.** M1b's no-wrap argument used \|v\| < 2^31, and M1b checked it at decode because v was a statement word. In M2 v is recomputed: its size depends on the conv taps (unbounded) and on the range of the SiLU table (not stated). Now checked. |
| cg_j | w | \|cg\| <= 2,199,022,468,607 (2^41.0) | \|cg\| < 2^24 | derive check | **no. The review's gap.** Holds for \|gain\| <= 1.41 only. Now checked. |

Values that are not derived and need nothing new: S0, S_T, H, xq, xk, xv, ar, br, z and y are statement words, each class-checked at decode (section 2). The constants eps', 2^F, 2^18, 2^24 and 2^36 are fixed by this document. o is a witness value in M2.

**Gaps found, in total: two that could alias (cg, the review's; v, found by this audit) and one unstated check (a and beta).** For v the regression script (part D) shows the delta floor has the same kind of alias for a derived v of 2^52 to 2^62, on that one relation only (not a whole statement): 11 of 11, each rejected at derive under the rule. Reaching such a v from in-class inputs needs conv taps of about 2^19 each in real units (four taps, inputs at the 2^31 class edge, so that the conv output reaches 2^52) and a SiLU without a clamp, so it is further from any real configuration than the cg case. The fix is the same rule.

**Completeness cost for v.** Between 2^31 and about 2^52 there is no alias (no-wrap holds, section 4.4.2), but the check does fire, and with an unclamped SiLU it can fire on ordinary constants: four taps of 1.0 on in-class inputs near 2^31 give a conv output near 2^33. Such a statement is refused at derive. (Inputs that large are 2^19 in real units. The synthetic suite's largest pre-conv input is 1,478,242 integer units, about 361 in real units.) With the clamped SiLU table that section 3 requires, v is bounded by the table's largest entry, and the check cannot fire if that entry is below 2^31. This document does not yet fix the table's key clamp, so that bound is an obligation on the build's pinned tables. H4 measured max |v| = 527,711 on the synthetic suite.

**The recompute's own arithmetic.** The rule above is about values that enter relations. The recompute also has intermediates that no relation sees: the conv accumulator (4 taps times \|x\| < 2^31, taps unbounded), and the L2 norm's sum of squares (128 x u^2, which passes 2^63 once \|u\| reaches about 2^28). Section 4.5 already requires checked arithmetic on everything that touches a public input. For these two the build must use a 128-bit type or reject on overflow at "derive". A wrapped intermediate would give a wrong k, q or v that still passes its class check.

**At M3.** When the in_proj outputs are committed, the verifier cannot recompute k, q, a, beta, v or cg. Each bound in the table then has to be proved in the relation (an exact-limb or range-cell constraint on the committed coefficient) or carried by the commitment's own admission. A bound that the M2 verifier checks and the M3 relation does not prove would reopen this gap.

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
| o (new, witness) | \|o\| < 2^18 | builder rejects otherwise. Nearly provable: \|o\| <= \|S'\|max x \|\|q\|\|_1 / 2^F, and \|\|q\|\|_1 <= sqrt(128) \|\|q\|\|_2 <= 2^F + 64 after rounding, so \|o\| < 2^18 (1 + 2^-6). In practice it is 40x below. | 6,379 |
| w (new) | \|w\| <= 2^12 | provable for honest o: \|w\| <= \|o\| Rc / 2^24 <= \|o\| 2^12 / sigma <= 2^12, since \|o\| <= sigma. The no-wrap argument (section 4.4.2) does not use this; it uses only what RNG proves, \|w\| < 2^23. | 4,048 |

No other class needs a split. The registered split rule (H4) did not have to fire. The M2 head has 272,384 RNG cells at T = 16: 17,024 cell rows, laid as two matrices of 16,384 and 1,024 rows. That gives 348,160 digit entries at N = 10.

### 4.3 Remainders (hard rule c): two arms

The M1b result showed remainder bits are 12 of the 17.4 product columns per state cell per token. The design registers two arms:

**Arm A: exact bits** (M1b as is). A width-w remainder costs:
- w columns [x, x, x]
- 2w relations (a = b, c = a)
- w terms in the floor relation

**Arm B: lookup-exact remainders.**
- Each 12-bit remainder (F = 12) is ONE product cell [r, 0, 0] in a key region of row a. It is a direct key of a second LKP instance into the public range table {0, .., 2^12 - 1}: LkpTablePart with empty rows, one function, unshifted.
- A 24-bit remainder (the M floor, 2^2F) is two such cells, r = lo + 2^12 hi. Both terms go directly into the floor relation, so no extra relation is needed. (This departs from PREREG D5, which registered two limbs plus one recombination relation. The deviation is disclosed in RESULTS.md and is worth 512 relations at the M1b shape. No ratio or verdict moves.)
- An exact interval [0, 2^12) on each limb gives r in [0, 2^24) exactly, so floor uniqueness is unchanged from M1b.

This is an exact range proof, not RNG's approximate one, so the floor-uniqueness argument of M1b goes through as is. The keys come in parts (LkpPublic::parts, allowed for one unshifted function). The key region is laid like RNG's cells, and LKP's key claim becomes a laid_form on message 0, as `rng_key_row` does for the digits.

**Multiplicities (post-review, #66 should-fix 1).** The remainder lookup sends its multiplicities as planes x 2^12 places, like RNG's (`rng_planes_places`). At T = 16 it has 278,528 keys (parts 2^18 + 2^14), so 19 planes, 77,824 places. RNG's digit lookup needs 21 planes x 2^13 = 172,032 places. The design puts both in RNG's multiplicity row (message 3), which then holds 249,856 places, well under 2^21. The count model now sizes this row and lets it bound the table length. Neither H2 nor H3 moves (RESULTS.md, post-review correction).

**Transcript separation between the two lookup instances (build requirement).** The arm-B run has two LKP instances in one chain: RNG's digit lookup (shifted, g = 1, d = 13) and the remainder lookup (unshifted, one function, parts, d = 12). The build must give them distinct challenges that are bound to distinct labels:
- each instance's public parameters (LkpPublic: parts, d, mu, live, tables, shifted, read_from) are bound into the transcript under its own Binder label ("range check: digit lookup", "remainder lookup") before any of its challenges are drawn;
- each instance draws its own alpha (and RNG its own theta) after both instances' key and multiplicity messages are fixed, so no challenge of one instance is available while the other's keys can still change;
- the remainder lookup's multiplicities are in a fixed, public place range of message 3, disjoint from RNG's, and each instance's `read_from` names only its own messages.

The build's hostile suite must include a **challenge-replay case**: a prover that reuses the digit lookup's alpha (or its sumcheck challenges) as the remainder lookup's, or swaps the two instances' order, must be rejected by the verifier, and the case must show that an honest proof whose two instances are relabelled does not verify (section 7).

**Savings (count model, H2 and H3):**

| | arm A | arm B | B / A |
|---|---|---|---|
| M1b shape (T = 4, public o, no norm): product columns per state cell per token | 17.41 | 6.07 | **0.349** |
| same: relations | 2,231,808 | 609,792 | **0.273** |
| same: terms | 5,174,272 | 1,186,816 | 0.229 |
| same: table log-length | 21 | 19 | |
| M2 head (T = 16, witness o, norm): gate columns + range cells + keys | 4,649,440 | 1,605,872 | 0.345 |
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
y_j   = floor(cg_j w_j / 2^F)   remainder in [0, 2^F); cg_j derived and admitted, |cg_j| < 2^24 (section 3.1); y_j public
```

The sigma here is the root of the sum, not of the mean. The sqrt(128) goes into cg, as docs/model.md section 5 puts it into the weights.

**Gates per token:**
- sigma x sigma, Rc x sigma
- 128 x (o x o), 128 x (o x Rc)

**Exact limbs per token** (arm B keys / arm A bits): sigma 2, e1 2, e2 2, Rc 3, rr 2, gap 2, and per j: one 24-bit remainder (2) and one 12-bit remainder (1).

**Uniqueness.** The bounds are provable from the cell contracts (|o| < 2^18, so Vx < 2^43, sigma < 2^22, e1, e2 <= 2 sigma < 2^23, Rc < 2^36). e1 >= 0 and e2 >= 0 pin sigma = isqrt. rr in [0, sigma) pins Rc. Each floor has an exact remainder. All of this is over the integers, so it needs the no-wrap argument of section 4.4.2.

The H4 range suite found no exact limb outside its interval and no negative exact quantity in 20/20 runs.

#### 4.4.1 The lowering, relation by relation (third review, #66 should-fix S1)

The earlier text gave the equations but not the relations, and the count model's term counts did not match any one lowering of them. This is the lowering the count model now implements. "pieces(x)" is the weighted sum of the exact pieces of x: in arm B one key cell per 12 bits (coefficients 1, 2^12, 2^24), in arm A one boolean column per bit (coefficients 2^i), each with its two 2-term boolean relations. A gate is a product column [a, b, c] with c = a b.

Per token, scalars. Pieces: sigma 24 bits, e1 24, e2 24, Rc 36, rr 24, gap 24. Gates: G_ss = [sigma, sigma, sigma^2] and G_rs = [Rc, sigma, Rc sigma].

| relation | | terms, arm B | terms, arm A |
|---|---|---|---|
| S1 | G_ss.a - pieces(sigma) = 0 | 3 | 25 |
| S2 | G_ss.b - G_ss.a = 0 | 2 | 2 |
| S3 | G_rs.a - pieces(Rc) = 0 | 4 | 37 |
| S4 | G_rs.b - G_ss.a = 0 | 2 | 2 |
| S5 | sum_j G_oo_j.c - G_ss.c - pieces(e1) = -eps' | D + 3 | D + 25 |
| S6 | G_ss.c + 2 G_ss.a - sum_j G_oo_j.c - pieces(e2) = eps' | D + 4 | D + 26 |
| S7 | G_rs.c + pieces(rr) = 2^36 | 3 | 25 |
| S8 | G_ss.a - pieces(rr) - pieces(gap) = 1 | 5 | 49 |

Per token and channel j. Gates: G_oo_j = [o_j, o_j, o_j^2] and G_oR_j = [o_j, Rc, o_j Rc]. Range cell: w_j. Pieces: the w remainder rw_j (24 bits) and the y remainder ry_j (12 bits).

| relation | | terms, arm B | terms, arm A |
|---|---|---|---|
| C1, C2, C3 | G_oo_j.a, G_oo_j.b and G_oR_j.a each equal the o_j range cell | 2 + 2 + 2 | 2 + 2 + 2 |
| C4 | G_oR_j.b - G_rs.a = 0 (the Rc operand cell is reused, not rebuilt from its pieces) | 2 | 2 |
| C5 | 2^24 w_j + pieces(rw_j) - G_oR_j.c = 0 | 4 | 26 |
| C6 | cg_j w_j - pieces(ry_j) = 2^F y_j (cg_j derived and admitted, section 3.1; y_j public) | 2 | 13 |

The product cg_j w_j needs no gate: cg_j is a relation coefficient on the w_j cell.

Totals per token, D = 128:

| | arm B | arm A |
|---|---|---|
| gates | 2D + 2 = 258 | the same 258, plus 156 + 36D = 4,764 bit columns |
| range cells (w) | D = 128 | 128 |
| keys | 13 + 3D = 397 | 0 |
| relations | 8 + 6D = 776 | 776, plus 2 per bit = 9,528 |
| terms | 16D + 26 = **2,074** | 193D + 815 = **25,519** (of which 4 per bit = 19,056 are the boolean relations) |

The gate, range-cell, key and relation counts are what the model had before. The third review derived them from closed forms without using this model, and they matched. (The second review reran this model and got the same file, which is a rerun, not a second derivation.) Only the terms changed. At T = 16 the head's terms are 21,107,440 (arm A) and 4,782,496 (arm B), against 21,110,960 and 4,786,704 before (RESULTS.md, deviations). The third review's own totals for a direct-substitution lowering were 21,180,592 and 4,786,656. They differ from this lowering by exactly 16 x (35D + 92) = 73,152 terms in arm A and 16 x (2D + 4) = 4,160 in arm B, all of it in the norm and all of it operand reuse:
- per channel, C4: this lowering ties G_oR_j.b to the Rc operand cell (2 terms). Direct substitution rebuilds Rc from its pieces in every channel (37 terms in arm A, 4 in arm B). That is the 35 and the 2.
- scalars: this lowering reads sigma from the cell G_ss.a in S2, S4, S6 and S8 (1 term each). Rebuilding sigma from its pieces there costs 24 terms each in arm A and 2 in arm B. That is the 92 and the 4.

The review published its totals per group, and each group matches this split: in arm A, scalar ties 112 against 66 here, scalar residuals 2D + 171 against 2D + 125, channel ties and floors 82D against 47D, bit checks equal; in arm B, 13 against 11, 2D + 17 against 2D + 15, and 16D against 14D. Which relation inside a group carries the extra terms is inferred.

Both lowerings are valid. The recurrence terms are identical in both. `count_model.py` asserts the closed forms above and asserts that no gate, range, key, relation or layout count moved.

**These are counts for a stated lowering, with no builder to check them.** A build may choose another operand reuse and get another total. Terms drive no verdict here: H2 and H3 are on columns, relations and table length.

#### 4.4.2 No wrap, in full (third review, #66 must-fix M1)

**What has to be shown.** Every relation is an equation mod p. Uniqueness (above) is an argument over the integers. So for each relation, the integer expression it stands for must be smaller than p in magnitude: then "zero mod p" means "zero".

**What is known about each value, and from where.**
- A range cell (S', M, delta_lo, delta_hi, o, w) is an integer with |x| < 2^23. RNG proves this (approximately, with the error of section 4.2). The honest contract is 2^18, but the argument uses only what is proved.
- An exact piece is an integer in [0, 2^12) (arm B: lookup into the range table) or a bit (arm A: boolean relations). So sigma, e1, e2, rr, gap and each rw_j are in [0, 2^24), Rc is in [0, 2^36), and each ry_j is in [0, 2^12).
- A statement word is an integer in its class, checked at decode (section 2): |y| < 2^31, |S0|, |S_T| < 2^18.
- A derived value is an integer in its class, **checked at derive (section 3.1)**: |k|, |q| <= 2^12, a and beta in [0, 2^12], |v| < 2^31, **|cg| < 2^24**.
- A gate output is the field product of its two operand cells. Where both operands are known integers, it is congruent to their integer product, and the bounds below show that product is below p.

**The ledger.** Largest magnitude of each identity: the sum of the magnitudes of its terms, with every value at the bound just listed. delta stands for 2^18 delta_hi + delta_lo, so |delta| < 2^41 + 2^23.

| identity | largest magnitude | log2 |
|---|---|---|
| I1 M floor: 2^2F M + r - a sum_i S_i k_i | 18,155,133,850,353,663 | 54.0 |
| I2 delta floor: 2^F delta + r - (v - M) beta | 9,016,062,993,489,919 | 53.0 |
| I3 state floor: 2^F S' + r - a S - k_i delta_j | 9,007,301,260,206,079 | 53.0 |
| I4 output floor: 2^F o + r - sum_i S'_i q_i | 4,432,405,725,183 | 42.0 |
| I5 state ends: cell - S0, cell - S_T | 8,650,750 | 23.0 |
| N1 e1: sum o^2 + eps' - sigma^2 - e1 | 9,288,672,067,193,059 | 53.0 |
| N2 e2: sigma^2 + 2 sigma - sum o^2 - eps' - e2 | 9,288,672,100,747,489 | 53.0 |
| N3 rr: Rc sigma + rr - 2^36 | 1,152,921,504,606,846,976 | 60.0 |
| N4 gap: sigma - 1 - rr - gap | 50,331,646 | 25.6 |
| N5 w floor: 2^24 w + r - o Rc | 576,601,421,063,913,472 | 59.0 |
| **N6 y floor: cg w - 2^F y - r** | **149,533,556,211,712** | **47.1** |

The rows are the closed identities: each floor or residual equation after its tie relations are substituted in. A tie relation (a gate operand equals a cell; P_j equals the sum of 128 gate outputs; delta = 2^18 delta_hi + delta_lo; M + g6.a = v) says that one cell is the field image of an integer expression in integers that are already bounded. Substituting it is field arithmetic, so it is exact mod p, and what is left is one integer expression per row. The integers the ties define are small themselves: the largest is P_j, below 2^42.

p is 2^64 - 2^32 + 1, about 2^64. Every row is below it; the largest (N3) is 2^60. So every identity holds over the integers, and the uniqueness argument applies: sigma is isqrt(sum o^2 + eps'), Rc is floor(2^36 / sigma), w_j is floor(o_j Rc / 2^24), and **y_j is floor(cg_j w_j / 2^F)**.

**N6 is the row the third review broke.** Its bound is |cg| |w| + 2^F |y| + r < 2^24 x 2^23 + 2^12 x 2^31 + 2^12 < 2^47.1. The factor 2^24 is the admitted class of cg. Before this revision nothing supplied it. Without it, |cg| |w| is unbounded, and at |cg| near 2^41 it reaches p. With the rule of section 3.1 it is a checked fact about every admitted statement.

**I2 has the same shape for v**, and the same remark: its bound uses |v| < 2^31, which is now a derive check (section 3.1).

The ledger is computed, not typed: `norm_alias_regression.py` part E builds it from the bounds and checks every row against p, and for each derived value finds the largest bound that keeps every row below p (the "needs" column of section 3.1). Part C checks N6 directly: 200,000 pairs (cg, w) in their bounds, including the corners, and in every one the only solution of the relation mod p inside the y class is the integer floor.

**What this argument is not.** It is an argument, not a machine-checked proof. It assumes RNG's range claim and the exactness of the pieces, both of which are properties of the proof system at research settings (target 10 bits). It covers the relations of sections 4.1 to 4.4. The M2 build has to re-derive the ledger for the relations it actually emits.

### 4.5 Verifier entry point (hard rule a)

`verify_m2(shape_constants, statement_words, proof_bytes)` is the only entry. The prototype is `verify_from_words` in `research/operators/qwen_deltanet_m2/admit_proto.cpp`, on the M1b statement. It runs these steps:
1. Fix the shape from the verifier's own constants. The header words must equal them, and the word count must be exact.
2. Decode every public word as a canonical Goldilocks element (< p), read it as a signed integer (a word above p/2 is negative), and check it against its class bound (section 2). A non-canonical word, a huge element, or an integer outside its class is rejected **here**.
3. Recompute the public-only stage (section 3) from the decoded integers, with checked arithmetic (an overflow is a reject at "derive").
   **3a. Admit every derived value (section 3.1).** For every token: every k_i and q_i in [-2^F, 2^F], a and beta in [0, 2^F], every |v_j| < 2^31, every |cg_j| < 2^24. One value outside its class is a reject with verdict "derive". This runs before step 4, so no out-of-class integer is ever turned into a relation coefficient, a target or a field element. It is a comparison on integers, not a reduction: nothing is clamped or taken mod p.
4. Derive every relation target and coefficient from those integers with the relation-only builder. The relation-only builder computes **no witness**: it reads only the decoded public integers, so no in-class statement can make it overflow, and it never ends the process.
5. Size the run (a pure function of the shape) and run the unchanged proof verifier.

**Why step 3a is needed even though the verifier never multiplies cg by w.** The verifier is witness-free: it never computes cg_j w_j, so checked host arithmetic alone cannot catch a cg that is too large. The product happens inside the relation, in the field. The only place the bound can be enforced is on the coefficient, before it enters the relation. That is step 3a.

**The prototype does not have this step, because it has nothing to apply it to.** `admit_proto.cpp` works on the M1b statement. There a, beta, k, v and q are statement words, each class-checked at decode (step 2), and there is no recompute stage and no norm, so no cg. Its C++ is unchanged by the third review. The rule is exercised at design level by `norm_alias_regression.py` (section 7), and is a build requirement for the M2 head.

Every failure is a returned verdict (decode, derive or proof). Nothing on the verifier path calls exit() or a BLK_REQUIRE that a statement can reach: the entry checks lookup_size()'s guards on the derived statement first and returns "derive" if one would fire. (Post-review, #66 should-fix 3: the first prototype ran the full witness path with its checks off, so in-class but inconsistent inputs could reach i64 overflow, and a failed sizing called exit(1). The prototype now uses a witness-free derivation and checks that it gives the prover's relation list exactly.)

**Build requirement: no unchecked arithmetic on public inputs, plus a sanitizer run.** A second review of #66 ran UBSan on the first prototype. On an in-class statement with every public value at its class extreme (S0 = 2^18 - 1, k = a = 2^12, v = o = 2^31 - 1), the verifier's derivation overflowed signed i64 at `aP = Pj * a` in m1b_builder.h. No soundness break was seen: the relation targets do not read the overflowed witness, and at -O2 the statement was rejected at the proof stage. But it was undefined behaviour on attacker-chosen input, inside the verifier. The M2 verifier must therefore:
- compute no witness value from public inputs (the derivation is witness-free);
- do every integer operation that touches a public input with checked arithmetic (`__builtin_*_overflow` or a 128-bit type with an explicit bound), and turn an overflow into a reject, never a wrap or an exit;
- run the full hostile suite, including the all-extremes statements, under `-fsanitize=undefined -fno-sanitize-recover` in CI, with 0 reports as the pass condition.

The prototype now does all three. `build()` routes every i64 product, sum and difference through checked helpers that set an overflow flag, the entry rejects at "derive" when the flag is set, and `record.py ubsan` runs the suite under UBSan. The review's statement is in the hostile suite twice. Through the witness-free entry it passes derive and is rejected at the proof stage. Through the old witness path, kept as a checked control, it is rejected at derive.

There is no `admissible()` that a caller runs separately, and no entry point that accepts caller-built relations or a caller-built `LookupRun`. The low-level `lookup_verify(run, ...)` stays a library internal. **The M2 build must not export it as a verifier.**

The prototype measured this on the M1b statement (RESULTS.md H5):
- 10/10 honest seeds accepted.
- 34/34 hostile encodings rejected at the expected stage, including a huge field element in each of the 8 public classes and the #63 review's R9.
- Post-review rerun with the conv history and the witness-free derivation: see RESULTS.md, "Post-review rerun".
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
- **H4 admission:** this lane's H5 suite on the M2 statement words, plus a huge element in xq, ar, z and the conv history H, and the R9 analogue on y. All rejected by `verify_m2` alone. Also: H changed in class (must fail at the proof verifier, since the conv recompute reads it), and the derive-overflow cases (every class at its extreme; every word random in class), which must return a verdict and never exit or overflow. The whole suite runs under `-fsanitize=undefined -fno-sanitize-recover` with 0 reports (section 4.5: no unchecked arithmetic on public inputs).
- **H2 hostile, two lookups:** the challenge-replay case of section 4.3 (the digit lookup's alpha and sumcheck challenges reused in the remainder lookup; the two instances swapped), rejected.
- **H4 admission, derived values (third review, #66 must-fix M1; build requirement).** `verify_m2` must implement step 3a of section 4.5: every recomputed k, q, a, beta, v and cg is checked against its class (section 2) with checked arithmetic, before any relation or field conversion, and a failure returns "derive" and never exits. The build's suite must contain, as cases run through `verify_m2` itself:
  - **cg boundary:** a head constant (gain) and a z chosen so that one cg_j is exactly 2^24 - 1, otherwise valid, with an honest proof: accepted. The same with cg_j = 2^24: rejected at derive. Both signs.
  - **the 22 large-gain aliases:** each statement of `norm_alias_regression.py` part A (o_0 in {4096, 8192}, cg_0 = 2^52 .. 2^62, with its compatible 16-token statement and its alias y): rejected at derive. As a control, the same 22 with the derive check compiled out and a hostile prover that commits the alias witness: the build must report whether the proof verifier accepts them. If it does, that is the hole this rule closes; if it does not, say what else rejected them.
  - **v boundary:** conv taps and xv chosen so that one derived v_j is 2^31 - 1 (accepted, with an honest proof) and 2^31 (rejected at derive).
  - **a, beta, k, q:** a table or constant corrupted so that one derived value leaves its class: rejected at derive. (For k and q this cannot happen with a correct recompute; the case guards the build.)
  - **recompute overflow:** conv taps and inputs that overflow the conv accumulator or the L2 sum of squares in 64 bits: a returned verdict, no wrap, 0 UBSan reports.
  - The design-level regression (`norm_alias_regression.py --check norm_alias_expected.json`) stays in the build's CI and must keep passing; the build must also re-derive the no-wrap ledger of section 4.4.2 for the relations it emits, and re-run part G on its own pinned tables.
- **Kill:** no honest T = 16 arm B proof in 6 h, then fall back to arm A at T = 8 and report.
