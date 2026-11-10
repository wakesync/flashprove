// Proves and verifies one generated KDA slice on the CPU, then runs hostile cases.
//   run FIXTURE.bin TARGET WORK LOG_LEN LOG_N MASK_LOG_N STAGES k h log_n mask_log_n ... [--skip-hostile-provers]
// LOG_LEN >= the fixture's own log-length: unused columns are 0*0=0 and nothing reads them.
// Prints one JSON line. Exit 0 only if the honest proof is accepted AND every hostile case is rejected.
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sys/resource.h>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "product.h"
using namespace blk;
using Clock = std::chrono::steady_clock;
static double since(Clock::time_point t) { return std::chrono::duration<double>(Clock::now() - t).count(); }
[[noreturn]] static void fail(const char *s) { std::printf("{\"ok\":false,\"fail\":\"%s\"}\n", s); std::exit(1); }
static void check(bool ok, const char *s) { if (!ok) fail(s); }

struct Fixture {
  u64 h[16];
  Table t;
  std::vector<Coordinate> coordinates;
  std::vector<WireEquality> wires;
  std::vector<AffineRelation> relations;
};
static Fixture load(const char *path, unsigned want_L) {
  std::FILE *f = std::fopen(path, "rb"); check(f, "open fixture");
  Fixture x;
  auto rd = [&](void *p, size_t n) { check(std::fread(p, 1, n, f) == n, "short fixture"); };
  rd(x.h, sizeof x.h);
  check(x.h[0] == 0x4b44415330303031ULL, "fixture magic");
  const u64 L = want_L, n = x.h[2], nc = x.h[3], nw = x.h[4], nr = x.h[5], nt = x.h[6];
  check(x.h[1] <= L && L <= 30 && n <= (u64(1) << L), "fixture size");
  x.t = Table(1, 3, size_t(1) << L);
  std::vector<u64> col(n);
  for (unsigned r = 0; r < 3; ++r) {
    rd(col.data(), 8 * n);
    for (u64 i = 0; i < n; ++i) { check(col[i] < P, "canonical"); x.t.set(r, i, E::from(F{col[i]})); }
  }
  // unused columns stay 0*0=0: they satisfy the product relation and nothing reads them.
  std::vector<u64> c(3 * nc); rd(c.data(), 8 * c.size());
  for (u64 i = 0; i < nc; ++i) x.coordinates.push_back({c[3 * i], c[3 * i + 1], F{c[3 * i + 2]}});
  std::vector<u64> w(4 * nw); rd(w.data(), 8 * w.size());
  for (u64 i = 0; i < nw; ++i) x.wires.push_back({w[4 * i], w[4 * i + 1], w[4 * i + 2], w[4 * i + 3]});
  std::vector<u64> len(nr), tgt(nr), terms(3 * nt);
  rd(len.data(), 8 * nr); rd(tgt.data(), 8 * nr); rd(terms.data(), 8 * terms.size());
  u64 at = 0;
  for (u64 i = 0; i < nr; ++i) {
    AffineRelation a; a.target = F{tgt[i]};
    for (u64 j = 0; j < len[i]; ++j, ++at) a.terms.push_back({terms[3 * at], terms[3 * at + 1], F{terms[3 * at + 2]}});
    x.relations.push_back(std::move(a));
  }
  check(at == nt, "term count");
  char extra; check(std::fread(&extra, 1, 1, f) == 0, "trailing fixture bytes");
  std::fclose(f);
  return x;
}
static E eval(const AffineRelation &a, const Table &t) {
  E x = E::zero();
  for (auto z : a.terms) x += E::from(z.coefficient) * t.at(z.row, z.column);
  return x;
}
// Honest when hostile=false. Hostile: binds the TRUE statement but substitutes truthful local
// targets of its (false) table for wire and affine rows, as in PR16/PR19's complete attacks.
static Writer prove(const ScaleRun &run, const Table &t, bool hostile, u64 key, u64 label = KDA_SCALE_LABEL) {
  EngineCpu engine; ToyCoins coins(key); Writer proof;
  Binder b(label, run.product.plan); auto in = scale_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins); FoldMask mask;
  auto g = toy_prove_preamble(pr, in.product, t, mask); auto oracle = pr.st.group(g).members[0];
  coordinate_rows(pr.st, g, ch.get(in.coordinates));
  for (auto w : ch.get(in.equalities)) {
    auto row = wire_row(oracle, w);
    if (hostile) row.target = t.at(w.left_row, w.left_column) - t.at(w.right_row, w.right_column);
    pr.st.add_row(g, std::move(row));
  }
  for (const auto &a : ch.get(in.relations)) {
    auto row = affine_row(oracle, a);
    if (hostile) row.target = eval(a, t);
    pr.st.add_row(g, std::move(row));
  }
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask));
  ch.finish(); pr.st.require_all_tested(); return proof;
}
static bool verify(const ScaleRun &run, const u8 *p, size_t n, u64 label = KDA_SCALE_LABEL) { return scale_verify(run, p, n, nullptr, label); }

