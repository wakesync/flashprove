# Design note: admitting query width dq != d in cp_verify (issue #163)

Base: every file:line in this note is at main `184f89b3679f752c550be4de2818231361d8f9fb`.
Desk note. It changes no code and reports no measurement. "Unknown" marks what this note did not establish.

## Answer in three lines

1. In the six verifier files, every size that belongs to the query or attention-output side already uses `dq` (or `dkv`, or `nqk = dq + dkv`). Every use of `d` belongs to the residual stream or to a projection input or output of width d. This note found no place where `d` stands for `dq`.
2. The equality `H * dh = d` (`cp_verify.cpp:520`) is not used by any bound or theorem argument in those files. It does three things only: it bounds dq and dh through `d <= 2^20` (`cp_verify.cpp:492`), it is stated or relied on in five doc rows (rows 58-62 below; two of them, `FORMAT.md:2162` and `FORMAT.md:2183`, give it as a reason), and the prover enforces the same equality (`prover/common/parameter_file.h:376`, `prover/prover/layout.h:188`). So admitting dq != d is an admission change: drop the equality, add an explicit bound on dq, restate the five doc rows, and open the prover's gate. It is not a design change.
3. The one no-overflow condition that reads dq, the output projection's site `W-o` (`cp_verify.cpp:1483`), gives the same verdict at dq = 6,144 as at dq = 5,120 for every allowed shift k and digit form (arithmetic below). The negative outcome described in the issue was not found. Qwen's full-attention shape is still refused, by limits that do not depend on dq: dh = 256 fails `af-no-wrap-N4` (`vf_attention_shape.h:234`), and rotary is out of the standard form (`vf_common.h:706`).

## Scope and method

Files read in full or at every match of `\bd\b`, `dq`, `dkv`, `nqk`, `dh`, `ldh`, `Pd`, `lPd`, `H * dh`:
`verifier/src/cp_verify.cpp`, `verifier/src/vf_attention_shape.h`, `verifier/src/vf_attention_check.h`, `verifier/src/vf_layers_plan.inc`, `verifier/src/vf_layers_check.inc`, `verifier/src/vf_weights_layout.h`.
Also read: `verifier/docs/parameter-file.md`, `docs/format/FORMAT.md`, `docs/format/11-2-feed-forward-segment.md`, `docs/format/11-3-attention-segment.md`, `docs/format/11-5-weights-in-the-table.md`, `research/operators/qwen_ops/LIMITS-AND-ROTARY.md`, `experiments/20261112-135-dense-standard-form/RESULTS.md`, and, for the prover's side only, the matches of the same names in `prover/`.

Symbols: d residual width; H query heads; Gk (G) key/value heads; dh head dimension; dq = H dh; dkv = Gk dh; nqk = dq + dkv; S2 = 2^(la - lt); Pd = 2^ceil(log2 d). Qwen3.8-27B full attention: H = 24, Gk = 4, dh = 256, d = 5,120, so dq = 6,144, dkv = 1,024, nqk = 7,168 (`LIMITS-AND-ROTARY.md:7`).

Classes used in the table:
- **OK**: correct for dq != d as written.
- **CHANGE**: must change from d to dq (or dkv). None was found.
- **NEW**: needs a new condition, or a restated argument, once the equality is gone.
- **DEP**: refused or unmet for Qwen for a reason other than dq (stated as a dependency, not designed here).

## 1. Every use, classified

### 1a. Where dq, dkv and nqk are derived

