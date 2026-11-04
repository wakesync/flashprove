// SPDX-License-Identifier: Apache-2.0
// Research-only: one Qwen3.8 Gated DeltaNet head (state D x D, D = 128) over T tokens,
// staged floor at F fractional bits, proved on the shared committed product oracle
// (toy PSC/IOPP) with wide affine rows (product.h). Usage:
//   test.bin <fixture.bin> honest            one honest proof + verify, prints a JSON line
//   test.bin <fixture.bin> hostile           honest proof + every pre-registered hostile class
// Witness lowering here uses explicit quotient/remainder arithmetic and is checked
// cell by cell against reference.py's numpy floor division (stored in the fixture).
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
#include "product.h"
using namespace blk;

static void check(bool ok, const char *s) { if (!ok) { std::fprintf(stderr, "FAIL: %s\n", s); std::exit(1); } }
static F fi(i64 x) { return x >= 0 ? F{u64(x)} : F{P - u64(-x)}; }
static i64 fdiv(i64 a, i64 b) { i64 q = a / b; if ((a % b) != 0 && ((a < 0) != (b < 0))) --q; return q; }
constexpr i64 BOUND = i64(1) << 18;   // signed 19-bit contract (smallness bound)

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
      if (std::llabs(z.k[t][i]) > one || std::llabs(z.q[t][i]) > one || std::llabs(z.v[t][i]) >= BOUND || std::llabs(z.o[t][i]) >= BOUND) return false;
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
  std::vector<std::vector<i64>> M, delta, S, o;
};
static Built build(const Fixture &z) {
  Built b; const int D = z.D, FB = z.F; const i64 one = i64(1) << FB;
  auto col = [&](i64 x, i64 y) { b.cols.push_back({fi(x), fi(y), fi(x) * fi(y)}); return u64(b.cols.size() - 1); };
  auto rel = [&](std::vector<AffineTerm> t, i64 target) { b.rel.push_back({std::move(t), fi(target)}); return u64(b.rel.size() - 1); };
  // Unsigned width-bit decomposition of n (honest n must fit; builder asserts). Returns the
  // bit columns; each bit column is [x,x,x] with relations a-b=0, c-a=0, so x*x=x (boolean).
  auto bits = [&](i64 n, unsigned width, std::vector<AffineTerm> &terms, i64 coef) {
    check(n >= 0 && n < (i64(1) << width), "honest value outside its declared bit width");
    std::vector<u64> out;
    for (unsigned i = 0; i < width; i++) {
      i64 x = (n >> i) & 1; u64 c = col(x, x);
      rel({{0, c, F{1}}, {1, c, fi(-1)}}, 0); rel({{2, c, F{1}}, {0, c, fi(-1)}}, 0);
      terms.push_back({0, c, fi(coef * (i64(1) << i))}); out.push_back(c);
    }
    return out;
  };
  std::vector<i64> S = z.S0; std::vector<u64> canon(D * D);
  b.state_col.resize(z.T); b.state_rbits.resize(z.T); b.state_qbits.resize(z.T);
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
      check(M[j] > -BOUND && M[j] < BOUND, "honest M out of range (statement rejected)");
      u64 g6 = col(z.v[t][j] - M[j], beta); if (j == 0) b.g6_first.push_back(g6);
      // 2^2F * (v - g6.a) + r - g5.c = 0
      std::vector<AffineTerm> ft = {{0, g6, fi(-(i64(1) << (2 * FB)))}, {2, g5, fi(-1)}};
      auto mb = bits(rM, 2 * FB, ft, 1); if (j == 0) b.m_rbit0.push_back(mb[0]);
      u64 rf = rel(ft, -(i64(1) << (2 * FB)) * z.v[t][j]);
      // M + 2^18 = bits, M = v - g6.a
      std::vector<AffineTerm> mt = {{0, g6, fi(-1)}}; bits(M[j] + BOUND, 19, mt, -1);
      u64 rr = rel(mt, -BOUND - z.v[t][j]);
      if (j == 0) { b.rel_v0_floor.push_back(rf); b.rel_v0_range.push_back(rr); }
      b.rel_beta[t].push_back(rel({{1, g6, F{1}}}, beta));
      const i64 num = (z.v[t][j] - M[j]) * beta; delta[j] = fdiv(num, one); const i64 rd = num - delta[j] * one;
      check(delta[j] > -BOUND && delta[j] < BOUND, "honest delta out of range (statement rejected)");
      // delta lives in g3[0][j].b; created below, so reserve now
      dcell[j] = col(z.k[t][0], delta[j]);
      u64 r0 = rel({{0, dcell[j], F{1}}}, z.k[t][0]); b.rel_k0[t].push_back(r0);
      std::vector<AffineTerm> dt = {{1, dcell[j], fi(one)}, {2, g6, fi(-1)}};
      auto db = bits(rd, FB, dt, 1); if (j == 0) { b.d_rbit0.push_back(db[0]); b.d_cell.push_back(dcell[j]); }
      rel(dt, 0);
      std::vector<AffineTerm> drt = {{1, dcell[j], F{1}}}; bits(delta[j] + BOUND, 19, drt, -1); rel(drt, -BOUND);
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
      check(Sn[c] > -BOUND && Sn[c] < BOUND, "honest state out of range (statement rejected)");
      g4[c] = col(Sn[c], z.q[t][i]);
      u64 rq = rel({{1, g4[c], F{1}}}, z.q[t][i]); if (i == 0) b.rel_q0[t].push_back(rq);
      std::vector<AffineTerm> ft = {{0, g4[c], fi(one)}, {2, g1[c], fi(-1)}, {2, g3, fi(-1)}};
      auto rb = bits(r, FB, ft, 1); rel(ft, 0);
      std::vector<AffineTerm> st = {{0, g4[c], F{1}}}; auto qb = bits(Sn[c] + BOUND, 19, st, -1); rel(st, -BOUND);
      if (c == 0) { b.state_rbits[t] = rb; b.state_qbits[t] = qb; }
    }
    std::vector<i64> o(D);
    for (int j = 0; j < D; j++) {
      i64 sum = 0; std::vector<AffineTerm> ot;
      for (int i = 0; i < D; i++) { sum += Sn[i * D + j] * z.q[t][i]; ot.push_back({2, g4[i * D + j], fi(-1)}); }
      o[j] = fdiv(sum, one); bits(sum - o[j] * one, FB, ot, 1);
      u64 r = rel(ot, -one * z.o[t][j]); if (j == 0) b.rel_o0.push_back(r);
    }
    if (t == z.T - 1) for (int c = 0; c < D * D; c++) { u64 r = rel({{0, g4[c], F{1}}}, z.S[t][c]); if (c == 0) b.rel_S4_00 = r; }
    for (int c = 0; c < D * D; c++) canon[c] = g4[c];
    b.state_col[t] = g4;
    S = Sn; b.M.push_back(M); b.delta.push_back(delta); b.S.push_back(Sn); b.o.push_back(o);
  }
  return b;
}

