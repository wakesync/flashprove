# Design note: head dimension 256 and partial rotary (issue #175)

Base: every source citation is at main `59bff9a4608e0cc720d58d7c30823a8838fa43e4`.
Desk design only, not an experiment, implementation or soundness theorem. No code, verifier, parameter file, proof or results-ledger change. NEW below is a design obligation, not an assertion that the change is implemented or sufficient for a Qwen proof.

## Answer in three lines

1. **N4: prefer a separately versioned wider score-key layout, with flag at bit 33 and exponential weight at bit 34, retaining the 2,047 clamp.** The arithmetic fits the existing conservative field budget, but the standard-softmax table also needs `kFD = 17`; the shared forest independently caps it at 16. This is a new-layout design dependency, not permission to raise two constants and start an admission build.
2. **Rotary: choose a new `rp = 2` mode, fixed to R = 64 within dh = 256, rotate-half pairs `(j,j+32)`, theta0 = 10,000,000, cs = 12, T <= 1,024, using the pinned Q256 integer generator already on main.** Keep the existing `rp = 0/1` function, table bytes and digest construction unchanged.
3. **No build green light from this note.** A q/k-only clamp of 1,665 is the smaller arithmetic alternative, conditional on its own fidelity decision; two bounded 128-wide partial sums do not fix the final score's N4. Neither option proves Qwen admission, acceptable fidelity or an abliterated reply under proof.

## Scope, notation and evidence boundary

Inventory: `verifier/src/cp_verify.cpp`, `vf_attention_shape.h`, `vf_attention_check.h`, `vf_common.h`, `vf_layers_check.inc`, and `verifier/docs/parameter-file.md`. Matches of `dh`, `ldh`, `Smax`, `CLAMP`, `CLAMPED_CELL_BOUND`, `trope`, `hRope`, `rp`/`klRp`, `ropeC`, `cs`, `theta0` and `kap`, plus their immediate consumers, are grouped below. Source filenames without a directory mean `verifier/src/`; `parameter-file.md` means `verifier/docs/`. An additional shared-forest blocker is explicitly outside that six-file inventory, not hidden in an OK row.

**OK**: the expression remains correct for the proposed dimensions; still subject to its existing guards and tests. **NEW**: needs a new definition, profile-specific branch or argument. **DEP**: another work item must supply the prerequisite. An OK dimension formula is not evidence that a complete file plans.

Use `b` for the absolute q/k clamp, `b_v` for the value clamp, `Smax = dh b^2`, `Ty = 2^18`, `Ty2 = 257 Ty`, `Ty4 = 16,843,009 Ty`, `TS = T 2^S`. Let `Pbudget = 2^61 - 1` and `P2 = 2^60`. The local variable named `p` in `vf_attention_shape.h:218` is this conservative budget, **not** the actual field modulus. The field is unchanged (field 2 in `parameter-file.md:71`). Let `C = u0 2^sh`, `rho = 65,536 - 2^sh`, `nHD = ceil((4 Smax + 1)/rho)`, and `Om = 2 Smax + C` (`vf_attention_shape.h:156-162`). `C` here is not the clipped-gap policy's limit. Likewise `parameter-file.md:33` distinguishes theta (the acceptance policy) from theta0 (the rotary base); that terminology is **OK** and unchanged.

Prior design inputs on main: `DQ-NE-D.md` (separate query-width admission), `LIMITS-AND-ROTARY.md` (separate rotary width and pairing), `rotary/README.md` and `rotary_tables.py` (standalone deterministic table/gadget), `docs/model.md` section 4 and `scales/tests/table_ties.py` (legacy floating-point definition). Their integration limitations remain in force. No unmerged lane's measurement is evidence for this note. Which clamp or scale rule is accurate enough is an open input, not decided here.

## 1. Every use, classified

### 1a. Header, layout, configuration and clamp plumbing

| # | Source | Use | Class and obligation |
|---|---|---|---|
| 1 | `cp_verify.cpp:217-220,246,358,364-365,396-397` | stores/reads dh, cs, theta0; points at the rotary and KL digests in the statement | **OK** for existing words. **NEW** profile/rotary-mode binding must not reinterpret an old statement |
| 2 | `cp_verify.cpp:459,520-527` | dh power-of-two and >=2, H dh = d, H+Gk <=64; derives dq, dkv, ldh; cs must be12 | **DEP** equality/query-width bound is DQ-NE-D's issue. **OK** ldh=8 for dh = 256 and cs = 12; no substitution of R for dh here |
| 3 | `cp_verify.cpp:599-602,626-629,752` | qa q/o widths dq and kx/v widths dkv; fill check; qk weight kind has per-head dh output features | **OK** full head stays256, even though only 64 coordinates rotate |
| 4 | `cp_verify.cpp:631-636` | one shared FC table clamps to +/-CLAMP, encodes output with offset CLAMP+1 at radix 2^28 | **OK** for wide layout, **NEW** for narrower q/k: separate table for CQK, not a global CLAMP edit |
| 5 | `cp_verify.cpp:662-663,689-692,702-713` | QK/QKH and CQK/CV segments; default FC call includes norm, q/k and v clamps | **NEW** only for narrow arm: routing CQK to a new clamp table must still cover every segment once; norm/v stay legacy |
| 6 | `cp_verify.cpp:843-849,951-952,1103-1120,1193-1196,1306-1310` | policy named words, all table-digest lines, configuration hash, held-digest comparison | **NEW** profile serialization and new trope preimage; **OK** continue comparing held digests, including dense files |
| 7 | `cp_verify.cpp:1360-1363,1573-1578` | local aliases dh/ldh/dq; WsShape receives dh separately | **OK** no rotary-width aliasing |
| 8 | `cp_verify.cpp:1366-1386,1393-1410` | 13-word KL records, TH(KL), final record word rp, `rp > 1` rejects | **NEW** admit2 only in the exact new rotary profile, preserving record length and 0/1 semantics |
| 9 | `cp_verify.cpp:1445,1482-1484,1531-1534,1854` | BC=CLAMPED_CELL_BOUND for layer/head bounds; qk numerator bound `2*2^cs*d*BC*BWw`; v and output bounds | **OK** wide layout and new rotary with coefficients bounded by 2^cs. Keep BC=2048 even in q/k-only narrow arm; it also bounds norm/v, not merely q/k |
| 10 | `cp_verify.cpp:1539-1544,2187-2191,2441-2445` | configuration digest, KL digest consistency, serialized KL bytes and first transcript query | **OK** existing binding route. **NEW** profile must reach statement/configuration before challenges, not be a verifier-local switch |
| 11 | `cp_verify.cpp:1593-1603` | theta0 !=0; ropeC bypass returns (2^cs,0); otherwise binary64 pow with denominator dh, then cos/sin and round | **NEW** mode2 selects pinned Q256 coefficients with denominator R; bypass must remain scaled identity. Do not use theta0 alone to select the generator |
| 12 | `cp_verify.cpp:1605-1614` | trope is H(72; u32 coefficients+4096), order [sin/cos selector][t][i<dh/2]; hash ignores per-layer bypass | **NEW** separate mode2 preimage including metadata and active coefficients. Preserve old order/offset/domain exactly for legacy |
| 13 | `cp_verify.cpp:1833-1843` | local `cs = fs.dT-lt`, shifts in forest placement | **OK**, unrelated name: this cs is not rotary scale |
| 14 | `cp_verify.cpp:1947-1955,1992-2004` | AFork takes ldh, H, kFD; owner/reader agreement; dh divisible byS2; per-head tensors tile dq/dkv | **OK** dimensions at 256; **NEW** pass a bound score profile through ACfg rather than a global radix change |
| 15 | `cp_verify.cpp:2373-2377,2407-2416` | standard-form explanation, held-table condition, `rotaryServed(theta0,dh,lt)` | **NEW** exact disjoint rotary profile predicate, plus updated explanation; no blanket `dh<=256` relaxation |