| # | file:line | what it says | class | the statement it protects |
|---|---|---|---|---|
| 1 | cp_verify.cpp:355-358 | the statement's words d, H, Gk, dh are read separately (`parseHeader`) | OK | d, H, Gk and dh are four words of the statement, so dq = H dh is fixed by the statement independently of d |
| 2 | cp_verify.cpp:492 | `d > (1u << 20)` rejects (`shape-words`) | OK for d; see row 4 | bounds every d-sized vector |
| 3 | cp_verify.cpp:505-506 | `Pd = 2^clog2(d)`, `lPd` | OK | Pd pads d only; used only for the stream and norm rows (rows 32-33) |
| 4 | cp_verify.cpp:520-521 | `shape-heads`: H, Gk, dh nonzero, dh a power of two at least 2, **H dh = d**, H + Gk <= 64 | NEW | the equality is the only thing in the verifier that bounds dq and dh from above (through row 2). Without it, dq = H dh can reach 63 * 2^31, about 2^37 (H < 64, dh a power of two in a 32-bit word). See section 2, need N1 |
| 5 | cp_verify.cpp:522-524 | `y.dq = H dh`, `y.dkv = Gk dh`, `y.nqk = dq + dkv` | OK | derived from H and dh, never from d |
| 6 | cp_verify.cpp:525 | `ldh = clog2(dh)` | OK | |
| 7 | cp_verify.cpp:526 | `dkv % S2 || nqk % S2` rejects (`shape-la`) | OK | S2 divides nqk and dkv, so S2 divides dq = nqk - dkv without the equality. Today's doc reasons via "H dh = d" instead (row 60) |
| 8 | vf_attention_shape.h:192-196 | the attention fork derives `dq = H dh`, `dkv = G dh` from its own `ACfg` (H, lgk, ldh) | OK | the fork never sees d at all: `ACfg` has no d field (`vf_attention_shape.h:78-91`) |
| 9 | cp_verify.cpp:1947-1949 | the layer side passes `c.H = h.H`, `c.ldh = ldh` to the fork | OK | |
| 10 | cp_verify.cpp:1999-2000 | `X.A.dq != y.dq || X.A.dkv != y.dkv || ... || X.A.dh % y.S2` rejects (`plan-tensor-layout`) | OK | owner (layer sub-proof) and reader (attention sub-proof) agree on dq, dkv; S2 divides dh |
| 11 | cp_verify.cpp:2002-2004 | `atQ.J != H dh || atO.J != atQ.J || atK.J != G dh || atV.J != atK.J` rejects | OK | q and o have H heads of dh, kx and v have G heads of dh: written against H dh, not d |

### 1b. The tensors of qa and the weight kinds (layout)