static E eval(const WideRelation &a, const Table &t) { E x = E::zero(); for (auto z : a.terms) x += E::from(z.coefficient) * t.at(z.row, z.column); return x; }
static size_t violated(const std::vector<WideRelation> &rel, const Table &t) { size_t n = 0; for (auto &a : rel) if (!(eval(a, t) == E::from(a.target))) n++; return n; }
static bool products_hold_all(const Table &t) { for (size_t i = 0; i < t.len; i++) if (!(t.at(2, i) == t.at(0, i) * t.at(1, i))) return false; return true; }

// Prover. hostile: each linear row's target is replaced by its true local value on the (tampered)
// committed table, as in research/operators/glm_kda_fixedpoint/test.cpp. Unchanged verifier.
static Writer prove(const WideRun &run, const Table &t, bool hostile) {
  EngineCpu engine; ToyCoins coins(100); Writer proof; Binder b(WIDE_LABEL, run.product.plan); auto in = wide_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins); FoldMask mask;
  auto g = toy_prove_preamble(pr, in.product, t, mask); auto oracle = pr.st.group(g).members[0];
  for (const auto &a : ch.get(in.relations)) { auto row = wide_row(oracle, a); if (hostile) row.target = eval(a, t); pr.st.add_row(g, std::move(row)); }
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask)); ch.finish(); pr.st.require_all_tested(); return proof;
}
static double secs(std::chrono::steady_clock::time_point a) { return std::chrono::duration<double>(std::chrono::steady_clock::now() - a).count(); }
static long rss_kb() { rusage u; getrusage(RUSAGE_SELF, &u); return u.ru_maxrss; }

