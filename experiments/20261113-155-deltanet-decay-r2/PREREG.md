# PREREG: 20261113-155-deltanet-decay-r2

Issue: #155 (part of #35, follows #136 / PR #146, informs #8, tracking #32). Lane: decay155 (CPU only, no proof, no table digest or format change). Date (UTC): 2026-11-13T01:36Z (read from the host clock; the commit time is the record). Base commit: 17d216d4f81d3e5ecc6011a2fa2c698b8993bf55 (main).

This file is the first commit of the experiment, alone, before any experiment code. What was read before writing it: issue #155; PR #146's directory on main (`experiments/20261112-136-deltanet-decay/`: PREREG, RESULTS, `decay_tables.py`, `suite.py`, `runs/eval/eval-meta.json`); `experiments/20261109-32-qwen-m3-design/DESIGN.md` sections 5.0, 5.2, 5.3, 7.2; and PR #146's committed per-head table `runs/eval/domain.json.gz` (sha256 8dd43595ed8949824edef09b55ff87ccdce356b6fabd48d4a38e4430b8ef8666), from which the per-head A, dt_bias and the min / median / max of x and g were tabulated to fix the design constants below. No recorded activation array has been opened by this lane: the 48 array files of PR #146's scratch output were hashed as bytes only (list at the end of "Runs").

## Question
PR #146 measured that none of T0 to T3 keeps every DeltaNet head's decay a = exp(-A softplus(ar + dt_bias)) within its bar on real Qwen3.8-27B abliterated activations (best: T3, 6,391 of 23,040 cells and 1,513 of 2,304 heads fail). Does any of the changes its section 5 names, registered here as arms U1 to U4, meet the same bar on the same recorded activations?

## Hypothesis
H (falsifiable): arm U3 (per-head cA exponent, internal scale 2^-20, softplus domain widened down to -16) meets the acceptance threshold on every one of the 23,040 (layer, head, prompt) cells, and U1 and U2 do not.
Each of the four arms gets its own PASS / FAIL; H is judged on U1, U2, U3. Any combination of verdicts is a valid outcome and is reported as measured.

Expectation written before the run, from arithmetic only (not part of H, reported against the result either way): the error of a in the key x is at most (1/e) per unit of x for every A (sup over x of A sigmoid(x) exp(-A softplus(x)) = (A/(1+A))^(A+1) < 1/e), so a floor key at step 1/256 alone costs at most 0.00144 of the 0.00195 per-token bar. In U1 to U3 a second floor of up to 1/256 in g sits on top for g >= 1 (the coarse exp table), in the same direction, so U1 to U3 may fail the per-token bar on tokens with g >= 1 (two floors together can reach about 0.0029). U2 is expected to fail on large-A heads whose x goes below -8 (clamp error A x 1.5e-4 in g for layer 44 head 29 at its committed x minimum). U4 has one floor key only and is expected to pass.

## Setup (fixed now, all as PR #146)
- Checkpoint, forward, logging hook, prompt set S10 (10 prompts, 1,461 tokens, `prompts-e2e.json` sha256 47aa61b46e142382ffa58b88f918df6ec63f1158629df5938ec00961a5242cfc), 48 DeltaNet layers x 48 V heads: exactly PR #146's PREREG "Setup" and "Prompt set". Nothing is re-chosen here.
- Reference: x = ar + dt_bias, g = A softplus(x) (`np.logaddexp(0, x)`), a = exp(-g), float64, by PR #146's `decay_tables.float_decay`, imported unchanged.
- Activations: the ar arrays PR #146 recorded (see "Runs" for which copy and how it is checked).

