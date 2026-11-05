// SPDX-License-Identifier: Apache-2.0
// Research-only: bias-corrected stable top-k MoE router with normalized, scaled weights and
// weighted aggregation of expert outputs, proved on the shared committed product oracle
// (toy PSC/IOPP) with wide affine rows (product.h). Usage:
//   test.bin <fixture.bin> honest     one honest proof + verify, prints a JSON line
//   test.bin <fixture.bin> hostile    honest proof + every pre-registered hostile class
//   test.bin <fixture.bin> enum       relation-only enumeration of every candidate routing
// The witness is built from a one-hot selection matrix and explicit quotient/remainder cells;
// it is checked against reference.py (Python sort + big-int floor) stored in the fixture.
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <map>
#include <string>
#include <sys/resource.h>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "product.h"
using namespace blk;

static void check(bool ok, const char *s) { if (!ok) { std::fprintf(stderr, "FAIL: %s\n", s); std::exit(1); } }
static F fi(i64 x) { return x >= 0 ? F{u64(x)} : F{P - u64(-x)}; }
static i64 fdiv(i64 a, i64 b) { i64 q = a / b; if ((a % b) != 0 && ((a < 0) != (b < 0))) --q; return q; }

constexpr int WF = 12;         // weight fraction bits
constexpr int SB = 16;         // unsigned score bits
constexpr i64 BOFF = 1 << 15;  // bias offset: b in [-2^15, 2^15)
constexpr int KB = 26;         // key bits: K < E * 2^17 <= 384 * 2^17 < 2^26
constexpr int WB = 14;         // weight bits: w <= 2^12 * 5/2 < 2^14
constexpr int DB = 19;         // D - 1 bits: D <= 8 * (2^16 - 1) < 2^19 + 1
constexpr int RB = 21;         // remainder and slack bits: RSd * D <= 2 * 2^19 = 2^20 < 2^21

struct Token { std::vector<i64> s, b; std::vector<std::vector<i64>> X; std::vector<i64> y, idx, w; };
struct Fixture { int E, k, h, T, RSn, RSd; std::vector<Token> tok; };
static Fixture load(const char *path) {
  std::ifstream f(path, std::ios::binary); check(bool(f), "open fixture");
  std::vector<i64> w; i64 x; while (f.read((char *)&x, 8)) w.push_back(x);
  size_t p = 0; auto take = [&](size_t n) { check(p + n <= w.size(), "fixture short"); std::vector<i64> r(w.begin() + p, w.begin() + p + n); p += n; return r; };
  Fixture z; auto hd = take(6); z.E = hd[0]; z.k = hd[1]; z.h = hd[2]; z.T = hd[3]; z.RSn = hd[4]; z.RSd = hd[5];
  for (int t = 0; t < z.T; t++) {
    Token k; k.s = take(z.E); k.b = take(z.E); auto xs = take(size_t(z.E) * z.h);
    for (int i = 0; i < z.E; i++) k.X.emplace_back(xs.begin() + size_t(i) * z.h, xs.begin() + size_t(i + 1) * z.h);
    k.y = take(z.h); k.idx = take(z.k); k.w = take(z.k); z.tok.push_back(std::move(k));
  }
  check(p == w.size(), "fixture trailing data");
  return z;
}
// Statement-side admission (not a relation): visible public ranges and the verifier-fixed shape.
static bool admissible(const Fixture &z) {
  if (z.E < 2 || z.E > 384 || z.k < 1 || z.k > z.E || z.k > 8 || z.h < 1 || z.RSd < 1 || z.RSn < 1 || z.RSn > 5 * z.RSd / 2 + 1) return false;
  for (auto &t : z.tok) {
    for (int i = 0; i < z.E; i++) {
      if (t.b[i] < -BOFF || t.b[i] >= BOFF) return false;
      for (auto x : t.X[i]) if (x < -(i64(1) << 15) || x >= (i64(1) << 15)) return false;
    }
    for (auto y : t.y) if (std::llabs(y) >= (i64(1) << 40)) return false;
  }
  return true;
}

