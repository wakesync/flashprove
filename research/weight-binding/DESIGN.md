# Weight binding for Qwen3.8-27B: a per-tensor commitment in the statement (Q2, design)

Agenda question Q2, use case U1 (model substitution). Part of #36. Measured companion:
[experiments/20261110-36-weight-binding](../../experiments/20261110-36-weight-binding/RESULTS.md).
Status: **design, counted, not built.** Nothing here is a proof. Evidence cited is on main or in this
PR only.

## 0 The answer in plain words

- **Can a verifier tell which weights ran, today?** For Qwen, no: there is no Qwen proof on main at
  all (M3 is designed in #70, not built). For the upstream Maverick path a `YES` is meant to tie a
  reply to the one integer weight table under the commitment ID, but the ID "does not say whose
  weights the table contains" (`blocks/frame/heads.h`, `published_id`). Which checkpoint that
  table came from is the vouching party's word (`docs/limits.md`, "The provider chooses the
  committed model"), or the signer's word in #59's manifest.
- **Would stock and huihui-abliterated be distinguishable under proof?** The commitments would
  differ: after the repository's conversion rule, 6 of 6 sampled changed tensors differ in 33% to
  68% of their integers, the unchanged control is identical (this PR, H2). But a proof
  distinguishes them only if (a) the verifier can tie the ID to the public checkpoint, which no
  program does today, and (b) the statement reaches layers 17 to 51 and opens the changed tensors'
  claims against a bound table. A statement on layers 0 to 16 or 52 to 63 is the same for both
  (#68). And under the clipped-gap policy, an abliterated reply proved against the stock ID is
  accepted whenever its tokens fall within the stock limits (#50 accepted 5 of 54 changed steered
  replies); only exact match turns "same ID" into "same tokens as stock".
- **What is missing**, by effort, is in section 6.

## 1 What main has today (U1)

| piece | what it binds | what it does not | where |
|---|---|---|---|
| commitment ID | hash of the configuration digest, the anchor table's name (root, shape) and its OOD seeds and answers; meant to fix one integer weight matrix | which model; binding for the programs is not proved (row LIM-2) | `blocks/frame/heads.h`; `docs/protocol.md` 4, 5.5 |
| key file | WF range proof (digits in [-128, 127], two-digit weights in [-4,096, 4,095]) and the one-time test on the anchor | **Maverick unit kinds only** (`docs/format/11-5-weights-in-the-table.md`: kinds 0 to 13, no DeltaNet in_proj_qkv/z/a/b, conv, A_log, dt_bias, linear out_proj); four-digit units (embedding) get digit bounds only | `docs/protocol.md` 6.1 |
| `wsums.txt` | per-tensor SHA-256 of the integers and the exponent; `cp_commit` refuses weights whose integers do not match | checked at commit time by the committer only; not in the ID, not seen by `cp_verify`; kept private because it lets anyone test a guess of hidden weights | `weight_sums/README.md`, `prover/hash_commitment/hf_commit.cu` |
| signed manifest (#59) | upstream repo, revision, file hashes, conversion, commitment ID, serving files, signed | detached and client-side (not in the configuration or the proof); `commitment.kind` always the signer's word; `committed_files` and upstream files only with rehash flags; rederivation needs `cp_commit` on a GPU | `experiments/20261104-58-signed-manifest/RESULTS.md` |
| per-tensor diff (#68) | 70 of 1,199 tensors differ (down_proj + out_proj / o_proj, layers 17 to 51); every shard file hash differs, because of header metadata | a file hash says nothing about which tensors changed | `experiments/20261109-8-qwen-real-weights/RESULTS.md` section 3 |
| M3 design (#70) | weight table under the ID; matmuls as claims on the table; weight cells (taps, gain, cA, dt_bias) with an in-trace class and an addressed tie (r2/r3, section 6.2) | designed and counted, not built; no Qwen WF layout; section 10 says a partial statement on layers 0 to 3 cannot tell the pins apart | `experiments/20261109-32-qwen-m3-design/DESIGN.md` 3.1, 6.2, 10 |
| Qwen operators (#67) | local relations | statements are existential: the prover chooses the conv kernel and history; a history replacement against the same outputs was accepted 1 / 1 | `experiments/20261109-35-qwen-operators/RESULTS.md` |
| model identity (#36 Stage 1, #46; steering #50) | exact match refused 57 of 57 changed steered replies; clipped-gap accepted 5 of 54 | synthetic model; #46 had no CPU proof path | `experiments/20261103-model-identity`, `experiments/20261104-36-steering-real-proofs` |

The review of #70 (opus M1, `REVIEW70` comment on #70) found that r1 read conv taps, the gated-norm
gain, cA and dt_bias as plain trace cells with no tie to the weight table, so a cheating prover
could put gain = 2^50 in the trace and make y free. #70 r2/r3 designed the fix (section 6.2) and
counted it; it is not built.

## 2 The design: verifier-held model id -> per-tensor roots -> the table

**Use case U1.** The verifier holds a 32-byte **model id** for a named pin, obtained from a party
it trusts or, for open weights, computed by itself (section 4). The id commits to a list of
per-tensor leaves. The statement proves that the committed weight table holds, tensor by tensor,
the integers those leaves name, and that every relation that reads a weight reads it from that
table at an address the configuration fixes.

### 2.1 The manifest (hash level, built in this PR, H1)

Leaf of a tensor t, sorted by name:
`H(0x00 || "fp-wb-leaf-v1" || name || dtype || shape || sha256(source bytes of t))`; nodes
`H(0x01 || "fp-wb-node-v1" || l || r)`; id `H("fp-wb-id-v1" || n || root)`, H = SHA-256.

The production leaf adds what the conversion needs so that the leaf names integers, not floats:
- the conversion rule version and the tensor's exponent e_t (public in the configuration, covered
  by the commitment ID: the leaf must equal the configuration's value);
- for a matrix that has a norm folded in (`weight_sums.py`, `multipliers`), the source digest of
  that norm too: its integer is RNE(2^e RN32(v RN32(g c))), so its leaf depends on two tensors;
- `int_sha256`: SHA-256 of the integers (the `wsums.txt` line). For open weights this file can be
  published: nothing is hidden (#70 section 10 makes the same point);
- `y_t`: the field fingerprint of section 2.2.

Use tensor-byte hashes, never file hashes: #68 shows all 18 shard hashes differ although 1,129 of
1,199 tensors are identical.

### 2.2 Binding the table to the leaves (in the key file)

The integers of tensor t occupy a set of cells of the committed matrix W at positions the 11.5
placement fixes from the parameter file. Let MLE_t be the multilinear extension of those integers
(zero-padded to 2^(n_t)). After the anchor's root is fixed, derive a point z_t by hashing (root,
model id, t). The key file proves, for every committed tensor, **MLE_t(z_t) = y_t**, as one more
batched linear claim in the one-time test (the LIN / FOLDEQ machinery the matmul claims already
use: the evaluation of a block of W at a point is a linear functional of W). The verifier:
1. recomputes the model id from the manifest it holds, or compares the held id;
2. reads y_t from the manifest (or recomputes it from the public checkpoint, section 4);
3. checks the key file's claim with those y_t.

Two different integer tensors agree at a random z_t with probability at most n_t / |F| per tensor
(Schwartz-Zippel; n_t <= 31 here, F the cubic extension of Goldilocks). The point must come after
the root (Fiat-Shamir): a point known first lets a committer pick a table that agrees at it.
H3 in this PR is the toy version (mod 2^31 - 1, numpy): 6 of 6 changed tensors differ, the control
is equal. With hidden weights y_t leaks one field element per tensor, like the OOD answers do per
row; with open weights it leaks nothing new.

### 2.3 Which relations must open against the bound table

Every place a weight enters the statement. Use case U1 needs all of them; one gap is enough to
serve another model.

| # | relation | how it must open | status on main |
|---|---|---|---|
| R1 | matmuls: in_proj_qkv / z / a / b, linear out_proj, q / k / v / o_proj, gate / up / down, embedding, lm_head | claims on the weight table at addresses from the 11.5 placement; needs **new unit kinds** for every DeltaNet tensor and Qwen's shapes | upstream form for Maverick only; Qwen kinds absent |
| R2 | weight cells read by the trace: conv taps (40,960 a DeltaNet layer), gated-norm gain (128), cA (48), dt_bias (48); q / k norm gains (512 an attention layer) if kept as cells | in-trace exact class plus the addressed batched tie of #70 DESIGN 6.2 | designed, counted, not built |
| R3 | folded RMSNorm gains (input / post-attention) | no cell: bound through the folded matrix's integers; the leaf must carry the norm's digest and the rule | upstream rule exists (`weight_sums.py`); leaf form is new |
| R4 | range of every committed weight | WF range proof on a Qwen layout (two-digit units); four-digit units for the embedding and dt_bias (#70 r3) | Maverick layout only |
| R5 | exponents and shifts e_t, s_t | public in the configuration (under the ID), equal to the leaf's; each floor's remainder class exact for its s (#70 5.0) | in #70 design |
| R6 | conv history and recurrent state across chunks | not weights, but a prover-chosen history substitutes earlier computation: chain inside the proof, first chunk from zero (#34, #71 SA) | #71 chain check is outside the proof in its harness |
| R7 | scope | for this pair the statement must reach a layer in 17 to 51 and open its down_proj and out_proj / o_proj | M3a/M3b plan layers 0 to 3 (#70 section 10) |

## 3 Attacks and what stops each (U1)

| attack | today | with this design |
|---|---|---|
| **A1 alias gain = 2^50** (opus review of #70, M1): a trace weight cell with no tie, so the floor wraps and y is free | open in r1; #70 r2/r3 design fix | R2: class [-4,096, 4,095] in the trace stops the large value, the tie stops an in-class wrong value. Hostile cases listed in #70 M3a-1 |
| **A2 table-only range proof**: WF bounds table entries, not trace cells; and there is no Qwen layout, so a Qwen table has no range proof at all | open | R2 for cells; R4 needs the Qwen WF layout. #70 r3: the in-oracle fallback does not fit any 2^22 table (9,866,118 keys for one head) |
| **A3 prover-chosen kernel / history** (#67): the operator statements are existential; the same conv outputs were proved with another kernel, and a replaced history was accepted 1 / 1 | open | kernel: R2 tie at config-fixed addresses; history: R6 in-proof chain |
| **A4 address remap**: a cell or claim points at another tensor's entry (e.g. layer 16's down_proj where layer 17's is read; L16 is identical in both pins) | not applicable yet | addresses derived by the verifier from the configuration (6.2 step 2; 11.5 placement) |
| **A5 wrong checkpoint under a vouched ID**: commit the abliterated weights, publish the ID as stock's | stopped only by trusting the vouching party or #59's signer | refutable by anyone: y_t or `int_sha256` recomputed from the public pin do not match (H2: 6 of 6 integer hashes differ) |
| **A6 partial-statement blind spot**: a statement or a sampled audit (U2) that touches only layers 0 to 16 and 52 to 63 is identical for both pins | inherent | R7. U2: a uniformly sampled single layer touches 17 to 51 with probability 35 / 64 = 0.55; 4 distinct layers 0.963; 8 distinct 0.999 (counted, `runs/counted.json`) |
| **A7 tolerance of the acceptance policy**: under clipped-gap, a reply from another model is accepted if within the limits of the committed one | #50: 5 of 54 changed steered replies accepted | not a binding problem: use exact match for U1 claims, with the integer model served (#70 section 10, "integer-served") |
| **A8 commitment.kind and rederivation** (#59): hidden and public-weights commitments look alike; the kind is the signer's word | open | irrelevant to binding once 2.2 is checked: binding no longer needs rederivation |
| **A9 conversion freedom**: other exponents, rounding or a quantised copy give a "close" table | exponents are public in the configuration; nothing ties them to a pin | leaf pins rule and e_t; a quantised or re-exponented copy has other integers and fails the check. This is the substitution U1 wants caught |
| **A10 point before root**: z_t known before the table is fixed | n/a | derive z_t from the root (2.2); Fiat-Shamir order as in #41 |
| **A11 file-hash identity**: comparing shard hashes | #68: all 18 differ although 1,129 tensors are equal | per-tensor leaves (H1) |

## 4 Two routes to "the ID is pin P", for open weights

- **Route A, rederivation (no protocol change).** An auditor runs `cp_commit -public-weights` with
  a public seed on the pinned files and compares the ID. Byte-identical output under one seed is
  shown at small size only (`docs/limits.md`, "What a reader can check"); at full size there was
  no control. Needs a GPU per pin and Qwen support in `cp_commit` (absent). Hides nothing, which
  is fine for open weights.
- **Route B, per-tensor evaluations in the key file (section 2.2).** Anyone recomputes y_t on a
  CPU from the pin; the key file proves the table matches. Works with hidden weights too (the
  manifest then needs a trusted publisher of y_t, as the ID does today). Needs a protocol change:
  a new item in the key file's first chain, a format version, and the Qwen placement.

Route A is the cheaper first step for the stock / abliterated pair, both open. Route B is the one
that makes the proof itself say which weights ran.

## 5 Cost with main's numbers (U1, counted unless marked)

All from `runs/counted.json` (this PR) unless cited.

| item | number | kind |
|---|---|---|
| committed integers, text model | 26,895,337,984 (56.3 GB) | counted, #70 |
| manifest | 1,199 leaves, 11-sibling openings (about 0.6 KB), both pins built and checked in 0.17 s | measured here, n = 1 |
| hash both pins' tensors from the Hub | 290.0 s and 273.1 s streaming, 55.56 GB each | measured, #68, n = 1 |
| recompute y_t for the whole model | about 84 min at the toy numpy rate of 5.3 M elements / s on one process | **extrapolated** from H3 (393 M elements, 74 s); a C or GPU field kernel would differ |
| key-file claim | 851 text tensors' evaluations, one batched linear claim in the one-time test | counted; table-side cost not counted |
| commit time for Qwen | about 2.6 min | **extrapolated** in #70 from upstream's 39 min Maverick figure, linear in weights |
| weight cells (R2), whole model | 1,985,024 cells: 5.96 M keys, 3.98 M relations, once per window | counted (arm B layout of #70 count_m3 `wcells`) |
| R2 against the window | 0.39% of a T = 16 window's packed entries, 0.006% at T = 1,024 | counted ratio of keys to #70's 95,057,841 packed entries per token; the units differ (keys vs entries), so read as an order of magnitude |
| verifier | 851 field comparisons plus one manifest hash | counted |

The binding itself is cheap. What costs is building the pieces it rests on (section 6), and the
statement having to reach layers 17 to 51 at all.

## 6 What is missing for a real "you served model X" proof, ordered by effort

1. **Publish per-tensor manifests for both pins (hours, CPU).** This PR builds the hash-level one
   from #68's hashes (H1). Add `int_sha256` per tensor (the `wsums.txt` line; publishable for open
   weights) and the exponents, and put the manifest root into #59's signed manifest. Still the
   signer's word about the table, but now checkable against the Hub by anyone.
2. **A verifier-side recompute tool (days, CPU).** Pin -> integers -> y_t in the protocol's field
   at points derived from a given root, following the 11.5 placement. H3 is the toy version.
3. **Rederivation for open weights, Route A (one GPU run per pin, once Qwen is supported by
   `cp_commit`).** No protocol change; needs a full-size byte-reproducibility control.
4. **Qwen layout of the weight table and its WF range proof (weeks).** New unit kinds for DeltaNet
   tensors in the 11.5 placement; four-digit units for dt_bias. Without it A2 is open.
5. **Per-tensor evaluation claims in the key file, Route B (weeks, protocol change).** One batched
   claim; new chain item; format version.
6. **The weight-cell tie of #70 6.2, built (weeks)**, in M3a with the hostile suite: gain 2^50,
   in-class mismatch, address remap, kernel and history swaps (A1, A3, A4).
7. **A statement that reaches layers 17 to 51 (months)**: M3c or a block inside 17 to 51, with the
   state and history chain inside the proof (R6, R7). Only then does stock vs abliterated show up
   in a proof.
8. **Fidelity (Q1, open research).** Until the integer model tracks the float model (#68: it does
   not at layer 0 for F = 12, 14, 16 under the M2 lowering), the claim is "you served the integer
   model of pin P under rule R", with exact match. That is a U1 claim only if the provider serves
   the integer model. Clipped-gap acceptance against a float-served reply is not model identity
   (A7).

## 7 Other use cases

- **U2 (sampled audit).** The binding is per commitment, so it costs nothing per sample. What
  matters is that a sample reaches a changed tensor; the counted probabilities are in A6. A
  sampled layer proved alone, with its input stream as a free or prover-supplied value, can be
  proved with the stock weights on whatever input the abliterated model produced, so a sample
  catches a swap only if its input is bound to the request (the earlier layers proved, or a
  committed stream that later checks open). That is R6 again; Q4 owns the sampling side.
- **U3 (proof with TEE).** Tinfoil Modelwrap attests a dm-verity root over weight files. That binds
  files in the enclave, not the computation. Route B's manifest and Modelwrap's root can name the
  same tensors, which joins them: the enclave attests the files, the proof shows the computation
  used a table equal to them per tensor. Not designed further here.