### 1b. Attention shape, bounds and lookup tables

| # | Source | Use | Class and obligation |
|---|---|---|---|
| 16 | `vf_attention_shape.h:13-15,386-387` | CLAMP=2047 is shared by FC, Smax, Om, N6 and CLAMPED_CELL_BOUND | **OK** wide arm. **NEW** narrow arm needs distinct q/k and v bounds; changing the shared constant changes unrelated model operations |
| 17 | `vf_attention_shape.h:71-74` | headFeat requires dh divides J and hd<J/dh, returns hd*dh | **OK** full head256, never rotary width 64 |
| 18 | `vf_attention_shape.h:78-91,142,155` | ACfg.ldh; AFork's dh/dq/dkv and Smax | **NEW** score-profile field and validation; **OK** full-head dimension storage |
| 19 | `vf_attention_shape.h:156-162` | nHD and causal Om derived from full Smax | **OK** wide arm recomputes at full256; **NEW** narrow arm substitutes its proved q/k bound; **NEW** split cannot substitute a half bound for the final sum |
| 20 | `vf_attention_shape.h:173-175,183-200` | WL/WH dimensions include ldh; derives dh=2^ldh, dq, dkv; ls<=ldh | **OK** eight channel bits; parent must still bound shift counts before allocation |
| 21 | `vf_attention_shape.h:201-218` | softmax table/zero threshold; Smax=dh CLAMP^2; Ty2/Ty4 and budgets | **OK** softmax and cell bounds unchanged. **NEW** explicit score bound and profile; Smax is not derived from observed activations |
| 22 | `vf_attention_shape.h:222-234` | kFD8..16, sh = 4..12, table occupancy, C+65536<=2^24, N3 and N4 | **NEW** wide arm requires kFD = 17 and radix 33/34; narrow arm retains these rules. Both must satisfy occupancy, not only N4 |
| 23 | `vf_attention_shape.h:236-245` | N1, N2, N5, N6, N9 | **OK** wide arm formulas unchanged and rechecked in section2. **NEW** split must bind its sum before invoking N1. q/k-only clamp leaves N6's value term unchanged |
| 24 | `vf_attention_shape.h:298-313,326-336` | pieces/call sizes; KFD public rows with flag 2^32 and e2^33 | **NEW** wide profile's paired table/key radix change; count/forest plans must reflect kFD = 17. Narrow arm only changes the table's Smax-derived extent |
| 25 | `vf_attention_shape.h:345-359` | ao and qa offsets use dq/dkv, two limbs for q/k/v/o | **OK** wide arm needs no extra committed score or q/k limb; **NEW** any split-sum witnesses would require their own layout, not reuse these offsets |

N7 and N8 do not exist in this implementation (`docs/format/11-3-attention-segment.md:981-994`). Do not claim to have passed nine implemented tests.

### 1c. Attention checks and layer-side rotary equation