| # | file:line | what it says | class | the statement it protects |
|---|---|---|---|---|
| 12 | cp_verify.cpp:579-580 | `qkw`, `rqk`: J = nqk | OK | the q and k projections' outputs, then digits |
| 13 | cp_verify.cpp:581-582 | `vw`, `rv`: J = dkv | OK | |
| 14 | cp_verify.cpp:572-578 | `xs`, `ro`, `rd`, `aw`, `ra`, `mw`, `rm`: J = d | OK | stream values and the o and down projections' outputs, which are d wide; `ro` is the remainder of the o projection's output, d wide |
| 15 | cp_verify.cpp:584-587 | `a`, `m`, `xr`: J = d | OK | normed stream (the q/k/v projections' input), width d |
| 16 | cp_verify.cpp:599-602 | qa: `q` J = dq, `kx` J = dkv, `v` J = dkv, `o` J = dq | OK | q and o are two separate tensors, each dq wide. Nothing packs q and o into one segment of width d |
| 17 | cp_verify.cpp:622-625 | stream xb: J = d, `tensorsFill(..., NLx d, S2, "stream")` | OK | |
| 18 | cp_verify.cpp:626-629 | `tensorsFill(qa, feat[3], S2, "qa")` | OK | tests at run time that every qa tensor's J is a multiple of S2 (`cp_verify.cpp:113`) and that q, kx, v, o tile qa exactly |
| 19 | vf_attention_shape.h:349-359 | ao: `oRhp = Lam dq`, `featO = 2 Lam dq`; qa: `oK = 2 Lam dq`, `oV = oK + 2 Lam dkv`, `oO = oV + 2 Lam dkv`, `featQ = oO + 2 Lam dq`; `atQ/atO` J = dq, `atK/atV` J = dkv | OK | same layout as rows 16-18 on the reader's side; row 10 and `tensorsAgree` (`cp_verify.cpp:1995-1998`) compare them |
| 20 | vf_layers_check.inc:224-226 | `AH[hd]` for hd < H + Gk: `headFeat(tq, hd, dh)` on q (J = dq), then `tq.J + headFeat(tk, ...)` on kx | OK | head hd's columns in QK; `headFeat` rejects unless dh divides J and hd < J / dh (`vf_attention_shape.h:72-74`), i.e. hd < H on q |
| 21 | cp_verify.cpp:752 | weight kind 0 `qk`: L = 64, segs `2 Lam d dh` | OK | the q/k projection's input is the normed stream, width d. Per `cp_verify.cpp:448-449` "Only idx is read" |
| 22 | cp_verify.cpp:753 | kind 1 `v`: L = dkv, segs `2 Lam d` | OK | input d, output dkv |
| 23 | cp_verify.cpp:754 | kind 2 `o`: L = d, segs `2 Lam dq` | OK | input dq, output d |
| 24 | cp_verify.cpp:1573-1578 | `WsShape` gets d, dh, dkv, dq separately | OK | |
| 25 | vf_weights_layout.h:146-147 | d, dh, dkv, dq, f each in 1..2^24 else `shape-words` | OK, and see row 61 | a live bound on dq at layout time; today it cannot fail (`FORMAT.md:2183`) |
| 26 | vf_weights_layout.h:164 | unit 0: groups `hd` (64, class A), `cd` (dh, class A), `kk` (d, class E) | OK | queries and keys as 64 head slots of dh by input d. Needs H + Gk <= 64 (row 4 keeps it; Qwen 24 + 4 = 28) |
| 27 | vf_weights_layout.h:165 | unit 1: `kk` d, `x` dkv | OK | |
| 28 | vf_weights_layout.h:166 | unit 2: `kk` dq (class E, low), `x` d (class E, high) | OK | class E splits R = o 2^z with o odd (`vf_weights_layout.h:83-96`). dq = 6,144 = 3 * 2^11 and 5,120 = 5 * 2^10 are both of that kind; `weights_twin_test` already builds unit 2 with dq != d (row T1 below) |

### 1c. The layer sub-proof (lookup segments, sites, panels, claims)

| # | file:line | what it says | class | the statement it protects |
|---|---|---|---|---|
| 29 | cp_verify.cpp:662-663, 691 | segments QK, QKH, CQK: n = nqk | OK | the q and k projections' rounding and clamp, one key per output feature |
| 30 | cp_verify.cpp:664-669, 679-680, 689-690 | N1, N1H, N2, N2H, **O**, D, OH, DH, CN1, CN2: n = d | OK | O and OH are the o projection's rounding: its quotient is the stream difference `str(2 lam + 1) - str(2 lam)` (`vf_layers_check.inc:450`), d keys per token. Its accumulator sums over dq (rows 37 and 45), but its keys are per output feature, d |
| 31 | cp_verify.cpp:670, 681, 692 | V, VH, CV: n = dkv | OK | |
| 32 | vf_layers_check.inc:96-114 | norm product layer over `NI` instances of `Pd` features, scale 2^-lPd | OK | norms of the stream, width d |
| 33 | vf_layers_check.inc:1002-1010, 1153-1158 | the norm claim and the embedding claim sum over `d / S2` blocks of xb, `e[(i Pd) / S2 + kh]` | OK | stream only |
| 34 | vf_layers_check.inc:432-442 | LINE of QK/QKH: two halves `[0, dq)` with shift kq and `[dq, nqk)` with shift kk | OK | queries and keys rounded at their own shifts; the split point is dq, not d |
| 35 | vf_layers_check.inc:472-474 | LINE of CQK: `SBA(wh, 0, dq, "q", ...) + SBA(wh, dq, nqk, "kx", ..., dq)` | OK | clamp of q and of kx, keyed at the split dq |
| 36 | vf_layers_check.inc:450 | LINE of O: `SxsA(wh, Z, 2 lam + 1) - SxsA(wh, Z, 2 lam)` over d / S2 blocks | OK | see row 30 |
| 37 | vf_layers_check.inc:653-667 | panels: G, U, V take A = `a` or `m` with ny = d; **O takes A = `o` with ny = dq** | OK | the o projection's sum over k2 < dq of Wo(k2, j) o(k2, t) (`11-2-feed-forward-segment.md:345-347`) |
| 38 | vf_layers_check.inc:695-698 | token-sumcheck panel QK: A = `a`, ny = d | OK | the q/k projection's input is `a`, width d |
| 39 | vf_layers_check.inc:886 | weight claim of O: `wy = clog2(dq)` for group `kk` | OK | must match row 37's panel width `b.wy = clog2(ny)` (`vf_layers_check.inc:606`) |
| 40 | vf_layers_check.inc:917 | weight claim of QK: group `kk` = `facRs(G, 0, clog2(d))` | OK | matches row 38 |
| 41 | vf_layers_plan.inc:67-68 | lamS: `4 * 2^(wi + clog2 d) + 2^(wi + clog2 dq) + 2^(wi + clog2 f) + 2 * 2^wi` | OK | the batched sumcheck's size; the dq term is the O panel (row 37). It must equal the panels' placement, tested at `vf_layers_check.inc:745` (`internal-stack`) |
| 42 | vf_layers_plan.inc:99 | `LayerRounds.lPd = lPd` | OK | norm rounds |
| 43 | cp_verify.cpp:1445 | `acc = d BC BWw` | OK | accumulator bound for sites whose sum is over the normed input (gate, up, qk, v): width d |
| 44 | cp_verify.cpp:1482 | site `qk`: `A = 2 * 2^cs * acc` | OK | input width d, times the rotary factor 2^cs |
| 45 | cp_verify.cpp:1483 | site `o`: `A = dq BC BWw`, span `2^(lsg + 2)`, quotient `2^(lsg + 1)` | OK; margin checked in section 2 | the o projection's sum is over dq products of a clamped-scale value and a weight |
| 46 | cp_verify.cpp:1524 | `no-wrap-ledger`: `residualStreamLimbs d Ty^2 < 2^53` | OK | convolution sums of the stream, width d |
| 47 | cp_verify.cpp:1600-1611 | rotary table over `dh / 2` pairs | DEP | independent of dq; rotary width is a separate #35 limit |

### 1d. The attention sub-proof

| # | file:line | what it says | class | the statement it protects |
|---|---|---|---|---|
| 48 | vf_attention_shape.h:173-175, 200 | segment widths WL, WH include `ldh`; `ls <= ldh` | OK | per head, never per d |
| 49 | vf_attention_shape.h:214 | `Smax = dh CLAMP^2` | DEP | the score bound is per head (dh), not dq. See section 4 |
| 50 | vf_attention_shape.h:230-237 | `af-no-wrap-N1`, `N3`, `N4` read Smax | DEP | dh = 256 fails N4 (section 4) |
| 51 | vf_attention_shape.h:298, 345-347 | pieces per (segment, lam, a < HA); `ah` offsets `4 Lam H`, `8 Lam H`, `Lam lt H` | OK | per head; H only |
| 52 | vf_attention_check.h:39 | `forest-depth-A`: `dT >= max(lmS, lt + ldh)` | OK | per head |
| 53 | vf_attention_check.h:289-291 | `run()` reads `dq` from the fork | OK | |
| 54 | vf_attention_check.h:622-648 | `lng()` and the qa/ao tables: `cutLast(zc, ldh, ls)` within one head | OK | |
| 55 | vf_attention_check.h:702-713 | `XL()`: `headFeat(X, hd, dh)` on a TenAt whose J is dq (q, o) or dkv (kx, v) | OK | |
| 56 | vf_attention_check.h:798-807 | `rh`, `rhp` read as `TenAt{oRh or oRhp, 1, Lam, dq}` | OK | per (head, channel) of the output, dq of them |
| 57 | vf_attention_check.h:850, 912 | `XL(qO, A.atO, ...)`, `XL(qF, A.atQ, ...)` | OK | |

### 1e. Docs and the prover (where the equality is stated or relied on)

| # | file:line | what it says | class |
|---|---|---|---|
| 58 | verifier/docs/parameter-file.md:106 | "H * dh = d" in the user contract | NEW (restate) |
| 59 | docs/format/FORMAT.md:2152 | row `shape-heads`: "H dh = d" | NEW (restate) |
| 60 | docs/format/FORMAT.md:2162 | `plan-tensor-layout-fill-<arr>` "cannot fail ... H dh = d by shape-heads" | NEW (restate: S2 divides dq because it divides nqk and dkv, row 7) |
| 61 | docs/format/FORMAT.md:2183 | `shape-words` "none of these can fail ... H dh ... from 1 to 2^24" | NEW (restate, once need N1 exists) |
| 62 | docs/format/11-2-feed-forward-segment.md:294, 1035 | "dq = H dh, which must equal d"; row `shape-heads` | NEW (restate) |
| 63 | prover/common/parameter_file.h:376 | prover's own `shape-heads` with `H * dh == d` | NEW (prover gate; out of this note's code scope, but an honest dq != d proof needs it opened) |
| 64 | prover/prover/layout.h:188 | `L.dq != s.d` rejects in `make_layer_layout` | NEW (prover gate, same) |
| 65 | verifier/tests/parameter_walk.py:33, 218 | the random walk sets `d = H * dh` | NEW (test harness keeps every walked file at dq = d; the walk never explores dq != d) |
| 66 | integrations/vllm/integer_model/tests/chosen_model.py:227-231 | `d = H * dh` in the integer model's chosen shapes | OK for now (documents today's rule; Unknown whether the integer model itself assumes dq = d elsewhere) |

