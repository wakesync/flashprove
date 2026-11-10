// SPDX-License-Identifier: Apache-2.0
// Research-only: the Qwen Gated DeltaNet head lowered onto the two-lookup run (two_lookup.h).
// One builder for both stages of experiments/20261109-32-qwen-deltanet-lookup-build:
//   stage 1  the M1b statement (T = 4, public o, no norm), remainders as lookup keys
//   stage 2  the M2 head (T = 16, witness o, proved gated RMSNorm, public y)
// Three kinds of product column:
//   gate        [x, y, x y]   a product gate
//   range cell  [x, 0, 0]     in an RNG matrix region of row a: RNG proves |x| < 2^23 (honest < 2^18)
//   key cell    [r, 0, 0]     in a key region of row a: the remainder lookup proves r in [0, 2^12)
// The relation list (terms, coefficients, targets) depends only on the shape and on verifier-known
// integers (`Derived`). build(.., relonly = true) computes NO witness: it is the verifier's
// derivation. Every i64 operation is checked; an overflow sets Built::overflow.
// The scale F, the norm's constants and the norm lowering are in ONE place: HeadParams/NormParams
// and the block "gated RMSNorm" of build(). The layout code reads only counts.
#pragma once
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <memory>
#include <string>
#include <sys/resource.h>
#include "two_lookup_prove.h"
using namespace blk;

static void check(bool ok, const char *s) { if (!ok) { std::fprintf(stderr, "FAIL: %s\n", s); std::exit(1); } }
static F fi(i64 x) { return x >= 0 ? F{u64(x) % P} : F{(P - (u64(0) - u64(x)) % P) % P}; }
static i64 fdiv(i64 a, i64 b) { i64 q = a / b; if ((a % b) != 0 && ((a < 0) != (b < 0))) --q; return q; }
static i64 isqrt64(i64 n) { if (n <= 0) return 0; i64 r = (i64)std::sqrt((long double)n); while ((__int128)r * r > n) r--; while ((__int128)(r + 1) * (r + 1) <= n) r++; return r; }
constexpr i64 BOUND = i64(1) << 18;    // honest contract of every range cell
constexpr i64 VBOUND = i64(1) << 31;   // public v, o, y, pre-conv inputs
constexpr i64 CGBOUND = i64(1) << 24;  // the derived norm coefficient: |cg| < 2^24 (checked admission)
constexpr u64 RTAG = u64(1) << 40, KTAG = u64(1) << 41;
constexpr u64 RCOLS = 16;
constexpr i64 KEYS = i64(1) << REM_BITS;

// The gated RMSNorm's constants (DESIGN.md 4.4 of PR #66). A different norm scaling changes these
// and the block "gated RMSNorm" in build(), nothing else.
struct NormParams {
  i64 eps = 2147;         // round(128 * 1e-6 * 2^2F) at F = 12
  unsigned rc_shift = 36; // Rc = floor(2^rc_shift / sigma)
  unsigned w_shift = 24;  // w = floor(o Rc / 2^w_shift)
};
struct HeadParams {
  int T = 4, D = 128, F = 12;
  bool norm = false;  // stage 2: o is a witness range cell and the gated norm is proved
  NormParams np;
};
// The verifier-known integers that the relation list reads.
struct Derived {
  std::vector<i64> S0, ST;                // D*D
  std::vector<i64> a, beta;               // T
  std::vector<std::vector<i64>> k, v, q;  // T x D
  std::vector<std::vector<i64>> o;        // stage 1: public head output
  std::vector<std::vector<i64>> cg, y;    // stage 2: derived norm coefficient, public result
};