| # | Source | Use | Class and obligation |
|---|---|---|---|
| 26 | `vf_attention_check.h:37-39` | forest depth >= max(lmS,lt+ldh) for shared ao table | **OK** inequality unchanged; new shape requires sufficient depth, not an unconditional OK plan |
| 27 | `vf_attention_check.h:267-271,289-291` | nvKF/nvF sumcheck dimensions and local dh/ldh/dq | **OK** full256-wide dot product; no use of R here |
| 28 | `vf_attention_check.h:622-648` | lng/cutLast, TO equality of lt+ldh coordinates, rcK, q/k table queries | **OK** eight channel bits. **NEW** split arm would need separate domains and checked recombination, not merely ldh-1 |
| 29 | `vf_attention_check.h:702-713` | XL and headFeat read full per-head qa/ao tensor | **OK** q/k/v/o stay256 wide |
| 30 | `vf_attention_check.h:755-793` | KFD claim binds score sumcheck to q/k and row maximum; DP has C padding or causal Om; flag 2^32, weight 2^33 | **NEW** wide arm changes both coefficients to 33/34 under the same bound profile as the table. **NEW** split needs final M-s relation. No separate softmax per half |
| 31 | `vf_attention_check.h:777-781` | rcK takes final ldh coordinates of dot-product sumcheck, then XL(q), XL(k) | **OK** wide arm; **NEW** split requires two correctly bound128-wide subdomains |
| 32 | `vf_attention_check.h:798-807,850,912` | rh/rhp, o and q read with dq and the full channel domain | **OK**, downstream mean and output layout stay full head width |
| 33 | `vf_layers_check.inc:219-227` | head weights AH use dh blocks; lfc is eq on ldh channel bits | **OK** lfc length 256, not 64 |
| 34 | `vf_layers_check.inc:466-476` | clamp key forms use fixed +2^11 output encoding and +2^39 packed offset, CQK reads q/k, CV reads v | **OK** wide arm; **NEW** narrow q/k-only FC must retain the encoding offset 2048 or change both ends together; tightening range is not changing radix |
| 35 | `vf_layers_check.inc:894-920` | kap(dh), adjacent pairs2i/2i+1, Ct/St from ropeC, weight-kind0 cd factor=kap | **NEW** mode2 uses rotate-half pairs inside prefix64 and scaled identity on 192 remaining coordinates, as section3 specifies. Same qk weight claim, not an unbound standalone gadget |

### 1d. Standard form and user contract

| # | Source | Use | Class and obligation |
|---|---|---|---|
| 36 | `vf_common.h:563-567,705-706,721` | rotaryTable boolean, rotaryServed theta in{10000,500000}, dh<=128, lt<=10, servedForm refusal | **NEW** retain this predicate for legacy; add an explicit mode2/profile predicate. `rotary-table` is a standard-form condition, not by itself a low-level shape refusal |
| 37 | `parameter-file.md:106,120-121,133,166` | H/G/dh, cs, theta0, S2 divisibility and forest depth | **DEP** dq equality; **OK** keep dh meaning and cs = 12; **NEW** document R/pairing/profile separately from dh and do not imply all nonzero theta are standard |
| 38 | `parameter-file.md:177-185,237` | attention table parameters and all 32 table-digest words | **NEW** profile-specific kFD and mandatory mode2 trope; no missing-digest waiver |
| 39 | `parameter-file.md:273,277-290` | no-overflow caveat; float-table definition, H(72;table), rotary depends on lt/dh/cs/theta0, dense handling | **NEW** new deterministic table preimage and mode dependency; preserve caveat that numerical guard checks are not a theorem |
| 40 | `parameter-file.md:294,318,331,336,338` | KL rotary flag; rotary standard form; tie-distance scope; required dense digests; dh<=128 description | **NEW** document rp2/R = 64/Q256 and disjoint admission, while keeping full-width byte compatibility and existing dense requirements |

Completeness exclusions: comments and local declarations are included in the ranges above. Neither `vf_attention_check.h` nor `vf_attention_shape.h` currently reads rotary tables: rotary is fused into the layer's qk projection claim, not performed by the attention dot-product checker. `cs` in row13 is a distinct variable. `rp` is accessed through `klRp`, and `trope` through `hRope`/`tblHeld`, so a literal-word grep alone is insufficient. The separate score-table coefficients2^32/2^33 are included even though those lines do not say Smax.

**Extra dependency discovered:** `vf_lookup_argument.h:94-104` rejects every call with `k>16` as `shape-pt-words-*`, independently of AFork's kFD guard. `vf_lookup_argument.h:112-135` then sizes the forest from kT, n and dT and checks its key/pin budget. A wide layout must audit this shared machinery and its prover twin; this note does not establish that changing its ceiling is sound. A profile-specific path must preserve the old ceiling for all legacy calls. `prover/common/parameter_file.h:339` has another kFD = 16 cap. These are DEP, not an authorization to change a shared Maverick path.

## 2. N4 alternatives, recomputed as exact integers

All numbers below were independently evaluated with Python integer operations in this lane's own desk script, not copied from issue text or another lane. The formulas and a self-contained reproduction recipe are in section7. No float computation was used for these bounds.

The implemented N4 is

`L(dh,b,C) = 6 dh b^2 + 2 C + 3*65536 < 2^32`.

The C policy gives `Cmax = 2^24-65536 = 16,711,680`; it is an upper bound, not a claim that the standard softmax attains it. At dh = 256, b = 2047: `Smax=1,072,693,504`, `L(Cmax)=6,469,780,992`, so N4 fails. At dh = 128 with the same b, `Smax=536,346,752`, `L(Cmax)=3,251,700,480`, so it passes. Both signs of a score can attain Smax: all q=b and all k=b gives +Smax; all q=b and all k=-b gives -Smax. A score range assumption must cover both, not just a positive maximum sampled from activations.

### 2a. Narrow only q/k, not v or norms

Because the inequality is strict, the largest integer clamp is

`isqrt((2^32 - 1 - 2*C - 3*65536) // (6*256))`.

| C | largest b | L(b) | positive margin2^32-L(b) | L(b+1), refused |
|---|---:|---:|---:|---:|
| 0 | 1,672 | 4,294,213,632 | 753,664 | 4,299,351,552 |
| 16,711,680 | 1,665 | 4,291,757,568 | 3,209,728 | 4,296,873,984 |

C=0 is an algebraic diagnostic, **not an admitted configuration**: u0 is positive and sh>=4. For a bound valid for every admitted C, choose b <= 1665, not 1672. At1665, Smax=709,689,600.

Soundness need: CQK must actually prove that q/k are the new clamp's outputs, through the existing committed projection/rounding path. Do not merely insert 1665 into Smax while FC still permits 2047. A dedicated FCQK table can retain `(input+32768) + 2^28*(clamp_b(input)+2048)`, so the layer's fixed affine offsets remain valid. CQK's kind/call routing and public table identity then need their own profile definition. Leave CN1/CN2/CV and BC unchanged. If all q/k/v clamps were instead narrowed, N6 improves, but that is a different model and fidelity question, not the q/k-only option.