### 1f. Residual-width uses and derived sizes (completeness)

Rows 1-66 cover every use that touches the query side or the equality. The rows below cover the remaining reads of `d` (and of sizes derived from it) in the six files, plus two prover comments, so that the inventory is exhaustive for these files. Related uses are grouped by range.

| # | file:line | what it says | class | the statement it protects |
|---|---|---|---|---|
| 67 | cp_verify.cpp:514 | `d % S2 || f % S2 || (p3 && fe % S2)` rejects (`shape-la`) | OK | S2 divides the stream's tensors (J = d, row 14) and the feed-forward ones; residual and hidden widths, never dq |
| 68 | cp_verify.cpp:672 | MoE segment XR: n = d | OK | the router's rounding over its input, the normed stream `m` (width d); `XR`'s LINE is row 76 |
| 69 | cp_verify.cpp:758-770 | weight kinds 3-11: g, u, gs, us, gr, ur, r have segs `2 nd d` (input d); dn and dnr have L = d (output d) | OK | every dense and MoE projection reads or writes the residual stream, width d; none reads attention's output |
| 70 | cp_verify.cpp:1686-1727 | output head: offsets `oRa = 2 d`, `oD1 = 4 d`, `oD2`, `oE`, `feat = 4 d + ...`, `fillD = 2 d`; segments NF, NFH, CNF with n = d | OK | the final norm and the head read the residual stream, width d |
| 71 | cp_verify.cpp:1869 | `SH = 2 d BCh BW + 1`, used by `W-HD0` and `three-digits` (`cp_verify.cpp:1871`, `:1874`) | OK | a logit is a sum over the normed stream, d products of a clamped cell and a weight; dq does not enter the head |
| 72 | cp_verify.cpp:2092 | `muV = lNI + lPd + lt` (with `muH`, `muH2` from f, fe), `shape-product-layer` | OK | rounds of the norm product layer, over Pd (row 3) |
| 73 | cp_verify.cpp:2177 | `muVH = lPd + lt`, `shape-product-layer-H` | OK | the head's norm product layer, over Pd |
| 74 | vf_layers_plan.inc:71-72 | lamS's MoE terms: `2^(wm + clog2 d)`, `2^(le + clog2 d)`, `2^(le + clog2 fe)` | OK | the router and routed experts' panels, input d (rows 77-78); the dq term is row 41 |
| 75 | vf_layers_check.inc:469 | LINE of CN1/CN2: sum over x < d of `a` or `m` | OK | the clamp of the normed stream, width d |
| 76 | vf_layers_check.inc:486 | LINE of XR: sum over x < d of `xr` | OK | MoE router input, width d |
| 77 | vf_layers_check.inc:677 | panel LR: A = `m`, ny = d | OK | router's product over the normed stream |
| 78 | vf_layers_check.inc:707, 729-730 | token panels: XR sums `m` over x < d; routed G/U `tri(claim, d, ...)` over `xr` | OK | MoE inputs, width d |
| 79 | vf_layers_check.inc:923 | MoE weight claim `wk = clog2(d)` for G/U (fe for D) | OK | matches rows 77-78's panel widths, as row 39 matches row 37 |
| 80 | vf_layers_check.inc:953-954 | embedding claim: point over `lPd - G.z` bits | OK | the embedding writes the stream, width d (padded to Pd) |
| 81 | vf_weights_layout.h:168-184 | units 3-13: `kk` or `x` of width d for g, u, dn, gs, us, gr, ur, dnr, r, embedding (12) and head (13) | OK | same sides as row 69; unit 2 (row 28) is the only unit with a dq group |
| 82 | prover/common/parameter_file.h:378 | comment on the prover's `shape-la`: "and so (H + G) dh = d + G dh" | NEW (restate comment) | states the equality. The rule itself (`G dh` divisible by S2) does not rely on it; the comment's conclusion that S2 divides `(H + G) dh` then needs the verifier's own `nqk % S2` test (row 7), which the prover has no copy of. See N5 |
| 83 | prover/common/parameter_file.h:469-475 | comment above `prover-only-f`: `prover_gemm()` adds products of signed bytes (at most 2^14 each) into 32-bit words, so a word holds 131,071 of them; "A word gets at most 2 d of them ... d = H dh is at most 63 * 128 by the rules on H, G and dh" | NEW (restate argument) | the int32 no-overflow argument of the prover's forward pass. Once the equality goes, the o projection (`gemm3(b.mT, d, dq)`, `prover/prover/forward.cuh:1551`) sums over dq, not d. See N5 |
| 84 | prover/common/parameter_file.h:481-482 | "by the other rules d, G dh and (H + G) dh have at most six one-bits" | OK | does not use the equality: d's odd part is at most 32 (`:467`), G is a power of two, H + G <= 64 |
| 85 | vf_attention_shape.h:157, 226, 327; vf_lookup_argument.h:66 and its uses | local `ShD d` (a shift's digit table) and `h.d()` (a forest's depth) | n/a | unrelated variables also named d; listed so that a grep for `\bd\b` is fully accounted for |