struct Built {
  HeadParams hp;
  std::vector<std::array<F, 3>> gates;
  std::vector<WideRelation> rel;
  std::vector<i64> rcv, keyv;  // honest values of range cells and key cells
  bool overflow = false, refused = false;
  const char *why = "";
  // layout
  RegionSpec rs; KeySpec ks;
  std::vector<u64> rc_off, key_off;  // first cell number of each matrix / part
  u64 gate_base = 0, laid = 0, key_cells = 0; unsigned L = 0;
  u64 rng_planes = 0, rem_planes = 0;
  // witness (honest values)
  std::vector<std::vector<i64>> M, delta, S, o, w, y;
  // tagged columns for attacks: [t] unless noted
  std::vector<u64> state0, state0_key, state0_rc, g1_first, g6_first, M_rc, M_key, d_cell, d_key, dlo_rc, dhi_rc;
  std::vector<u64> o_key_last, o_rel_last; std::vector<i64> o_rem_last;  // last token, per j (stage 1)
  struct NormIdx { u64 gss, grs; std::vector<u64> sk, e1k, e2k, rk, rrk, gk, oo, orr, o_rc, o_key, w_rc, rw_key, ry_key; i64 sigma, Rc; };
  std::vector<NormIdx> norm;  // [t] (stage 2)
  u64 place(u64 c) const {
    if (c >= KTAG) { const u64 k = c - KTAG; size_t p = 0; while (p + 1 < key_off.size() && k >= key_off[p + 1]) p++; return ks.first_place[p] + (k - key_off[p]); }
    if (c >= RTAG) { const u64 k = c - RTAG; size_t m = 0; while (m + 1 < rc_off.size() && k >= rc_off[m + 1]) m++; return rs.first_place[m] + (k - rc_off[m]); }
    return gate_base + c;
  }
};
static std::vector<u64> pieces(u64 n, u64 quantum) {
  n = (n + quantum - 1) / quantum * quantum; std::vector<u64> out;
  for (int b = 62; b >= 0; b--) if ((n >> b) & 1) out.push_back(u64(1) << b);
  return out;
}
static Setting research_setting() { Setting set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES; set.target = 10; set.set_work(ErrorKind::QUERY, Scope::REQUEST, 6); return set; }

// Layout, a function of the three counts only (as count_model.py arm B): RNG matrices (16 columns,
// rows in pieces of at least 1,024) and key parts (pieces of at least 16,384) first, largest first,
// each aligned to its size; the gates after.
static void lay_out(Built &b) {
  const std::vector<u64> rows = pieces((b.rcv.size() + RCOLS - 1) / RCOLS, 1024), parts = pieces(b.keyv.size(), 16384);
  struct Block { u64 size; bool key; size_t idx; };
  std::vector<Block> blocks;
  for (size_t i = 0; i < rows.size(); i++) blocks.push_back({rows[i] * RCOLS, false, i});
  for (size_t i = 0; i < parts.size(); i++) blocks.push_back({parts[i], true, i});
  std::stable_sort(blocks.begin(), blocks.end(), [](const Block &x, const Block &y) { return x.size > y.size; });
  b.rs.rows = rows; b.rs.first_place.assign(rows.size(), 0); b.rs.columns = RCOLS;
  b.ks.part_bits.clear(); for (u64 p : parts) b.ks.part_bits.push_back(ceil_log2(p));
  b.ks.first_place.assign(parts.size(), 0);
  u64 pos = 0;
  for (const Block &x : blocks) { const u64 first = (pos + x.size - 1) / x.size * x.size; (x.key ? b.ks.first_place : b.rs.first_place)[x.idx] = first; pos = first + x.size; }
  u64 off = 0; b.rc_off.clear(); for (u64 r : rows) b.rc_off.push_back(off), off += r * RCOLS;
  off = 0; b.key_off.clear(); for (u64 p : parts) b.key_off.push_back(off), off += p;
  b.key_cells = off;
  b.gate_base = pos; b.laid = pos + b.gates.size();
  unsigned L = std::max(18u, ceil_log2(b.laid));
  const Setting s0 = research_setting();
  const unsigned N0 = rng_combinations(s0, Scope::REQUEST);
  u64 cell_rows = 0; for (u64 r : rows) cell_rows += r;
  const u64 dc = pow2_at_least(cell_rows), np = pow2_at_least(N0);
  RngShape probe; probe.digit_bits[0] = 12, probe.digit_bits[1] = 11, probe.combinations = N0, probe.digit_columns = dc;
  b.rng_planes = rng_planes_places(rng_lookup(probe));
  b.rem_planes = rng_planes_places(rem_lookup(b.ks, 0, 3));
  while ((u64(1) << L) < dc * np || (u64(1) << (L - 1)) < b.rng_planes || (u64(1) << (L - 1)) < b.rem_planes + 3 * s0.samples) L++;
  b.L = L;
  for (auto &r : b.rel) for (auto &t : r.terms) t.column = b.place(t.column);
}

