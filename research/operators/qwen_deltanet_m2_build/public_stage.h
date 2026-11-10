// SPDX-License-Identifier: Apache-2.0
// Research-only: the public-only stage of the M2 head, recomputed by the verifier (and, with the
// same function, by the prover) from decoded public integers and the head's fixed constants:
// causal conv1d (kernel 4, public history H), SiLU, q/k L2 norm with the q scale, the decay and
// beta gates, and the norm coefficient cg. Integer arithmetic only, pinned tables only
// (tables/pinned_f12.h: the operators lane's F = 12 files, PR #67). No float, no libm.
// Every operation on a public input is checked. A table input outside its domain, an overflow, or
// a derived coefficient outside its bound is a returned reject ("derive"), never a clamp, a wrap or
// an exit. The bounds on derived coefficients are checked HERE, before any relation is derived and
// before any integer becomes a field element:
//   a, beta in [0, 2^F];  |k|, |q| <= 2^F;  |v| < 2^31;  |cg| < 2^24.
// |cg| < 2^24 is what the norm's last floor needs: RNG proves only |w| < 2^23 for a hostile w, so
// |cg w| < 2^47 < p / 2 and the field equation cg w - r = 2^F y is an integer equation. Without the
// check a large fixed gain gives modular aliases (fourth review of PR #66).
#pragma once
#include "head.h"
#include "tables/pinned_f12.h"

// The head's fixed constants: the verifier's own configuration, not statement words.
struct HeadConsts {
  std::vector<i64> W;          // conv taps at 2^12: W[(c * D + ch) * 4 + tau], c = 0 q, 1 k, 2 v
  // Verifier-owned copies: defaults are byte-identical to the pinned tables. Hostile tests
  // deliberately corrupt copies, never the pinned files or caller-supplied statement words.
  std::vector<i64> silu = std::vector<i64>(m2tables::silu_f12, m2tables::silu_f12 + m2tables::ROWS);
  std::vector<i64> decay = std::vector<i64>(m2tables::decay_one_f12, m2tables::decay_one_f12 + m2tables::ROWS);
  std::vector<i64> sigmoid = std::vector<i64>(m2tables::sigmoid_f12, m2tables::sigmoid_f12 + m2tables::ROWS);
  i64 k_numerator_scale = 4096, q_numerator_scale = 4096, q_divisor_scale = 46341;
  i64 dt_bias = 0;             // at 2^F, added to ar before the decay table (A = 1)
  std::vector<__int128> G;     // per channel, at 2^12: gain * sqrt(D). cg = floor(G silu(z) / 2^12)
};
// What the statement words decode to.
struct PublicIn {
  std::vector<i64> S0, ST, H;                  // H[tau * 3D + c * D + ch] = pre-conv input at token -1 - tau
  std::vector<std::vector<i64>> xq, xk, xv, z, y;  // T x D
  std::vector<i64> ar, br;                     // T
};
constexpr i64 EPS_L2 = 17, SQRT_D_Q12 = 46341;
constexpr i64 ZBOUND = i64(1) << 20;  // class of ar, br, z

struct PubStage { bool ok = true; const char *why = ""; };
static bool table_row(i64 x, i64 &row) { row = fdiv(x, 16) + 2048; return row >= 0 && row < m2tables::ROWS; }
// The one admission rule for the derived norm coefficient.
static bool cg_admitted(__int128 cg) { return cg > -(__int128)CGBOUND && cg < (__int128)CGBOUND; }