int main(int argc, char **argv) {
  check(argc == 3, "usage: test.bin <fixture.bin> honest|hostile");
  const std::string mode = argv[2];
  auto z = load(argv[1]); check(admissible(z), "public inputs admissible");
  auto t0 = std::chrono::steady_clock::now();
  Built b = build(z);
  // Independent lowering vs reference.py (numpy floor) values, cell by cell.
  for (int t = 0; t < z.T; t++) { check(b.M[t] == z.M[t] && b.delta[t] == z.delta[t] && b.S[t] == z.S[t] && b.o[t] == z.o[t], "C++ lowering equals reference.py"); }
  unsigned L = 1; while ((u64(1) << L) < b.cols.size()) L++;
  Table tab(1, 3, u64(1) << L);
  for (size_t c = 0; c < b.cols.size(); c++) for (int r = 0; r < 3; r++) tab.set(r, c, E::from(b.cols[c][r]));
  // Padding columns are 0*0=0. Check relations and products on the honest table.
  check(products_hold_all(tab), "honest products"); check(violated(b.rel, tab) == 0, "honest relations hold");
  Setting set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES; set.target = 10; set.set_work(ErrorKind::QUERY, Scope::REQUEST, 6);
  size_t terms = 0; for (auto &a : b.rel) terms += a.terms.size();
  auto run = wide_size(set, L, L + 1, L + 1, {{1, 1, L, L}, {0, 0, L, L}}, b.rel);
  check(run.product.plan->holds(), "plan holds");
  const double build_s = secs(t0);
  auto tp = std::chrono::steady_clock::now(); auto proof = prove(run, tab, false); const double prove_s = secs(tp);
  auto tv = std::chrono::steady_clock::now(); const bool ok = wide_verify(run, proof.data(), proof.size()); const double verify_s = secs(tv);
  std::printf("{\"mode\":\"honest\",\"accept\":%s,\"D\":%d,\"T\":%d,\"F\":%d,\"columns_used\":%zu,\"log_length\":%u,\"relations\":%zu,\"relation_terms\":%zu,\"proof_bytes\":%zu,\"build_s\":%.3f,\"prove_s\":%.3f,\"verify_s\":%.3f,\"peak_rss_kb\":%ld}\n",
              ok ? "true" : "false", z.D, z.T, z.F, b.cols.size(), L, b.rel.size(), terms, proof.size(), build_s, prove_s, verify_s, rss_kb());
  std::fflush(stdout);
  check(ok, "honest proof accepted");
  if (mode != "hostile") return 0;

  int classes_ok = 0, total = 0;
  auto report = [&](const char *cls, const char *what, size_t viol, bool accepted) {
    total++; if (!accepted) classes_ok++;
    std::printf("{\"mode\":\"hostile\",\"class\":\"%s\",\"attack\":\"%s\",\"violated_relations\":%zu,\"rejected\":%s}\n", cls, what, viol, accepted ? "false" : "true");
    std::fflush(stdout);
  };
  // Complete hostile proof on a tampered table (products preserved, public relations unchanged).
  auto complete = [&](const char *cls, const char *what, std::function<void(Table &)> tamper) {
    Table bad = tab; tamper(bad);
    check(products_hold_all(bad), "attack preserves every product gate");
    const size_t viol = violated(b.rel, bad);
    auto p = prove(run, bad, true);
    report(cls, what, viol, wide_verify(run, p.data(), p.size()));
  };
  auto setcol = [&](Table &t, u64 c, E x, E y) { t.set(0, c, x); t.set(1, c, y); t.set(2, c, x * y); };
  auto bump0 = [&](Table &t, u64 c, E d) { setcol(t, c, t.at(0, c) + d, t.at(1, c)); };
  auto bump1 = [&](Table &t, u64 c, E d) { setcol(t, c, t.at(0, c), t.at(1, c) + d); };
  const E one = E::one(); const E twoF = E::from(fi(i64(1) << z.F));
  // c1: private mid-sequence state cell (S_1 and S_3) +1
  complete("c1-state", "S_1[0,0] += 1", [&](Table &t) { bump0(t, b.state_col[0][0], one); });
  if (z.T >= 3) complete("c1-state", "S_3[0,0] += 1", [&](Table &t) { bump0(t, b.state_col[2][0], one); });
  // c2: S_2[0,0] += 1 with floor equation preserved: low remainder bit -= 2^F (non-boolean),
  // quotient range bits re-derived honestly for the new value.
  complete("c2-state-floor-preserving", "S_2[0,0] += 1, remainder -= 2^F, range bits consistent", [&](Table &t) {
    const int tt = z.T >= 2 ? 1 : 0; u64 c = b.state_col[tt][0]; bump0(t, c, one);
    u64 rb = b.state_rbits[tt][0]; E x = t.at(0, rb) - twoF; t.set(0, rb, x); t.set(1, rb, x); t.set(2, rb, x * x);
    i64 nv = b.S[tt][0] + 1 + BOUND; for (unsigned i = 0; i < 19; i++) { u64 qc = b.state_qbits[tt][i]; E bit = E::from(F{u64((nv >> i) & 1)}); setcol(t, qc, bit, bit); }
  });
  // c3: decay tampered in one gate (public a unchanged)
  complete("c3-decay", "token-1 decay gate operand a += 1", [&](Table &t) { bump1(t, b.g1_first[0], one); });
  // c4: beta tampered in one gate
  complete("c4-beta", "token-1 beta gate operand += 1", [&](Table &t) { bump1(t, b.g6_first[0], one); });
  // c5: memory-read and delta floors shifted (truncation toward zero style): quotient +1, remainder -2^k
  complete("c5-memory-floor", "M[0] += 1 (v-M operand -= 1), remainder -= 2^2F", [&](Table &t) {
    bump0(t, b.g6_first[0], E::zero() - one); u64 rb = b.m_rbit0[0]; E x = t.at(0, rb) - E::from(fi(i64(1) << (2 * z.F))); t.set(0, rb, x); t.set(1, rb, x); t.set(2, rb, x * x);
  });
  complete("c5-delta-floor", "delta[0] += 1, remainder -= 2^F", [&](Table &t) {
    bump1(t, b.d_cell[0], one); u64 rb = b.d_rbit0[0]; E x = t.at(0, rb) - twoF; t.set(0, rb, x); t.set(1, rb, x); t.set(2, rb, x * x);
  });
  // c6: one range bit flipped (state range bit, remainder bit)
  complete("c6-range-bit", "S_1[0,0] range bit 3 flipped", [&](Table &t) { u64 c = b.state_qbits[0][3]; E x = one - t.at(0, c); setcol(t, c, x, x); });
  complete("c6-range-bit", "S_1[0,0] remainder bit 0 flipped", [&](Table &t) { u64 c = b.state_rbits[0][0]; E x = one - t.at(0, c); setcol(t, c, x, x); });
  // c3/c4/c7: public statement mutations against the honest proof
  auto mutate = [&](const char *cls, const char *what, std::function<void(std::vector<WideRelation> &)> m) {
    auto rel = b.rel; m(rel); auto changed = wide_size(set, L, L + 1, L + 1, {{1, 1, L, L}, {0, 0, L, L}}, rel);
    report(cls, what, 0, wide_verify(changed, proof.data(), proof.size()));
  };
  auto add = [&](std::vector<WideRelation> &r, u64 i, i64 d) { r[i].target = r[i].target + fi(d); };
  mutate("c3-decay", "public a_1 += 1 (every binding)", [&](auto &r) { for (u64 i : b.rel_a[0]) add(r, i, 1); });
  mutate("c4-beta", "public beta_1 += 1 (every binding)", [&](auto &r) { for (u64 i : b.rel_beta[0]) add(r, i, 1); });
  mutate("c7-public", "public S0[0,0] += 1", [&](auto &r) { add(r, b.rel_S00, 1); });
  mutate("c7-public", "public k_1[0] += 1 (every binding)", [&](auto &r) { for (u64 i : b.rel_k0[0]) add(r, i, 1); });
  mutate("c7-public", "public v_1[0] += 1", [&](auto &r) { add(r, b.rel_v0_floor[0], -(i64(1) << (2 * z.F))); add(r, b.rel_v0_range[0], -1); });
  mutate("c7-public", "public q_1[0] += 1 (every binding)", [&](auto &r) { for (u64 i : b.rel_q0[0]) add(r, i, 1); });
  mutate("c7-public", "public o_4[0] += 1", [&](auto &r) { add(r, b.rel_o0[z.T - 1], -(i64(1) << z.F)); });
  mutate("c7-public", "public S_4[0,0] += 1", [&](auto &r) { add(r, b.rel_S4_00, 1); });
  // c8: byte flips, truncations, trailing byte, cross-domain
  auto bytes = proof.bytes(); const size_t n = bytes.size();
  for (int k = 0; k < 12; k++) { size_t i = (n * (2 * k + 1)) / 24; bytes[i] ^= 1; report("c8-bytes", "flip one bit", 0, run_verifier(WIDE_LABEL, run.product.plan, run, wide_bind, wide_decide, bytes.data(), bytes.size())); bytes[i] ^= 1; }
  for (int k = 0; k < 9; k++) { size_t cut = k == 8 ? n - 1 : (n * k) / 8; report("c8-bytes", "truncate", 0, run_verifier(WIDE_LABEL, run.product.plan, run, wide_bind, wide_decide, bytes.data(), cut)); }
  bytes.push_back(0); report("c8-bytes", "trailing byte", 0, run_verifier(WIDE_LABEL, run.product.plan, run, wide_bind, wide_decide, bytes.data(), bytes.size())); bytes.pop_back();
  report("c8-bytes", "verify under the affine_rows transcript label", 0, run_verifier(AFFINE_LABEL, run.product.plan, run, wide_bind, wide_decide, bytes.data(), bytes.size()));
  std::printf("{\"mode\":\"hostile-summary\",\"rejected\":%d,\"total\":%d,\"peak_rss_kb\":%ld}\n", classes_ok, total, rss_kb());
  return classes_ok == total ? 0 : 1;
}