Attention conditions touched: N1, N3, N4 through Smax; N2 unchanged; N5 unchanged; N6 unchanged when b_v stays2047; N9 unchanged; N7/N8 absent. Om and nHD change consistently. At standard S = 12, rx = 8, kFD = 16 can satisfy occupancy for every sh = 4..12 (section2d). No legacy Maverick verdict may change: new clamp/table identity is opt-in, never a replacement for global CLAMP. **This is the least score-layout work, but it spends numerical range. Fidelity remains an unmet prerequisite; passing these inequalities does not select a quantizer or certify a model.**

### 2b. Two128-wide partial scores

Let s0 and s1 be the dot products over disjoint channel halves. Each satisfies `|si|<=536,346,752`, and its own N4-sized expression at Cmax is 3,251,700,480. But `s=s0+s1` still has `|s|<=1,072,693,504`; final `M-s`, the causal offset and KFD key still require L=6,469,780,992. Indeed the conservative masked distance upper bound `4*Smax+Cmax=4,307,485,696` already exceeds2^32. An all-same-sign vector attains the sum bound, so there is no cancellation argument.

This arm must prove both 128-product relations, signed bounds on both partials, an exact recombination relation and that the row maximum belongs to the **sum**. Two independent maxima or softmaxes compute a different function. If recombination is only a field equality, add the integer no-wrap argument for it before using the summed bound. N1 must apply to the final maximum/score; N3/N4 remain on the final distance and are still unsatisfied with the old radix. N2 may be reused only for unchanged digit encodings; N5/N6/N9 stay unchanged if the downstream softmax/mean is unchanged. Any new partial-digit encoding brings additional obligations, not covered by the old labels. N7/N8 remain unused.

Counted, not built: two 128-product reductions per score instead of one 256-product reduction, plus one checked recombination and any partial-range witnesses. The total number of products is not reduced. Additional witness/round counts depend on a new layout and are unknown. Legacy branch can remain byte-identical, but **splitting alone is not an N4 remedy**. Do not start this arm as a one-line ldh change.

### 2c. Wider score digit inside the existing field, recommended design direction

Let Rb=33 for a new score profile (legacy Rb=32). Replace the KFD key and table together:

`D' - r + 2^Rb*flag + 2^(Rb+1)*e`.

Replace N4's limit with 2^Rb and N3 with

`L + 2^Rb + 2^(Rb+1)*(Ty2+128+2^S) < Pbudget`.

This is a change to the packed lookup digit layout, **not** a larger field and **not** a relaxation of N4 while keeping the old key. N1/N2/N5/N6/N9 retain their formulas; N7/N8 do not exist. No committed score limb is added by this proposal: M has the same four limbs; q/k still have two. The radix change belongs in `vf_attention_shape.h:230-234,333-335` and `vf_attention_check.h:755-790` together, with matching prover construction, format and transcript/accounting plans.

For dh = 256, b = b_v = 2047, Ty = 262144, Cmax, T = 1024, S = 12:

| condition | left side | strict upper bound | verdict |
|---|---:|---:|---|
| N1 | 4,416,366,444,800 | 1,152,921,504,606,846,976 | below |
| N2 first | 288,232,850,187,354,240 | 2,305,843,009,213,693,951 | below |
| N2 radix | 262,528 | 1,048,576 | below |
| N3, new 33/34 layout | 1,157,497,687,061,366,272 | 2,305,843,009,213,693,951 | below |
| N4, new 33-bit low digit | 6,469,780,992 | 8,589,934,592 | below |
| N5 | 4,415,297,945,600 | 1,152,921,504,606,846,976 | below |
| N6 | 565,183,349,063,681 | 1,152,921,504,606,846,976 | below |
| N9 | 131,072 | 1,152,921,504,606,846,976 | below |

At maximal allowed S = 14 the new N3 left side is 1,157,708,793,293,899,264, still below Pbudget. Enumerating all 182 pairs `(lt,S)` with lt = 2..16, S = 1..14, lt+S+1<=24, and conservatively using Cmax, leaves every listed condition below its bound for both the narrow1665 and wide33 arms. This is a superset bound check, not182 admitted parameter files; rx/u0/occupancy and the other planner rules can still reject. At the same worst C and S, new N3 permits Ty at most 522,183, whereas the actual Ty = 262,144 is fixed by the range-check construction. Do not infer arbitrary new cell bounds. With a low digit below 2^33, a flag at 2^33 and e <= 2^14, the conservative packed-row upper bound is 281,492,156,579,839, below both the u64 storage limit and Pbudget. This checks row storage/budget only, not the missing 17-bit lookup argument.

Soundness argument still needed: use N3 to lift the key equality to integers, N4 to separate its low digit, the existing KR relation to constrain remainder/flag, and the high digit to force e to the chosen table value. Every occurrence of the radix in table, affine join and prose must agree. The range check remains on the committed cells it already covers. The note checks numerical sufficient-condition candidates, **not** that the existing argument was a complete proof; `parameter-file.md:273` and `docs/format/11-3-attention-segment.md:996-1004` explicitly limit that claim.

**Maverick preservation:** default/legacy profile keeps exact old N3/N4, table rows, kFD ceiling and all encodings. The wider layout must be explicitly configuration- and statement-bound, not auto-selected by an untrusted witness or by an unbound CLI option. Suggested parameter contract: a new opt-in `af_profile` value for wide33-v1, limited initially to dh = 256, standard softmax and the fixed cell bound. Absence selects legacy and must not append/change any old statement bytes. The build design must assign its versioned statement serialization and reject unknown profiles before sizing; names here are proposed, not currently parsed syntax. If this cannot be done without changing an existing legacy verdict, stop.

### 2d. The second obstruction: KFD rows and shared forest width

