// SPDX-License-Identifier: Apache-2.0
// Research-only. The M1b statement builder and prover (research/operators/qwen_deltanet_lookup/
// test.cpp, PR #63), split out as a header for the M2 design prototype admit_proto.cpp. Unchanged
// except: a relation-only switch (g_relonly) that turns off the honest-witness assertions when the
// verifier builds the relations (the column allocation and the relation list do not depend on it),
// and indices of the last token's output floors for the R9 attack.
#pragma once
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <string>
#include <sys/resource.h>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "../qwen_deltanet_lookup/lookup.h"
using namespace blk;

static void check(bool ok, const char *s) { if (!ok) { std::fprintf(stderr, "FAIL: %s\n", s); std::exit(1); } }
static F fi(i64 x) { return x >= 0 ? F{u64(x)} : F{P - u64(-x)}; }
static i64 fdiv(i64 a, i64 b) { i64 q = a / b; if ((a % b) != 0 && ((a < 0) != (b < 0))) --q; return q; }
constexpr i64 BOUND = i64(1) << 18;   // honest contract for S', M, delta limbs
constexpr u64 RTAG = u64(1) << 40;
constexpr u64 RCOLS = 16;
constexpr i64 VBOUND = i64(1) << 31;  // public v and o admissibility (widened; no-wrap argument in PREREG)

struct Fixture {
  int T, D, F;
  std::vector<i64> S0;                       // D*D, [i*D+j]
  std::vector<i64> a, beta;                  // T
  std::vector<std::vector<i64>> k, v, q;     // T x D
  std::vector<std::vector<i64>> M, delta, S, o;  // reference values per token
};
static Fixture load(const char *path) {
  std::ifstream f(path, std::ios::binary); check(bool(f), "open fixture");
  std::vector<i64> w; i64 x; while (f.read((char *)&x, 8)) w.push_back(x);
  size_t p = 0; auto take = [&](size_t n) { check(p + n <= w.size(), "fixture short"); std::vector<i64> r(w.begin() + p, w.begin() + p + n); p += n; return r; };
  Fixture z; auto h = take(3); z.T = h[0]; z.D = h[1]; z.F = h[2];
  const size_t D = z.D; z.S0 = take(D * D);
  for (int t = 0; t < z.T; t++) { auto ab = take(2); z.a.push_back(ab[0]); z.beta.push_back(ab[1]); z.k.push_back(take(D)); z.v.push_back(take(D)); z.q.push_back(take(D)); }
  for (int t = 0; t < z.T; t++) { z.M.push_back(take(D)); z.delta.push_back(take(D)); z.S.push_back(take(D * D)); z.o.push_back(take(D)); }
  check(p == w.size(), "fixture trailing data");
  return z;
}
// Public admission: every public value is visibly inside its declared range.
static bool admissible(const Fixture &z) {
  const i64 one = i64(1) << z.F;
  for (auto s : z.S0) if (s <= -BOUND || s >= BOUND) return false;
  for (int t = 0; t < z.T; t++) {
    if (z.a[t] < 0 || z.a[t] > one || z.beta[t] < 0 || z.beta[t] > one) return false;
    for (int i = 0; i < z.D; i++) {
      if (std::llabs(z.k[t][i]) > one || std::llabs(z.q[t][i]) > one || std::llabs(z.v[t][i]) >= VBOUND || std::llabs(z.o[t][i]) >= VBOUND) return false;
    }
  }
  for (auto s : z.S[z.T - 1]) if (s <= -BOUND || s >= BOUND) return false;
  return true;
}