## Arms (integer emulation, fixed now)
Common front end of every arm, as T3: ar_int = floor(2^12 ar); dt_int = RNE(2^12 dt_bias); X = ar_int + dt_int (x at 2^12); softplus row r = floor(X / 16) (the v1 row grid, step 1/256).
Per-head exponent rule (U1 to U3): e_h = the largest e in 1..24 with RNE(2^e A_h) <= 4,095; cA_h = RNE(2^(e_h) A_h); the shift of the product floor is s_h = e_h. This is DESIGN 5.0's weight rule applied per head instead of per layer. From the committed A values it gives e_h in 4..20 and cA_h in 2,051..4,091 (every head keeps 12 bits).
Internal scale rule (U2 to U4): G = the smallest integer with 2^-G <= the smallest per-head median g in PR #146's committed `domain.json.gz` (1.72e-6; 2^-19 = 1.91e-6, 2^-20 = 9.5e-7). **G = 20.** Fixed from the committed medians, not from any error.

- **U1** (T3 + per-head exponent): sp = softplus-f12[clamp(r + 2048, 0, 4095)] (the pinned v1 table), or sp = X if X >= 8 x 2^12. g_int = floor(cA_h sp / 2^(e_h)). If g_int < 4,096: a_int = RNE(2^12 exp(-g_int / 4096)) (T2's fine table); else a_int = coarse12[clamp(floor(g_int / 16) + 2048, 0, 4095)] (PR #146's v1-layout coarse exp table). a = a_int / 2^12. No reject.
- **U2** (U1 + scale 2^-20 for the softplus output, g, the fine exp key and the output a): sp = SP20[clamp(r + 2048, 0, 4095)], SP20[i] = RNE(2^20 softplus((i - 2048) / 256)) (same 4,096 rows and row grid as v1, output at 2^20); or sp = 2^8 X if X >= 8 x 2^12. g_int = floor(cA_h sp / 2^(e_h)) (g at 2^-20). If g_int < 2^20: a_int = RNE(2^20 exp(-g_int / 2^20)) (fine table keyed on g_int directly: **2^20 = 1,048,576 rows** instead of 4,096); else a_int = coarse20[clamp(floor(g_int / 2^12) + 2048, 0, 4095)], coarse20[i] = RNE(2^20 exp(-(i - 2048) / 256)). a = a_int / 2^20. No reject. X stays at 2^12 (the stream scale is not changed).
- **U3** (U2 + softplus domain widened below): the softplus table has 6,144 rows over [-16, 8) on the same grid: SP20w[j] = RNE(2^20 softplus((j - 4096) / 256)), key clamp(r + 4096, 0, 6143): **2,048 more rows**. Everything else as U2. Why a wider domain and not sp = exp(x) passthrough: exp(x) is itself a table over the same x range, so the passthrough costs the same rows plus a second table kind and a branch, while widening keeps one table and one lookup. Why -16: the committed minimum of x is -15.11; below -16 the clamp error in g is at most A softplus(-16) = 139.4 x 1.13e-7 = 1.6e-5 for the largest A in the model.
- **U4** (per-head decay table keyed on x, one lookup): for head h a table D_h of 12,288 rows over x in [-16, 32) on the same grid; row j covers floor(X / 16) = j - 4096 and holds D_h[j] = RNE(2^20 exp(-A_h softplus((j - 4096 + 1/2) / 256))), the value at the middle of the row, computed in float64 from A_h = exp(A_log) (no cA cell, no product, no g). Key below row 0: clamp to row 0 (same bound as U3). Key above row 12,287: reject (fail closed; counts as a failure of its cell; |dt_bias| < 32 is the dt class of DESIGN 5.0). a = D_h[j] / 2^20. **Size: 12,288 rows per head, 589,824 per DeltaNet layer, 28,311,552 for the 48 layers; one lookup per head per token.** The table is derived from a weight, so in a build it is committed with the model (conversion output), not a public format table.

Table rows: the 4,096-row and 6,144-row tables are generated with the pinned integer generator's functions (`tables.expq`, `tables.logq`, `tables.nearest`, as PR #146's `coarse_exp` and `softplus_grid`). For the 2^20-row fine table only the rows used are produced; if the integer generator is too slow for the budget they are computed as RNE of float64 (`numpy.exp`, `numpy.rint`) and a fixed sample of at least 10,000 used rows (the smallest, the largest and evenly spaced used keys) is checked equal to the integer generator's value; the count of mismatches is reported and a mismatch voids nothing but is disclosed next to the verdict. U4 rows are float64 by definition.