static Built build(const HeadParams &hp, const Derived &z, const bool relonly) {
  Built b; b.hp = hp; const int D = hp.D, FB = hp.F, T = hp.T; const i64 one = i64(1) << FB, one2 = i64(1) << (2 * FB);
  auto refuse = [&](const char *s) { if (!b.refused) b.refused = true, b.why = s; };
  auto mul = [&](i64 x, i64 y) { i64 r; if (__builtin_mul_overflow(x, y, &r)) { b.overflow = true; return i64(0); } return r; };
  auto add = [&](i64 x, i64 y) { i64 r; if (__builtin_add_overflow(x, y, &r)) { b.overflow = true; return i64(0); } return r; };
  auto sub = [&](i64 x, i64 y) { i64 r; if (__builtin_sub_overflow(x, y, &r)) { b.overflow = true; return i64(0); } return r; };
  auto gate = [&](i64 x, i64 y) { b.gates.push_back({fi(x), fi(y), fi(x) * fi(y)}); return u64(b.gates.size() - 1); };
  auto rel = [&](std::vector<AffineTerm> t, i64 target) { b.rel.push_back({std::move(t), fi(target)}); return u64(b.rel.size() - 1); };
  auto rcell = [&](i64 x) { if (!relonly && !(x > -BOUND && x < BOUND)) refuse("an honest range cell is outside its contract (statement refused, never saturated)"); b.rcv.push_back(relonly ? 0 : x); return RTAG + u64(b.rcv.size() - 1); };
  // n in [0, 2^(12 count)) as `count` key cells, low limb first
  auto limbs = [&](i64 n, unsigned count) {
    if (!relonly && !(n >= 0 && (count >= 5 || n < (i64(1) << (REM_BITS * count))))) refuse("an honest exact quantity is outside its interval");
    std::vector<u64> ks;
    for (unsigned i = 0; i < count; i++) { b.keyv.push_back(relonly ? 0 : (n >> (REM_BITS * i)) & (KEYS - 1)); ks.push_back(KTAG + u64(b.keyv.size() - 1)); }
    return ks;
  };
  auto with = [&](std::vector<AffineTerm> &terms, const std::vector<u64> &ks, i64 coef) { for (size_t i = 0; i < ks.size(); i++) terms.push_back({0, ks[i], fi(mul(coef, i64(1) << (REM_BITS * i)))}); };
  std::vector<i64> S = relonly ? std::vector<i64>(size_t(D) * D, 0) : z.S0; std::vector<u64> canon(size_t(D) * D);
  for (int t = 0; t < T; t++) {
    const i64 a = z.a[t], beta = z.beta[t];
    // g1 = S a (decay), g2 = S k[i] (memory read)
    std::vector<u64> g1(size_t(D) * D), g2(size_t(D) * D);
    for (int i = 0; i < D; i++) for (int j = 0; j < D; j++) {
      const int c = i * D + j;
      g1[c] = gate(S[c], a);
      if (t == 0) { canon[c] = g1[c]; rel({{0, g1[c], F{1}}}, z.S0[c]); }
      else rel({{0, g1[c], F{1}}, {0, canon[c], fi(-1)}}, 0);
      rel({{1, g1[c], F{1}}}, a);
      g2[c] = gate(S[c], z.k[t][i]);
      rel({{0, g2[c], F{1}}, {0, canon[c], fi(-1)}}, 0);
      rel({{1, g2[c], F{1}}}, z.k[t][i]);
    }
    b.g1_first.push_back(g1[0]);
    std::vector<i64> M(D), delta(D); std::vector<u64> dcell(D);
    for (int j = 0; j < D; j++) {
      i64 Pj = 0; std::vector<AffineTerm> pt;
      for (int i = 0; i < D; i++) { if (!relonly) Pj = add(Pj, mul(S[i * D + j], z.k[t][i])); pt.push_back({2, g2[i * D + j], fi(-1)}); }
      const u64 g5 = gate(Pj, a); pt.insert(pt.begin(), AffineTerm{0, g5, F{1}}); rel(pt, 0);
      rel({{1, g5, F{1}}}, a);
      const i64 aP = mul(Pj, a); M[j] = fdiv(aP, one2); const i64 rM = sub(aP, mul(M[j], one2));
      const u64 g6 = gate(sub(z.v[t][j], M[j]), beta); if (j == 0) b.g6_first.push_back(g6);
      // 2^2F (v - g6.a) + r - g5.c = 0, r in [0, 2^24) as two keys
      std::vector<AffineTerm> ft = {{0, g6, fi(-one2)}, {2, g5, fi(-1)}};
      const std::vector<u64> mk = limbs(rM, 2); with(ft, mk, 1); if (j == 0) b.M_key.push_back(mk[0]);
      rel(ft, mul(-one2, z.v[t][j]));
      const u64 mc = rcell(M[j]); if (j == 0) b.M_rc.push_back(mc);
      rel({{0, mc, F{1}}, {0, g6, F{1}}}, z.v[t][j]);  // M + g6.a = v
      rel({{1, g6, F{1}}}, beta);
      const i64 num = relonly ? 0 : mul(sub(z.v[t][j], M[j]), beta); delta[j] = fdiv(num, one); const i64 rd = sub(num, mul(delta[j], one));
      const i64 dhi = fdiv(delta[j], BOUND), dlo = sub(delta[j], mul(dhi, BOUND));
      dcell[j] = gate(z.k[t][0], delta[j]);
      rel({{0, dcell[j], F{1}}}, z.k[t][0]);
      std::vector<AffineTerm> dt = {{1, dcell[j], fi(one)}, {2, g6, fi(-1)}};
      const std::vector<u64> dk = limbs(rd, 1); with(dt, dk, 1); if (j == 0) { b.d_key.push_back(dk[0]); b.d_cell.push_back(dcell[j]); }
      rel(dt, 0);
      const u64 lo = rcell(dlo), hi = rcell(dhi); if (j == 0) { b.dlo_rc.push_back(lo); b.dhi_rc.push_back(hi); }
      rel({{1, dcell[j], F{1}}, {0, hi, fi(-BOUND)}, {0, lo, fi(-1)}}, 0);
    }
    // update: S'[i,j] = floor((a S + k[i] delta[j]) / 2^F); output gate g4 = S' q[i]
    std::vector<i64> Sn(size_t(D) * D); std::vector<u64> g4(size_t(D) * D);
    for (int i = 0; i < D; i++) for (int j = 0; j < D; j++) {
      const int c = i * D + j;
      u64 g3 = dcell[j];
      if (i > 0) {
        g3 = gate(z.k[t][i], delta[j]);
        rel({{0, g3, F{1}}}, z.k[t][i]);
        rel({{1, g3, F{1}}, {1, dcell[j], fi(-1)}}, 0);
      }
      const i64 num = relonly ? 0 : add(mul(a, S[c]), mul(z.k[t][i], delta[j])); Sn[c] = fdiv(num, one); const i64 r = sub(num, mul(Sn[c], one));
      g4[c] = gate(Sn[c], z.q[t][i]);
      rel({{1, g4[c], F{1}}}, z.q[t][i]);
      std::vector<AffineTerm> ft = {{0, g4[c], fi(one)}, {2, g1[c], fi(-1)}, {2, g3, fi(-1)}};
      const std::vector<u64> sk = limbs(r, 1); with(ft, sk, 1); rel(ft, 0);
      const u64 sc = rcell(Sn[c]); rel({{0, g4[c], F{1}}, {0, sc, fi(-1)}}, 0);
      if (c == 0) { b.state0.push_back(g4[c]); b.state0_key.push_back(sk[0]); b.state0_rc.push_back(sc); }
    }
    // head output o[j] = floor(sum_i g4.c / 2^F)
    std::vector<i64> o(D); std::vector<u64> o_rc(D), o_key(D);
    for (int j = 0; j < D; j++) {
      i64 sum = 0; std::vector<AffineTerm> ot;
      for (int i = 0; i < D; i++) { if (!relonly) sum = add(sum, mul(Sn[i * D + j], z.q[t][i])); ot.push_back({2, g4[i * D + j], fi(-1)}); }
      o[j] = fdiv(sum, one); const i64 ro = sub(sum, mul(o[j], one));
      const std::vector<u64> ok = limbs(ro, 1); with(ot, ok, 1); o_key[j] = ok[0];
      u64 r;
      if (hp.norm) { o_rc[j] = rcell(o[j]); ot.push_back({0, o_rc[j], fi(one)}); r = rel(ot, 0); }  // witness o
      else r = rel(ot, mul(-one, z.o[t][j]));                                                         // public o
      if (t == T - 1) { b.o_key_last.push_back(ok[0]); b.o_rel_last.push_back(r); b.o_rem_last.push_back(ro); }
    }
    // ---- gated RMSNorm of the witness o (the only place that knows the norm lowering) ----
    if (hp.norm) {
      const NormParams &np = hp.np; const i64 two_rc = i64(1) << np.rc_shift, two_w = i64(1) << np.w_shift;
      Built::NormIdx ix;
      i64 Vx = 0, sigma = 0, e1 = 0, e2 = 0, Rc = 0, rr = 0, gap = 0;
      if (!relonly) {
        for (int j = 0; j < D; j++) Vx = add(Vx, mul(o[j], o[j]));
        const i64 n = add(Vx, np.eps); sigma = isqrt64(n);
        e1 = sub(n, mul(sigma, sigma)); e2 = sub(add(mul(sigma, sigma), mul(2, sigma)), n);
        if (sigma <= 0) refuse("sigma is not positive"); else { Rc = two_rc / sigma; rr = sub(two_rc, mul(Rc, sigma)); gap = sub(sub(sigma, 1), rr); }
      }
      ix.sigma = sigma, ix.Rc = Rc;
      ix.gss = gate(sigma, sigma); ix.grs = gate(Rc, sigma);
      ix.sk = limbs(sigma, 2); ix.e1k = limbs(e1, 2); ix.e2k = limbs(e2, 2); ix.rk = limbs(Rc, 3); ix.rrk = limbs(rr, 2); ix.gk = limbs(gap, 2);
      { std::vector<AffineTerm> x = {{0, ix.gss, F{1}}}; with(x, ix.sk, -1); rel(x, 0); }  // sigma = its limbs (both operands, and Rc's partner)
      { std::vector<AffineTerm> x = {{1, ix.gss, F{1}}}; with(x, ix.sk, -1); rel(x, 0); }
      { std::vector<AffineTerm> x = {{0, ix.grs, F{1}}}; with(x, ix.rk, -1); rel(x, 0); }
      { std::vector<AffineTerm> x = {{1, ix.grs, F{1}}}; with(x, ix.sk, -1); rel(x, 0); }
      std::vector<AffineTerm> v1 = {{2, ix.gss, fi(-1)}}, v2 = {{2, ix.gss, F{1}}, {0, ix.gss, fi(2)}};
      for (int j = 0; j < D; j++) {
        const u64 oo = gate(o[j], o[j]); ix.oo.push_back(oo);
        rel({{0, oo, F{1}}, {0, o_rc[j], fi(-1)}}, 0); rel({{1, oo, F{1}}, {0, o_rc[j], fi(-1)}}, 0);
        v1.push_back({2, oo, F{1}}); v2.push_back({2, oo, fi(-1)});
      }
      with(v1, ix.e1k, -1); rel(v1, -np.eps);  // sum o^2 + eps - sigma^2 = e1 >= 0
      with(v2, ix.e2k, -1); rel(v2, np.eps);   // sigma^2 + 2 sigma - sum o^2 - eps = e2 >= 0
      { std::vector<AffineTerm> x = {{2, ix.grs, F{1}}}; with(x, ix.rrk, 1); rel(x, two_rc); }                      // Rc sigma + rr = 2^36
      { std::vector<AffineTerm> x = {{0, ix.gss, F{1}}}; with(x, ix.rrk, -1); with(x, ix.gk, -1); rel(x, 1); }      // sigma - 1 - rr = gap >= 0
      std::vector<i64> w(D), y(D);
      for (int j = 0; j < D; j++) {
        const u64 orr = gate(o[j], Rc); ix.orr.push_back(orr);
        rel({{0, orr, F{1}}, {0, o_rc[j], fi(-1)}}, 0); rel({{1, orr, F{1}}, {0, ix.grs, fi(-1)}}, 0);
        const i64 prod = relonly ? 0 : mul(o[j], Rc); w[j] = fdiv(prod, two_w); const i64 rw = sub(prod, mul(w[j], two_w));
        const u64 wc = rcell(w[j]); const std::vector<u64> rwk = limbs(rw, 2);
        { std::vector<AffineTerm> x = {{0, wc, fi(two_w)}, {2, orr, fi(-1)}}; with(x, rwk, 1); rel(x, 0); }        // 2^24 w + r = o Rc
        const i64 cg = z.cg[t][j], num = relonly ? 0 : mul(cg, w[j]); y[j] = fdiv(num, one); const i64 ry = sub(num, mul(y[j], one));
        const std::vector<u64> ryk = limbs(ry, 1);
        { std::vector<AffineTerm> x = {{0, wc, fi(cg)}}; with(x, ryk, -1); rel(x, mul(one, z.y[t][j])); }          // cg w - r = 2^F y, y public
        ix.o_rc.push_back(o_rc[j]); ix.o_key.push_back(o_key[j]); ix.w_rc.push_back(wc); ix.rw_key.push_back(rwk[0]); ix.ry_key.push_back(ryk[0]);
      }
      b.norm.push_back(ix); b.w.push_back(w); b.y.push_back(y);
    }
    if (t == T - 1) for (int c = 0; c < D * D; c++) rel({{0, g4[c], F{1}}}, z.ST[c]);
    for (int c = 0; c < D * D; c++) canon[c] = g4[c];
    S = Sn; b.M.push_back(M); b.delta.push_back(delta); b.S.push_back(Sn); b.o.push_back(o);
  }
  lay_out(b);
  return b;
}