// Witness + relation builder. Relations depend only on public values (shape is fixed by T, D, F).
struct Built {
  std::vector<std::array<F, 3>> cols;
  std::vector<WideRelation> rel;
  // indices for attacks
  std::vector<std::vector<u64>> state_col;      // [t] -> column of canonical S_{t+1}[0..D*D) (row 0 of g4)
  std::vector<std::vector<u64>> state_rbits;    // [t] -> low remainder bit column of the S_{t+1}[0] floor
  std::vector<std::vector<u64>> state_qbits;    // [t] -> range bit columns of S_{t+1}[0]
  std::vector<u64> g1_first, g6_first, m_rbit0, d_rbit0, d_cell;
  std::vector<std::vector<u64>> rel_a, rel_beta, rel_k0, rel_q0;
  std::vector<u64> rel_v0_floor, rel_v0_range, rel_o0;
  u64 rel_S00 = 0, rel_S4_00 = 0;
  std::vector<u64> o_rbit0_last, o_rel_last; std::vector<std::vector<u64>> o_rbits_last; std::vector<i64> o_rem_last;  // last token: o remainder bit-0 column and remainder, per j
  std::vector<std::vector<i64>> M, delta, S, o;
  std::vector<u64> rc;                          // columns of the range cells, in range-cell order
  std::vector<i64> rcv;                         // their honest values
  u64 rc_base = 0, rc_rows = 0;                 // region: product columns [rc_base, rc_base + 16 rc_rows)
  std::vector<u64> rcell_state, rcell_M, rcell_dlo, rcell_dhi; // [t] -> range-cell index of S_{t+1}[0,0], M[0], delta_lo[0], delta_hi[0]
};
static bool g_relonly = false;  // relation-only build (verifier side): witness checks off, columns allocated identically
static Built build(const Fixture &z) {
  Built b; const int D = z.D, FB = z.F; const i64 one = i64(1) << FB;
  auto col = [&](i64 x, i64 y) { b.cols.push_back({fi(x), fi(y), fi(x) * fi(y)}); return u64(b.cols.size() - 1); };
  auto rel = [&](std::vector<AffineTerm> t, i64 target) { b.rel.push_back({std::move(t), fi(target)}); return u64(b.rel.size() - 1); };
  // Unsigned width-bit decomposition of n (honest n must fit; builder asserts). Returns the
  // bit columns; each bit column is [x,x,x] with relations a-b=0, c-a=0, so x*x=x (boolean).
  auto bits = [&](i64 n, unsigned width, std::vector<AffineTerm> &terms, i64 coef) {
    check(g_relonly || (n >= 0 && n < (i64(1) << width)), "honest value outside its declared bit width");
    std::vector<u64> out;
    for (unsigned i = 0; i < width; i++) {
      i64 x = (n >> i) & 1; u64 c = col(x, x);
      rel({{0, c, F{1}}, {1, c, fi(-1)}}, 0); rel({{2, c, F{1}}, {0, c, fi(-1)}}, 0);
      terms.push_back({0, c, fi(coef * (i64(1) << i))}); out.push_back(c);
    }
    return out;
  };
  // A range cell: column [x, 0, 0], range-checked by RNG (|x| < 2^23 proved); returns its range-cell index.
  // Range cells live in one aligned region after all other columns (placed at the end of build()):
  // range cell k is product column base + k, laid for RNG as cell (k mod rows, k div rows) of a
  // rows x 16 matrix. Until then a term names it by RTAG + k.
  auto rcell = [&](i64 x) { check(g_relonly || (x > -BOUND && x < BOUND), "honest range cell outside its contract"); b.rcv.push_back(x); b.rc.push_back(RTAG + b.rcv.size() - 1); return u64(b.rcv.size() - 1); };
  std::vector<i64> S = z.S0; std::vector<u64> canon(D * D);
  b.state_col.resize(z.T); b.state_rbits.resize(z.T); b.state_qbits.resize(z.T); b.rcell_state.resize(z.T); b.rcell_M.resize(z.T); b.rcell_dlo.resize(z.T); b.rcell_dhi.resize(z.T);
  b.rel_a.resize(z.T); b.rel_beta.resize(z.T); b.rel_k0.resize(z.T); b.rel_q0.resize(z.T);
  for (int t = 0; t < z.T; t++) {
    const i64 a = z.a[t], beta = z.beta[t];
    // g1 = S*a (decay), g2 = S*k[i] (memory read)
    std::vector<u64> g1(D * D), g2(D * D);
    for (int i = 0; i < D; i++) for (int j = 0; j < D; j++) {
      const int c = i * D + j;
      g1[c] = col(S[c], a);
      if (t == 0) { canon[c] = g1[c]; u64 r = rel({{0, g1[c], F{1}}}, S[c]); if (c == 0) b.rel_S00 = r; }
      else rel({{0, g1[c], F{1}}, {0, canon[c], fi(-1)}}, 0);
      b.rel_a[t].push_back(rel({{1, g1[c], F{1}}}, a));
      g2[c] = col(S[c], z.k[t][i]);
      rel({{0, g2[c], F{1}}, {0, canon[c], fi(-1)}}, 0);
      u64 r = rel({{1, g2[c], F{1}}}, z.k[t][i]); if (i == 0) b.rel_k0[t].push_back(r);
    }
    b.g1_first.push_back(g1[0]);
    std::vector<i64> M(D), delta(D); std::vector<u64> dcell(D);
    for (int j = 0; j < D; j++) {
      i64 Pj = 0; std::vector<AffineTerm> pt;
      for (int i = 0; i < D; i++) { Pj += S[i * D + j] * z.k[t][i]; pt.push_back({2, g2[i * D + j], fi(-1)}); }
      u64 g5 = col(Pj, a); pt.insert(pt.begin(), AffineTerm{0, g5, F{1}}); rel(pt, 0);
      b.rel_a[t].push_back(rel({{1, g5, F{1}}}, a));
      const i64 aP = Pj * a; M[j] = fdiv(aP, i64(1) << (2 * FB)); const i64 rM = aP - M[j] * (i64(1) << (2 * FB));
      check(g_relonly || (M[j] > -BOUND && M[j] < BOUND), "honest M out of range (statement rejected)");
      u64 g6 = col(z.v[t][j] - M[j], beta); if (j == 0) b.g6_first.push_back(g6);
      // 2^2F * (v - g6.a) + r - g5.c = 0
      std::vector<AffineTerm> ft = {{0, g6, fi(-(i64(1) << (2 * FB)))}, {2, g5, fi(-1)}};
      auto mb = bits(rM, 2 * FB, ft, 1); if (j == 0) b.m_rbit0.push_back(mb[0]);
      u64 rf = rel(ft, -(i64(1) << (2 * FB)) * z.v[t][j]);
      // M + 2^18 = bits, M = v - g6.a
      // M (range cell) + g6.a = v
      const u64 mc = rcell(M[j]); if (j == 0) b.rcell_M[t] = mc;
      u64 rr = rel({{0, b.rc[mc], F{1}}, {0, g6, F{1}}}, z.v[t][j]);
      if (j == 0) { b.rel_v0_floor.push_back(rf); b.rel_v0_range.push_back(rr); }
      b.rel_beta[t].push_back(rel({{1, g6, F{1}}}, beta));
      const i64 num = (z.v[t][j] - M[j]) * beta; delta[j] = fdiv(num, one); const i64 rd = num - delta[j] * one;
      const i64 dhi = fdiv(delta[j], BOUND), dlo = delta[j] - dhi * BOUND;  // two limbs, dlo in [0, 2^18)
      // delta lives in g3[0][j].b; created below, so reserve now
      dcell[j] = col(z.k[t][0], delta[j]);
      u64 r0 = rel({{0, dcell[j], F{1}}}, z.k[t][0]); b.rel_k0[t].push_back(r0);
      std::vector<AffineTerm> dt = {{1, dcell[j], fi(one)}, {2, g6, fi(-1)}};
      auto db = bits(rd, FB, dt, 1); if (j == 0) { b.d_rbit0.push_back(db[0]); b.d_cell.push_back(dcell[j]); }
      rel(dt, 0);
      // delta = 2^18 delta_hi + delta_lo, both limbs range cells
      const u64 lo = rcell(dlo), hi = rcell(dhi); if (j == 0) { b.rcell_dlo[t] = lo; b.rcell_dhi[t] = hi; }
      rel({{1, dcell[j], F{1}}, {0, b.rc[hi], fi(-BOUND)}, {0, b.rc[lo], fi(-1)}}, 0);
    }
    // update: S'[i,j] = floor((a*S + k[i]*delta[j]) / 2^F); output gate g4 = S' * q[i]
    std::vector<i64> Sn(D * D); std::vector<u64> g4(D * D);
    for (int i = 0; i < D; i++) for (int j = 0; j < D; j++) {
      const int c = i * D + j;
      u64 g3 = dcell[j];
      if (i > 0) {
        g3 = col(z.k[t][i], delta[j]);
        rel({{0, g3, F{1}}}, z.k[t][i]);
        rel({{1, g3, F{1}}, {1, dcell[j], fi(-1)}}, 0);
      }
      const i64 num = a * S[c] + z.k[t][i] * delta[j]; Sn[c] = fdiv(num, one); const i64 r = num - Sn[c] * one;

      g4[c] = col(Sn[c], z.q[t][i]);
      u64 rq = rel({{1, g4[c], F{1}}}, z.q[t][i]); if (i == 0) b.rel_q0[t].push_back(rq);
      std::vector<AffineTerm> ft = {{0, g4[c], fi(one)}, {2, g1[c], fi(-1)}, {2, g3, fi(-1)}};
      auto rb = bits(r, FB, ft, 1); rel(ft, 0);
      const u64 sc = rcell(Sn[c]); rel({{0, g4[c], F{1}}, {0, b.rc[sc], fi(-1)}}, 0);
      if (c == 0) { b.state_rbits[t] = rb; b.rcell_state[t] = sc; }
    }
    std::vector<i64> o(D);
    for (int j = 0; j < D; j++) {
      i64 sum = 0; std::vector<AffineTerm> ot;
      for (int i = 0; i < D; i++) { sum += Sn[i * D + j] * z.q[t][i]; ot.push_back({2, g4[i * D + j], fi(-1)}); }
      o[j] = fdiv(sum, one); auto ob = bits(sum - o[j] * one, FB, ot, 1);
      if (t == z.T - 1) { b.o_rbits_last.push_back(ob); b.o_rbit0_last.push_back(ob[0]); b.o_rem_last.push_back(sum - o[j] * one); }
      u64 r = rel(ot, -one * z.o[t][j]); if (j == 0) b.rel_o0.push_back(r);
      if (t == z.T - 1) b.o_rel_last.push_back(r);
    }
    if (t == z.T - 1) for (int c = 0; c < D * D; c++) { u64 r = rel({{0, g4[c], F{1}}}, z.S[t][c]); if (c == 0) b.rel_S4_00 = r; }
    for (int c = 0; c < D * D; c++) canon[c] = g4[c];
    b.state_col[t] = g4;
    S = Sn; b.M.push_back(M); b.delta.push_back(delta); b.S.push_back(Sn); b.o.push_back(o);
  }
  // Place the range region: rows a power of two, base aligned to the region's size.
  b.rc_rows = pow2_at_least((b.rcv.size() + RCOLS - 1) / RCOLS);
  const u64 size = b.rc_rows * RCOLS; b.rc_base = (b.cols.size() + size - 1) / size * size;
  b.cols.resize(b.rc_base + size, {F{0}, F{0}, F{0}});
  for (u64 k = 0; k < b.rcv.size(); k++) b.cols[b.rc_base + k] = {fi(b.rcv[k]), F{0}, F{0}};
  for (auto &c : b.rc) c = c - RTAG + b.rc_base;
  for (auto &r : b.rel) for (auto &t : r.terms) if (t.column >= RTAG) t.column = t.column - RTAG + b.rc_base;
  return b;
}