Even after the wider radix, the table still covers the full score range. Its independent policy is `u0+nHD <= 2^kFD <= u0+2*nHD`, kFD<=16 today. For standard S = 12, rx = 8 the first zero weight index is 2307. It was recomputed with integer lower/upper bounds for ln2: the zero threshold is the first integer u above `256*13*ln2`, since rounding exp to zero occurs below or at one half and this threshold is nonintegral. This models the mathematical threshold; the platform table's actual consistency remains the legacy softmax test's responsibility, not newly established here.

| b | sh | nHD | permitted row-count interval | power-of-two choice |
|---|---:|---:|---:|---|
| 1665 | 4 | 43,327 | [45,634,88,961] | 65,536 (kFD = 16) |
| 1665 | 12 | 46,204 | [48,511,94,715] | 65,536 (kFD = 16) |
| 2047 | 4 | 65,489 | [67,796,133,285] | 131,072 (kFD = 17) |
| 2047 | 12 | 69,837 | [72,144,141,981] | 131,072 (kFD = 17) |

Every intermediate shift4..12 was recomputed too and gives the same respective choice. C ranges from 36,912 to 9,449,472 here, within Cmax. Thus a complete standard-softmax dh = 256/clamp2047 plan encounters `af-policy-kF` **before N4** (`vf_attention_shape.h:228`); N4 is a separate failure, not necessarily the first printed refusal. Widening kFD only in AFork next encounters the shared forest cap.

Counted new-layout cost, not a proof-size or timing prediction: one extra low-digit bit, one corresponding shift of the e digit, zero extra committed score limbs, and 65,536 extra public KFD rows per expanded KFD call. A 131,072-row u64 table occupies 1,048,576 bytes. Call count depends on the configured segments and shifts; do not multiply by a fixed model count. Additional forest rounds, range-check tables, masks and accounting must be rederived from kT = 17. No audit here establishes them. **Until that dependency has its own design and legacy-isolation test, do not start the widened-admission build lane.**

## 3. Rotary: exact new semantics, not a larger cap

### 3a. Parameter and statement contract

Choose **a new rp value**, not an arbitrary width word in the first build:

- Legacy rp0: disabled rotary, scaled identity. Legacy rp1: full-width adjacent pairing and the current float64 definition. Existing statement/table bytes remain unchanged, including the table hashed even for bypassed layers.
- New rp2: R = 64, dh = 256, pairs `(j,j+32)` for j = 0..31, untouched coordinates 64..255, theta0=10,000,000, cs = 12, text-only position t in 0..T-1, T<=1024. This one value fixes R, pairing, generator version, coefficient rounding and mask semantics. Reject unknown rp, other dh/theta/cs, larger T, and mixed rp1/rp2 within one configuration for this first extension. rp0 layers may coexist with rp2 and use scaled identity.
- Keep the KL record thirteen words. rp remains in its final word; TH(KL), hKV and the configuration digest already bind it (`cp_verify.cpp:1366-1383,1539-1544`). Existing dh/cs/theta/lt statement words bind those values. Do not put R into a runtime-only variable without making its fixed meaning a normative part of rp2.
- For mode2, require held table-digest lines and an exactly matching pinned table before claiming standard form. `rotaryServed` becomes a dispatch over validated mode/profile plus existing arguments: old predicate unchanged for legacy, or the exact rp2 domain and generator identity. A theta/dh-only OR is insufficient; it would bless adjacent-pair/full-width files at the new theta too.
- A future general R is a different version with an even-width bound `0<R<=dh`, explicit pairing and generator identity, digest and parameter words. It is not implicitly admitted by rp2.

The score profile and rotary mode are independent configuration choices. Neither should silently turn on the other. A score-only planning fixture can use a valid legacy rotary configuration without claiming the new rotary standard form; a rotary helper test can be isolated from N4. A full Qwen profile needs both, plus the dependencies below.

### 3b. Pinned generator and what trope covers

Choose the **F12 coefficients of the existing Q256 generator** (`research/operators/qwen_ops/rotary_tables.py:10-62`, `research/operators/qwen_ops/tables.py:10-24` for Q and nearest), with its existing manifest/artifact as the fixed source. It uses integer Machin pi,32nd-root frequencies, integer range reduction,128 recurrence steps and nearest-even rounding of the computed Q256 approximation. It is deterministic without libm. It is **not a theorem of correctly rounded sin/cos**, and nearest-even here is not permission to replace legacy away-from-zero rounding.

Do not transplant the standalone proof statement: its inputs are unbound (`rotary/README.md`, “What is public, committed and prover-chosen”). Reuse only the specified coefficient artifact/generator; bind the integrated operation through the existing weight/projection claim. Also do not transplant the gadget's final floor into the layer's projection rounding. The standalone gadget and fused projection are different integer relations.

For mode2, define `trope` as the existing H(72; words) digest of a **new domain-separated, versioned preimage**. Proposed canonical u32 header, in this exact order: `[LE32("QRP2"), 1, 1, 1, 256, 64, 12, 10000000, 0, T, 1, 1, 1]`. Here LE32 packs the four ASCII tag bytes little-endian; the next three words are schema version 1, Q256-v1 generator ID 1 and nearest-even-of-Q256 coefficient-rounding ID 1. The next six are dh, R, cs, theta0 low/high and T. The final three IDs mean rotate-half-prefix pairing, text-sequential position rule and scaled-identity tail, respectively. No other ID is admitted in this schema. Follow it by the used coefficient prefix in order `[t][j][cos,sin]`, each coefficient encoded as coefficient+4096. This exact order and IDs must enter the format spec with test vectors before implementation; the current digest is not already such a digest. Unused positions beyond T need not be in the runtime preimage because generator identity pins the full artifact and T is in the header. Identity-tail coefficients need not be repeated because their rule, dh, R and cs are covered. Range-check each coefficient in[-4096,4096], verify the pinned artifact identity, and compare the derived digest with the held trope words. The caller cannot supply arbitrary table bytes and merely update trope to redefine the generator.