static Table table_of(const Built &b) {
  Table tab(1, 3, u64(1) << b.L);
  for (size_t c = 0; c < b.gates.size(); c++) for (int r = 0; r < 3; r++) tab.set(r, b.gate_base + c, E::from(b.gates[c][r]));
  for (size_t k = 0; k < b.rcv.size(); k++) tab.set(0, b.place(RTAG + k), E::from(fi(b.rcv[k])));
  for (size_t k = 0; k < b.keyv.size(); k++) tab.set(0, b.place(KTAG + k), E::from(fi(b.keyv[k])));
  return tab;
}
static size_t violated(const std::vector<WideRelation> &rel, const Table &t) { size_t n = 0; for (auto &a : rel) if (!(two_eval(a, t) == E::from(a.target))) n++; return n; }
static bool products_hold_all(const Table &t) { for (size_t i = 0; i < t.len; i++) if (!(t.at(2, i) == t.at(0, i) * t.at(1, i))) return false; return true; }
static double secs(std::chrono::steady_clock::time_point a) { return std::chrono::duration<double>(std::chrono::steady_clock::now() - a).count(); }
static long rss_kb() { rusage u; getrusage(RUSAGE_SELF, &u); return u.ru_maxrss; }

// Sizing: a pure function of the derived statement. The stage schedules are tried in a fixed order.
struct Sized { std::unique_ptr<TwoRun> run; bool ok = false; };
static Sized size_run(const Built &b) {
  const unsigned L = b.L; const Setting set = research_setting();
  const std::vector<std::vector<StageChoice>> tries = {
      {{1, 1, L, L}, {0, 0, L, L}}, {{1, 1, L + 1, L + 1}, {0, 0, L + 1, L + 1}}, {{2, 1, L + 1, L + 1}, {0, 0, L, L}},
      {{2, 1, L + 1, L + 1}, {0, 0, L + 1, L + 1}}, {{1, 1, L + 2, L + 2}, {0, 0, L + 2, L + 2}}};
  Sized s;
  for (unsigned up = 1; up <= 2; up++)
    for (const auto &f : tries) {
      s.run = std::make_unique<TwoRun>(two_size(set, L, L + up, L + up, f, b.rel, b.rs, b.ks));
      if (s.run->product.plan->holds()) { s.ok = true; return s; }
    }
  return s;
}