static E eval(const WideRelation &a, const Table &t) { E x = E::zero(); for (auto z : a.terms) x += E::from(z.coefficient) * t.at(z.row, z.column); return x; }
static size_t violated(const std::vector<WideRelation> &rel, const Table &t) { size_t n = 0; for (auto &a : rel) if (!(eval(a, t) == E::from(a.target))) n++; return n; }
static bool products_hold_all(const Table &t) { for (size_t i = 0; i < t.len; i++) if (!(t.at(2, i) == t.at(0, i) * t.at(1, i))) return false; return true; }

// Prover. hostile: each linear row's target is replaced by its true local value on the (tampered)
// committed table, as in research/operators/glm_kda_fixedpoint/test.cpp. Unchanged verifier.
// The RNG cells, read back from row a of the (possibly tampered) table: a field element above
// p/2 is read as negative. cells[0][i * 16 + c] = product column base + c * rows + i.
static std::vector<std::vector<i64>> range_cells(const Built &b, const Table &t) {
  std::vector<std::vector<i64>> cells(1, std::vector<i64>(b.rc_rows * RCOLS));
  for (u64 i = 0; i < b.rc_rows; i++) for (u64 c = 0; c < RCOLS; c++) {
    const u64 v = t.at(0, b.rc_base + c * b.rc_rows + i).c[0].v;
    cells[0][i * RCOLS + c] = v > P / 2 ? -(i64)(P - v) : (i64)v;
  }
  return cells;
}
// rmode: rng_prove_research mode (0 honest digits, 1 wrap out-of-window combinations, 2 one digit moved).
static u64 last_wrapped = 0;
static Writer prove(const LookupRun &run, const Built &bt, const Table &t, bool hostile, int rmode = 0) {
  EngineCpu engine; ToyCoins coins(100); Writer proof; Binder b(LOOKUP_LABEL, run.product.plan); auto in = lookup_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins); FoldMask mask;
  auto g = toy_prove_preamble(pr, in.product, t, mask); auto oracle = pr.st.group(g).members[0];
  for (const auto &a : ch.get(in.relations)) { auto row = wide_row(oracle, a); if (hostile) row.target = eval(a, t); pr.st.add_row(g, std::move(row)); }
  RngOutput out; last_wrapped = 0;
  check(rng_prove_research(pr, in.range, ch.get(in.weights), range_cells(bt, t), g, out, rmode, &last_wrapped), "range check: a combination leaves its window (use rmode 1)");
  E x; pr.st.add_row(g, rng_row(pr, in.range, out, x));
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask)); ch.finish(); pr.st.require_all_tested(); return proof;
}
static double secs(std::chrono::steady_clock::time_point a) { return std::chrono::duration<double>(std::chrono::steady_clock::now() - a).count(); }
static long rss_kb() { rusage u; getrusage(RUSAGE_SELF, &u); return u.ru_maxrss; }