The prover side was only grepped, not audited. Its weight code already sizes the o projection's input from `H * dh` (`prover/weights_blocks/block_weights.cuh:69`, `prover/weights_commitment/fold_source.cuh:35`, `prover/weights_commitment/kernels.cuh:113,123` via `S.dq`), so it looks dq-aware behind the two gates. That is not established here.

## 2. What each NEW row needs

**N1: an explicit bound on dq (rows 4, 25, 61).** Today `H dh = d <= 2^20` bounds dq <= 2^20, dh <= 2^20 (so `ldh <= 20`), and the qa sizes `4 Lam (dq + dkv)`. Without the equality, H < 64 and dh up to 2^31 give dq up to about 2^37 before `WsLay::build` sees it (row 25 runs at `cp_verify.cpp:1588`, after `layout()` has already sized qa and the request matrices from `y.feat[3]`, `cp_verify.cpp:603-613`). The new condition: in `layout()`, right where the equality was, reject unless `dq <= 2^20` (same bound as d, `cp_verify.cpp:492`). With H >= 1 this restores `dh <= 2^20` as well, so every shift by `ldh` and every vector sized by dh or dq keeps the bound it had. The name can stay `shape-heads` (its meaning changes) or be a new `shape-dq`; the build lane should pick one and say so in FORMAT.md's table. Soundness need: none beyond sizing; it is a resource and shift-count guard. Existing test that would catch a mistake here: `ws_build_fuzz` (`SUITE.md:237`) exercises `WsLay::build` with independent random dq, but not `layout()`. For `layout()`: none.