// Prover strategy. Honest: rows from the canonical routing, honest weights. Hostile strategies
// replace the selection rows and/or the weight formula; every other cell is then filled as
// consistently as the forged choice allows, and the public output y is the forged one.
enum class WMode { HONEST, BIAS_LEAK, UNNORMALIZED };
struct Strategy {
  std::function<std::vector<std::vector<int>>(int t, const std::vector<int> &honest)> rows;  // null = honest
  WMode wmode = WMode::HONEST;
};

struct Built {
  std::vector<std::array<F, 3>> cols;
  std::vector<WideRelation> rel;
  bool masked = false;                       // a range value did not fit (hostile only)
  std::vector<std::vector<i64>> y;           // statement outputs (forged if hostile)
  std::vector<std::vector<int>> sel_idx;     // honest canonical routing per token
  std::vector<std::vector<i64>> wts;         // weights used
  // public relation indices for mutation attacks
  std::vector<std::vector<u64>> rel_s, rel_b, rel_y; std::vector<std::vector<std::vector<u64>>> rel_X;
  // per token column accounting
  std::map<std::string, size_t> cols_by_part;
};

static std::vector<int> canonical(const Token &t, int E, int k) {
  std::vector<int> o(E); for (int i = 0; i < E; i++) o[i] = i;
  std::stable_sort(o.begin(), o.end(), [&](int a, int b) { i64 ca = t.s[a] + t.b[a], cb = t.s[b] + t.b[b]; return ca != cb ? ca > cb : a < b; });
  o.resize(k); return o;
}

