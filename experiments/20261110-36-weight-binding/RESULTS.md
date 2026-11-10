# RESULTS: 20261110-36-weight-binding

Part of #36 (model identity). Agenda Q2 (weight binding), use case U1 (model substitution).
PREREG: [PREREG.md](PREREG.md), first commit 43d9b4e3. Design: [research/weight-binding/DESIGN.md](../../research/weight-binding/DESIGN.md).
Code and commands: [research/weight-binding/README.md](../../research/weight-binding/README.md). Raw data: `runs/`.

**Nothing in this experiment is a proof.** H1 is hash bookkeeping over #68's per-tensor hashes.
H2 and H3 are arithmetic on 7 real tensors. No `cp_commit`, `cp_prove` or `cp_verify` ran. All
numbers are measured once (deterministic), unreplicated, on a shared loaded CPU host, unless
marked counted or extrapolated.

## Verdict against the pre-registration

| item | registered threshold | result | verdict |
|---|---|---|---|
| H1 whole manifest | refused both ways | stock id refuses the abliterated manifest, abliterated id refuses stock's | PASS |
| H1 own openings | 1,199 / 1,199 both ways | 1,199 / 1,199 both ways | PASS |
| H1 changed openings (other pin) | 0 / 70 accepted both ways | 0 / 70 both ways | PASS |
| H1 unchanged openings (other pin) | **1,129 / 1,129 accepted** both ways | **0 / 1,129** both ways | **FAIL** |
| H2 gating (fetched bytes = #68 hash) | 14 / 14 | 14 / 14 | PASS |
| H2 changed tensors, integer fraction differing >= 0.01 | 6 / 6 | 6 / 6 (0.327 to 0.679) | PASS |
| H2 control identical | 0 entries, equal hash | 0 entries, equal SHA-256 of integers, bytes identical | PASS |
| H3 fingerprints | differ 6 / 6, equal on control | differ 6 / 6, equal 1 / 1 | PASS |

**H1 fails as registered, on the clause about unchanged tensors.** The expectation was wrong, not
the code: a Merkle opening carries the sibling path of the tree it came from, and the abliterated
tree's path for an unchanged tensor still hashes up to the abliterated root, because 70 other
leaves under it differ. So against the stock id, every opening built from the abliterated tree is
refused, changed tensor or not. The registered clause tried to express "a statement confined to
unchanged tensors cannot tell the pins apart". The correct form is at the leaf level: the leaves of
the 1,129 unchanged tensors are byte-identical, so an opening taken from the held pin's own tree
verifies whether the prover ran stock or abliterated weights for that tensor. That is
true by construction (the leaf of an unchanged tensor is the same 32 bytes in both trees) and is
what the design (DESIGN.md A6, R7) relies on. A run that counts it (amendment A1) was written and
held by the gateway before running; it is not in this PR (deviation 2).

## H1: a per-tensor manifest for each pin (hash level)

`runs/h1-manifest-demo.json`, `runs/manifest-{stock,abl}.json`. Leaves are #68's streamed SHA-256
of each tensor's BF16 bytes (`experiments/20261109-8-qwen-real-weights/runs/stream-*.json`); no
weights read for H1.

- 1,199 leaves per pin, sorted by name; the name, dtype and shape lists are identical across pins.
- model id stock `eb2cfd30...801f`, abliterated `16834f8e...9e86` (full values in the run file).
- 70 leaves differ, exactly #68's 70 tensors: 35 `mlp.down_proj`, 26 `linear_attn.out_proj`, 9
  `self_attn.o_proj`, layers 17 to 51.
- A forged opening (the held pin's honest path with the other pin's digest for a changed tensor) is
  refused, both directions.
- An opening has 11 sibling hashes (about 0.6 KB with the leaf fields). Building both manifests
  and checking all 4 x 1,199 openings took 0.17 s (n = 1).

What this shows for U1: a per-tensor id tells the two pins apart and says which tensors differ,
where #68's 18 shard file hashes all differ and say nothing. What it does not show: anything about
a computation. The id would have to be bound into the statement (DESIGN.md 2.2).

## H2: the integers differ after the repository's conversion rule

`runs/h2h3-int.json`. Conversion as `weight_sums/weight_sums.py` for a matrix that reads no norm
(per-tensor e = the largest with RNE(2^e max|v|) <= 4,095; w = RNE(2^e v)). The upstream rule folds
a norm's gain only into matrices that read a norm. These do not: `down_proj` reads the MLP product,
`o_proj` the attention output, and `linear_attn.out_proj` the gated norm, whose gain #70 keeps as a
separate committed cell. So this is the rule they would get.

| tensor | elements | e stock / abl | BF16 entries differing | integers differing | fraction | max abs delta (integer units) |
|---|---|---|---|---|---|---|
| L17 mlp.down_proj | 89,128,960 | 14 / 14 | 68,605,268 | 60,499,880 | 0.679 | 152 |
| L17 linear_attn.out_proj | 31,457,280 | 12 / 12 | 24,510,291 | 15,633,364 | 0.497 | 62 |
| L19 self_attn.o_proj | 31,457,280 | 12 / 12 | 24,335,741 | 15,272,203 | 0.485 | 34 |
| L34 linear_attn.out_proj | 31,457,280 | 12 / 12 | 24,326,327 | 15,074,767 | 0.479 | 47 |
| L50 mlp.down_proj | 89,128,960 | 12 / 12 | 67,619,678 | 34,872,448 | 0.391 | 26 |
| L51 self_attn.o_proj | 31,457,280 | 11 / 11 | 23,918,695 | 10,299,940 | 0.327 | 17 |
| L16 mlp.down_proj (control) | 89,128,960 | 13 / 13 | 0 | 0 | 0 | 0 |

- Every fetched tensor's bytes matched #68's streamed hash (14 / 14), and the 7 fetches add a
  second independent read of these tensors.
- The exponent is the same for both pins on all 7: the abliteration changes the values, not the
  scale, on this sample.
- Between 33% and 68% of the integers differ. The integer delta is small against the 4,095 range
  (at most 152 units, at L17 down_proj, where e = 14 gives the finest grid). So a 13-bit integer
  model of the abliterated pin is a different committed table, not a rounding of stock's.
- Conversion rounding absorbs part of the change: 77% of BF16 entries differ, 33% to 68% of
  integers do. On these 6 tensors the abliteration survives the conversion.

## H3: an algebraic fingerprint per tensor (toy field)

The multilinear extension of each tensor's integers, at a point derived from (label, tensor name)
only, modulo 2^31 - 1. Stock and abliterated differ on 6 / 6 changed tensors and are equal on the
control (values in the run file). This is the kind of claim DESIGN.md 2.2 asks the key file to
open per tensor; the toy prime is not the protocol's field (Goldilocks and its cubic extension) and
no security figure follows from it. Time, descriptive: 74.0 s for 393,216,000 integers in one
numpy process (3.2 s to 21.1 s per tensor), about 5.3 M per second.

## Counted, from main's numbers (`runs/counted.json`, `wb_count.py`)

Counts and extrapolations, not measurements:
- weight cells the trace would read for the whole model (R2 of the design): 1,985,024 (41,184 per
  DeltaNet layer: 40,960 conv taps, 128 gains, 48 cA, 48 dt_bias; 512 q / k norm gains per
  attention layer), so 5.96 M keys and 3.98 M relations in #70's arm B layout, once per window;
- that is 0.39% of #70's 95,057,841 packed entries per token times 16 tokens, and 0.006% at
  T = 1,024 (an order-of-magnitude comparison: keys and entries are different units);
- y_t for the whole model (26.9 G integers) at the toy rate: about 84 min on one process
  (**extrapolated**);
- U2: a uniformly sampled single layer is in 17 to 51 with probability 35 / 64 = 0.547; 4 distinct
  sampled layers touch it with 0.963; 8 with 0.999 (counted).

## Deviations from the PREREG

1. **H1's unchanged-tensor clause was wrong as registered** (above). Reported as a FAIL, not
   reworded. The threshold was not changed.
2. **Amendment A1 not run.** An unregistered leaf-level count (`wb_manifest.py leaves`) was written
   after H1; the command that fixed a line in it and ran it was held by the host gateway for
   approval (20:44 UTC) and is not re-run any other way, whole or in part. The function stays in
   the code with the original line (correct, only slower than the held fix); its output is not in
   this PR. The leaf-level claim above stands on the
   construction (identical leaf bytes), which `runs/h1-manifest-demo.json`'s `n_same = 1129`
   (equal leaf inputs) states.
3. H3's per-tensor fingerprint times were taken inside the registered run, n = 1 per tensor; they
   are descriptive only, as registered.

## What is established and what is not

Established here: per-tensor ids for both pins; that the 70-tensor difference is visible per
tensor at hash level; that after the repository's conversion rule the integers of 6 sampled
changed tensors differ (33% to 68%) and the control's do not; a toy per-tensor evaluation separates
them.

Not established: any proof relation. No Qwen weight table, Qwen WF layout, key-file evaluation
claim, weight-cell tie or layer 17 to 51 statement exists. The other 64 changed tensors were not
converted (their BF16 hashes differ, #68; that their integers differ too is likely but not measured).
Norm-folded tensors (in_proj, gate / up, q / k / v) were not converted; they are unchanged by the
abliteration, so they would be equal in both pins in any case.

## Next experiment I would register

Route A of DESIGN.md section 4 on CPU where possible: extend H2 to all 70 changed tensors and all
851 text tensors with the full upstream rule (norm folding included), publish `int_sha256` and
exponents per tensor for both pins, and a recompute of y_t in the Goldilocks cubic extension at
root-derived points, with a mismatch suite (one entry changed, exponent +1, layer 16 / 17 address
swap, a quantised copy of one tensor). Threshold: every mismatch refused, every honest tensor
accepted, full-model time reported.