**N2: the `W-o` no-overflow margin at dq > d (row 45).** The site's bound is `A = dq BC BWw` with BC = 2^11 (`vf_attention_shape.h:387`, CLAMP + 1 = 2048) and BWw = 2^12 (`vf_widths_and_bounds.h:33`). At d = 5,120, A = 2^35.32; at dq = 6,144, A = 2^35.58. The conditions (`cp_verify.cpp:1456-1465`) are `U-o`: `SP << max(k, 16) <= 2^60` with SP = 2^(lsg + 2), and `W-o`: `((A + 2^(k-1) + (Qb << k)) << t) + form term < 2^60` with Qb = 2^(lsg + 1), t = 16 - k for k < 16 (else 0), and form term 0, `2^16 (Ty + 128)` or `2^16 (Ty2 + 32896)` for forms 0, 1, 2, where Ty = 2^18 (`cp_verify.cpp:1531-1532`) and Ty2 = 257 Ty (`cp_verify.cpp:1445`). Domain: every k the KL file allows (1..16, 1..24, 1..32 for forms 0, 1, 2, `cp_verify.cpp:1396`) and both lsg (30 with four limbs, 39 with five, `cp_verify.cpp:1455`): 72 (lsg, form, k) triples, each evaluated at dq = 5,120 and at dq = 6,144 (144 evaluations per condition).

Result: **no (lsg, form, k) changes verdict between dq = 5,120 and dq = 6,144**, for `W-o` or `U-o` (`U-o` does not read A). The k that pass both conditions, identical at both widths:
- lsg = 30: k = 1..16 (form 0), 1..24 (form 1), 1..28 (form 2);
- lsg = 39: k = 1..16 (form 0), 1..19 (form 1), 1..19 (form 2).
Above these ranges `U-o` fails at either width (`2^(lsg + 2 + k) > 2^60`), and so does `W-o` at the first k above (its left side reaches 2^60).

k = 1 is not the worst case over all forms. The dq-dependent term is `A << t`: it is largest at k = 1 (2^50.59 at dq = 6,144, 2^50.32 at 5,120) and falls to A itself (2^35.58) from k = 16 on. The whole left side is dominated by `(Qb << k) << t` for most k, and by the form term at lsg = 39. At dq = 6,144:
- lsg = 30, k = 1: 2^50.70 in every form. The largest accepted left side is 2^55.00 in form 1 (k = 24) and 2^59.00 in form 2 (k = 28);
- lsg = 39, k = 1: about 2^56.03 in every form (2^56.0334, 2^56.0334, 2^56.0335). The largest accepted left side is 2^59.00 in forms 1 and 2 (k = 19).
So the tightest accepted cases sit about one bit below 2^60, and there the dq term is about 2^35.6, some 2^23 below the other terms: moving dq from 5,120 to 6,144 shifts the left side by far less than the gap to the next verdict. That is why no verdict flips; the margin is not a uniform 2^9.

These are exact integer computations on the constants above, recomputed independently by this fix lane's desk script `fix166_arith.py` (not committed; a direct transcription of `cp_verify.cpp:1456-1466` and `:1483` with the constants cited here, so each number can be reproduced from this paragraph). So the margin does not disappear at dq = 1.2 d. In general `W-o` at k = 1 needs `dq BC BWw << 15` to stay below 2^60 minus the other terms: the largest dq passing `W-o` at k = 1, form 2, is 4,193,775 (2^22.00) at lsg = 30 and 3,932,143 (2^21.91) at lsg = 39. N1's 2^20 keeps it, and N4 (section 4) keeps dq <= 8,064 in any file that completes planning. Existing test that would catch a wrong A here: none that varies dq (every kit has dq = d).