static Built build(const Fixture &z, const Strategy &st, int k_shape = -1) {
  Built b; const int E = z.E, k = k_shape > 0 ? k_shape : z.k, h = z.h; const i64 RSn = z.RSn, RSd = z.RSd;
  std::string part = "selection";
  auto col = [&](i64 x, i64 y) { b.cols.push_back({fi(x), fi(y), fi(x) * fi(y)}); b.cols_by_part[part]++; return u64(b.cols.size() - 1); };
  auto rel = [&](std::vector<AffineTerm> t, i64 target) { b.rel.push_back({std::move(t), fi(target)}); return u64(b.rel.size() - 1); };
  // Unsigned width-bit decomposition of n; each bit column is [x,x,x] with a-b=0 and c-a=0, so x*x=x.
  // Adds coef * n (as bits) to terms. Honest values must fit; hostile values are masked (relation then fails).
  auto bits = [&](i64 n, unsigned width, std::vector<AffineTerm> &terms, i64 coef) {
    if (n < 0 || n >= (i64(1) << width)) { b.masked = true; n &= (i64(1) << width) - 1; }
    std::vector<u64> out;
    for (unsigned i = 0; i < width; i++) {
      i64 x = (n >> i) & 1; u64 c = col(x, x);
      rel({{0, c, F{1}}, {1, c, fi(-1)}}, 0); rel({{2, c, F{1}}, {0, c, fi(-1)}}, 0);
      terms.push_back({0, c, fi(coef * (i64(1) << i))}); out.push_back(c);
    }
    return out;
  };
  // Reuse an existing decomposition (same cells), so two relations see the same value.
  auto reuse = [&](const std::vector<u64> &bc, std::vector<AffineTerm> &terms, i64 coef) {
    for (size_t i = 0; i < bc.size(); i++) terms.push_back({0, bc[i], fi(coef * (i64(1) << i))});
  };
  b.rel_s.resize(z.T); b.rel_b.resize(z.T); b.rel_y.resize(z.T); b.rel_X.resize(z.T);
  for (int t = 0; t < z.T; t++) {
    const Token &tk = z.tok[t]; part = "selection";
    auto honest = canonical(tk, E, k); b.sel_idx.push_back(honest);
    auto rows = st.rows ? st.rows(t, honest) : std::vector<std::vector<int>>();
    if (!st.rows) for (int m = 0; m < k; m++) rows.push_back({honest[m]});
    check(int(rows.size()) == k, "strategy keeps k rows (an empty row models k-1)");
    std::vector<std::vector<i64>> Pm(k, std::vector<i64>(E, 0));
    for (int m = 0; m < k; m++) for (int i : rows[m]) Pm[m][i] = 1;
    auto Kof = [&](int i) { return i64(E) * (tk.s[i] + tk.b[i] + BOFF) + (E - 1 - i); };
    const bool leak = st.wmode == WMode::BIAS_LEAK;
    // (1) public s_i, b_i in one column each; s_i range 16 bits.
    std::vector<u64> sb(E);
    for (int i = 0; i < E; i++) {
      sb[i] = col(tk.s[i], tk.b[i]);
      b.rel_s[t].push_back(rel({{0, sb[i], F{1}}}, tk.s[i]));
      b.rel_b[t].push_back(rel({{1, sb[i], F{1}}}, tk.b[i]));
      std::vector<AffineTerm> r = {{0, sb[i], fi(-1)}}; bits(tk.s[i], SB, r, 1); rel(r, 0);
    }
    // (2) one-hot selection: Boolean P[m,i]; P*K and P*s gathers.
    std::vector<std::vector<u64>> Pb(k, std::vector<u64>(E)), PK(k, std::vector<u64>(E)), PS(k, std::vector<u64>(E));
    for (int m = 0; m < k; m++) {
      std::vector<AffineTerm> rowsum;
      for (int i = 0; i < E; i++) {
        const i64 p = Pm[m][i];
        Pb[m][i] = col(p, p); rel({{0, Pb[m][i], F{1}}, {1, Pb[m][i], fi(-1)}}, 0); rel({{2, Pb[m][i], F{1}}, {0, Pb[m][i], fi(-1)}}, 0);
        rowsum.push_back({0, Pb[m][i], F{1}});
        PK[m][i] = col(p, Kof(i));
        rel({{0, PK[m][i], F{1}}, {0, Pb[m][i], fi(-1)}}, 0);
        // K_i = E*(s_i + b_i + 2^15) + (E-1-i), from the public score/bias cells
        rel({{1, PK[m][i], F{1}}, {0, sb[i], fi(-E)}, {1, sb[i], fi(-E)}}, i64(E) * BOFF + (E - 1 - i));
        const i64 sv = leak ? tk.s[i] + tk.b[i] : tk.s[i];
        PS[m][i] = col(p, sv);
        rel({{0, PS[m][i], F{1}}, {0, Pb[m][i], fi(-1)}}, 0);
        rel({{1, PS[m][i], F{1}}, {0, sb[i], fi(-1)}}, 0);
      }
      rel(rowsum, 1);
    }
    // (3) sel_i = sum_m P[m,i] is Boolean: no duplicate expert.
    std::vector<u64> sel(E); std::vector<i64> selv(E, 0);
    for (int i = 0; i < E; i++) {
      for (int m = 0; m < k; m++) selv[i] += Pm[m][i];
      sel[i] = col(selv[i], selv[i]);
      std::vector<AffineTerm> r = {{0, sel[i], F{1}}}; for (int m = 0; m < k; m++) r.push_back({0, Pb[m][i], fi(-1)}); rel(r, 0);
      rel({{0, sel[i], F{1}}, {1, sel[i], fi(-1)}}, 0); rel({{2, sel[i], F{1}}, {0, sel[i], fi(-1)}}, 0);
    }
    // (4) carriers: G_m = gathered key, S_m = gathered score.
    std::vector<u64> car(k); std::vector<i64> G(k, 0), S(k, 0);
    for (int m = 0; m < k; m++) {
      for (int i = 0; i < E; i++) { G[m] += Pm[m][i] * Kof(i); S[m] += Pm[m][i] * (leak ? tk.s[i] + tk.b[i] : tk.s[i]); }
      car[m] = col(G[m], S[m]);
      std::vector<AffineTerm> rg = {{0, car[m], F{1}}}, rs = {{1, car[m], F{1}}};
      for (int i = 0; i < E; i++) { rg.push_back({2, PK[m][i], fi(-1)}); rs.push_back({2, PS[m][i], fi(-1)}); }
      rel(rg, 0); rel(rs, 0);
    }
    // (5) strict descending order: G_m - G_{m+1} - 1 in [0, 2^26).
    for (int m = 0; m + 1 < k; m++) {
      std::vector<AffineTerm> r = {{0, car[m], fi(-1)}, {0, car[m + 1], F{1}}}; bits(G[m] - G[m + 1] - 1, KB, r, 1); rel(r, -1);
    }
    // (6) threshold: u_i = (1 - sel_i) * (G_{k-1} - K_i - 1) in [0, 2^26).
    for (int i = 0; i < E; i++) {
      const i64 av = G[k - 1] - Kof(i) - 1, bv = 1 - selv[i];
      u64 c = col(av, bv);
      rel({{0, c, F{1}}, {0, car[k - 1], fi(-1)}, {1, PK[0][i], F{1}}}, -1);
      rel({{1, c, F{1}}, {0, sel[i], F{1}}}, 1);
      std::vector<AffineTerm> r = {{2, c, fi(-1)}}; bits(av * bv, KB, r, 1); rel(r, 0);
    }
    // (7) weights: D = sum S_m, D - 1 >= 0, w_m * (RSd*D) + r_m = 2^12*RSn*S_m, 0 <= r_m < RSd*D.
    i64 D = 0; for (int m = 0; m < k; m++) D += S[m];
    i64 Dclaim = st.wmode == WMode::UNNORMALIZED ? (i64(1) << SB) : D;
    std::vector<u64> W(k); std::vector<i64> w(k);
    for (int m = 0; m < k; m++) {
      const i64 num = (i64(1) << WF) * RSn * S[m], den = RSd * Dclaim;
      w[m] = den > 0 ? fdiv(num, den) : 0; const i64 r = num - w[m] * den;
      W[m] = col(w[m], Dclaim);
      std::vector<AffineTerm> rd = {{1, W[m], F{1}}}; for (int j = 0; j < k; j++) rd.push_back({1, car[j], fi(-1)}); rel(rd, 0);
      std::vector<AffineTerm> rf = {{2, W[m], fi(RSd)}, {1, car[m], fi(-(i64(1) << WF) * RSn)}}; auto rbits = bits(r, RB, rf, 1); rel(rf, 0);
      // 0 <= r < RSd*D: RSd*D - r - 1 = slack >= 0, r taken from the SAME bit cells as above.
      std::vector<AffineTerm> rr = {{1, W[m], fi(RSd)}}; reuse(rbits, rr, -1); bits(den - 1 - r, RB, rr, -1); rel(rr, 1);
      std::vector<AffineTerm> rw = {{0, W[m], F{1}}}; bits(w[m], WB, rw, -1); rel(rw, 0);
      if (m == 0) { std::vector<AffineTerm> r1 = {{1, W[m], F{1}}}; bits(Dclaim - 1, DB, r1, -1); rel(r1, 1); }
    }
    b.wts.push_back(w);
    // (8) aggregation: XG[m][d] = sum_i P[m,i] X_i[d]; y[d] = floor(sum_m w_m XG[m][d] / 2^12).
    part = "aggregation";
    std::vector<std::vector<u64>> AG(k, std::vector<u64>(h));
    b.rel_X[t].assign(E, std::vector<u64>());
    std::vector<i64> yv(h, 0);
    for (int m = 0; m < k; m++) for (int d = 0; d < h; d++) {
      i64 xg = 0; std::vector<AffineTerm> rx;
      for (int i = 0; i < E; i++) {
        u64 c = col(Pm[m][i], tk.X[i][d]); xg += Pm[m][i] * tk.X[i][d];
        rel({{0, c, F{1}}, {0, Pb[m][i], fi(-1)}}, 0);
        u64 r = rel({{1, c, F{1}}}, tk.X[i][d]); if (d == 0) b.rel_X[t][i].push_back(r);
        rx.push_back({2, c, fi(-1)});
      }
      AG[m][d] = col(w[m], xg);
      rel({{0, AG[m][d], F{1}}, {0, W[m], fi(-1)}}, 0);
      rx.insert(rx.begin(), AffineTerm{1, AG[m][d], F{1}}); rel(rx, 0);
    }
    for (int d = 0; d < h; d++) {
      i64 sum = 0; std::vector<AffineTerm> ry;
      for (int m = 0; m < k; m++) { sum += w[m] * [&] { i64 x = 0; for (int i = 0; i < E; i++) x += Pm[m][i] * tk.X[i][d]; return x; }(); ry.push_back({2, AG[m][d], fi(-1)}); }
      yv[d] = fdiv(sum, i64(1) << WF); bits(sum - yv[d] * (i64(1) << WF), WF, ry, 1);
      b.rel_y[t].push_back(rel(ry, -(i64(1) << WF) * yv[d]));
    }
    b.y.push_back(yv);
  }
  return b;
}

