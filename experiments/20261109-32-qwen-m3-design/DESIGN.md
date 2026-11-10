# Qwen3.8-27B M3: statement design

Issue #32. PREREG: [PREREG.md](PREREG.md) (first commit c9dc2c05). Results and verdicts: [RESULTS.md](RESULTS.md).
Plain-language status page: [docs/qwen-port.md](../../docs/qwen-port.md).

**This is a design. No M3 proof exists and nothing here was run on a GPU.** Numbers are of three kinds
and are kept apart:

- **counted**: exact outputs of `research/operators/qwen_m3/count_m3.py` or of the upstream planner
  (`cp_verify -plan arrays`). A count says how big a statement is, not that it can be proved.
- **extrapolated**: a count multiplied by a rate taken from another model's runs. Each one names its
  assumption. None is a measurement of Qwen.
- **measured**: only numbers already in `research/results.yaml` from earlier PRs. This lane measured
  nothing new.

Two reviews of #66 shaped this design. Section 6 answers the second one (every coefficient that
multiplies a witness value needs an enforced bound). Term counts are marked provisional throughout,
because that review found the norm's term counts in `count_model.py` inexact.

**One parameter is open and this design does not close it.** While this lane ran, the real-weights
lane (PR #68, draft, unreviewed) reported that on real layer-0 weights the M2 range bounds hold at
F = 12 but the integer head output misses its fidelity threshold at F = 12, 14 and 16, and that
F >= 14 breaks the ranges. So one global F with the M2 norm lowering is **not** final. The scaling of
the head output and the gated norm (o, w, t, y, and possibly the recurrence) is an open parameter,
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

**Public** (all bound into the first query of the request's chain, as upstream does,
`blocks/chain/public.h`):
- the configuration: shape, scales (`KL.bin` with per-layer DeltaNet fields added), layout, the
  acceptance policy, and the SHA-256 or BLAKE2b digests of every nonlinear table (section 5.2);
- the commitment ID, which covers the configuration and the weight table's root
  (`published_id`, `blocks/frame/heads.h`);
- the request: T token ids, r, e; the next token.

**Committed once** (`cp_commit`): every integer weight of the text model, 26,895,323,648 values
(counted from the published shapes; section 7.1). This includes the small per-head tensors that M2
treated as public constants: conv taps (10,240 x 4 a layer), the gated-norm gain, and the decay
constants. Every entry outside the embedding is shown to be in -4,096 .. 4,095 by the key file's
range proof (docs/protocol.md 6.1 step 2). That one proof is what bounds every committed
coefficient in section 6.

**Committed per request:** the trace, segment by segment (section 7.3 for the volume).

**The verifier:**
1. recomputes the ID and refuses another one;
2. decodes each public word canonically and checks its class (the #66 entry, DESIGN 4.5 there);
3. derives coefficients and targets from public data only, with checked integer arithmetic. In the
   full-model form the only public values that multiply a committed value are constants of the
   format (powers of two, table steps), the rotary table and the token ids as embedding indices;
4. runs the no-overflow check of section 6 on the configuration before any proof byte is read, and
   refuses a configuration that fails it;
5. checks each segment's sub-proof and the chain of kept values between segments;
6. checks the test on the weight table (shared and second chain, unchanged).

### 3.2 M3a form (the first build, CPU)

M3a keeps the full form's rules and shrinks the boundary so it fits the research harness:

- **Public:** the layer's normed input a (T x 5,120 integers, class |a| <= 2,047, the range of
  upstream's norm output) and the statement's output (one head's out_proj contribution, T x 5,120,
  class |x| < 2^31). S0 = 0 and H = 0 (a sequence start), as constants, not as words.
- **Committed:** that head's weights (3,288,578 values: its rows of in_proj, its conv taps, gain,
  decay constants, its rows of out_proj), under a root that the statement names.
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
| conv1d, softplus and exp tables, per-head q/k norm, gated norm | gadgets | #35 (PR #67, draft) |
| state and conv-history carry between chunks | kept rows or a boundary commitment | #34 |
| second and third lookup instances keyed on the statement's own cells | harness | lookup build lane |
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

### 5.1 Matmuls
x_j = rq(sum_k a_k W_kj, s): per output one range cell x_j and one exact 24-bit remainder. No gate
column and no relation per multiply: the whole product is one claim on the weight table after a
sumcheck (or, with a public as in M3a, directly a linear claim).

### 5.2 Nonlinear tables
One format for all of them, the operators lane's v1 (4,096 rows, input step 2^(F-8), output scale
2^F, domain [-8, 8), generated without floating point, hashed). A lookup is a pair (idx, y) checked
against the public table, plus the index remainder shown in range by two 12-bit keys. The table's
digest is part of the configuration, so prover and verifier cannot disagree on a row.