**N3: the S2 divisibility argument (rows 7, 18, 60).** The doc proves `plan-tensor-layout-fill-qa` cannot fail by "H dh = d by shape-heads". Restated: S2 divides nqk and dkv (`cp_verify.cpp:526`), hence dq. The run-time test `tensorsFill` (`cp_verify.cpp:108-127`) still checks it, so a wrong argument would show as a rejection, not as a weakened statement. Soundness need: none new.

**N4: the statement binds dq (rows 1, 10).** dq is a function of the statement words H and dh, which are words 7 and 9 of the statement, counting from 0 (`cp_verify.cpp:356-358`, value-line order at `cp_verify.cpp:950-951`), and the whole statement except y is the first chain's first query (`cp_verify.cpp:2441-2445`). So a proof made under (d, H, dh) with H dh = d and checked under (d, H', dh') with H' dh' != d meets a different first query. Soundness need: the existing Fiat-Shamir binding of the statement; nothing new. Test that would catch a mistake: none today exercises two statements that differ only in H or dh (T3 below).

**N5: the prover gates and the prover's stated arguments (rows 63, 64, 82, 83).** Out of the verifier's scope, but no honest dq != d proof can be produced until both gates are opened. When the build lane opens them it must also:
- restate the int32 no-overflow comment at `prover/common/parameter_file.h:469-475` (row 83). Its conclusion still holds, for other reasons: `no-wrap-H-three-digits` (`:413-415`) keeps d <= 8,191 (7,936 at sh 7), and `prover-only-attention` (dh in {32, 64, 128}, `:490`) with H + G <= 64 (`:376`) keeps dq = H dh <= 63 * 128 = 8,064 (7,680 once `H <= 16 G`, `:500`, also applies). So a word gets at most 2 max(d, dq) <= 16,382 products, below 131,071. Recomputed by script (`fix166_arith.py`, a desk script of this fix lane, not committed: it enumerates H, G, dh under the quoted rules and evaluates the `no-wrap-H-three-digits` inequality for every d). The build lane should either write this two-bound argument into the comment or add an explicit rule `2 max(d, dq) <= 131,071`;
- restate the `:378` comment (row 82): S2 divides `(H + G) dh` because it divides `G dh` and must divide `H dh`, which the prover then needs as its own test (today it follows from `d % S2`, `:370`, and the equality);
- note that the note's grep terms (`H * dh`) did not match `:473`, which writes "d = H dh" without an asterisk; the build lane should grep the prover for `d = H dh`, `H dh = d` and `dq != s.d` too.
Unknown whether the prover has other places that assume dq = d; it was grepped, not read.

**N6: the walk harness (row 65).** `parameter_walk.py` must be allowed to change H or dh without resetting d, or the walk will keep testing only dq = d files.

No CHANGE row (d where dq is meant) was found. In particular: the o projection's panel is sized dq (row 37), its weight claim is clog2(dq) (row 39), lamS has a dq term (row 41), unit 2's input group is dq (row 28), and the O lookup segment is d because its keys are output features (row 30).

## 3. Tests a build lane must add

CPU-only unless marked. "Planning call" means `cp_verify` on a parameter file with no proof (as `verifier/tests/example_kits_test.py` does).

- **T1, layout twin at dq != d (exists).** `verifier.weights_twin_test` (`SUITE.md:174`) already has shapes with dq != d ("dense layers, sizes with odd parts": d = 24, dq = 16, dkv = 8; `verifier/tests/weights_twin_test.cpp:103`). Keep it; add one shape with dq > d and odd part 3 (for example d = 8, dh = 4, dq = 12).
- **T2, honest planning call at a small dq != d shape.** A parameter file with H = 3, Gk = 1, dh = 4, d = 8 (dq = 12, dkv = 4, nqk = 16; Gk must be a power of two dividing H, so Gk = 1), S2 dividing 4. Expected: planned, no `shape-heads`. Then the same with dq < d (H = 1, dh = 4, d = 8). CPU.
- **T3, statement swap (hostile).** Take an existing proof fixture with dq = d and change only H and dh in its parameter file so that H' dh' != d (and H' + Gk <= 64, Gk divides H'). Expected: NO. And the reverse once an honest dq != d proof exists. CPU if a committed proof fixture exists; Unknown whether one does in a form this can reuse.
- **T4, mis-sized o (hostile).** A proof whose qa `o` tensor or whose O panel is sized d instead of dq. The verifier sizes both from the statement, so the test is: build a dq != d proof with a prover patched to size `o` by d, and expect `plan-tensor-layout`, `internal-stack` or a NO. **Needs GPU** (cp_prove needs sm_90a, `prover/build.sh:14`).
- **T5, weight layout overlap (hostile).** Feed `WsLay::build` a shape where dq != d and check unit 2's rows do not overlap unit 3's (`ws_build_fuzz` checks bounds, not overlap). CPU.
- **T6, honest end-to-end at dq != d.** cp_commit + cp_prove + cp_verify at the T2 shape: YES. **Needs GPU** and the prover gates opened (N5).
- **T7, bound N1.** Planning calls at dq = 2^20 (accepted, if every other line allows) and dq = 2^20 + dh (rejected under the chosen name). CPU.
- **T8, unchanged.** Every existing Maverick and dense test, and `example_kits_test`, `ws_build_fuzz`, `weights_twin_test`, with identical expected outputs. The unmodified verifier at this note's base passes the two run here (section 6).

