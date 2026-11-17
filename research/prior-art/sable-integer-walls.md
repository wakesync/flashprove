# Desk note: what the Sable prover does about our five Qwen integer-lowering walls (issue #213)

Experiment id `20261117-213-sable-walls` ([PREREG](../../experiments/20261117-213-sable-walls/PREREG.md)).
Base: main `37576f43d3eeeca7fcfe7543b2e3e87add450b47`. Written 2026-11-17 UTC.

**This is a desk read, not a measurement.** Nothing was run, built or measured. Nothing from Sable was
cloned, installed, imported or run, and none of its code is copied here beyond short quoted
excerpts with their source.

Sources, and only these:

- the paper: arXiv 2611.14083v1, "Sable: A Small-Field Sumcheck Argument for Bit-Exact Inference of
  Large Language Models" (submitted 10 Nov 2026), HTML version. Sections read: 5, 6, 11.7, 11.8 and
  11.9 (the issue names 5, 6, 11.8 and 11.9), plus 1.2, 3.1, 3.6, 4, 7.5, 7.6 and 12 to fill the
  differences table;
- four files of the repository moonmath-ai/Sable at commit
  `0bc6b549afef2f8eb9b8bc4c2f24d6e554dbaacb` (commit message "release 1.0.0", 2026-11-03), read through
  the GitHub contents API: `zk/model.py`, `zk/tables.py`, `zk/llm.py`, `scripts/fo_domain_scan.py`.

**Every statement about Sable below is from public source, not verified by us.** Its numbers are its
authors' numbers, quoted. Nothing here says anything about Sable's soundness. Paper citations are
"P" plus a section; repository citations are "file:lines" at the pinned commit. Our side is cited on
main by path and line.

## Answer in three lines

1. **Walls 1 and 3 (MLP input and both pre-norms above the 2,047 class):** Sable does not have a fixed
   public class for a norm output. It requantizes every residual row to 8 bits with a per-row
   power-of-two exponent, normalizes with a 16-bit rsqrt table so the output is at most 127 by
   construction, and folds the RMSNorm gain (and a random rotation) into the next weight matrix. That
   mechanism uses only model-independent tables and fits the Goldilocks field, so it is compatible in
   principle; it is a different statement from ours. Sable's reported accuracy (greedy agreement with
   BF16 of 82.4% to 88.7% on WikiText-2, on its own three models) uses a different metric, reference,
   models and data from our registered token bar, so the numbers are not comparable. They motivate
   caution. They are not a measured failure of our bar, and they do not isolate what the 8-bit
   formats contribute. Candidate for a future registered arm, not a recommendation.
2. **Wall 2 (SiLU inputs outside the v1 domain):** Sable faces the same kind of wall and handles it
   by (a) sizing the SiLU table's input scale per model from calibration with a 25% margin and (b)
   making the integer function undefined outside it, so the honest prover aborts. It does not
   saturate. Compatible with our field; the table contents become per-model (still public and fixed
   per commitment).
3. **Walls 4 and 5 (head dimension 256, partial rotary):** Sable does not face them. All three of its
   models have head dimension 128, its prover asserts `dh == 128`, and its RoPE rotates the whole
   head. Nothing carries over; this note recommends nothing for these two walls.

## The five walls, one record each

### Wall 1. MLP input above the 2,047 class

**Our side.** The M3a-MLP statement takes the MLP input m = RNE(2^12 x norm output) as a public word
in the class |m| <= 2,047; the class comes from upstream's Maverick norm, which clamps to 12 bits,
and Qwen's RMSNorm has a learned gain (1 + w), so at scale 2^12 its output does not fit
(`experiments/20261112-132-int-mlp-e2e/RESULTS.md:32`, `:44`; `research/operators/qwen_m3/bounds.py:53`).
The class is exceeded in every measured layer, maximum 142,651 inside the cutoff
(`docs/qwen-port.md:111-113`). The later registered integer-MLP token test failed at 1,423 of 1,461
(`experiments/20261112-132-int-mlp-e2e/runs-resume150b/RESULTS.md:7`).

**Does Sable face it?** Not in this form. Sable has no fixed public class for a norm output.

**What Sable does** (from public source, not verified by us):

- Before every matrix product a residual row is requantized to integers in [-127, 127] with one
  power-of-two exponent per row, "the least exponent at which the row fits", and the rule "never
  clips" (P 5.1, P 5.2 `Requant8`). The proof checks minimality of the exponent with a selected index
  and two 15-bit limbs (P 6.2).