At T = 1024 the artifact has 65,536 signed i64 coefficient words, 524,288 bytes; there are 32 active pairs and 192 identity coordinates per head. The artifact SHA-256 in its manifest is an artifact integrity check, **not** a substitute for the statement's H(72;...) trope. Legacy keeps its [cos/sin][t][i] u32 preimage and no new prefix; repacking every old table would break old proof identities.

Alternative not selected: use upstream binary64 pow/cos/sin at theta0=10^7 with denominator 64 for R = 64 (denominator 256 describes a different frequency schedule). That needs a new exhaustive tie-distance computation for all t<1024 and active pairs, the defined sequence of binary64 operations and rounding, and comparison with the actual implementation. If full-width dh = 256 were also to be admitted, it requires its own256-width cases. `scales/tests/table_ties.py:1-63,202-210` covers only the legacy domain and records limits of that computed evidence. Raising the cap is not this check. No new tie-distance check was run in this lane.

### 3c. The layer claim and the unrotated suffix

Let X be the pre-rotation q/k projection accumulator, not a new prover-chosen vector. For j<R/2 set a=j, b=j+R/2 and coefficients Ct/St at the public position:

`Y_a = Ct X_a - St X_b`, `Y_b = St X_a + Ct X_b`.

These are the **scaled numerators** fed into the already specified q/k shift/round/clamp chain; for c>=R use `Y_c = 2^cs X_c`. After compensating for the rotary scale, this is the identity branch, not a proof that rounded q/k equal the unrounded projection. The scale must not disappear on unrotated channels.

The transposed coefficients of a claimed output linear combination are therefore:

`kap[a] = Ct*lfc[a] + St*lfc[b]`

`kap[b] = Ct*lfc[b] - St*lfc[a]`

`kap[c] = 2^cs*lfc[c]` for c>=R.

Here Ct and St in the actual checker are their token-equality-weighted sums; initialize the whole kap to the scaled identity and overwrite exactly the active pairs. At rp0 overwrite none. Keep kap lengthdh and `claim(0,lam)`'s hd/cd/kk factors; using R as the head dimension would corrupt head addressing and the projection matrix. Coefficients bounded by 2^cs give at most two such terms per rotated coordinate, so the existing conservative qk numerator bound in row9 still applies; the identity suffix is smaller, not a reason to weaken the global bound.

**DEP:** Qwen's q/k RMSNorm occurs between projection and rotation. The current fused projection-to-rotary claim cannot magically prove that operation. This note specifies the linear rotary transformation and its transpose for integration, not the missing normalization seam. Until that separate design binds the normalized q/k inputs and correctly places shifts/rounding, these equations do not establish Qwen's operator order. The sigmoid output gate is a separate dependency as well.

## 4. Needs N1 through N10

These are design needs, distinct from the verifier's `af-no-wrap-N*` labels.

- **N1, profile and statement binding.** Freeze wide33-v1's parameter/statement encoding with a strict legacy default; bind rp2 through KL and its exact normative semantics. No hidden switch, missing mode, unknown ID or cross-profile replay. No legacy header growth.
- **N2, complete score-key algebra.** Re-derive the integer implication of the new 33/34 KFD row/key relation, including signed extremes, padding, causal Om, flags and e. Recompute N1/N3/N4 from actual q/k range witnesses; retain N2/N5/N6/N9. The table and join must share one profile object, not duplicated magic constants.
- **N3, lookup-width design dependency.** A 17-bit KFD table needs a separately reviewed path through shared forest sizing/lookup arguments, prover tables, table queries, multiplicities, masks, sumcheck rounds and accounting. Preserve legacy k<=16 and its exact failures. Until this is resolved, the recommended score arm is blocked, even though its numerical N conditions fit.
- **N4, narrow-arm fallback only.** If choosing1665 instead, require a distinct CQK clamp table and range argument with 2048 encoding offset, and a fidelity decision on that exact q/k-only operation. Never silently lower v, norms or all model clamps. Recompute nHD/Om and all affected conditions. This is not the selected build plan.
- **N5, rotary domain and coefficient identity.** Freeze rp2, R = 64, rotate-half pairing, F12, theta, T, sequential positions, Q256-v1 algorithm/artifact and canonical trope header/word order; reject unsupported modes and all mismatched held digests before proof use. Keep dense mandatory digests.
- **N6, scaled identity and bound inputs.** Implement the transpose over the full dh vector with identity tail and disabled layers; tie its inputs to the intended committed q/k stage. Do not reuse the standalone gadget's existential input statement or its final floor. q/k norm seam remains a prerequisite for Qwen semantics.
- **N7, shape/resource and owner-reader agreement.** Keep dq admission separate, bound dimensions before allocations/shifts, and rebuild tensor/forest plans for ldh = 8. Assert qa/ao owners and readers agree and S2 dividesdh. A successful isolated inequality is not a complete plan.
- **N8, legacy isolation.** Old rp0/1, CLAMP, N conditions, table digests, statement bytes, configuration IDs and existing proof verdicts must be unchanged. A new mode must not reinterpret a legacy file at a formerly nonstandard theta.
- **N9, prover and documentation twins.** Parameter reader, forward arithmetic, KL handling, table generator/export, prover layout and verifier must share these modes. Update model/format/parameter-file definitions and counted plans together. This lane did not audit all prover uses or provide a patch estimate for them.
- **N10, separate fidelity/composition decision.** Before describing a Qwen result, require evidence for the exact integer projection/norm/rotary/attention/gate chain, fitted scales and tested context range. A successful wider representation preserves the chosen integer attention computation, not its agreement with float Qwen.

## 5. Tests T1 through T12 for a future build lane

These tests are requirements, **not tests run here**. Helpers may be CPU-only; honest model proof production needs separate authorized resources and prerequisites. Do not spend a GPU to paper over a failed desk invariant.

