# Per-head q/k RMSNorm as a proof constraint, bounded research prototype (issue #35)

Registration and receipts: [`experiments/20261111-35-qk-rmsnorm`](../../../experiments/20261111-35-qk-rmsnorm/). Research only. Not Qwen support, not a production verifier, no model claim.

## What this adds over what main already has

- `research/operators/qwen_ops` (PR #67) has a per-head norm: one head per proof, a bounded mean-square **table** for 1/sqrt, **unit gain, no epsilon**, and zero or low-energy vectors have **no witness**. Its inputs are prover-chosen committed cells.
- `research/operators/qwen_deltanet_m2_build` (M2) proves the **gated** output RMSNorm of a DeltaNet head with exact isqrt and 12-bit limb lookups; it is not the attention q/k norm.

New here (`qk_norm.cpp`): the attention-style **q_norm / k_norm** (RMSNorm over one head's channels, with **epsilon** and a **learned per-channel gain**), several heads in one proof in GQA shape (2 q heads share the q gain vector, 1 k head uses the k gain vector), exact integer isqrt and division with range-checked residuals and remainders (bit decomposition on the #67 product oracle, no table, no lookup), and a gain bound in the admitted statement. Epsilon gives zero and near-zero heads a witness (output exactly 0 for a zero head). Nothing cryptographically new; the isqrt-by-residuals gadget is the standard one.

## Relation (per head h, channels j = 0..D-1)

Public statement: F = 12, D in {16, 256}, the pre-norm integers `x[h][j]` in [-2^F, 2^F), gains `gq[j]`, `gk[j]` (scale 2^F, |g| < 2^(F+3)), outputs `y[h][j]` with |y| < 2^(F + D2 + 4), D2 = log2(D)/2. Verifier constants, not statement fields: m = 8, K = 45, s = K - F - m - D2, epsN = round(4^m D 1e-6 2^(2F)).

```
E      = sum_j x_j^2                                   (x pinned to the public inputs)
sigma  : 4^m E + epsN - sigma^2 = e1,  sigma^2 + 2 sigma - 4^m E - epsN = e2,  e1, e2 in [0, 2^26), sigma in [0, 2^25)
R      : R sigma + rr = 2^K,  sigma - 1 - rr = gap,  rr, gap in [0, 2^25), R in [0, 2^34)
Z_j    : x_j R = 2^s Z_j + rz_j,  rz_j in [0, 2^s),  Z_j in [-2^(F+D2+1), 2^(F+D2+1))
y_j    : g_j Z_j - ry_j = 2^F y_j,  ry_j in [0, 2^F)   (g and y public coefficients / targets)
```

So sigma = isqrt(4^m E + epsN) and R = floor(2^K / sigma) exactly, Z_j = floor(x_j R / 2^s), y_j = floor(g_j Z_j / 2^F), i.e. y ~= g x / sqrt(mean(x^2) + 1e-6) at scale 2^F. The 2^m pre-scale inside the isqrt keeps the isqrt floor error near 2^-8 relative even for a unit-spike head.

### No-wrap argument (Goldilocks p ~ 2^64)

E < D 2^(2F) <= 2^32 at D = 256; 4^m E + epsN < 2^49. sigma < 2^25 so sigma^2 + 2 sigma < 2^51; e1, e2 < 2^26; the two isqrt equations have magnitudes below 2^52, so they are integer equations and with e1, e2 >= 0 they pin sigma = isqrt(.) (sigma >= 0 by its range). epsN > 0 forces sigma >= 1 (a hostile sigma = 0 makes e1 = 4^m E + epsN, but then e2 = -(4^m E + epsN) < 0 fails its range). R < 2^34 and sigma < 2^25 give R sigma < 2^59, rr < 2^25, so R sigma + rr = 2^45 is an integer equation; 0 <= rr <= sigma - 1 pins R. |x_j R| <= 2^12 2^34 = 2^46, |2^s Z_j| < 2^(s + F + D2 + 1) = 2^38 and rz_j < 2^s, so the floor equation has magnitudes below 2^47, no wrap; the remainder range pins Z_j (a hostile x_j R outside the Z range has no solution). |g_j Z_j| < 2^15 2^17 = 2^32 (D256), ry_j < 2^12, 2^F |y_j| < 2^32: integer equation, pins y_j. All bounds are of the malicious relation (range checks), not measured honest ranges. Honest values: sigma <= 2^(M + F + D2) <= 2^24, sigma >= isqrt(epsN) >= 4194, so 2^21 <= R < 2^34, and |Z_j| <= 2^(F + D2) because |x_j| <= sqrt(E), so honest witnesses fit the ranges with margin (checked by the harness, which refuses an honest violation).

## What is public, what is bound, what is not

- **The inputs are public and pinned in-proof.** This is the opposite choice from #67 (where inputs are free committed cells). It makes the norm relation itself checkable, but **nothing ties these inputs to a q/k projection, to model weights, or to an earlier layer.** That is the M3 statement / #34 job, out of scope here.
- **The gains are public statement fields with an admitted bound.** Nothing ties them to the real model's `q_norm.weight` / `k_norm.weight` (model-input provenance, out of scope). The verifier reads gains only from the statement.
- **Which gain vector applies to which head** is fixed by the verifier (heads 0..Hq-1 use gq, Hq.. use gk).
- Not covered: Qwen's real head count (this is Hq = 2, Hk = 1), the q scale 1/sqrt(d) or rotary (separate operators), BF16 rounding fidelity, F = 14/16, real activations, production security. Research target 10 bits per round including 6 bits of proof-of-work, toy deterministic coins, no whole-proof soundness figure.
- Complete malicious proofs are rejected by an equation check with a large margin, not a low-probability query round; they show each constraint exists and is wired to the right cell, not that the protocol reaches its security target. No grinding attack was attempted.

## What the verifier recomputes

From the statement and its own constants: the whole relation list (every coefficient and target, including the gains as coefficients and the public x and y as targets), the configuration text (`operator-family qwen-qk-rmsnorm-v1`, profile with F, D, Hq, Hk, m, K, s, epsN), and the admission checks. It never reads a witness; the harness asserts the witness builder's relation list is byte-identical to the verifier's.

## Reproduce

From the repository root, g++ C++17 and Python 3 standard library, no downloads:

```
python3 research/operators/qwen_qk_norm/run.py build --out <fresh dir>
python3 research/operators/qwen_qk_norm/run.py build --ubsan --out <fresh dir>
python3 research/operators/qwen_qk_norm/run.py suite --out <fresh dir>
python3 research/operators/qwen_qk_norm/run.py suite --ubsan --out <fresh dir>
python3 research/operators/qwen_qk_norm/run.py fidelity --out <fresh dir>
python3 research/operators/qwen_qk_norm/run.py summary --out <fresh dir>
```

Without `--out` the commands write to the experiment's `runs/` and refuse existing receipts. `run.py debug` uses seeds 901..903, disjoint from the registered 1..10, and writes only to ignored `work/`. The release suite is a few CPU-minutes (D256 dominates); on a shared host run it through the host's heavy-job gate with a few pinned cores.