- `NormScale` then computes the row's sum of squares, writes it as a 16-bit mantissa times an even
  power of two, and multiplies by a 16-bit rsqrt table entry, giving |q'| <= 127 "by construction";
  "This is RMSNorm with the gain vector fused into the next weight matrix" (P 5.2;
  `zk/model.py:185-194`, which checks `qp.abs().max() <= 127`; table `RSQ`, `zk/tables.py:17`).
  The row exponent E_h enters the next shift, so later shifts are per row (P 5.3 step 7,
  `k_g = kappa_g + max(E_h, K_gl)`).
- The checkpoint is multiplied by a fixed random orthogonal matrix from a public seed "as in
  QuaRot", and each RMSNorm gain and the rotation are fused into the adjacent weights; weights are
  8-bit with per-column power-of-two exponents (P 5.7; gate and up weights built from
  `g2[:, None] * gate_proj` in `zk/model.py:848-857`, attention input in `zk/model.py:654-659`).
- The residual stream itself is 24-bit, A = [-2^23, 2^23), with f_h fractional bits that the
  quantization program may lower per model (Qwen3-32B: 10 to 8) (P 5.1, P 5.7).

**Compatible with Goldilocks and fixed public tables?** Yes in principle. The tables this mechanism
uses (ranges, powers of two, the 8-bit range, rsqrt on 16-bit mantissas) do not depend on the model.
Sable's tight no-wrap budget comes from its 31-bit field (P 6, Lemma 6.1); in a 64-bit field the same
relations have more room, not less. The rotation and gain fusion change only the committed weights.

**What it would cost in our statement** (qualitative, not counted): m stops being a public 12-bit
class word at a fixed scale and becomes an 8-bit committed value with a committed per-row exponent;
each consumer's shift becomes row-dependent, which needs a per-row shift-regime lookup and a
minimality witness per row; the norm becomes a new gadget (sum of squares, mantissa, rsqrt lookup);
the committed weights become rotated and gain-fused. Qwen3.8-27B's norms use a zero-centred gain
`x * (1 + w)` (`research/ports/qwen3.8-27b/FEASIBILITY.md:57`); Sable's models fold a plain gain w,
and our feasibility note says `1 + w` "folds the same way" (`research/ports/qwen3.8-27b/FEASIBILITY.md:69`),
which this note did not check against Sable's code. The precision goes down from 12 to 8 bits per
entry. By Sable's own attribution, "unrounded MLP input" would remove 12% (paired 95% interval 1 to
21) of its Qwen3-32B excess log perplexity over BF16, measured on the first 24 WikiText-2 windows
(P 11.8, Table 15, whose caption defines the figure as a share of excess log perplexity), and its
overall greedy agreement with BF16 is 86.3% (Qwen2.5-32B) and 82.4% (Qwen3-32B) on WikiText-2
(P 11.8, Tables 12 and 14). Those are different metrics, references, models and data from our
registered bar (>= 99% top-1 against float64, teacher-forced, on an abliterated Qwen3.8-27B
checkpoint: `experiments/20261112-132-int-mlp-e2e/PREREG.md:26`, `:36`), so they are not comparable
numbers. They give no reason to expect an 8-bit input to clear a bar that our 12-bit path
missed; that is an inference that motivates caution, not a measured failure of our bar, and Sable's
agreement figures do not isolate what its 8-bit norm output or matrix inputs contribute.

### Wall 2. SiLU inputs outside the v1 domain

**Our side.** The v1 table domain is [-8, 8), 4,096 rows at F = 12
(`research/operators/qwen_ops/tables/manifest.json:225-233`). Six gate inputs left it in layers 21 to
26; the numerical run saturated them, the v1 proof rule would reject them
(`experiments/20261112-132-int-mlp-e2e/RESULTS.md:34`; `docs/qwen-port.md:113-114`).

**Does Sable face it?** Yes, the same kind of wall: its SiLU table also has a bounded input domain.

**What Sable does** (from public source, not verified by us):

- Table `SILU` holds (c + 2^14, tau_SiLU(c)) for |c| <= 2^14, 2^15 + 1 rows; tau_SiLU is the SiLU of
  c x 2^eG in units 2^eA, correctly rounded, clipped to 16 bits (P 5.2; `zk/tables.py:19`, `:90`,
  `:142`; `zk/model.py:34`, `:499-509`). The gate shift is at most 15 (`zk/model.py:38`).
