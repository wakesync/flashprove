# Qwen3.8-27B M3: statement design

Issue #32. PREREG: [PREREG.md](PREREG.md) (first commit c9dc2c05). Results and verdicts: [RESULTS.md](RESULTS.md).
Plain-language status page: [docs/qwen-port.md](../../docs/qwen-port.md).

**This is a design. No M3 proof exists and nothing here was run on a GPU.**

**Revision r2 (2026-11-10), after two independent reviews of this PR** (astra:
https://github.com/wakesync/flashprove/pull/70#issuecomment-6757513561, opus:
https://github.com/wakesync/flashprove/pull/70#issuecomment-6758415494). Both asked for changes of
substance. Section 12 lists every change and every changed number. The ones that change what this
design says: floors at a variable shift now have an exact remainder class (r1 admitted a wrong
floor); the weight cells the trace reads are tied to the weight table (r1 left them free); the
bound ledger is redone over every term; M3a-MLP no longer fits 2^22 at T = 16 after a wrap in its
down projection was fixed; and **whether the full model fits one H200 is unknown** (section 7.3).
The low-rank state figures are **not established** and are not the plan. Counts of r2 are in
`runs/model-r2.json` and `runs/bounds-r2.json`; the r1 files are kept unchanged.

Numbers are of three kinds and are kept apart:

- **counted**: exact outputs of `research/operators/qwen_m3/count_m3.py` or of the upstream planner
  (`cp_verify -plan arrays`). A count says how big a statement is, not that it can be proved.
- **extrapolated**: a count multiplied by a rate taken from another model's runs. Each one names its
  assumption. None is a measurement of Qwen.
- **measured**: only numbers already in `research/results.yaml` from earlier PRs. This lane measured
  nothing new.

Two reviews of #66 shaped this design. Section 6 answers the second one (every coefficient that
multiplies a witness value needs an enforced bound). Term counts are marked provisional throughout,
because that review found the norm's term counts in `count_model.py` inexact.

**One parameter is open and this design does not close it.** PR #68 (merged) measured layer 0 only,
on 10 prompts, at F = 12, 14 and 16 with the M2 lowering: the M2 range bounds hold at F = 12, the
integer head output FAILED the fidelity threshold at all three F, and F >= 14 breaks the ranges.
Deeper layers, every layer that abliteration changes (17 to 51), other F and other lowerings are
unmeasured. So F and the norm lowering are **parameters of this design, and the choice is open**.
The scaling of the head output and the gated norm (o, w, t, y, and possibly the recurrence) is
owned by the norm-scaling lane and #8. Section 7.4 says which numbers here depend on it and by how
much. Every count in sections 7.2 and 7.3 is at F = 12 with the M2 norm lowering, and is a count
of that candidate, not of the final statement.

## 1 The M3 statement in five lines

1. **Public:** the commitment ID (which fixes the integer weights, the scales, the pinned tables and
   the acceptance policy), the request (a window of T token ids and a range), and the claimed next
   token.
2. **Committed, never shown to the verifier:** the weights (once, in the weight table), and for each
   request every intermediate value: projection outputs, conv outputs, q, k, v, the gates, every
   DeltaNet state, head outputs, MLP values and the residual stream.
3. **Proved:** every step from the embedding to the logits, against the committed weights. Matrix
   products reduce to one batched claim on the weight table. Conv, SiLU, the norms and the gates are
   gadgets on committed cells. The recurrence is a transition between committed states. Range checks
   and exact remainders make each equation hold over the integers, not only modulo the prime.
4. **Verifier:** recomputes the ID from the public files, admits its own public words, derives every
   relation coefficient from public data only, checks the sub-proofs, the state and history chain
   (what chunk c hands on is what chunk c + 1 reads; the first chunk starts from zero) and the one
   opening of the weight table. It never holds a weight or a state.