- **T1, N4 boundary and signs.** Unit-test the actual selected profile predicate, strict `<`, at L=2^33-1 and L=2^33 (accept/refuse), plus integer dh = 256 clamp boundary at Cmax: b = 2360 gives L = 8,588,525,568 (below), b = 2361 gives L = 8,595,777,024 (above). These b values are predicate tests, not new allowed clamps. For fixed admitted b = 2047 construct q/k sign patterns reaching +Smax and -Smax, and causal masked/unmasked distances; a mutation that aliases a flag/e digit across the low radix must be refused. Legacy32 predicate controls must still refuse dh = 256/b = 2047. If fallback arm is selected instead, use 1665/1666 at Cmax and 1672/1673 at C0, both score signs, with C0 explicitly predicate-only.
- **T2, all affected guards and earlier failures.** Recompute N1..N6/N9 with Ty fixed, all sh = 4..12, C boundaries and allowed softmax parameters. Check kFD = 16 rejection and profile-specific17 occupancy at standard softmax, along with the shared forest cap. Test the predicate independently when a full plan refuses earlier; do not label an earlier `af-policy-kF` rejection an exercised N4 rejection.
- **T3, KFD key/row twins and padding.** Compare separately written exact-integer row and affine-key constructions for both profiles, both signs, sh endpoints, active/zero softmax, diagonal causal mask, empty tile and padding keys. A mixed32/33 table or join must fail. Exercise field-lift assumptions, not only honest row equality.
- **T4, partial-table off-by-one.** Keep configuration/held trope fixed, alter exactly one F12 coefficient by+1 (also -1 in another case), recompute the verifier-side preimage and require `table-digest-rope` before proof parsing. Also alter the held trope alone. Positive control uses the pinned table. If the held trope is changed to match altered coefficients, pinned-generator validation must still refuse; a digest cannot certify arbitrary prover-chosen tables.
- **T5, every position/pair and transpose.** Independently regenerate the Q256 coefficient artifact and compare every F12 entry and manifest identity; compare the explicit rotate-half matrix with kap's transpose on integer basis vectors for all 256 coordinates and boundary positions 0 and 1023, then the token-weighted multilinear form. Check swapped sine/cosine, sign, wrong pair, adjacent-pair substitution, and R/denominator confusion are detected. Identity coordinates 64..255 and rp0 must carry exactly 2^cs, not 1 or 0. No tolerance-based float comparison substitutes for this equality.
- **T6, old verifier rejects partial file.** Use an otherwise valid legacy-shaped fixture whose only changed KL word is rp2; unmodified `cp_verify` should reject `KL-rp` before using a proof. Separately use the full intended dh = 256/R = 64/theta10^7 file: old verifier must refuse, recording its actual first cause (it may be shape-heads or kF, not rotary). Positive control on the modified implementation must validate the new rotary helper/profile; a refused malformed file alone proves no integration.
- **T7, four stored proofs byte-identical.** Use unchanged files in `examples/accepted-proof`, `examples/accepted-proof-clipped-gap`, `examples/full-size`, `examples/full-size-clipped-gap` (listed in `experiments/20261112-135-dense-standard-form/RESULTS.md:83-100`). Compare file hashes, derived legacy rotary bytes/digests, statement/configuration IDs, plans and final outcomes before/after. Full calls and quiet calls must keep their original YES or WITHIN LIMITS result; planning calls remain PLAN ONLY. Compare deterministic output bytes, normalizing only the documented timing/build-identification lines, never causes, counts, hashes or verdicts. These stored proofs have synthetic weights, not real Maverick weight evidence.
- **T8, bound mode/header replay.** Change only rp, profile, R-derived interpretation, generator ID, pairing ID, position rule, T or theta, one at a time. With a valid alternative configuration that passes its own planning, replaying the original proof under the different bound statement must fail proof checking. Distinguish this from unsupported-parameter rejection. Old-mode files must produce exactly old digest preimages.
- **T9, complete planning at dh = 256.** After independent dq admission and lookup-width design, regenerate every dimension-dependent layout/mask/accounting word for a small supported full-head fixture, then the intended H/G/dh shape. Assert owner-reader agreement, call/slot/claim counts, kT/dT, table lengths and integer budgets. No copying a kit and treating the first shape failure as coverage. Stop on a need to change an unreviewed shared path.
- **T10, full composed proof and hostile seam.** Once q/k norm and gate designs exist, prove one small honest composed instance and reject changed normalized q/k, an altered unrotated coordinate, stale position and an unbound substituted input. This must bind weights/previous layer to rotary and attention; a standalone existential gadget accept does not count. Not run or authorized by this note.
- **T11, regressions outside new modes.** Existing verifier unit/served-form/parameter/forest/tensor tests and legacy no-wrap verdicts remain unchanged. Explicitly test legacy kFD = 17 remains refused, unknown profile fails early, rp1 at theta10^7 is not newly declared standard, and missing dense table digests remain disallowed.
- **T12, split-arm negative control.** If a future lane revisits splitting, construct both partials at the same signed extreme, verify their bounds, and demonstrate the full-range final score still triggers legacy N4. Only a separately specified final-score layout can turn that arm into a candidate.

## 6. Dependencies, counted scope and stop rule

Dependencies not designed here: dq!=d admission (`DQ-NE-D.md`); shared 17-bit lookup design; Qwen q/k RMSNorm and the correctly bound rotary-input seam; sigmoid output gate; hybrid DeltaNet/full-attention scheduling; model/input provenance; prover integration and exact-chain fidelity. Neither a clamp change nor a table hash supplies these. The active rotary table is reusable data, not a composed model proof.

Counted scope of the proposed score layout is in section2d, not a line-count or performance estimate. Rotary changes need a mode validator, coefficient source/preimage, full-dh transpose with active-prefix pairing, standard-form predicate, producer twins and tests. No honest total code-size/round-count estimate is established before the shared forest and norm seam designs. The negative desk result is: **there is no drop-in admission change here that both preserves the 2047 score semantics and stays inside the present 16-bit KFD lookup layout.** A narrow q/k range can fit the old layout but needs its own numerical-fidelity decision; a mere split cannot. Recommend wide33 as a new-layout design, not an enabled feature.