static E eval(const WideRelation &a, const Table &t) { E x = E::zero(); for (auto z : a.terms) x += E::from(z.coefficient) * t.at(z.row, z.column); return x; }
static size_t violated(const std::vector<WideRelation> &rel, const Table &t) { size_t n = 0; for (auto &a : rel) if (!(eval(a, t) == E::from(a.target))) n++; return n; }
static bool products_hold_all(const Table &t) { for (size_t i = 0; i < t.len; i++) if (!(t.at(2, i) == t.at(0, i) * t.at(1, i))) return false; return true; }
static unsigned logn(size_t n) { unsigned L = 1; while ((u64(1) << L) < n) L++; return L; }
static Table table_of(const Built &b, unsigned L) {
  Table tab(1, 3, u64(1) << L);
  for (size_t c = 0; c < b.cols.size(); c++) for (int r = 0; r < 3; r++) tab.set(r, c, E::from(b.cols[c][r]));
  return tab;
}
static Setting research_setting() { Setting set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES; set.target = 10; set.set_work(ErrorKind::QUERY, Scope::REQUEST, 6); return set; }
static WideRun sized(const std::vector<WideRelation> &rel, unsigned L) { return wide_size(research_setting(), L, L + 1, L + 1, {{1, 1, L, L}, {0, 0, L, L}}, rel); }