Tables M3 needs: silu, sigmoid, softplus, and exp(-x) on [0, 8) (requested from #35: their
`decay-*` tables fix the decay constant, and Qwen's is a learned per-head weight).

### 5.3 Conv, q/k norm, gates
- **conv:** acc = sum of 4 (tap x input) with taps as committed weight cells, 4 gates a channel;
  c = floor(acc / 2^12) with an exact remainder. The inputs before token 0 are the committed history.
- **q/k L2 norm:** the isqrt and reciprocal form of #66 section 4.4 (exact, no domain limit), then
  one floor per channel. **The norms of PR #67 are not this.** They are table lookups on a bounded
  domain (mean square in [1/4, 17/4)), with no epsilon and no near-zero handling: a different
  integer function, which rejects inputs the isqrt form accepts. This design counts the isqrt form.
  The table form stays a candidate for the attention layers' q/k RMSNorm and for whatever the
  norm-scaling lane recommends.
- **decay:** sp = softplus[ar + dt_bias]; g = floor(cA x sp / 2^F) with cA = round(2^e exp(A_log)) a
  committed weight; a = exp_neg[g]. **beta** = sigmoid[br].
- **The decay table needs a finer step than table format v1 has.** On real weights the median decay
  is 0.998 (PR #68, draft), so the exponent g is about 0.002. Format v1 has an input step of 1/256,
  about 0.004: more than half of the real exponents would fall in the first row and read as
  "no decay". A table keyed on g itself at 2^-12 over [0, 1), with the coarse table beyond, costs
  one more lookup per head per token (1 in about 520). This is a request to #35, and a fidelity
  question for #8; the counts here include one exp lookup, not two.

### 5.4 Gated norm without a derived coefficient
M2 had y = floor(cg w / 2^F) with cg computed by the verifier from the gain and SiLU(z). In M3
neither is public. The design:

    s = Ts[z]                    a table cell, |s| <= 4,095 by the table's image
    t = floor(s w / 2^F)         one gate, one range cell, exact remainder
    y = floor(gain t / 2^sg)     one gate with the committed gain, exact remainder

A cheaper variant folds the gain into out_proj at conversion time, as upstream folds every norm
gain into the next matrix (docs/model.md 11.3). Then the last line disappears. The counts in this
lane keep the gain gate, so they are on the high side. The choice changes rounding, so it belongs
with the fidelity work (#8).

### 5.5 Statement kinds for M3a
- **M3a-head:** section 3.2. One per V head. A QK head's q/k path is proved again in each of the 3
  V heads that share it (simple, and 3x redundant on about 2% of the cells).
- **M3a-MLP:** the layer's SwiGLU MLP from its normed input m (public) to its output (public): gate
  key and up value as range cells, SiLU by lookup, one gate s x u, down projection by the product
  argument.
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
| key range proof | **every committed weight**: in_proj, out_proj, conv taps, gain, cA, dt_bias: \|w\| <= 4,096 | the key file's range proof, checked on every call | **no** |
| table image | outputs of SiLU, sigmoid, softplus, exp lookups | exact lookup into a public table whose digest the ID covers | no |
| exact key | 12-bit remainder limbs | lookup-exact (arm B) or bits (arm A) | no |
| range check | every other cell: \|x\| < 2^23 against a cheating prover | RNG | no |
| implied | q, k, w, t (each <= 2^12) | follows once the relation before it holds over the integers | no |

So when the verifier cannot recompute a coefficient, its bound is **proved**: by the key file's
range proof if it is a weight, by a lookup if it is a function value, by the range check otherwise.
Nothing is left as a contract on honest behaviour.

Real Qwen gains are not 1. A gain enters as a committed integer gain_int = RNE(2^e gain) with the
tensor's own exponent e, exactly as upstream converts a weight matrix (docs/model.md 11.4), so
|gain_int| <= 4,095 whatever the float gain is. The exponent e is public (it sets the shift sg).

`research/operators/qwen_m3/bounds.py` recomputes the worst magnitude of the 21 relation kinds from
these bounds: the largest is 2^61 (the reciprocal relation Rc x sigma), all are below 2^63, and the
control row (the M2 coefficient at 2^62) fails as it should. That script is arithmetic on the
design. **Build requirement:** the M3 verifier runs the same computation on its configuration at
start-up, as `cp_verify` runs its no-overflow conditions, and the hostile suite has a commitment
with an out-of-range gain (must fail at the key), the boundary pair 4,095 / 4,097, and the #66
alias statements.

## 7 Counting results (verdicts and full tables: RESULTS.md)

### 7.1 Weights (counted from shapes)

| | integers |
|---|---|
| one DeltaNet layer (in_proj 84.4M, conv 40,960, out_proj 31.5M, MLP 267.4M) | 383,262,816 |
| one attention layer | 372,244,480 |
| embedding; output head | 1,271,398,400 each |
| **text model** | **26,895,323,648** (56.3 GB as 16-bit weights and a 32-bit embedding) |
| M3a-head (one V head) | 3,288,578 |
| M3b block (3 DeltaNet + 1 attention) | 1,522,032,928 |

### 7.2 M3a and one layer on the research harness (counted)

| statement, arm B, T = 16 | gate columns | range cells | lookup keys | relations | table |
|---|---|---|---|---|---|
| M2 head (#66, reproduced) | 1,056,800 | 272,384 | 276,688 | 2,402,432 | 2^21 |
| **M3a-head** | 1,111,890 | 296,112 | 326,432 | 2,505,232 | **2^21, fits** |
| M3a-MLP | 835,584 | 557,056 | 1,835,008 | 1,114,112 | 2^22, fits |
| one layer as ONE statement, T = 16 | 54,206,304 | 14,770,432 | 17,503,744 | 121,365,248 | 2^27, does not fit |
| one layer as ONE statement, T = 1 | 3,462,864 | 974,992 | 1,093,984 | 8,322,608 | 2^23, does not fit |

Everything M3 adds to the M2 head costs 137,010 laid columns, about 8% more. Largest T that fits
2^22: 38 for M3a-head, 20 for M3a-MLP. Term counts are in `runs/model.json` as `terms_PROVISIONAL`.

These tables are the trace only. The committed weights of the statement (3,288,578 for one head)
sit in a separate table with its own range proof and opening, and the matmuls' sumcheck rounds are
extra. Neither is counted here (RESULTS.md H3, "What these counts leave out").

**If the lookup build falls back to exact bits (arm A):** remainders become bits and each table
lookup becomes a one-hot selector over 4,096 rows. M3a-head then needs 2^26 at T = 16 and fits only
at T = 1. A two-level selector (64 x 64, counted after the fact, not registered) fits up to T = 9.
So M3a without lookups is a T = 8 statement at best, and the MLP statement does not fit at all.
Lookups are not an optimisation for M3. They are a precondition.

### 7.3 Full model (counted, then extrapolated): see RESULTS.md H5

Summary only here. Per window token, all 64 layers and the head:

| DeltaNet state handling | committed entries per token | DeltaNet share |
|---|---|---|
| every state committed, wide product oracle (the only lowering that exists) | about 250M product columns, 750M field elements | not comparable |
| every state committed, packed as byte limbs (design count) | 95.1M | 88% |
| chunk-boundary state only, low-rank inside a chunk of 64 (#34, not built) | 16.5M | 31% |
| dense family alone (upstream planner, proxy shape) | 13.0M | 0 |

Whether these fit one H200, how long they take and what a token costs are extrapolations, and they
are in RESULTS.md H5 with their assumptions and their spread (the prove-time estimates span a
factor of about 60). The short form: the lowering that exists does not fit by a factor of more
than 40; a packed DeltaNet sub-proof with every state committed is borderline or fits depending on how
it is cut into segments; with chunk-boundary state the DeltaNet part stops being the largest term.


### 7.4 What depends on the open norm and head-output scaling (counted)

Range facts this section uses, all from PR #68 (draft, unreviewed), layer 0 only, F = 12: max M
202,297 (77% of 2^18; the synthetic study had 53,294), max S 175,232, max o 23,630. **Deeper layers
are unmeasured.** No count in this design uses the synthetic maxima as a bound: the harness counts
use the cell contract (2^18 honest), and the packed counts use the limb capacity (2^23 for three
signed bytes).

| if the fix is | research harness, M3a-head, T = 16 | packed, full model, per token |
|---|---|---|
| nothing (F = 12, M2 norm) | 1,750,866 columns, 2^21, largest T 38 | 95.1M (per-token state); 16.5M (low-rank) |
| norm input o gets 4 to 8 more bits, state unchanged | o, t, y become two cells each: +0.9% columns, still 2^21, largest T 38 | no change on layer-0 maxima: 23,630 x 2^8 is under 2^23, the same three limbs. One more limb for o, t, y if deeper layers need it: +0.4% / +2.3% |
| the recurrence also needs more bits (S', M wider) | S' and M become two cells each: +47% columns, 2^22, largest T 26 | a fourth limb on S and M: +17% (per-token state), +2.3% (low-rank) |

So the answer to "how much if the norm input needs 4 to 8 more bits": almost nothing, as long as
the state keeps its scale. The M3a verdict (fits) and the full-model verdicts do not move. What
would move them is a larger F on the recurrence itself: that is +47% on the harness and +17% on
the packed per-token count, and it is a lower bound, because a recurrence at F = 16 also has
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
   negative control (PR #67, draft) shows what happens otherwise: inside one standalone proof a
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

### 8.2 Operators (#35, lane `qwen-operators`, PR #67 draft)
M3 adopts the table format v1 as published. Differences M3 needs resolved:
- a plain exp(-x) table, because the decay constant is a committed per-head weight;
- inputs outside [-8, 8) are **rejected** in v1. Upstream's Ts table clamps. With reject, a request
  whose activations leave the domain cannot be proved at all. On real weights dt_bias alone reaches
  19.3 (PR #68, draft), more than twice the domain's edge, so for such heads the softplus input
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
tables, whose key is a linear form of two cells (index and value). (b) is not in that lane's brief
and is the first thing an M3a build must add. If the lane falls back to exact bits: section 7.2.

## 9 Milestone ladder

| step | what | where | evidence gate | stop rule |
|---|---|---|---|---|
| **M3a-1** | M3a-head: one V head against committed weights, T = 16 | CPU harness | honest 10/10; hostile suite rejected, including: proof verified under another weight root, one tap changed, history changed, gain out of range, the #66 aliases; UBSan clean; columns and relations equal to this lane's counts | no honest proof in 8 h of build time: commit the head's weights in the proof's own oracle with the root in the statement (weaker, stated) and report |
| **M3a-2** | one full DeltaNet layer as 48 head proofs + 1 MLP proof, synthetic then real layer-0 weights | CPU harness | the public recombination equals an integer reference of the whole layer; ranges hold on real weights | a range class over 2^18 on real weights: split that class and recount before going on |
| **F-gate** | fix the head-output and norm scaling and the cell widths from real-weight fidelity (#8, the norm-scaling lane). Already known: no single F in {12, 14, 16} passes both range and fidelity on layer 0 (PR #68, draft) | CPU | a registered fidelity threshold met on real weights, on more than layer 0 and including one layer that abliteration changes; ranges re-measured under the chosen arithmetic | no candidate passes: stop before any GPU work, the statement would be about a model that does not track Qwen. A candidate that widens the recurrence: recount with section 7.4 and redo the bound ledger |
| **M3b-1** | DeltaNet sub-proof in the GPU prover and in `cp_verify`; one 4-layer block, T = 64, synthetic weights, at the arithmetic the F-gate chose | H200 | `cp_verify` accepts; the standard mutations are rejected; measured VRAM, time and proof size replace every extrapolation here | needs the owner's decision on the GPU (it serves a live endpoint today); measured bytes per entry over twice the central value: take the smaller segments or #34 first |
| **M3b-2** | the same block at T = 256 and 1,024, with chunked state from #34 | H200 | measured numbers, n >= 3; state chain attacks rejected | DeltaNet segment over 127 GB: stop at the largest T that fits and report |
| **M3c** | all 64 layers and the head, synthetic weights, T = 64 | H200 | one accepted proof, verified on a separate CPU machine | |
| **M3d** | stock real weights, then the abliterated checkpoint with a per-tensor manifest | H200 | the smallest end-to-end result: section 10 | |

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
one to stock. But two facts from PR #68 (draft) constrain everything around it:
- Stock and abliterated differ in 70 of 1,199 tensors: `mlp.down_proj` plus `out_proj` or `o_proj`
  in layers 17 to 51. Layers 0 to 16 and 52 to 63 are identical. **A partial statement on layers
  0 to 3 (M3a, M3b as laid out below) cannot tell the two checkpoints apart.** The smallest
  statement that can is a block inside 17 to 51, for example layers 16 to 19.
- Every shard's file hash differs, changed tensor or not, because of header metadata. So a file
  hash is not a model ID. The manifest has to bind **per tensor**: the hash of each tensor's bytes
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
3. **Composition risk at M3a:** a weight table next to the research harness has not been built.
4. **Lookups are a precondition** (7.2), and function-table lookups are not yet in any lane's scope.
5. **Fidelity and scaling are open.** On real layer-0 weights (PR #68, draft, unreviewed) the head
   output misses the fidelity threshold at F = 12, 14 and 16 (median relative error 0.659, 0.177,
   0.049 against 0.01), and F >= 14 breaks the ranges. The statement's arithmetic is therefore not
   final (section 7.4). A proof of the F = 12 integer model would be a correct proof about a model
   that does not track Qwen.
5a. **Ranges are measured on one layer.** They hold at F = 12 on layer 0 (480 of 480 pairs), with M
   at 77% of its bound. The other 47 DeltaNet layers, including every layer that abliteration
   changes, are unmeasured.
5b. **Table domain.** Format v1 rejects inputs outside [-8, 8). Real dt_bias reaches 19.3 (PR #68),
   so the softplus input leaves that domain on real weights. Section 8.2.
6. **State semantics under #34.** The cheap strategy changes the integer model.
7. **No Lean coverage.** Upstream's soundness theorem is about the Maverick-shaped model. A Qwen
   proof would rest on unverified C++ and CUDA plus this design's arguments.
8. **Standard form.** `cp_verify` cannot say `YES` for a model without experts today (section 4).
9. **Term counts are provisional**, and the M3 additions to the count model have no builder to
   check them against. Columns, cells, keys and relations of the M2 part were reproduced by an
   independent reviewer; the M3 part was not reviewed.