int main(int argc, char **argv) {
  if (argc < 8) return 2;
  bool hostile_provers = true;
  if (std::strcmp(argv[argc - 1], "--skip-hostile-provers") == 0) hostile_provers = false, --argc;
  Setting set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES;
  set.target = (unsigned)std::atoi(argv[2]); set.set_work(ErrorKind::QUERY, Scope::REQUEST, (unsigned)std::atoi(argv[3]));
  const unsigned L = (unsigned)std::atoi(argv[4]), log_n = (unsigned)std::atoi(argv[5]), mask_log_n = (unsigned)std::atoi(argv[6]), stages = (unsigned)std::atoi(argv[7]);
  check(argc == 8 + 4 * (int)stages, "stage arguments");
  std::vector<StageChoice> further;
  for (unsigned i = 0; i < stages; ++i)
    further.push_back({(unsigned)std::atoi(argv[8 + 4 * i]), (unsigned)std::atoi(argv[9 + 4 * i]), (unsigned)std::atoi(argv[10 + 4 * i]), (unsigned)std::atoi(argv[11 + 4 * i])});
  auto t_load = Clock::now();
  Fixture fx = load(argv[1], L);
  const double load_s = since(t_load);
  // Reference checks of the generated statement on the honest table (host-side; the proof is what binds).
  for (const auto &a : fx.relations) check(eval(a, fx.t) == E::from(a.target), "reference affine");
  for (const auto &w : fx.wires) check(fx.t.at(w.left_row, w.left_column) == fx.t.at(w.right_row, w.right_column), "reference wire");
  for (const auto &c : fx.coordinates) check(fx.t.at(c.row, c.column) == E::from(c.value), "reference coordinate");
  for (size_t i = 0; i < fx.t.len; ++i) check(fx.t.at(2, i) == fx.t.at(0, i) * fx.t.at(1, i), "reference product");
  auto t_plan = Clock::now();
  auto run = scale_size(set, L, log_n, mask_log_n, further, fx.coordinates, fx.wires, fx.relations);
  const double plan_s = since(t_plan);
  if (!run.product.plan->holds()) { std::printf("{\"ok\":false,\"fail\":\"plan refused: %s\"}\n", run.product.plan->why_not().c_str()); return 1; }
  const u64 planned = run.product.plan->size_of(0).bytes;

  auto t0 = Clock::now();
  Writer proof = prove(run, fx.t, false, 101);
  const double prove_s = since(t0);
  std::vector<double> vt;
  for (int i = 0; i < 3; ++i) {
    auto t1 = Clock::now(); const bool ok = verify(run, proof.data(), proof.size()); vt.push_back(since(t1));
    check(ok, "honest proof accepted");
  }
  std::sort(vt.begin(), vt.end());
  unsigned rejected = 0;
  // 1. mutated proof bytes: 16 spread single-bit flips + 4 truncations + a trailing byte.
  auto bytes = proof.bytes();
  for (int i = 0; i < 16; ++i) {
    const size_t at = (size_t)((bytes.size() - 1) * (u64)i / 15);
    bytes[at] ^= u8(1 << (i % 8)); check(!verify(run, bytes.data(), bytes.size()), "flipped proof rejected"); bytes[at] ^= u8(1 << (i % 8)); ++rejected;
  }
  for (size_t cut : {size_t(0), bytes.size() / 3, bytes.size() / 2, bytes.size() - 1}) { check(!verify(run, bytes.data(), cut), "truncated proof rejected"); ++rejected; }
  bytes.push_back(0); check(!verify(run, bytes.data(), bytes.size()), "trailing byte rejected"); ++rejected; bytes.pop_back();
  // 2. wrong public output: change the published output coordinate, and a published final-state cell.
  { auto bad = run; bad.coordinates[0].value = F{(bad.coordinates[0].value.v + 1) % P}; check(!verify(bad, proof.data(), proof.size()), "wrong public output coordinate rejected"); ++rejected; }
  { auto bad = run; auto &r = bad.relations[fx.h[10]]; r.target = F{(r.target.v + 1) % P}; check(!verify(bad, proof.data(), proof.size()), "wrong public final state rejected"); ++rejected; }
  // 3. cross-domain: the same proof under another transcript label.
  check(!verify(run, proof.data(), proof.size(), AFFINE_LABEL), "cross-domain rejected"); ++rejected;
  unsigned hostile = 0; double hostile_s = 0;
  if (hostile_provers) {
    auto th = Clock::now();
    // 4a. complete hostile proof, private range bit flipped (products and public cells preserved).
    { auto bad = fx.t; const u64 col = fx.h[9];
      bad.set(0, col, bad.at(0, col) + E::one()); bad.set(1, col, bad.at(0, col)); bad.set(2, col, bad.at(0, col) * bad.at(1, col));
      for (auto c : fx.coordinates) check(bad.at(c.row, c.column) == E::from(c.value), "attack keeps coordinates");
      auto attack = prove(run, bad, true, 202); check(!verify(run, attack.data(), attack.size()), "hostile range-bit proof rejected"); ++hostile; }
    // 4b. complete hostile proof, paired quotient/remainder change keeping p = 2^f q + r (truncation toward zero).
    { auto bad = fx.t; const u64 q = fx.h[7], r = fx.h[8]; const u64 scale = u64(1) << (fx.h[15] - 2);
      bad.set(0, q, bad.at(0, q) + E::one()); bad.set(2, q, bad.at(0, q));
      bad.set(0, r, bad.at(0, r) - E::from(F{scale})); bad.set(2, r, bad.at(0, r));
      auto attack = prove(run, bad, true, 303); check(!verify(run, attack.data(), attack.size()), "hostile quotient/remainder proof rejected"); ++hostile; }
    // 4c. complete forgery of a WRONG public output: the statement publishes output+1, the table
    //     stores output+1 in that cell (a*1=c kept), the prover substitutes truthful local targets.
    { auto bad = fx.t; auto forged = run; const auto c = fx.coordinates[0];
      check(c.row == 0 && fx.t.at(1, c.column) == E::one(), "output is stored linear cell");
      bad.set(0, c.column, bad.at(0, c.column) + E::one()); bad.set(2, c.column, bad.at(0, c.column));
      forged.coordinates[0].value = F{(c.value.v + 1) % P};
      for (auto x : forged.coordinates) check(bad.at(x.row, x.column) == E::from(x.value), "forgery matches its public output");
      auto attack = prove(forged, bad, true, 404); check(!verify(forged, attack.data(), attack.size()), "forged wrong-output proof rejected"); ++hostile; }
    hostile_s = since(th);
  }
  rusage ru; getrusage(RUSAGE_SELF, &ru);
  std::printf("{\"ok\":true,\"log_len\":%u,\"target\":%u,\"work\":%u,\"proof_bytes\":%zu,\"planned_bytes\":%llu,\"prove_s\":%.4f,"
              "\"verify_s\":%.4f,\"verify_min_s\":%.4f,\"plan_s\":%.4f,\"load_s\":%.4f,\"rejected_static\":%u,\"hostile_provers\":%u,"
              "\"hostile_s\":%.3f,\"max_rss_kb\":%ld}\n",
              L, set.target, set.work[(int)ErrorKind::QUERY][(int)Scope::REQUEST], proof.size(), (unsigned long long)planned, prove_s,
              vt[1], vt[0], plan_s, load_s, rejected, hostile, hostile_s, ru.ru_maxrss);
  return 0;
}