// Prover. hostile: each linear row's target is replaced by its true local value on the committed
// table, as in research/operators/qwen_deltanet/test.cpp. The verifier is unchanged.
static Writer prove(const WideRun &run, const Table &t, bool hostile) {
  EngineCpu engine; ToyCoins coins(100); Writer proof; Binder b(MOE_LABEL, run.product.plan); auto in = wide_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins); FoldMask mask;
  auto g = toy_prove_preamble(pr, in.product, t, mask); auto oracle = pr.st.group(g).members[0];
  for (const auto &a : ch.get(in.relations)) { auto row = wide_row(oracle, a); if (hostile) row.target = eval(a, t); pr.st.add_row(g, std::move(row)); }
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask)); ch.finish(); pr.st.require_all_tested(); return proof;
}
static double secs(std::chrono::steady_clock::time_point a) { return std::chrono::duration<double>(std::chrono::steady_clock::now() - a).count(); }
static long rss_kb() { rusage u; getrusage(RUSAGE_SELF, &u); return u.ru_maxrss; }

int main(int argc, char **argv) {
  check(argc == 3, "usage: test.bin <fixture.bin> honest|hostile|enum");
  const std::string mode = argv[2];
  auto z = load(argv[1]); check(admissible(z), "public inputs admissible");
  const int E = z.E, k = z.k;

  if (mode == "enum") {
    // Relation-level uniqueness: every ordered k-tuple of experts (with repetition), as one-hot rows,
    // with honest weight/output cells for that choice. Count tuples whose witness satisfies all relations.
    check(z.T == 1 && k <= 3, "enum fixture: T = 1, k <= 3");
    std::vector<int> tup(k, 0); size_t total = 0, distinct = 0, sat = 0, sat_distinct = 0; bool sat_is_ref = false;
    const auto ref = canonical(z.tok[0], E, k);
    for (;;) {
      bool dist = true; for (int a = 0; a < k; a++) for (int c = a + 1; c < k; c++) if (tup[a] == tup[c]) dist = false;
      Strategy st; auto cur = tup; st.rows = [&](int, const std::vector<int> &) { std::vector<std::vector<int>> r; for (int x : cur) r.push_back({x}); return r; };
      Built b = build(z, st); Table tab = table_of(b, logn(b.cols.size()));
      const bool ok = products_hold_all(tab) && violated(b.rel, tab) == 0;
      total++; distinct += dist; if (ok) { sat++; sat_distinct += dist; std::vector<int> v(tup.begin(), tup.end()); sat_is_ref = (v == ref); }
      int p = k - 1; while (p >= 0 && ++tup[p] == E) { tup[p] = 0; p--; } if (p < 0) break;
    }
    // Ties present in this fixture (corrected-score equalities among the top k+1).
    auto top = canonical(z.tok[0], E, std::min(E, k + 1)); int ties = 0;
    for (int m = 0; m + 1 < int(top.size()); m++) ties += (z.tok[0].s[top[m]] + z.tok[0].b[top[m]] == z.tok[0].s[top[m + 1]] + z.tok[0].b[top[m + 1]]);
    std::printf("{\"mode\":\"enum\",\"E\":%d,\"k\":%d,\"tuples\":%zu,\"distinct_tuples\":%zu,\"satisfying\":%zu,\"satisfying_distinct\":%zu,\"unique_equals_reference\":%s,\"adjacent_ties_in_top_k_plus_1\":%d}\n",
                E, k, total, distinct, sat, sat_distinct, (sat == 1 && sat_is_ref) ? "true" : "false", ties);
    return (sat == 1 && sat_is_ref) ? 0 : 1;
  }

  auto t0 = std::chrono::steady_clock::now();
  Built b = build(z, Strategy{});
  check(!b.masked, "honest values fit their ranges");
  for (int t = 0; t < z.T; t++) {
    std::vector<i64> idx(b.sel_idx[t].begin(), b.sel_idx[t].end());
    check(idx == z.tok[t].idx && b.wts[t] == z.tok[t].w && b.y[t] == z.tok[t].y, "C++ witness equals reference.py routing, weights and outputs");
  }
  const unsigned L = logn(b.cols.size()); Table tab = table_of(b, L);
  check(products_hold_all(tab), "honest products"); check(violated(b.rel, tab) == 0, "honest relations hold");
  size_t terms = 0; for (auto &a : b.rel) terms += a.terms.size();
  auto run = sized(b.rel, L); check(run.product.plan->holds(), "plan holds");
  const double build_s = secs(t0);
  auto tp = std::chrono::steady_clock::now(); auto proof = prove(run, tab, false); const double prove_s = secs(tp);
  auto tv = std::chrono::steady_clock::now(); const bool ok = wide_verify(run, proof.data(), proof.size()); const double verify_s = secs(tv);
  std::printf("{\"mode\":\"honest\",\"accept\":%s,\"E\":%d,\"k\":%d,\"h\":%d,\"T\":%d,\"columns_used\":%zu,\"selection_columns_per_token\":%.1f,\"aggregation_columns_per_token\":%.1f,\"log_length\":%u,\"relations\":%zu,\"relation_terms\":%zu,\"proof_bytes\":%zu,\"build_s\":%.3f,\"prove_s\":%.3f,\"verify_s\":%.3f,\"peak_rss_kb\":%ld}\n",
              ok ? "true" : "false", E, k, z.h, z.T, b.cols.size(), double(b.cols_by_part["selection"]) / z.T, double(b.cols_by_part["aggregation"]) / z.T,
              L, b.rel.size(), terms, proof.size(), build_s, prove_s, verify_s, rss_kb());
  std::fflush(stdout);
  check(ok, "honest proof accepted");
  if (mode != "hostile") return 0;

  int rejected = 0, total = 0;
  auto report = [&](const char *cls, const std::string &what, size_t viol, bool claim_false, bool accepted) {
    total++; if (!accepted) rejected++;
    std::printf("{\"mode\":\"hostile\",\"class\":\"%s\",\"attack\":\"%s\",\"violated_relations\":%zu,\"output_claim_differs\":%s,\"rejected\":%s}\n",
                cls, what.c_str(), viol, claim_false ? "true" : "false", accepted ? "false" : "true");
    std::fflush(stdout);
  };
  // Complete hostile prover: forged witness, statement = the forged public output, unchanged verifier.
  auto complete = [&](const char *cls, const std::string &what, Strategy st) {
    Built hb = build(z, st);
    check(hb.cols.size() == b.cols.size() && hb.rel.size() == b.rel.size(), "hostile witness has the honest shape");
    Table bad = table_of(hb, L); check(products_hold_all(bad), "attack preserves every product gate");
    const size_t viol = violated(hb.rel, bad);
    auto hrun = sized(hb.rel, L); auto p = prove(hrun, bad, true);
    report(cls, what, viol, hb.y != b.y, wide_verify(hrun, p.data(), p.size()));
  };
  const Token &t0k = z.tok[0];
  auto unselected_best = [&](const std::vector<int> &hon) {  // best unselected expert by corrected key
    auto top = canonical(t0k, E, k + 1); return top[k]; (void)hon;
  };
  auto on_token0 = [&](std::function<std::vector<std::vector<int>>(const std::vector<int> &)> f) {
    Strategy st; st.rows = [f, k](int t, const std::vector<int> &hon) {
      if (t != 0) { std::vector<std::vector<int>> r; for (int m = 0; m < k; m++) r.push_back({hon[m]}); return r; }
      return f(hon);
    }; return st;
  };
  auto rows_of = [](const std::vector<int> &v) { std::vector<std::vector<int>> r; for (int x : v) r.push_back({x}); return r; };
  // a1: wrong expert chosen.
  complete("a1-wrong-expert", "k-th selected replaced by best unselected", on_token0([&](const std::vector<int> &hon) { auto v = hon; v[k - 1] = unselected_best(hon); return rows_of(v); }));
  complete("a1-wrong-expert", "first selected replaced by best unselected, re-sorted by key", on_token0([&](const std::vector<int> &hon) {
    auto v = hon; v[0] = unselected_best(hon);
    std::stable_sort(v.begin(), v.end(), [&](int a, int c) { i64 ka = E * (t0k.s[a] + t0k.b[a] + BOFF) + (E - 1 - a), kc = E * (t0k.s[c] + t0k.b[c] + BOFF) + (E - 1 - c); return ka > kc; });
    return rows_of(v); }));
  complete("a1-wrong-expert", "lowest-scored expert replaces the k-th selected", on_token0([&](const std::vector<int> &hon) {
    auto all = canonical(t0k, E, E); auto v = hon; v[k - 1] = all[E - 1]; return rows_of(v); }));
  // a2: tie order. Fixture forces an exact tie at ranks 0/1 and at the k boundary.
  complete("a2-tie-order", "selected ranks 0 and 1 (exact corrected-score tie) swapped", on_token0([&](const std::vector<int> &hon) { auto v = hon; std::swap(v[0], v[1]); return rows_of(v); }));
  complete("a2-tie-order", "boundary tie: higher-index tied expert selected instead of lower", on_token0([&](const std::vector<int> &hon) {
    auto v = hon; int c = unselected_best(hon);
    check(t0k.s[c] + t0k.b[c] == t0k.s[v[k - 1]] + t0k.b[v[k - 1]] && c > v[k - 1], "fixture has a boundary tie");
    v[k - 1] = c; return rows_of(v); }));
  // a3: bias leaking into weights.
  { Strategy st; st.wmode = WMode::BIAS_LEAK; complete("a3-bias-in-weights", "weights from s+b (gathered score wire carries s+b)", st); }
  // a4: unnormalized weights.
  { Strategy st; st.wmode = WMode::UNNORMALIZED; complete("a4-unnormalized", "weights = 2^12*RS*s/2^16, claimed denominator 2^16", st); }
  // a5: duplicate expert.
  complete("a5-duplicate", "rank-0 expert also in slot 1", on_token0([&](const std::vector<int> &hon) { auto v = hon; v[1] = v[0]; return rows_of(v); }));
  complete("a5-duplicate", "rank-0 expert also in the last slot", on_token0([&](const std::vector<int> &hon) { auto v = hon; v[k - 1] = v[0]; return rows_of(v); }));
  // a6: k-1 and k+1 experts selected.
  complete("a6-k-minus-1", "last slot empty (k-1 experts)", on_token0([&](const std::vector<int> &hon) { auto r = rows_of(hon); r[k - 1].clear(); return r; }));
  complete("a6-k-plus-1", "last slot holds two experts (k+1 experts)", on_token0([&](const std::vector<int> &hon) { auto r = rows_of(hon); r[k - 1].push_back(unselected_best(hon)); return r; }));
  // a7: public statement mutations against the honest proof.
  auto mutate = [&](const char *cls, const std::string &what, std::function<void(std::vector<WideRelation> &)> m) {
    auto rel = b.rel; m(rel); auto changed = sized(rel, L);
    report(cls, what, 0, true, wide_verify(changed, proof.data(), proof.size()));
  };
  auto add = [&](std::vector<WideRelation> &r, u64 i, i64 d) { r[i].target = r[i].target + fi(d); };
  const int p0 = b.sel_idx[0][0], ub = canonical(t0k, E, k + 1)[k];
  mutate("a7-public", "s[p0] += 1 (selected expert)", [&](auto &r) { add(r, b.rel_s[0][p0], 1); });
  mutate("a7-public", "s[best unselected] += 1", [&](auto &r) { add(r, b.rel_s[0][ub], 1); });
  mutate("a7-public", "b[p0] -= 1", [&](auto &r) { add(r, b.rel_b[0][p0], -1); });
  mutate("a7-public", "X[p0][0] += 1 (every binding)", [&](auto &r) { for (u64 i : b.rel_X[0][p0]) add(r, i, 1); });
  mutate("a7-public", "y_1[0] += 1", [&](auto &r) { add(r, b.rel_y[0][0], -(i64(1) << WF)); });
  mutate("a7-public", "y_T[h-1] -= 1", [&](auto &r) { add(r, b.rel_y[z.T - 1][z.h - 1], i64(1) << WF); });
  // a8: proof bytes, truncation, trailing byte, other shapes and other transcript label.
  auto bytes = proof.bytes(); const size_t n = bytes.size();
  auto vb = [&](const WideRun &r, const u8 *d, size_t sz) { return run_verifier(MOE_LABEL, r.product.plan, r, wide_bind, wide_decide, d, sz); };
  for (int q = 0; q < 10; q++) { size_t i = (n * (2 * q + 1)) / 20; bytes[i] ^= 1; report("a8-bytes", "flip one bit", 0, false, vb(run, bytes.data(), bytes.size())); bytes[i] ^= 1; }
  for (int q = 0; q < 5; q++) { size_t cut = q == 4 ? n - 1 : (n * q) / 4; report("a8-bytes", "truncate", 0, false, vb(run, bytes.data(), cut)); }
  bytes.push_back(0); report("a8-bytes", "trailing byte", 0, false, vb(run, bytes.data(), bytes.size())); bytes.pop_back();
  report("a8-label", "verify under the DeltaNet wide transcript label", 0, false, run_verifier(0x46505157ULL, run.product.plan, run, wide_bind, wide_decide, bytes.data(), bytes.size()));
  for (int dk : {-1, +1}) {
    Built sb = build(z, Strategy{}, k + dk); auto r2 = sized(sb.rel, logn(sb.cols.size()));
    report("a8-shape", dk < 0 ? "honest proof against the k-1 statement" : "honest proof against the k+1 statement", 0, true, vb(r2, bytes.data(), bytes.size()));
  }
  std::printf("{\"mode\":\"hostile-summary\",\"rejected\":%d,\"total\":%d,\"peak_rss_kb\":%ld}\n", rejected, total, rss_kb());
  return rejected == total ? 0 : 1;
}