5. **Not covered:** how close the integer model is to the BF16 model (#8), vision and MTP, sampling,
   and whether the committed weights are the advertised checkpoint (that is the signed manifest's
   job, #59). Research security settings until a production accounting exists.

Why this is the first non-redundant Qwen statement: at M2 every input was public, so the verifier
could recompute the result. Here the verifier holds a 32-byte ID in place of 26.9 billion weights.
It cannot recompute anything past the token ids.

## 2 What changes from M2, step by step

| step | M2 (#66) | M3 | why |
|---|---|---|---|
| weights | not involved | **committed** in the weight table; the ID names them | the verifier must not need them |
| in_proj (qkv, z, a, b), out_proj | not proved; outputs were public words | **proved matmuls** against committed weights; outputs are committed cells | brief; section 4 |
| causal conv1d, kernel 4 | verifier recomputes | **proved**, taps are committed weights, history is a committed value | its inputs are committed |
| SiLU on conv outputs | verifier recomputes | **proved**, function-table lookup | same |
| q/k L2 norm | verifier recomputes | **proved**, isqrt and reciprocal in relation | same |
| decay a and beta | verifier recomputes from tables | **proved**: softplus lookup, product with a committed per-head constant, exp lookup; sigmoid lookup | A_log and dt_bias are weights |
| recurrence | proved (rehearsal) | proved, between committed states | #34 |
| gated RMSNorm | norm proved, coefficient cg derived by the verifier | **proved with no derived coefficient** (section 6) | #66 second review |
| state S0, S_T | 2 x 16,384 public words | committed, carried between chunks | #34 |
| conv history H | 1,152 public words | committed, carried with the state | #34 |
| result y | public | committed (an input of out_proj) | |
| MLP, pre-norms, residual, attention layers, head | not proved | proved by the dense family, with the limit changes of #35 | section 5 |

## 3 Public inputs, committed values and what the verifier does

### 3.1 Full-model form (the target)

**Public** (bound into the request's chain, `blocks/chain/public.h`):
- the configuration: shape, scales (`KL.bin` with per-layer DeltaNet fields added), layout, the
  acceptance policy, and the SHA-256 or BLAKE2b digests of every nonlinear table (section 5.2);
- the commitment ID, which covers the configuration and the weight table's root
  (`published_id`, `blocks/frame/heads.h`);
- the request: T token ids, r, e; the next token.

When each is bound (r2 correction; r1 said "all in the first query, as upstream does", which is
wrong): upstream binds the configuration, the ID and the request before the first query, and the
**next token later**, immediately before its final head segment (`verifier/src/vf_segments.inc`;
also #41). M3 reuses that order. Binding the next token earlier would be a protocol change and
is not proposed here.

**Committed once** (`cp_commit`): every integer weight of the text model, 26,895,337,984 values
(counted from the published shapes, including the 14,336 retained norm gains that r1 left out;
section 7.1). This includes the small per-head tensors that M2 treated as public constants: conv
taps (10,240 x 4 a layer), the gated-norm gain, and the decay constants.

**What bounds a committed weight, corrected in r2.** r1 said the key file's range proof
(docs/protocol.md 6.1 step 2; WF, `blocks/frame/wf_units.h`) bounds every committed coefficient.
That is not established for this port:
- the WF range proof exists **only for upstream's Maverick layout** (two-digit units in
  [-4,096, 4,095]; four-digit units, used for the embedding, get byte ranges only). **No Qwen layout
  of it exists**, and none has been composed with the research harness;
- it bounds **table entries**, not trace cells. The trace reads the conv taps, the gain, cA and
  dt_bias directly as cells. Nothing in r1 tied those cells to the table, so a prover could put
  gain = 2^50 in the trace and make y free (opus review M1; the same kind of gap #66 closed for cg);
- M3a-1's fallback (commit the head's weights in the proof's own oracle) **drops the WF range
  proof altogether**.
Section 6.2 gives the r2 fix: an in-trace exact class on each such cell plus an addressed tie to
the weight table, counted. The matrix weights (in_proj, out_proj, MLP) are never trace cells:
their products are claims on the table, and their bound is the table's, which needs a Qwen WF
layout (a build obligation, section 4).

**Committed per request:** the trace, segment by segment (section 7.3 for the volume).

**The verifier:**
1. recomputes the ID and refuses another one;
2. decodes each public word canonically and checks its class (the #66 entry, DESIGN 4.5 there);
3. derives coefficients and targets from public data only, with checked integer arithmetic, and
   admits every derived value against its class before use (section 6.3, the #66 rule). In the
   full-model form the only public values that multiply a committed value are constants of the
   format (powers of two, table steps, 362), the public shifts, the rotary table and the token ids
   as embedding indices;
4. runs the no-overflow check of section 6 on the configuration before any proof byte is read, and
   refuses a configuration that fails it;
5. checks each segment's sub-proof and the chain of kept values between segments;
6. checks the test on the weight table (shared and second chain, unchanged).

### 3.2 M3a form (the first build, CPU)

M3a keeps the full form's rules and shrinks the boundary so it fits the research harness:

- **Public:** the layer's normed input a (T x 5,120 integers, class |a| <= 2,047, the range of
  upstream's norm output) and the statement's output (one head's out_proj contribution, T x 5,120,
  class |x| < 2^31). S0 = 0 and H = 0 (a sequence start), as constants, not as words.
- **Committed:** that head's weights (3,288,706 values: its rows of in_proj, its conv taps, its 128
  gains, its two decay constants, its rows of out_proj; r1 said 3,288,578 and left out the gains),
  under a root that the statement names. 1,666 of them (taps 1,536, gains 128, cA, dt_bias) are
  read by the trace as cells and carry the tie of section 6.2.
- Everything between a and the output is committed cells.

a is public in M3a only because the layer before it does not exist yet. The proof is still not
redundant: the verifier cannot compute the output without the weights.

One consequence that makes M3a cheaper than it looks: with a public, in_proj is linear in the
committed weights, so it needs no product sumcheck, only a batched linear claim on the weight table
whose row weights the verifier computes from a. out_proj multiplies a committed y by committed
weights and needs the product argument.

## 4 Reuse and new work

**Reused unchanged** (the file is the reference; "unchanged" means the block, not that the
composition has been built):

| need | component | files |
|---|---|---|
| weight commitment, hiding encoding, Merkle tree, leaf tables | `cp_commit` | `prover/hash_commitment/hf_commit.cu`, `hf_commit_table.cuh`; `blocks/iop/link.h` |
| range proof on committed weights | WF | `blocks/iop/wf.h`; `blocks/frame/wf_units.h` |
| claims on the weight table, one opening per batch | LIN, FOLDEQ, BATT, member | `blocks/iop/lin.h`, `foldeq.h`, `batt.h`, `member.h`; `prover/hash_commitment/hf_keeper.cu` |
| matmul product argument | masked sumcheck | `blocks/iop/psc.h`, `hp.h`; `prover/hiding/sumcheck_door.cuh`; `prover/prover/layer_prove.cuh`; `verifier/src/vf_layers_check.inc` |
| approximate range check | RNG / smallness test | `blocks/iop/rng.h` (CPU harness); `prover/hiding/` and docs/format/11-1-machinery.md, third piece (GPU prover) |
| lookups | LKP / forest | `blocks/iop/lkp.h`; `prover/hiding/forest.cuh`; `verifier/src/vf_lookup_argument.h` |
| transcript, public-input binding, segments and kept rows | chain, Binder, request frame | `blocks/chain/chain.h`, `public.h`, `rounds.h`; `blocks/iop/req.h`; `blocks/toy/segments.h` |
| dense layer (norm, SwiGLU, residual), softmax attention, output head | upstream sub-proofs | `prover/prover/forward_ffn.cuh`, `prover/attn/`, `prover/head/`; `verifier/src/vf_attention_check.h`, `vf_output_head_check.inc` |
| SiLU and sigmoid tables | Ts, Sig | docs/model.md section 4 |
| research harness for the head | product oracle + RNG + LKP in one group; verifier entry | `research/operators/qwen_deltanet_lookup/lookup.h`; `research/operators/qwen_deltanet_m2/m1b_builder.h`, `admit_proto.cpp` |

**New** (nothing below exists for Qwen):

| item | where it lands | owner |
|---|---|---|
| DeltaNet recurrence as a sub-proof of the GPU prover and of `cp_verify` | new segment kind next to layer and attention | M3b build |
| conv1d, softplus and exp tables, per-head q/k norm, gated norm | gadgets | #35 (PR #67, merged) |
| state and conv-history carry between chunks | kept rows or a boundary commitment | #34 |
| second and third lookup instances keyed on the statement's own cells (the efficient function lookup on committed cells; see 8.3) | harness | lookup build lane |
| WF range proof for a Qwen weight layout (exists for upstream's Maverick layout only) | `blocks/frame/wf_units.h`, `cp_commit` | M3a build |
| tie of the trace's weight cells to the weight table (6.2) | harness | M3a build |
| more than 64 segments per window, if the per-layer cut is used (`vf_segments.inc` line 99) | `cp_verify` | M3b build |
| composition of LIN with the research harness (a weight table next to the product oracle) | harness | M3a build, its main risk |
| hybrid schedule (3 DeltaNet layers then 1 attention layer) in planner, layout and `KL.bin` | `cp_verify`, `pack_layout.py` | M3b build |
| limit changes: no experts, query width 6,144 != d, head dimension 256, partial rotary at theta 1e7, q/k RMSNorm and sigmoid output gate on attention | `verifier/src/cp_verify.cpp` shape tests | #35 |
| Lean model and soundness theorem for the new shape | `lean/` | not planned; see open risks |

Two facts about the limits, found while running the planner for this lane:
- The planner **accepts** a dense shape (NE 0, f 17,408, V 248,320, L 64) once the parameter file
  follows the repository's own recipe for a model without experts (RESULTS.md H4).
- By the repository's own test (`verifier/tests/served_form_test.py`, case "dense"), such a file
  misses three conditions of the standard parameter form (`routed-experts`, `both-clamps`,
  `table-digests`), so today no call under it can end `YES`. That was read, not run here.

## 5 Lowering of the new steps

Section 5 is written for the research harness (wide product oracle). The same relations, with
cells as byte limbs, are what a GPU sub-proof would prove.

### 5.0 One integer reference for the scales (r2, astra must-fix 1)

r1 had two scale mismatches with the merged M2 design (#66 at bd50893): the q/k counter normalised
q and k identically, without M2's 1/sqrt(128) on q, and the new gain expression did not say where
the RMS norm's sqrt(128), which M2 put into cg, went. And it used a variable shift with a fixed
12-bit remainder. r2 fixes one reference:

| quantity | integer form | scale | where the constant lives |
|---|---|---|---|
| activations, stream | x at 2^F | F = 12 (open parameter) | format |
| weight tensor T (every matrix, the conv taps, the gain, cA, dt_bias) | T_int = RNE(2^(e_T) T), \|T_int\| <= 4,095 | e_T per tensor, public | configuration (covered by the ID) |
| shift of a floor after a product with T | s_T = e_T, admitted only in 1..24 | | configuration |
| remainder of that floor | **exact class [0, 2^(s_T))**: limbs r0, r1 (12-bit keys) and one complement key on the top limb in use | | relation (counted: `vrem`) |
| k | floor(x Rc / 2^24), Rc = floor(2^36 / sigma), sigma = isqrt(sum x^2 + eps) | 2^12 | as #66 |
| q | floor(362 x Rc / 2^36), 362 = round(2^12 / sqrt(128)) | 2^12 / sqrt(128), \|q\| <= 362 | format constant, as #66 section 3 ("divisor multiplied by round(sqrt(128) 2^12)") up to the rounding of the constant |
| gated RMSNorm | the sqrt(128) of the mean is folded into the committed gain at conversion: gain_int = RNE(2^(e_g) sqrt(128) gain) | | conversion rule (in the manifest, #59) |
| decay | g = floor(cA_int sp / 2^(s_A)), cA_int = RNE(2^(e_A) exp(A_log)) | g at 2^F | s_A = e_A: the decay divisor is cA's own exponent |
| dt_bias | added to ar at ar's scale: dt_int = RNE(2^F dt_bias) | 2^F | its own public exponent F, no shift |

Two things that follow. (1) A public shift is an integer in 1..24, checked at admission like every
configuration word; a shift outside that range is a reject, and the remainder class is never wider
than 24 bits. (2) The q rounding differs from #66's by the rounding of 362 (relative 2^-13); it is
a different integer function and the fidelity study has to use this one.

**The review's counterexample against r1, and the r2 class.** At s_g = 8 with gain = 1 and t = 0,
r1's relation 2^(s_g) y + r = gain t with r in [0, 2^12) holds at y = -1, r = 256, although
floor(0 / 256) = 0. Under the r2 class r must be < 2^8 = 256, so (y, r) = (-1, 256) is refused and
only the floor remains. `bounds.py` section B checks that pair under both classes and sweeps every
s in 1..12 for a second solution (none).

### 5.1 Matmuls
x_j = rq(sum_k a_k W_kj, s): per output one range cell x_j and one exact remainder of class
[0, 2^s) (r2; r1 counted a fixed 24-bit class, which is exact only at s = 24). No gate column and
no relation per multiply: the whole product is one claim on the weight table after a sumcheck (or,
with a public as in M3a, directly a linear claim).

### 5.2 Nonlinear tables
One format for all of them, the operators lane's v1 (4,096 rows, input step 2^(F-8), output scale
2^F, domain [-8, 8), generated without floating point, hashed). A lookup is a pair (idx, y) checked
against the public table, plus the index remainder shown in range by two 12-bit keys. The table's
digest is part of the configuration, so prover and verifier cannot disagree on a row.

Tables M3 needs: silu, sigmoid, softplus, and exp(-x) on [0, 8) (requested from #35: their
`decay-*` tables fix the decay constant, and Qwen's is a learned per-head weight).

### 5.3 Conv, q/k norm, gates
- **conv:** acc = sum of 4 (tap x input) with taps as committed weight cells, 4 gates a channel;
  c = floor(acc / 2^(s_conv)) with an exact remainder of class [0, 2^(s_conv)). The inputs before
  token 0 are the committed history.
- **q/k L2 norm:** the isqrt and reciprocal form of #66 section 4.4 (exact, no domain limit), then
  one floor per channel. **The norms of PR #67 are not this.** They are table lookups on a bounded
  domain (mean square in [1/4, 17/4)), with no epsilon and no near-zero handling: a different
  integer function, which rejects inputs the isqrt form accepts. This design counts the isqrt form.
  The table form stays a candidate for the attention layers' q/k RMSNorm and for whatever the
  norm-scaling lane recommends.
- **decay:** sp = softplus[ar + dt_bias]; g = floor(cA x sp / 2^F) with cA = round(2^e exp(A_log)) a
  committed weight; a = exp_neg[g]. **beta** = sigmoid[br].
- **The decay table needs a finer step than table format v1 has.** On real weights the median decay
  is 0.998 (PR #68), so the exponent g is about 0.002. Format v1 has an input step of 1/256,
  about 0.004: at least half of the real exponents would fall in the first row and read as
  "no decay" (inferred from the reported median, not measured per head). A table keyed on g itself at 2^-12 over [0, 1), with the coarse table beyond, costs
  one more lookup per head per token (1 in about 520). This is a request to #35, and a fidelity
  question for #8; the counts here include one exp lookup, not two.

### 5.4 Gated norm without a derived coefficient
M2 had y = floor(cg w / 2^F) with cg computed by the verifier from the gain and SiLU(z). In M3
neither is public. The design:

    s = Ts[z]                    a table cell, |s| <= 32,741 < 2^15 by the pinned table's image
                                 (r2: r1 said 4,095; SiLU is not unit-bounded, row 4,095 is 32,741)
    t = floor(s w / 2^F)         one gate, one range cell, exact 12-bit remainder (F is a format constant)
    y = floor(gain t / 2^sg)     one gate with the committed gain (a tied weight cell, 6.2),
                                 exact remainder of class [0, 2^sg) (r2)

A cheaper variant folds the gain into out_proj at conversion time, as upstream folds every norm
gain into the next matrix (docs/model.md 11.3). Then the last line disappears. The counts in this
lane keep the gain gate, so they are on the high side. The choice changes rounding, so it belongs
with the fidelity work (#8).

### 5.5 Statement kinds for M3a
- **M3a-head:** section 3.2. One per V head. A QK head's q/k path is proved again in each of the 3
  V heads that share it (simple, and 3x redundant on about 2% of the cells).
- **M3a-MLP:** the layer's SwiGLU MLP from its normed input m (public) to its output (public): gate
  key and up value as range cells with exact 2^s remainders, SiLU by lookup, one gate s x u,
  **then h = floor(s u / 2^F) as a range cell with an exact 12-bit remainder (r2)**, down
  projection of h by the product argument. r1 fed the raw s x u into the down projection. Against a
  cheating prover (|u| < 2^23 by the range check, |s| <= 32,741) the down projection's sum over
  17,408 hidden units then reaches 2^64.1, past p: a wrap, found in r2 and kept in `bounds.py` as a
  control row. Rounding h costs one range cell and one key per hidden unit and makes M3a-MLP a 2^23
  statement at T = 16 (largest T that fits 2^22: 15). The other fix (an exact class
  [-2^17, 2^17) on u, product unrounded) gives the same table length and is counted next to it
  (`mlp_alt_exact_u`).
- The verifier adds the 48 head contributions, applies the public rounding and the residual, and
  computes the two pre-norms from public stream values. So a full layer in M3a is 48 + 1 proofs and
  a public recombination. That recombination is the part M3b removes.

## 6 Bounds: where every multiplier's bound comes from

The #66 second review showed that an unbounded coefficient breaks the floor equation: with
cg = 2^62 the field equation holds while the integer one is false. The rule for M3:

**No relation may multiply two values unless each has a bound from this list, and the worst
magnitude of every relation, computed from those bounds, stays below 2^63.**

| source | what it bounds | enforced by | does the verifier see the value? |
|---|---|---|---|
| format | powers of two, table steps | constants in the verifier | yes |
| admission | public statement words (M3a: a, the output) | class check at decode, before any relation is built | yes |
| weight table | matrix weights (in_proj, out_proj, MLP): \|w\| <= 4,096, as table entries | a WF range proof on the table. **Exists for upstream's Maverick layout only; a Qwen layout is a build obligation** | **no** |
| weight cell (r2) | the weights the trace reads as cells: conv taps, gain, cA, dt_bias | **in-trace exact class [-4,096, 4,095] plus the addressed tie of 6.2** | **no** |
| table image | outputs of SiLU (\|s\| <= 32,741), sigmoid and exp ([0, 2^12]), softplus (< 2^16) | exact lookup into a public table whose digest the ID covers | no |
| exact key | 12-bit remainder limbs; remainders at a public shift 2^s: exact [0, 2^s) | lookup-exact (arm B) or bits (arm A) | no |
| range check | every other cell: \|x\| < 2^23 against a cheating prover | RNG | no |
| implied | k (<= 2^12), q (<= 362) | follows once the relation before it holds over the integers | no |

So when the verifier cannot recompute a coefficient, its bound is **proved** in the statement: by
the weight table's range proof for a matrix weight (once a Qwen layout of it exists), by the
in-trace class and the tie for a weight cell, by a lookup for a function value, by the range check
otherwise. Nothing is left as a contract on honest behaviour. (r1 listed w and t as implied
<= 2^12; the r2 ledger does not use those, only what RNG proves.)

Real Qwen gains are not 1. A gain enters as a committed integer gain_int = RNE(2^e sqrt(128) gain)
with the tensor's own exponent e, exactly as upstream converts a weight matrix (docs/model.md
11.4), so |gain_int| <= 4,095 whatever the float gain is. The exponent e is public and is the shift
sg (section 5.0). That |gain_int| <= 4,095 is a property of an honest conversion; in the statement
it is enforced by the weight-cell class of 6.2, not assumed.

### 6.1 The ledger (r2, astra must-fix 2)

`research/operators/qwen_m3/bounds.py` (r2) bounds each relation by the exact sum of |term| over
all its terms, both sides, every independently ranged limb at its class edge, as an integer.
This is **proved from the classes** (arithmetic on enforced edges), not sampled. Output
`runs/bounds-r2.json`: 33 M3 rows, the largest 2^60.27 (the q floor, 362 Rc x), all below 2^63;
the two control rows wrap as they must (#66's cg = 2^62 alias, and r1's unrounded MLP down
projection at 2^64.09). Rows r1 had wrong, now corrected:

| row | r1 | r2 | why |
|---|---|---|---|
| SiLU image used in the s w row | 4,095 | 32,741 | pinned table row 4,095 |
| q/k square row (sum x^2 vs sigma^2 + e1) | 2^38 | 2^48.0007 | r1 omitted the sigma^2 and e1 side |
| k x delta (delta = 2^18 hi + lo) | stated 2^53 | 2^53.000005 | r1 omitted the low limb (2^53 + 2^35) |
| reciprocal Rc sigma + rr - 2^36 | 2^61 (log + 1) | 2^60.0 | exact sum |
| M3a-MLP down projection | not a row | wraps in r1; 2^55.02 after the r2 rounding | new |

r1's ledger was one log2 per row (the largest term plus one). It also omitted the e2 / gap rows and
the operand ties; r2 lists S5 to S8 of both norms, the class rows and the key rows.

**Build requirement:** the M3 verifier runs the same computation on its configuration at start-up,
as `cp_verify` runs its no-overflow conditions, and refuses a configuration that fails it. The
hostile suite has a commitment with an out-of-range gain (must fail at the weight-cell class and at
the table), a trace gain that differs from the table's (must fail at the tie), the boundary pair
4,095 / 4,097, a public shift of 0 and of 25, the review's (s = 8, y = -1, r = 256) floor, and the
#66 alias statements.

### 6.2 Tying the weight cells to the weight table (r2, opus M1, astra must-fix 3)

The trace reads 1,666 weights of one head as cells (1,536 conv taps, 128 gains, cA, dt_bias). For
each such cell w_i at table address addr_i:
1. **Class in the trace:** w_i + 4,096 = lo_i + 2^12 hi_i with lo_i a 12-bit key and hi_i in {0, 1}
   (a key and its complement). So w_i is in [-4,096, 4,095] by the trace alone, whatever the table
   says. This is what the ledger uses.
2. **Tie:** after the trace is committed, the transcript draws rho. The statement proves
   sum_i rho^i w_i = sum_i rho^i Tab[addr_i], where the right side is one batched opening of the
   weight table at the public addresses addr_i (the same LIN / FOLDEQ / member machinery that the
   matmul claims use, one more claim in the same batch). A trace cell that differs from its table
   entry fails with probability about 1,666 / p. The addresses are fixed by the configuration
   (tensor, head, row, column), so the prover cannot point a cell at another entry.
3. Counted (`wcells` in `count_m3.py`): 3 keys and 2 relations per cell, plus one sum split into
   relations of at most 256 terms. The opening on the table's side is in the matmul batch and is
   not in this count.

With both, gain = 2^50 in the trace fails at step 1, and a gain that is in class but not the
committed one fails at step 2. Step 1 is needed even with step 2: the class of a table entry rests
on WF, which has no Qwen layout yet; the in-trace class does not depend on it.

M3a-1's stop-rule fallback (the head's weights in the proof's own oracle with the root in the
statement) keeps step 1 and replaces step 2 by an equality inside that oracle. It has **no WF range
proof** on the matrix weights, so their bound must then come from an in-oracle class on every
weight: 3,288,706 x (3 keys + 2 relations), which that fallback does not fit at T = 16. The
fallback is weaker and is reported as such.

### 6.3 Values the verifier still computes itself: the #66 rule, carried explicitly (opus S5)

Every value the verifier derives from public data and then uses in a relation, or as a public
output, is checked against its class **before use**: one value out of class is a reject with
verdict "derive"; **no clamp, no saturation, no reduction mod p**; every intermediate in checked
arithmetic (`__builtin_*_overflow`) or a 128-bit type with an explicit bound, an overflow being a
reject, never a wrap or an exit (#66 DESIGN section 3.1, step 3a).

| derived value | where | class checked before use |
|---|---|---|
| sum of the 48 public head outputs, per channel | M3a-2 recombination | each head output \|x\| < 2^31 at admission; the sum (< 2^37) in checked i64 |
| rounding of that sum and the residual add | M3a-2 | the result in the stream class before it feeds anything |
| the two pre-norms from public stream values | M3a-2 | the sum of squares in 128-bit (5,120 x (2^31)^2 = 2^74.3 overflows 64 bits); sigma and the norm output in their classes |
| the q numerator in a verifier-side recompute | wherever q is recomputed from public u (M2 form, tests) | the M2 form's q numerator 2^12 x 2^12 x u reaches 2^63 at \|u\| = 2^39 (#66 re-review): 128-bit |
| conv accumulator in a recompute | same | in the M2 form the taps are unbounded constants, so 4 taps x \|x\| < 2^31 can wrap 64 bits (#66 re-review): taps admitted first, accumulator in checked arithmetic |
| L2 sum of squares in a recompute | same | 128 x u^2 passes 2^63 once \|u\| reaches about 2^28 (#66 re-review): 128-bit |
| cg, wherever an M2-form recompute remains | tests, M2 controls | cg computed **in integer form** (no float), \|cg\| < 2^24 checked |
| rotary table entries | full model | table digest in the ID; each entry in its class at load |
| token ids as embedding indices | full model | 0 <= id < V at admission |

In M3a-head and the full form, cg does not exist (section 5.4). The rule matters for the M3a-2
recombination, for the controls that reuse the M2 form, and for the full model's rotary table and
embedding index.

## 7 Counting results (verdicts and full tables: RESULTS.md)

### 7.1 Weights (counted from shapes)

| | integers |
|---|---|
r2 counts (`runs/model-r2.json`); r1 values in brackets.

| | integers |
|---|---|
| one DeltaNet layer (in_proj 84.4M, conv 40,960, out_proj 31.5M, MLP 267.4M, gated-norm gain 128) | 383,262,944 [383,262,816] |
| one attention layer (with q and k RMSNorm gains, 2 x 256) | 372,244,992 [372,244,480] |
| embedding; output head | 1,271,398,400 each |
| **text model** | **26,895,337,984** [26,895,323,648] (56.3 GB as 16-bit weights and a 32-bit embedding) |
| M3a-head (one V head, with its 128 gains) | 3,288,706 [3,288,578] |
| M3b block (3 DeltaNet + 1 attention) | 1,522,033,824 [1,522,032,928] |

The stream pre-norms and the final norm are folded into the next matrix at conversion, as
upstream does (docs/model.md 11.3), so they are not separate tensors. If a build keeps them, add
2 x 5,120 per layer and 5,120 once.

### 7.2 M3a and one layer on the research harness (counted)

r2 counts (`runs/model-r2.json`). Counted, not built.

| statement, arm B, T = 16 | gate columns | range cells | lookup keys | relations | table |
|---|---|---|---|---|---|
| M2 head (#66, reproduced) | 1,056,800 | 272,384 | 276,688 | 2,402,432 | 2^21 |
| **M3a-head** | 1,111,897 | 296,112 | 358,118 | 2,525,004 | **2^21, fits** |
| M3a-MLP | 835,584 | 835,584 | 2,752,512 | 2,031,616 | **2^23, does not fit** (r1: 2^22) |
| one layer as ONE statement, T = 16 | 54,206,640 | 15,048,960 | 19,942,176 | 123,231,808 | 2^27, does not fit |
| one layer as ONE statement, T = 1 | 3,463,200 | 992,400 | 1,471,296 | 8,589,568 | 2^23, does not fit |

Everything M3 adds to the M2 head costs 169,785 laid columns (r1: 137,010), about 11% more; the
r2 increase is the exact 2^s remainder classes and the weight-cell class and tie. Largest T that
fits 2^22: 37 for M3a-head (r1: 38), 15 for M3a-MLP (r1: 20). So **M3a-MLP has to run at T <= 15**,
or as two statements over halves of the hidden units. Every relation is at most 256 terms (the
harness cap), checked by the count model. Term counts are in `runs/model-r2.json` as
`terms_PROVISIONAL`.

These tables are the trace only. The committed weights of the statement (3,288,706 for one head)
sit in a separate table with its own range proof and opening, and the matmuls' sumcheck rounds are
extra. Neither is counted here (RESULTS.md H3, "What these counts leave out"). The weight-cell tie
(6.2) is counted on the trace side only.

**If the lookup build falls back to exact bits (arm A):** remainders become bits and each table
lookup becomes a one-hot selector over 4,096 rows. r1 counted three 4,097-term relations per
lookup; the harness refuses relations of more than 256 terms (`research/operators/qwen_deltanet/product.h`,
`wide_fault`), so **r1's arm-A counts were not a legal statement**. r2 splits each into partial
sums of at most 256 terms and recounts: M3a-head arm A needs 2^26 at T = 16 (39,475,107 laid
columns) and fits only at T = 1 (2,502,379, 2^22). A two-level selector (64 x 64, counted after the
fact, not registered) fits up to T = 9. So M3a without lookups is a T = 9 statement at best, and the
MLP statement does not fit at all. Lookups are not an optimisation for M3. They are a precondition.

### 7.3 Full model (counted, then extrapolated): see RESULTS.md H5

Summary only here. Per window token, all 64 layers and the head:

| DeltaNet state handling | committed entries per token | DeltaNet share |
|---|---|---|
| every state committed, wide product oracle (the only lowering that exists) | about 254M product columns (r1: 250M), 763M field elements | not comparable |
| every state committed, packed as byte limbs (design count; **plan of record**: full state handed on at each chunk boundary) | 95.1M | 88% |
| low-rank inside a chunk of 64: **not established** (see below) | (16.5M in r1; not a usable figure) | |
| dense family alone (upstream planner, proxy shape) | 13.0M | 0 |

**Does it fit one H200? Unknown.** No measured Qwen segment exists, and this design does not
establish a fit. What the numbers do and do not say (all **extrapolated, not measured**):
- **6,250 GB** (r1: 6,138) for the wide oracle is the **aggregate raw trace volume** over all 48
  DeltaNet layers and the whole 1,024-token window, before encoding. It is not peak memory and is
  not compared with a card's memory here; a segmented use of that lowering would hold less at once.
- At the **registered central rate** (23 bytes per entry, from one upstream Maverick point), the
  largest segment of the per-token case with one DeltaNet segment per layer is about 41 GB at
  T = 1,024. At **this fork's own measured rate** (about 220 bytes per entry, its one GPU memory
  reading, small synthetic example, a different model) the same segment needs about **393 GB** at
  T = 1,024. **Neither** that nor the (not established) low-rank form (about 138 GB) fits the
  127 GB rule. At that rate the largest windows that fit are **256 tokens** (per-token state) and
  512 (low-rank). These two rates differ by ten times and nothing here says which one a DeltaNet
  segment follows.
- "High" and "upper bound" in RESULTS are labels of a registered range, **not proved upper
  bounds**. A DeltaNet entry takes part in several products; it is not known to cost what a dense
  entry costs.
- The per-layer case needs **81 segments** per window. `cp_verify` refuses more than 64
  (`verifier/src/vf_segments.inc` line 99, "plan-shape"). Raising that cap is a **required change**
  for that case; the per-block case (49 segments) is within it.
- **Registered verdicts, kept as registered:** in the first run the per-token case with the
  DeltaNet mixer inside the 4-layer link did **not fit** (about 138 GB against 127 GB), and the
  aggregate H5 passed only through the low-rank case. **The separate DeltaNet segments (per block,
  per layer) were chosen after that result was seen: they are exploratory and post hoc**, and the
  "fits" verdicts they get are not registered results.

**The low-rank column is not established.** The independent review of PR #71
(https://github.com/wakesync/flashprove/pull/71#issuecomment-6758363867) found that the chunked
low-rank state form is costed with remainder widths that are too narrow, that edge inputs inside
its range contract give 65 to 67 bit intermediates, and that its only passing variant is
unregistered and has no proof. This design's own low-rank count also omits a second QK Gram, the
staged G table, the P0/Q0 outputs and the M/o remainders. So every low-rank figure here (the 10 /
14 / 29 GB rows, the 5.15M mixer entries, the 16.5M per token) depends on a construction that is
not specified or proved, and is not the plan. **The plan of record is the boundary handoff with
the full per-token cost.**


### 7.4 What depends on the open norm and head-output scaling (counted)

Range facts this section uses, all from PR #68 (merged), layer 0 only, 10 prompts, F = 12: max M
202,297 (77% of 2^18; the synthetic study had 53,294), max S 175,232, max o 23,630. **Deeper layers
are unmeasured.** No count in this design uses the synthetic maxima as a bound: the harness counts
use the cell contract (2^18 honest), and the packed counts use the limb capacity (2^23 for three
signed bytes).

r2 counts; low-rank figures are not established (7.3) and are shown only as r1 carried them.

| if the fix is | research harness, M3a-head, T = 16 | packed, full model, per token |
|---|---|---|
| nothing (F = 12, M2 norm) | 1,783,641 columns, 2^21, largest T 37 | 95.1M (per-token state); low-rank not established |
| norm input o gets 4 to 8 more bits, state unchanged | o, t, y become two cells each: +0.9% columns, still 2^21, largest T 37 | no change on layer-0 maxima: 23,630 x 2^8 is under 2^23, the same three limbs. One more limb for o, t, y if deeper layers need it: +0.4% (per-token) |
| the recurrence also needs more bits (S', M wider) | S' and M become two cells each: +45% columns, 2^22, largest T 25 | a fourth limb on S and M: +17% (per-token state) |

So the answer to "how much if the norm input needs 4 to 8 more bits": almost nothing, as long as
the state keeps its scale. The M3a-head verdict (fits) does not move. What would move it is a
larger F on the recurrence itself: that is +45% on the harness and +17% on the packed per-token
count, and it is a lower bound, because a recurrence at F = 16 also has
products wider than one field element can hold under the range check's slack (section 6), so its
gates would need splitting too. That case is not designed here.

Two constraints the scaling fix must respect, whatever it is:
- With a wider o the norm's sum of squares needs **exact** limb bounds, not the approximate range
  check: at |o| < 2^26 the sum of 128 squares is below 2^59, but the range check's slack (5 bits a
  limb) would take it past the prime.
- M sits at 77% of its cell bound on layer 0. If a deeper layer exceeds 2^18, M splits into two
  limbs as delta already does: about 128 more cells per head per token, under 1%.

## 8 Interfaces to the other lanes

### 8.1 State commitment (#34, lane `qwen-state-commit`)
M3 needs, from whichever strategy wins:
1. **In-cells and out-cells.** A chunk statement reads S_in and H_in as cells of its own relation
   and produces S_out and H_out as cells. H is the last 3 pre-conv inputs of every conv channel
   (3 x 10,240 a layer). **The conv history is carried and bound exactly like the state**: it is
   part of the same boundary value, under the same domain separation. The operators lane's own
   negative control (PR #67, merged) shows what happens otherwise: inside one standalone proof a
   different history with the same outputs verifies. A chunk that could choose its own history
   could change q, k and v at its first 3 tokens.
2. **Carry by commitment, proved.** "S_out of chunk c equals S_in of chunk c + 1" is a claim inside
   the proof (kept rows that the next segment reads, the mechanism of `blocks/toy/segments.h` and of
   upstream's class-B arrays), never a list of words the verifier holds. The carried value is
   domain-separated by request, layer, chunk index and token start, so a boundary cannot be replayed
   or taken from another chunk.
3. **Start.** The first chunk's S_in and H_in are zero by a claim with a public target.
4. **Two numbers:** the chunk size C, and whether the state inside a chunk is laid out as cells. If
   it is not (the low-rank form), the integer semantics change: per-step rounding of S becomes
   rounding at the boundary. Then #34 also owns the integer reference, and the range study and the
   fidelity study must be rerun on it.

That lane's interface v0 (its STATE file) matches points 1 to 3. M3a uses one chunk from a sequence
start, so it does not wait for #34. M3b does.

### 8.2 Operators (#35, lane `qwen-operators`, PR #67, merged)
M3 adopts the table format v1 as published. Differences M3 needs resolved:
- a plain exp(-x) table, because the decay constant is a committed per-head weight;
- inputs outside [-8, 8) are **rejected** in v1. Upstream's Ts table clamps. With reject, a request
  whose activations leave the domain cannot be proved at all. On real weights dt_bias alone reaches
  19.3 (PR #68), more than twice the domain's edge, so for such heads the softplus input
  will usually lie outside it (how often was not measured). M3
  needs clamp semantics (saturating tables, as upstream's Ts) or a wider domain for softplus;
- the decay table's step is too coarse for real decays near 1 (section 5.3);
- its norms are a bounded table approximation, not the isqrt semantics this design counts
  (section 5.3);
- that lane's first backend is a 4,096-row selector, which M3 can only afford at T = 1 (7.2);
- its own negative control shows the conv history is not bound to anything outside one proof. M3
  binds it through 8.1.

### 8.3 Lookup composition (lane `qwen-lookup-build`)
M3 assumes: (a) a second lookup instance keyed on the statement's own cells, with parts, for the
12-bit remainders, sound under separated transcript labels; (b) a third instance for function
tables, whose key is a linear form of two cells (index and value). If the lane falls back to exact
bits: section 7.2.

What exists for function lookups (r2 correction; r1 said they were "in no lane's scope", which is
wrong): PR #67 (merged) provides pinned v1 tables and a 4,096-row one-hot selector that proves
function membership, including the exact input remainder, as **standalone proofs whose inputs are
unbound**. That is the arm-A building block. **What no merged work provides is the efficient
lookup keyed on the statement's own committed cells** (arm B, item (b) above), with the learned
decay constants and the external input and root identity. That is the gap, and the first thing an
M3a build must add.

## 9 Milestone ladder

| step | what | where | evidence gate | stop rule |
|---|---|---|---|---|
| **M3a-1** | M3a-head: one V head against committed weights, T = 16 | CPU harness | honest 10/10; hostile suite rejected, including: proof verified under another weight root, one tap changed, history changed, a trace gain out of class (2^50, the opus alias), a trace gain in class but not the table's, a public shift of 0 or 25, the (s = 8, y = -1, r = 256) floor, the #66 aliases; UBSan clean; columns and relations equal to this lane's r2 counts | no honest proof in 8 h of build time: commit the head's weights in the proof's own oracle with the root in the statement and report. **That fallback drops the WF range proof** (6.2) and is weaker; it is reported as such |
| **M3a-2** | one full DeltaNet layer as 48 head proofs + 1 MLP proof (MLP at T <= 15, or split), synthetic then real layer-0 weights | CPU harness | the public recombination, done with the checks of 6.3, equals an integer reference of the whole layer; ranges hold on real weights | a range class over 2^18 on real weights: split that class and recount before going on |
| **F-gate** | fix F, the head-output and norm scaling and the cell widths from real-weight fidelity (#8, the norm-scaling lane). Already known: on layer 0, 10 prompts, with the M2 lowering, no F in {12, 14, 16} passes both range and fidelity (PR #68) | CPU | a registered fidelity threshold met on real weights, on more than layer 0 and including one layer that abliteration changes; ranges re-measured under the chosen arithmetic | no candidate passes: stop before any GPU work; a proof would then be about an integer model that has not been shown to stay close to Qwen. A candidate that widens the recurrence: recount with section 7.4 and redo the bound ledger |
| **M3b-1** | DeltaNet sub-proof in the GPU prover and in `cp_verify`; one 4-layer block, T = 64, synthetic weights, at the arithmetic the F-gate chose | H200 | `cp_verify` accepts; the standard mutations are rejected; measured VRAM, time and proof size replace every extrapolation here | needs the owner's decision on the GPU (it serves a live endpoint today); measured bytes per entry over twice the central value: take the smaller segments or #34 first |
| **M3b-2** | the same block at T = 256 and 1,024, with chunked state from #34 | H200 | measured numbers, n >= 3; state chain attacks rejected | DeltaNet segment over 127 GB: stop at the largest T that fits and report |
| **M3c** | all 64 layers and the head, synthetic weights, T = 64 | H200 | one accepted proof, verified on a separate CPU machine; CPU composition and identity gate passed first (attention-specific operators, carried state and history adversaries, a full segment and security-accounting plan, validated on CPU) | stop on: measured peak over 127 GB; output different from the integer reference; any accepted mutation; the registered runtime or budget cap reached. Set before the run, never relaxed silently |
| **M3d** | stock real weights, then the abliterated checkpoint with a per-tensor manifest | H200 | the smallest end-to-end result: section 10 | the M3c stops, and also: a real-checkpoint fidelity or range failure, or a manifest failure, judged separately for stock and for abliterated. Set before the run |

M3a-1 and M3a-2 exercise machinery and do not depend on the F-gate: their relations keep their
shape under any of the scaling fixes of section 7.4 that leave the recurrence alone. Their numbers
are about the F = 12 candidate. Nothing after the F-gate should be built before it passes. A block
of layers 0 to 3 is identical in the stock and the abliterated checkpoint, so M3b says nothing
about abliteration; if a partial result about the abliterated weights is wanted before M3c, the
block must lie in layers 17 to 51.

## 10 The smallest milestone that proves a real abliterated reply

All 64 layers, the abliterated weights committed, one request, a 64-token window that holds a
short prompt and a short reply, the manifest of #59 naming the commitment ID.

**What the model commitment must be.** The weight table commits the integers of every tensor under
one root, and the ID covers that root, so a commitment to the abliterated checkpoint differs from
one to stock. But two facts from PR #68 constrain everything around it:
- Stock and abliterated differ in 70 of 1,199 tensors: `mlp.down_proj` plus `out_proj` or `o_proj`
  in layers 17 to 51. Layers 0 to 16 and 52 to 63 are identical. **A partial statement on layers
  0 to 3 (M3a, M3b as laid out below) cannot tell the two checkpoints apart.** The smallest
  statement that can is a block inside 17 to 51, for example layers 16 to 19.
- Every shard's file hash differs, changed tensor or not, because of header metadata. A file hash
  identifies that serialized file; it does not say which tensors differ. Identifying the weights,
  and locating a change, needs a **per-tensor** commitment. The manifest has to bind per tensor: the hash of each tensor's bytes
  at a pinned revision, the conversion rule and exponent, and the commitment ID. Upstream already
  computes a SHA-256 of each tensor's integers (`weight_sums/`, `wsums.txt`) and keeps it secret
  because it lets anyone test a guess of hidden weights. Qwen's weights are public, so for this
  port that file can be published and is the natural per-tensor link.

Two versions of "a real reply", and they are not the same claim:
- **Integer-served, exact match.** The reply is generated by the integer model, and the proof says
  every reply token is that committed integer model's top choice. This is a strong statement about
  the integer model and says nothing about the float model.
- **Float-served, clipped gap.** The reply comes from the normal float engine and the proof says its
  tokens score within fitted limits under the integer model. How much that says depends on how
  close the two models are, which for Qwen is unmeasured beyond one layer.

The first is the one this design can reach without the fidelity question being settled.

## 11 Open risks

1. **No GPU DeltaNet sub-proof exists.** The whole full-model answer rests on a design count for it.
2. **The cost model's rates come from another model** (upstream's Maverick figures, not reproduced
   here) and its VRAM constant from one published point.
3. **Composition risk at M3a:** a weight table next to the research harness has not been built,
   no Qwen layout of the WF range proof exists, and the tie of 6.2 is designed and counted, not built.
4. **Lookups are a precondition** (7.2). PR #67 has the standalone arm-A pieces; the efficient
   lookup keyed on the statement's committed cells exists nowhere (8.3).
5. **Fidelity and scaling are open.** PR #68 measured layer 0 only, 10 prompts, F = 12, 14, 16,
   the M2 lowering: the integer head output FAILED the fidelity threshold at all three F (median
   relative error 0.659, 0.177, 0.049 against 0.01), and F >= 14 breaks the ranges. Other F, other
   lowerings, deeper layers and the abliterated layers 17 to 51 are unmeasured. The statement's
   arithmetic is therefore not final (section 7.4), and a proof of the F = 12 integer model would
   say nothing about how close it is to Qwen.
5a. **Ranges are measured on one layer.** They hold at F = 12 on layer 0 (480 of 480 pairs), with M
   at 77% of its bound. The other 47 DeltaNet layers, including every layer that abliteration
   changes, are unmeasured.
5b. **Table domain.** Format v1 rejects inputs outside [-8, 8). Real dt_bias reaches 19.3 (PR #68),
   so the softplus input is expected to leave that domain on real weights (inferred from the bias
   range, not measured). Section 8.2.
6. **State semantics under #34.** The cheap strategy changes the integer model.
7. **No Lean coverage.** Upstream's soundness theorem is about the Maverick-shaped model. A Qwen
   proof would rest on unverified C++ and CUDA plus this design's arguments.
8. **Standard form.** `cp_verify` cannot say `YES` for a model without experts today (section 4).
9. **Term counts are provisional**, and the M3 additions to the count model have no builder to
   check them against. Two independent reviewers reproduced r1's columns, cells, keys and relations
   with closed forms (+55,090 / +23,728 / +49,744 / +102,800); the r2 changes have not been
   reviewed.
10. **Fit on one H200 is unknown** (7.3). The registered central rate and this fork's own rate
   differ by ten times; the per-layer cut exceeds `cp_verify`'s 64-segment cap; the low-rank form is
   not established.

## 12 Changes in r2 (2026-11-10), by review item

Astra's items are numbered as in its must-fix list; opus's as M1, M2, S5. Where the two differ,
the more precise one is followed (said per item).

1. **Variable shift and scales** (astra 1): section 5.0. Exact class [0, 2^s) for every public
   shift, s admitted in 1..24 (counted: 3 keys and 1 relation per floor); q carries 362; sqrt(128)
   folded into the gain; cA's exponent is the decay divisor; dt_bias at 2^F.
2. **Bounds** (astra 2, opus agreed on SiLU and the q/k square): section 6.1, `bounds.py` r2.
3. **Weight cells** (opus M1, astra 3; opus's alias framing and astra's inventory both taken):
   sections 3.1 and 6.2. Gains in the inventory: 3,288,706 per head (astra's number), +14,336 in the
   model.
4. **Arm A relation width** (astra 4): split at 256 terms and recounted (7.2), not dropped. Opus's
   posted comment said no relation exceeds the cap; opus withdrew that in its result file.
5. **H200 fit** (astra 5, opus M2; astra's per-case wording followed): section 7.3, RESULTS H5.
6. **Low-rank** (review of #71): not established, not the plan (7.3).
7. **Caveats and fidelity scope** (astra 6): this file's header, 10, 11; RESULTS; CLAIMS summary;
   port page.
8. **Function lookups** (astra 6, opus check 8): 8.3.
9. **#66 rule, explicit** (opus S5): 6.3.
10. **Process** (astra 7): PREREG amendments A1 to A4; next-token timing (3.1); stop rules for
   M3c and M3d (9); the results.yaml status is no longer `done`.
11. **Found in r2, not in either review:** M3a-MLP's down projection wraps in r1 (5.5, 6.1).
    Fixed by rounding h; M3a-MLP no longer fits 2^22 at T = 16.