**Stop before starting a widened-admission build** until N1/N3/N5's profile serialization, lookup-width design and table preimage are reviewed. After those are supplied, a bounded build lane stops without publishing widened admission if any of the following occurs:

1. any legacy proof bytes/IDs, deterministic table bytes, expected no-wrap/served-form verdict or T7/T11 result changes;
2. any mode is not bound before challenges, an altered coefficient passes its held/pinned identity checks, or partial rotary is justified only by a cap change;
3. any N condition fails for the explicitly admitted domain, or a new digit/table layout lacks its own integer argument;
4. a complete plan needs an unreviewed shared-forest change, extra unaccounted round/witness or a place omitted from the inventory;
5. the integrated input seam is still unbound or skips q/k norm while making a Qwen claim;
6. the lane's registered wall-clock budget expires. Stop with the partial design/test failure; do not widen the scope or borrow another lane's results.

## 7. Reproduction and what was run

Desk arithmetic only. No verifier build, verifier unit suite, proof production/checking, weights, model activation run, GPU work or table regeneration was run. Repository claims and host-path checks are hygiene checks, not tests of the proposed extension. No PREREG/ENV or results row is added because no experiment or measured result is reported.

To reproduce the principal bounds, save the following as a Python file and run it. It uses integers only. Constants are transcribed from `vf_attention_shape.h:156-162,218-245` and `cp_verify.cpp:1531-1534`; the candidate33/34 substitutions are specified above, not taken from unmerged evidence. The lane's own scratch Python additionally enumerated all admitted `(lt,S)` inequality domains and all nine sh values and computed the displayed counts.

```python
from math import isqrt
Ty = 1 << 18
Ty2, Ty4 = 257 * Ty, 16843009 * Ty
P2, Pbudget = 1 << 60, (1 << 61) - 1
Cmax = (1 << 24) - 65536

def low(b, C, dh=256):
    return 6 * dh * b * b + 2 * C + 3 * 65536

for C in (0, Cmax):
    b = isqrt(((1 << 32) - 1 - 2*C - 3*65536) // (6*256))
    assert low(b, C) < (1 << 32) <= low(b+1, C)
    print(C, b, low(b, C), (1 << 32)-low(b, C), low(b+1, C))

for b, radix in ((1665, 32), (2047, 32), (2047, 33)):
    for lt in range(2, 17):
        for S in range(1, 15):
            if lt + S + 1 > 24:
                continue
            TS = (1 << lt) * (1 << S)
            checks = [
                (Ty4 + 256*b*b, P2),
                ((1 << 40)*Ty + (1 << 20)*(Ty+128) + Ty+128 + (1 << 41), Pbudget),
                (Ty+128+256, 1 << 20),
                (low(b, Cmax) + (1 << radix) + (1 << (radix+1))*(Ty2+128+(1 << S)), Pbudget),
                (low(b, Cmax), 1 << radix),
                (TS + Ty4, P2),
                (2*TS*2047 + TS + 2*TS*Ty2 + 2*TS+1 + 65536*(Ty+128)+65536, P2),
                ((1 << (16-lt))*2*(1 << lt), P2),
            ]
            expected = [True] * len(checks)
            if (b, radix) == (2047, 32):
                expected[4] = False
            assert [a < z for a, z in checks] == expected
            if (lt, S) == (10, 12):
                print(b, radix, checks)

# Rigorous integer interval for ln(2), using its atanh(1/3) series.
Q, n = 1 << 256, 128
lo = 2 * sum(Q // ((2*k+1)*3**(2*k+1)) for k in range(n))
hi = lo + 2*n + (3*Q + 4*3**(2*n)-1) // (4*3**(2*n))
a = 256 * 13
assert a*lo//Q == a*hi//Q
u0 = a*lo//Q + 1
for b in (1665, 2047):
    for sh in range(4, 13):
        rho = 65536 - (1 << sh)
        nHD = (4*256*b*b + 1 + rho-1) // rho
        ks = [k for k in range(8, 18) if u0+nHD <= (1 << k) <= u0+2*nHD]
        print(b, sh, u0, u0*(1 << sh), nHD, u0+nHD, u0+2*nHD, ks)

print("Smax", [(dh, b, dh*b*b) for dh, b in
               ((128, 2047), (256, 2047), (256, 1665), (256, 1672))])
print("split", low(2047, Cmax, 128), low(2047, Cmax),
      4*256*2047*2047+Cmax)
wb = isqrt(((1 << 33)-1-2*Cmax-3*65536) // (6*256))
assert low(wb, Cmax) < (1 << 33) <= low(wb+1, Cmax)
print("wide boundary", wb, low(wb, Cmax), low(wb+1, Cmax))
print("wide N3 S14", low(2047, Cmax)+(1 << 33)+(1 << 34)*(Ty2+128+(1 << 14)))
print("wide N3 max Ty", ((Pbudget-1-low(2047, Cmax)-(1 << 33)) //
                         (1 << 34)-128-(1 << 14)) // 257)
print("packed row upper", (1 << 33)-1+(1 << 33)+(1 << 34)*(1 << 14))
print("softmax shapes", sum(lt+S+1 <= 24 for lt in range(2, 17) for S in range(1, 15)))
print("extra KFD rows, bytes", (1 << 17)-(1 << 16), (1 << 17)*8)
print("rotary pairs, tail, words, bytes", 64//2, 256-64,
      1024*(64//2)*2, 1024*(64//2)*2*8)
```

## What this note does not establish

No formal soundness proof, implemented wide lookup, admitted dh = 256 parameter file, changed `rotaryServed`, integrated q/k norm or gate, correct Qwen operator order, real-activation clamp fidelity, cross-platform Q256 regeneration, new float tie-distance guarantee, honest composed proof, performance or end-to-end abliterated inference. The legacy four proofs were specified as regression requirements, not rerun. No result from another open PR is promoted into evidence. Independent review may find further consumers outside the six-file inventory, especially in the prover and shared lookup machinery.