// ---- verifier-side helpers shared by the two entries ----
enum class Verdict { ACCEPT, DECODE, ADMIT, DERIVE, PROOF };
static const char *stage_name(Verdict x) { return x == Verdict::ACCEPT ? "accept" : x == Verdict::DECODE ? "decode" : x == Verdict::ADMIT ? "admit" : x == Verdict::DERIVE ? "derive" : "proof"; }
struct VerifyTiming { double derive_s = 0, verify_s = 0; std::string why; Notes notes; };
static u64 enc(i64 x) { return fi(x).v; }
// One word as a signed integer of a class: canonical (< p), then lo <= x <= hi.
static bool decode(u64 w, i64 lo, i64 hi, i64 &out) {
  if (w >= P) return false;
  const i64 x = w > P / 2 ? -(i64)(P - w) : (i64)w;
  if (x < lo || x > hi) return false;
  out = x; return true;
}
// Steps 4 and 5 of an entry: witness-free derivation, sizing guards, sizing, the proof verifier.
static Verdict derive_and_verify(const HeadParams &hp, const Derived &z, const u8 *proof, size_t bytes, VerifyTiming *tm) {
  auto t1 = std::chrono::steady_clock::now();
  const Built b = build(hp, z, true);
  if (b.overflow) { if (tm) tm->why = "checked arithmetic overflowed while deriving the statement"; return Verdict::DERIVE; }
  if (two_size_fault(research_setting(), b.L, b.rel, b.rs, b.ks)) { if (tm) tm->why = "derived statement outside the sizing guards"; return Verdict::DERIVE; }
  const Sized s = size_run(b);
  if (!s.ok) { if (tm) tm->why = "no plan holds for the derived statement"; return Verdict::DERIVE; }
  if (tm) tm->derive_s += secs(t1);
  auto t2 = std::chrono::steady_clock::now();
  const char *why = nullptr;
  const bool acc = two_verify(*s.run, proof, bytes, &why, tm ? &tm->notes : nullptr);
  if (tm) { tm->verify_s = secs(t2); tm->why = acc ? "" : (why ? why : "proof verifier"); }
  return acc ? Verdict::ACCEPT : Verdict::PROOF;
}
static bool same_relations(const Built &x, const Built &y) {
  bool same = x.gates.size() == y.gates.size() && x.rel.size() == y.rel.size() && x.L == y.L && x.rs.first_place == y.rs.first_place && x.ks.first_place == y.ks.first_place;
  for (size_t i = 0; same && i < x.rel.size(); i++) {
    same = x.rel[i].target.v == y.rel[i].target.v && x.rel[i].terms.size() == y.rel[i].terms.size();
    for (size_t k = 0; same && k < x.rel[i].terms.size(); k++)
      same = x.rel[i].terms[k].row == y.rel[i].terms[k].row && x.rel[i].terms[k].column == y.rel[i].terms[k].column && x.rel[i].terms[k].coefficient.v == y.rel[i].terms[k].coefficient.v;
  }
  return same;
}
static void print_counts(const Built &b) {
  size_t terms = 0; for (auto &a : b.rel) terms += a.terms.size();
  std::printf("{\"mode\":\"counts\",\"T\":%d,\"D\":%d,\"F\":%d,\"norm\":%s,\"gate_columns\":%zu,\"range_cells\":%zu,\"lkp_keys\":%zu,\"key_cells_laid\":%llu,\"relations\":%zu,\"relation_terms\":%zu,\"columns_used\":%llu,\"log_length\":%u,\"rng_multiplicity_places\":%llu,\"remainder_multiplicity_places\":%llu,\"rng_matrices\":%zu,\"key_parts\":%zu}\n",
              b.hp.T, b.hp.D, b.hp.F, b.hp.norm ? "true" : "false", b.gates.size(), b.rcv.size(), b.keyv.size(), (unsigned long long)b.key_cells, b.rel.size(), terms, (unsigned long long)b.laid, b.L,
              (unsigned long long)b.rng_planes, (unsigned long long)b.rem_planes, b.rs.rows.size(), b.ks.part_bits.size());
  std::fflush(stdout);
}
static std::string hex_of(const E &x) { char buf[64]; std::snprintf(buf, sizeof buf, "%016llx%016llx%016llx", (unsigned long long)x.c[0].v, (unsigned long long)x.c[1].v, (unsigned long long)x.c[2].v); return buf; }
// The two lookups' alphas, from the verifier's notes (the digit lookup's comes first on the chain).
static std::vector<E> alphas_of(const Notes &notes) { std::vector<E> a; for (const auto &n : notes) if (n.first == "LKP: alpha") a.push_back(n.second); return a; }