- The input unit eG and output unit eA are global per model, fixed by calibration:
  `eG = ceil(log2(gate_max * 1.25 / SILU_CMAX))` (`zk/model.py:933-934`); the paper says "the SiLU
  range, for instance, is set 25% above the largest gate input seen" (P 11.9). The calibration also
  runs every vocabulary token at position 0 and widens eG, eA to cover them (P 5.7).
- Outside the domain the function is undefined: "|c| <= 2^14 with gate shift k_g <= 15" is one of the
  conditions, and "an honest prover detects the violation and aborts" (P 5.7, "Where F_O is
  undefined"; `zk/model.py:1061` checks it, `zk/model.py:1044-1062`). The table's own domain is the
  proof's bound (P 6.2, "MLP gate").
- Its scan (`scripts/fo_domain_scan.py:1-13`, `:79-81`) reports zero undefined sequences on 3.45 million
  tokens of real text and 160 adversarial sequences for all three models (P 11.9, Table 16). The
  paper adds: "This does not show that no input reaches a condition" (P 11.9).

**Compatible with Goldilocks and fixed public tables?** Yes for the field. For tables: Sable's table
contents depend on per-model constants (eG, eA), are pinned in the statement digest h_circ and are
committed as fixed units, not recomputed by the verifier (P 7.5, P 7.6). FlashProve's verifier
computes its public tables itself and compares their digests from the parameter file
(`verifier/docs/parameter-file.md:279`, `:336`), and the parameter file already carries a gate-table
input resolution `eg` (`verifier/docs/parameter-file.md:234`, `:265`). So a per-model input scale is
expressible on our side as a parameter the verifier recomputes from, not as a committed table; this
note did not check that `eg`'s allowed range (4 to 7) would cover Qwen.

**What it would cost in our statement.** Two different options, both existing somewhere: Sable's
(per-model scale with margin, abort outside: a refusal on rare inputs) and upstream FlashProve's
gate clamp `gcl`, under which the table is constant beyond its ends and saturation is the proved
function (`verifier/docs/parameter-file.md:269`). Sable's choice keeps the proved function equal to
the table function and moves the problem to refusals; a wider domain at the same resolution means
more table rows. Which of the two our Qwen statement should use is not decided here.

### Wall 3. Both pre-norms above 2,047

**Our side.** Both pre-norm outputs at 2^12 exceed 2,047 in every measured baseline layer (mixer
input up to 438,415, MLP input up to 232,871); clamp arm C met the fidelity bar on 0 of 27 layers,
widened arm W on 12 of 27 with 2,108 out-of-class entries; no registered arm verdict
(`experiments/20261112-148-norm-class/RESULTS.md:11-14`; `docs/qwen-port.md:118-126`).

**Does Sable face it?** Not in this form, for the same reason as wall 1: both pre-norms go through
the same `Requant8` + `NormScale` path (P 5.3 steps 1 and 6), with the input-norm gain fused into
the QKV weights and the post-attention gain into gate and up (`zk/model.py:654-659`, `:848-857`).
Qwen3's QK-norm is the same requantize-and-normalize applied per head row, with the gain applied as
an 8-bit public column (P 5.6, P 6.6).

**What Sable does that our arms did not try.** Our three arms were a clamp at the fixed scale (C), a
wider class at the fixed scale (W) and a smaller fixed scale (S). Sable's choice is none of them: a
**dynamic per-row power-of-two scale chosen before the norm**, an 8-bit norm output, and the gain
moved out of the norm into the next matrix, plus a rotation to spread outliers across channels
(P 5.2, P 5.7). This is a design observation, not evidence that it would pass our bar.

**Compatible?** Yes, as for wall 1. **Cost:** as for wall 1, applied to both norms; the mixer side
also feeds the DeltaNet layers, which Sable does not cover (issue #213, "Why this is on the shortest
path"), so its effect on those 48 layers is unknown.

### Wall 4. Head dimension 256

**Our side.** Qwen3.8-27B's full-attention layers have head dimension 256
(`research/ports/qwen3.8-27b/FEASIBILITY.md:45`). At dh = 256 with clamp 2,047 the score bound N4
fails, and the KFD lookup width is hit first; there is no drop-in admission change
(`research/operators/qwen_ops/DH256-ROTARY.md:6-10`, `:98`, `:253`).

**Does Sable face it?** No. All three of its models have head dimension 128 (P 5, P 5.6;
`zk/model.py:432-435`), and its prover requires it: `assert dh == 1 << TILE` with `TILE = 7`
(`zk/llm.py:38`, `:101`). The paper's score bound, |acc| <= 128 x 180^2 < 2^22, is stated for that
head dimension and for 9-bit RoPE outputs (P 5.4).

**Related observation, not a carry-over.** Sable keeps attention scores small by keeping queries and
keys at 8 bits (9 after RoPE). That is the same direction as our narrow q/k clamp alternative
(`research/operators/qwen_ops/DH256-ROTARY.md:10`), and Sable's own attribution says 12-bit queries
and keys would remove 37% of its Qwen2.5-32B excess log perplexity over BF16 on the WikiText-2 test
split (P 11.8, Table 13, whose caption defines the figure as a share of excess log perplexity) but
need a score rounding step before the exponential table, at an estimated 1.30x to 1.68x proving time
by its cost model (P 11.8). This note
does not check whether Sable's tables and bounds would hold at dh = 256.

**Compatible / cost:** not applicable. Negative result for this wall; nothing is recommended.

### Wall 5. Partial rotary

**Our side.** RoPE on 64 of 256 dimensions, theta 10,000,000, rotate-half layout
(`research/ports/qwen3.8-27b/FEASIBILITY.md:48`); the merged design proposes a new `rp = 2` mode with
R = 64 and a pinned Q256 generator, with no build green light
(`research/operators/qwen_ops/DH256-ROTARY.md:9-10`, `:178`).

**Does Sable face it?** No. `RoPE8` pairs element j with element j + dh/2 across the whole head
(`zk/model.py:1005-1006`; prover domain `zk/llm.py:2818-2866`), and its tables use the frequencies
theta^(-2j/dh) over all dh/2 pairs (`zk/model.py:524-535`). The model configuration has no partial
factor (`zk/model.py:420`).

**Related observation.** Sable's RoPE, exponential and SiLU tables are "correctly rounded": computed
in double precision, with every entry within 1e-4 of a rounding boundary recomputed in 60-digit
arithmetic, so they "do not depend on the platform's floating point" (P 5.2). That is a table
generation method, alongside the integer Q256 generator our design chose and the binary64
alternative it rejected (`research/operators/qwen_ops/DH256-ROTARY.md:187`, `:195`). It does not
address partial rotary itself.

**Compatible / cost:** not applicable. Negative result for this wall; nothing is recommended.

## Differences in what is proved

So that nobody reads Sable as a drop-in. Sable column: from public source, not verified by us.

| | FlashProve (main) | Sable (paper / repo at the pin) |
|---|---|---|
| What a proof states | checked tokens r+1..e of a window, under exact match or clipped gap; if e = T, also that the next token is the top choice (`docs/architecture.md:34-37`, `:47-56`, `:66-70`) | the whole reply: every generated token from the prompt, the stopping rule (no earlier stop token; last is a stop token or the length limit), and sampling from a statement-fixed seed at temperature > 0 (P 3.6, Definition 3.3) |
| Zero knowledge / weight hiding | proofs and public files masked by default, apart from a declared list (`docs/architecture.md:84-87`) | not zero-knowledge; the paper estimates about 1.9 x 10^4 proofs reveal the weights, so it targets open-weight models (P 1.2, P 4, P 12) |
| Field | Goldilocks, p = 2^64 - 2^32 + 1, cubic extension (`docs/architecture.md:252`) | KoalaBear, p = 2^31 - 2^24 + 1; challenges in degree-4 and degree-8 extensions (P 3.1) |
| Lookup tables | public tables the verifier computes itself and compares against digest lines in the parameter file (`verifier/docs/parameter-file.md:279`, `:336`) | one tagged table of 2^26 rows; exp, SiLU and RoPE contents depend on per-model constants, are pinned by the digest h_circ from a registry, and are committed fixed units the verifier does not evaluate (P 6.1, P 7.5, P 7.6) |
| Number formats at the walls | Qwen M3 design: public norm-output class 2,047 at scale 2^12 (`research/operators/qwen_m3/bounds.py:53`) | residual 24-bit; matrix inputs 8-bit with a per-row exponent; weights 8-bit with a per-column exponent; Q, K, V static per-head exponents (P 5.1) |
| Proof size | 4,149,564 bytes, upstream small synthetic example only; no Qwen proof exists (`research/gpu/README.md:38`; `docs/qwen-port.md:6-8`) | 134.8 to 345.7 MiB for Qwen2.5-32B at its three shapes (P 11.7); 106 to 477 MiB across its three models (P 4) |
| Prover hardware and time as reported | one rented H100 80GB, host CPU Xeon Platinum 8480+: the upstream small synthetic example only, one request proved in about 3 s (plus or minus 1 s, from file timestamps), n = 1, cold run; no Qwen proof exists, so there is no Qwen prover time (`research/gpu/README.md:7`, `:16`, `:18`, `:33`, `:44`; `docs/qwen-port.md:6-8`) | theirs, not verified by us: one NVIDIA RTX PRO 6000 Blackwell GPU (96 GB) in a host with a Xeon 6776P and 214 GB of memory; Qwen2.5-32B, all 64 layers: 92.5 s for one sequence of 4,096 tokens, 253 s for four such sequences, 398 s for one sequence of 16,384 tokens; Qwen3-32B 121.8 s and Qwen3-30B-A3B 84.7 s for 4,096 tokens (abstract; P 11.1). Different hardware, models and statement: not comparable with ours |
| Models covered | target Qwen3.8-27B: 48 Gated DeltaNet + 16 attention layers, dh 256, partial rotary; not proved (`docs/qwen-port.md:38-41`) | Qwen2.5-32B and Qwen3-32B (64 layers each), Qwen3-30B-A3B (48 layers); all dh 128, full rotary, no DeltaNet (P 5, P 5.6) |
| Out-of-domain inputs | v1 SiLU table rejects; a norm output outside its class cannot be admitted (`experiments/20261112-132-int-mlp-e2e/RESULTS.md:34`; `experiments/20261112-148-norm-class/RESULTS.md:81`); upstream gate clamp `gcl` saturates (`verifier/docs/parameter-file.md:269`) | the integer function is partial; listed conditions; the honest prover aborts; zero hits on its scan sets (P 5.7, P 11.9) |
| Accuracy reported | Qwen integer-MLP path: 97.40% top-1 against float64 on 1,461 teacher-forced positions, registered FAIL (`experiments/20261112-132-int-mlp-e2e/runs-resume150b/RESULTS.md:7`) | greedy agreement with BF16 on WikiText-2: 86.3% (Qwen2.5-32B), 82.4% and 88.7% (Qwen3) (P 11.8, Tables 12 and 14); not comparable with ours |

The paper's related-work section also describes FlashProve (P 2, "Concurrent work"). Those
statements are the paper's and are not reviewed here.

## What was confirmed from the source, and what is only quoted

The issue quoted figures from an earlier lane that read only the introduction and related work.
Checked against the source:

- Qwen2.5-32B, Qwen3-32B (QK-norm) and Qwen3-30B-A3B covered: **confirmed** (abstract, P 5, P 5.6).
  Clarification of the issue's wording ("all 64 layers of ... Qwen3-30B-A3B" can be read that way):
  Qwen3-30B-A3B has 48 layers (P 5.6, "L = 48"); the two 32B models have 64.
- 24-bit activations: **confirmed** as the residual range A = [-2^23, 2^23) (P 5.1).
- 8-bit matrix-product inputs: **confirmed** (P 5.1).
- 86.3% greedy agreement with BF16 on WikiText-2 and perplexity 8.3% higher: **confirmed** (Table 12).
- Qwen3 within 1.6 points of BF16 on MMLU and 1.7 on GSM8K: **confirmed** as the abstract's bound;
  Table 14 gives MMLU 1.4 and 1.6 points and GSM8K 1.7 and 1.3 points (the text says 1.4).
- Paper date 10 Nov 2026 and the pinned commit: **confirmed** (arXiv submission history; commit
  `0bc6b549afef...`, "release 1.0.0").
- Sable's per-row shifts and SiLU table: **established here** from P 5.2, P 5.3, P 6.2 and the files
  above, not assumed.

All of these remain the paper's claims. None of its numbers was reproduced.

## What this note does not establish

- Anything about Sable's soundness, its numbers, or whether its code does what its paper says.
- Whether Sable's per-row requantization and normalization would keep Qwen3.8-27B's tokens: no
  measurement, and Sable's own accuracy figures are for other models, metrics and references.
- Anything about the 48 Gated DeltaNet layers, which Sable does not cover.
- Whether Sable's tables and no-wrap bounds would hold at head dimension 256 or with partial rotary.
- A cost count: the costs above are qualitative.
- A choice for our next lowering. A registered experiment would have to decide it.

## Notes on the reading

- Read only the sections and files named above. The repository's `scripts/fo_domain_scan.py` has a
  usage line that says how to run it; it was read as text and not followed.
- The paper text was read from the arXiv HTML page at the known URL; the four repository files were
  read from the GitHub API at the pinned commit and never executed or imported.