Descriptive only (no verdict, labelled as such): for the best arm (fewest failing cells; ties to the lower number) the error split by source as PR #146 section 4 (cA rounding alone, the softplus table alone, the g floor and exp tables alone, output rounding alone, each with the other steps in float64; for U4 the row step alone and output rounding alone); failing heads per layer and the worst heads; and the per-arm cost counted from DESIGN 5.3 and 7 (extra committed cells per head, table rows, lookups per head per token), counted, not built.

## Metric
Unchanged from PR #146. For each arm, DeltaNet layer l (48), V head h (48), prompt p (10), over the tokens t of p, in float64 from the integer outputs:
- e_tok(l,h,p) = max_t |a_arm(t) - a(t)|, and the median over t.
- P(t) = prod_{s <= t} a(s), P_arm likewise; e_cum(l,h,p) = max_t |P_arm(t) - P(t)|; also max_t |ln P_arm(t) - ln P(t)|, descriptive.
- Reject count (U4 only can reject).
Computed with PR #146's `decay_tables.cell_metrics`, imported unchanged. Spread: medians and maxima over tokens and over cells, counts with their n.

## Acceptance threshold
Unchanged from PR #146. An arm PASSES iff on every one of the 23,040 (l, h, p) cells: no rejected lookup, e_tok <= 2^-9, and e_cum <= 0.01. Otherwise it FAILS, and RESULTS names the failing layers and heads with counts out of 23,040 cells and 2,304 heads.
H holds iff U3 PASSES and U1 and U2 FAIL.

## Kill criterion
- Lane hard stop 2026-11-13T04:00Z (wall clock, includes queue time). Not moved after registration.
- Input rule: the arrays in "Runs" are used only if every file's sha256 equals the list below AND PR #146's unchanged `decay_tables.py eval` on them reproduces PR #146's committed `runs/eval/cells.csv.gz` and `runs/eval/domain.json.gz` (equal decompressed bytes). If either check fails, the arrays are not used; `record.py` is then rerun unchanged under the host heavy gate only if the slot is granted by 03:05Z with MemAvailable >= 10 GB (forward stop 03:45Z by pid, RSS over 14 GB stops it); otherwise the lane ships with NO verdict for any arm, labelled KILLED (no input), and says so.
- If the registered evaluation of the four arms has not finished by 03:40Z it is stopped by pid and the arms that finished are reported; an arm that did not finish has no verdict.
- No arm, table constant, bar or prompt is changed after this commit. A defect found in the arm code after the registered run is reported as a defect with both outputs; the first output is not deleted.