## 4. Dependencies (not designed here)

- **dh = 256 and `af-no-wrap-N4`.** `Smax = dh * 2047^2` (`vf_attention_shape.h:214`). N4 needs `6 Smax + 2C + 3 * 65536 < 2^32` (`vf_attention_shape.h:234`). At dh = 128, 6 Smax = 3,218,080,512 < 2^32 = 4,294,967,296. At dh = 256, 6 Smax = 6,436,161,024 > 2^32: **refused by N4 alone, whatever dq is.** So Qwen's full attention stays refused after this change, by the dh limit. This is a property of the per-head score bound, not of dq.
- **dh = 256 and rotary.** `rotaryServed` needs dh <= 128 and theta0 in {10,000, 500,000} (`vf_common.h:705-706`); Qwen has dh = 256, theta0 = 10,000,000 and rotary width 64 (`LIMITS-AND-ROTARY.md:8`). Without it the run is not the standard form (`cp_verify.cpp:2414`). Partial rotary changes `kap` (`vf_layers_check.inc:898-909`) and the rotary table (`cp_verify.cpp:1600-1611`), both per head; neither reads dq.
- **Order.** Admitting dq != d does not make Qwen admissible on its own. It is independent of the dh limit (no row above reads dh through d), so it can land before or after it. The issue's concern that it must come first is not supported by this audit.
- q/k RMSNorm, the sigmoid output gate, the hybrid schedule and the segment cap: not read; they may add new uses of dq (a gate on o would be dq wide). Unknown.

## 5. Count estimate and stop rule for the build lane

Estimate (counted from the rows above, not built):
- Verifier code: `cp_verify.cpp:520` (drop `H dh != d`, add `dq > 2^20`), about 3 lines. No other verifier code row needs a change.
- Docs: 5 rows (58-62), about 10 lines.
- Prover gates: 2 places (63, 64), about 4 lines, plus the two comments of rows 82-83 (or one new rule). Required for T4 and T6 only.
- Tests: T1 (one shape line), T2 and T7 (one small Python test, about 80-150 lines, modelled on `example_kits_test.py`), T5 (about 40 lines in `ws_build_fuzz.cpp` or a new test), N6 (`parameter_walk.py`, about 5 lines). T3 depends on a fixture (Unknown). T4 and T6 need a GPU slot.
- Time: the CPU part (code, docs, T1, T2, T5, T7, T8) fits one 2.5 h lane. T4 and T6 are a second, GPU lane.

Stop rule for the build lane: stop and report, without pushing a widened admission, if any of these holds:
1. any existing test (T8) changes its expected output;
2. the honest planning call T2 is refused under any name, or plans with a different number of message slots from what the plan predicts (`internal-slot-count`, `internal-stack`, `internal-claim-count`);
3. a place outside the rows of section 1 has to change to make T2 plan (the audit missed a use: go back to the note);
4. any `no-wrap-*` verdict changes for an existing configuration;
5. 2.5 h elapsed.

## 6. What was run

Desk only, no weights, no GPU. On cores 10-15, at this note's base:
- `verifier/build.sh` (unmodified): built, `build=64abf54f904779731c64f1460d5daa450926f0aec0a0e7110f5a11d65622ac5c`.
- `verifier.weights_twin_test` (`SUITE.md:174` command): `weights_twin_test: ok (36 worlds, 588 units, 680940 cells, 4360560 places without a cell; 4152 checks)`, matching `SUITE.md`'s expected line.
- `verifier/tests/example_kits_test.py <cp_verify> <work> 2`: "7 parameter files (1 bare, 5 work, 1 yes), 12 plays with a line changed; 0 not as expected".
No other test was run; the full suite was not run.

## What this note does not establish

- That the prover handles dq != d anywhere beyond its two gates (only grepped).
- That an honest dq != d proof verifies: no such proof exists; T6 needs a GPU.
- That the six files are the only verifier places reading these sizes: the grep covered `verifier/src/*`, and only these six were read line by line (plus the matched lines elsewhere).
- Anything about dh = 256, partial rotary, q/k norm, the output gate, the hybrid schedule or the segment cap beyond the two dependencies stated.