static PubStage public_stage(const HeadParams &hp, const HeadConsts &hc, const PublicIn &in, Derived &z) {
  PubStage st; const int D = hp.D, T = hp.T; const i64 one = i64(1) << hp.F;
  auto bad = [&](const char *s) { if (st.ok) st.ok = false, st.why = s; };
  auto mul = [&](i64 x, i64 y) { i64 r; if (__builtin_mul_overflow(x, y, &r)) { bad("overflow in the public stage"); return i64(0); } return r; };
  auto add = [&](i64 x, i64 y) { i64 r; if (__builtin_add_overflow(x, y, &r)) { bad("overflow in the public stage"); return i64(0); } return r; };
  if (hp.F != 12 || hc.W.size() != size_t(3) * D * 4 || hc.G.size() != size_t(D) || hc.silu.size() != m2tables::ROWS || hc.decay.size() != m2tables::ROWS || hc.sigmoid.size() != m2tables::ROWS || hc.q_divisor_scale <= 0) { bad("head constants do not fit the shape"); return st; }
  z = Derived(); z.S0 = in.S0; z.ST = in.ST; z.y = in.y;
  const std::vector<i64> *xs[3];
  for (int t = 0; t < T && st.ok; t++) {
    std::vector<i64> s[3];
    for (int c = 0; c < 3; c++) {
      s[c].assign(D, 0);
      for (int ch = 0; ch < D; ch++) {
        i64 acc = 0;
        for (int tau = 0; tau < 4; tau++) {
          const int tt = t - tau;  // token index; negative: history
          i64 x;
          if (tt >= 0) { xs[0] = &in.xq[tt]; xs[1] = &in.xk[tt]; xs[2] = &in.xv[tt]; x = (*xs[c])[ch]; }
          else x = in.H[size_t(-1 - tt) * 3 * D + size_t(c) * D + ch];
          acc = add(acc, mul(hc.W[(size_t(c) * D + ch) * 4 + tau], x));
        }
        if (!st.ok) return st;
        i64 row;
        if (!table_row(fdiv(acc, 4096), row)) { bad("a conv output is outside the SiLU table's domain"); row = 0; }
        s[c][ch] = hc.silu[row];
      }
    }
    // q/k L2 norm, round half up: floor((2 num + sig) / (2 sig)), sig = isqrt(sum s^2 + eps)
    std::vector<i64> kq[2];
    for (int which = 0; which < 2; which++) {  // 0: q (with the 1 / sqrt(D) scale), 1: k
      const std::vector<i64> &u = s[which]; i64 n2 = EPS_L2;
      for (int ch = 0; ch < D; ch++) n2 = add(n2, mul(u[ch], u[ch]));
      if (!st.ok) return st;
      i64 sig = isqrt64(n2);
      if (sig <= 0) { bad("a norm's divisor is not positive"); sig = 1; }
      if (which == 0) sig = mul(sig, hc.q_divisor_scale);
      kq[which].assign(D, 0);
      for (int ch = 0; ch < D; ch++) {
        const i64 num = which == 0 ? mul(mul(u[ch], one), hc.q_numerator_scale) : mul(u[ch], hc.k_numerator_scale);
        const i64 numerator = add(mul(2, num), sig), denominator = mul(2, sig);
        if (!st.ok) return st;
        kq[which][ch] = fdiv(numerator, denominator);
        if (kq[which][ch] < -one || kq[which][ch] > one) bad(which == 0 ? "a derived q is outside [-2^F, 2^F]" : "a derived k is outside [-2^F, 2^F]");
      }
    }
    for (int ch = 0; ch < D; ch++) if (s[2][ch] <= -VBOUND || s[2][ch] >= VBOUND) bad("a derived v is outside its class");
    i64 row;
    if (!table_row(add(in.ar[t], hc.dt_bias), row)) { bad("ar + dt_bias is outside the decay table's domain"); row = 0; }
    const i64 a = hc.decay[row];
    if (!table_row(in.br[t], row)) { bad("br is outside the sigmoid table's domain"); row = 0; }
    const i64 beta = hc.sigmoid[row];
    if (a < 0 || a > one) bad("a derived a is outside [0, 2^F]");
    if (beta < 0 || beta > one) bad("a derived beta is outside [0, 2^F]");
    std::vector<i64> cg(D, 0);
    for (int ch = 0; ch < D; ch++) {
      if (!table_row(in.z[t][ch], row)) { bad("z is outside the SiLU table's domain"); row = 0; }
      __int128 prod;
      if (__builtin_mul_overflow(hc.G[ch], (__int128)hc.silu[row], &prod)) { bad("overflow in the norm coefficient"); prod = 0; }
      __int128 q = prod / 4096; if (prod % 4096 != 0 && prod < 0) q -= 1;  // floor
#ifndef M2_CONTROL_NO_CG_CHECK
      if (!cg_admitted(q)) { bad("a derived norm coefficient cg is outside |cg| < 2^24"); q = 0; }
#endif
      // The control removes ONLY the class bound, never the host conversion check.
      if (q < -(__int128(1) << 63) || q > (__int128(1) << 63) - 1) { bad("cg does not fit i64"); q = 0; }
      cg[ch] = (i64)q;
    }
    z.a.push_back(a); z.beta.push_back(beta); z.q.push_back(kq[0]); z.k.push_back(kq[1]); z.v.push_back(s[2]); z.cg.push_back(cg);
  }
  return st;
}