## Runs
- One deterministic evaluation (n = 1 per token; every number is a deterministic function of the recorded arrays). Determinism check instead of repeats: the registered evaluation is run twice and the two per-cell outputs must be equal (decompressed bytes). Variance is reported over tokens, prompts and cells as in "Metric", n stated each time. No exclusions: every token of every prompt, 48 layers, 48 heads, 4 arms: 92,160 cell rows.
- Completeness: the input goes through PR #146's `decay_tables.load_layers` / `suite.py` (refuses anything but the full registered suite), and the summary refuses a per-cell file that does not hold each (arm, layer, head, prompt) exactly once with the registered token count and finite values (a rejected U4 cell excepted).
- Debug before the registered run: only on synthetic heads (A, dt_bias and x drawn between each head's committed minimum and maximum in `domain.json.gz`, numpy seed 155) and on PR #146's debug fixture ("The capital of Italy is", not a suite prompt). No U arm is evaluated on any registered array, at any size, before the registered run.
- The provenance check (PR #146's own T0 to T3 evaluation on the arrays, compared with its committed output) is not a run of this suite and happens before the registered run.
- CPU, cores 0 to 5, under 2 GB; host shared and loaded (does not affect deterministic results).
- Input arrays: the output of PR #146's registered `record.py` run (2026-11-12T21:20Z to 21:44Z, code `513ab974`), still present in that lane's scratch directory `run/ar/` outside the repo, 48 files of 564,986 bytes. sha256, recorded here before any use:

```
c2f30790d52eb90b3e88a44f3a4217c359a35563af7403d8202a601597a63139  ar-L00.npz
a4be1c97c196be4a731229c87b1532ca2fa3fa41d7393c8dd00f11fa7d9365ab  ar-L01.npz
21250cc9658a94630b2aaeda7ac7767a92d130eb1ab4723db746cda05df77561  ar-L02.npz
0a1daa40898198e38ac2acd0553b0c9bf8569051b6eabc46de0e9fc1b961430b  ar-L04.npz
496ca3cec4370b588bd517546a5e00954578562dc319a8832c1572612b18fc43  ar-L05.npz
b20b23ab37502e59fc46defcf21c19c197282d8495ccde6d44185fb2f3b76234  ar-L06.npz
b6bbd9f7366206da82073fa8c4ef051d00f3b6f46db19f07835f9977cb8ab6dd  ar-L08.npz
5d67cdbe29c81aded01f449ed39cefa4852f2279d0c466e806cf537900f01403  ar-L09.npz
da37938b5a2692d9a90679d34ec1603152f6d6ef696c625c17585a2f6578e973  ar-L10.npz
45ce83fff963c665e52959fc60b54f4cdb7bec646853a533ab835d4633e70254  ar-L12.npz
31be459cb7665c7bd0464201eb154d98044f8ce0ef42d41940eee2cc4cc36095  ar-L13.npz
50373c08bc6b885509a048a85a55136d3eb6c2be2d274d2b8fc52ac5e70ac0f0  ar-L14.npz
fb02bcb4dc7c2548f9fc38a04ca6d103cbffefc7f3ffaeb17e224679df3f3295  ar-L16.npz
8b96439f0a9bacb32cc771282aae77a8e602b97223c6fb53fca81732f40ccd57  ar-L17.npz
e515b4b803d3614e0191889844029e19c0e497b6ba8854d18fad8738bb70aa93  ar-L18.npz
56339e3197ef2a79e16319effb841f16249ebe09f490a88cfd61aba3b3c4bedd  ar-L20.npz
cf26c91e91b83d78eb8e67d7945b0788a632c6adb64202dcd540dcfdb0773511  ar-L21.npz
053f991ba5ee9af4f4b56da10829c9128821fd442bd4da9f26dc52edaa62f7b0  ar-L22.npz
27fb9511c012d04686d47d5ae18d098ce4709c29a02dea6de042381cb7dc3d0a  ar-L24.npz
c322930fb4dc10364c9972878b4ab65a2f0adae62f351ae5ff123c6a0b69b5a7  ar-L25.npz
da74937c895178773b4b9af5c8112d11cce6b0c4e72bf0b35cf402d36bbd0f97  ar-L26.npz
eb7745442be0b26ba6c0a4995086d08f777ccdbcab7ec9bb3441fd7c5ac6f9d9  ar-L28.npz
1aebb639515077d9cb53960b0ae123bb0777e0e13c65e24ce03dada69807dd50  ar-L29.npz
5c752e899d3a1b76769763acf243b0283132a7f6eb6ae7ac7b73fb6506afb45d  ar-L30.npz
4d4c813cdfd6c7dc2fd0d5802ad052b25a0445f12531c1ae5bde7bc2a3880ab6  ar-L32.npz
1550d8a0a795d11be3dd84197b4e942fad1268f8f81e330fe385ce6dbb479fc2  ar-L33.npz
3af5394809b8aa9492353d673d1990ae3654e3c192fca32a8ed03349232ea6c1  ar-L34.npz
a62bb19c84ad64cb123c94d182e7864b6735d62f2778c17afbe028717f79d342  ar-L36.npz
72c2ee2ce7a6dad6b7ceea8fc345111f7794e1da77bf565e7d969fe1dd3fd9db  ar-L37.npz
80c6d19661d2c42171799e10043f160cf96818b6aa6202eb913bd41f897519be  ar-L38.npz
d956700d28613ccb21141af323fe9126ae3dd514c6a00087a22b8322f2fcac14  ar-L40.npz
27864f7342025866ff734c707b1ba95d0c7f043bf1d791ae268d5bcb445b51d4  ar-L41.npz
9557ccd9615a3e07863f5c3c98d3acfcc8d1dfd1f65646c9a9b1e10ac42066f5  ar-L42.npz
95c94fcab76595d19e0c22475512d9c8089e0e42c19ad9a4fe21b8c4d1307f9a  ar-L44.npz
1229e8ed51ed5fd4b675c456b95a146c1f38c53127addf31b3d115fa8f3bf817  ar-L45.npz
65701b22c4779b9deadd6d40b5f0394751f27eca081904b07cc5d089d79bd1cb  ar-L46.npz
e8025d4ed6e4ab371707f1e7302e58f6b6c2c286c8d8a3b0cc5dcab5b85fb0bf  ar-L48.npz
81d3a9ba955c7ed9e1c538cd1fb338707963b7f202c114491abbae2e5198cd4e  ar-L49.npz
f25f82da4595baedfa9e323825fda016f7aa60aa5d464c8cd64b15b45a9cd961  ar-L50.npz
c79bed122d51cbd60331afb898954a2c7903ff5cb4ebc11df7db96d46e91db55  ar-L52.npz
79b9d617d3811ef7cc292ceff2a1abeb20c09379d1a7c23b878f2cabfa39dac7  ar-L53.npz
27638c8eaae98a7ccdc5cc6cb98689830adc5cea02d4acd4efdc7b38658be518  ar-L54.npz
5e6fb42c63a7502bfc7fd36423ca69857c7a9b5af8ef3cdb62ae98ac1d076538  ar-L56.npz
351a1024877e376489fcd9fa78db467e6d8c18080e74f8002558bc384682e6b6  ar-L57.npz
1af1200a89d48666a8af2e1732a30174ac16e662f967183b218c73b7e70b5f57  ar-L58.npz
50cf79b8512adaa3245b144e8b88040adc852621781a52d6c12eacf85b4404aa  ar-L60.npz
51604fc374a1ccf82945b39653d4719d36f4cf9996eb610ed60ad7db08ff229b  ar-L61.npz
95a4815a990c056e0fdeddf901588038ff52e77b0009911170172d350b863d0c  ar-L62.npz
```

The arrays are not committed by PR #146 (about 27 MB); a reader without the scratch copy reproduces them with PR #146's `record.py` (24 min, pinned checkpoints) and can compare against this list only if numpy writes the same bytes; the content check against PR #146's committed per-cell output is the portable one.

## Prior art
In this repo: PR #146 (`experiments/20261112-136-deltanet-decay`: T0 to T3 all FAIL; section 4 attributes the remaining T3 failures to the g floor at 2^-12, the per-layer cA exponent and the softplus rows; section 5 names the three changes registered here and says they were not measured as arms; its F' sweep showed a finer internal scale with the per-layer cA does not close it); DESIGN M3 5.0 / 5.3 / 8.2 (softplus lookup, cA product with one exponent per tensor, exp lookup, the fine g table suggestion); PR #67 (`research/operators/qwen_ops`: table format v1, pinned softplus-f12 / f14 / f16, the integer generator); PR #68 (layer-0 weight ranges); PR #124 (end-to-end agreement with float gates at 2^-18). Outside: zkLLM (Sun et al. 2024, tlookup: non-arithmetic functions by lookup with the input split into digits and one small table per digit, the standard way to get a fine exp without a 2^20-row table; not an arm here, named as the alternative realisation of U2's fine table in the cost section); EZKL and Jolt (fixed-domain lookup tables, out-of-domain inputs range-reduced or rejected); Mamba / Gated DeltaNet reference kernels (softplus with linear passthrough above a threshold). What is new: the first registered measurement of whether a per-head exponent, a finer scale and a wider softplus domain, or one per-head table keyed on x, keep every head's decay within a half-BF16-ulp bar on the real 27B model's activations.

## Amendments
(empty at registration)
