// Profile A of experiments/20261111-7-cpu-phase-cost: the CPU reference protocol fixture of PR #40
// (experiments/20261103-7-cpu-commit/reference.cpp), split into a prover process and an
// independent verifier process that reads only the files the prover wrote.
// NOT cp_commit/cp_prove and NOT model inference: the toy segments multiply toy vectors and bind
// replies; they do not prove that the replies are correct (blocks/frame/tests/seam_world.h).
//
//   phase_a prove  <out_dir> <seed> <batches>   commit once, then prove <batches> batches of 3
//   phase_a verify <out_dir> <batches>           check key, entry, then every proof file
// Each prints one JSON line per phase and a final summary line. Exit 0 only if everything held.
#define BLK_PLANS_BY_HAND_FOR_A_TEST
#define BLK_TESTED_TABLE_FOR_A_TEST
#include "frame/check_entry.h"
#include "frame/check_key.h"
#include "frame/tests/seam_world.h"
#include "frame/tests/toy_matrix.h"
#include <sys/resource.h>
#include <chrono>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>

using Clock = std::chrono::steady_clock;
static double since(Clock::time_point a) { return std::chrono::duration<double>(Clock::now() - a).count(); }
static long rss_kb() { rusage u; getrusage(RUSAGE_SELF, &u); return u.ru_maxrss; }
static void phase(const char *name, double s, long batch = -1) {
  std::printf("{\"phase\":\"%s\",\"batch\":%ld,\"s\":%.6f}\n", name, batch, s);
  std::fflush(stdout);
}
static void save(const std::string &path, const std::vector<u8> &v) {
  std::ofstream f(path, std::ios::binary);
  f.write(reinterpret_cast<const char *>(v.data()), std::streamsize(v.size()));
  BLK_REQUIRE(bool(f), "write artifact");
}
static std::vector<u8> load(const std::string &path) {
  std::ifstream f(path, std::ios::binary);
  BLK_REQUIRE(bool(f), "read artifact");
  return std::vector<u8>(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
}
static std::string pf(const std::string &dir, long b, size_t i) { return dir + "/proof-b" + std::to_string(b) + "-" + std::to_string(i) + ".bin"; }
// Public, fixed by the profile: the two public files, the requests and the replies.
static const std::vector<std::vector<u8>> REQUESTS = {{1, 2, 3, 4}, {5, 6, 7}, {8, 9}};
static const std::vector<E> &replies() {
  static const std::vector<E> r = {E::from(from_u64(1001)), E::from(from_u64(1002)), E::from(from_u64(1003))};
  return r;
}
static std::vector<std::string> public_files() { return {seam_file(4), toy_model(3, {})}; }

static int do_prove(const std::string &out, u64 seed, long batches) {
  auto t = Clock::now();
  const Configured c = configure(public_files(), toy_shapes);
  BLK_REQUIRE(c.refused().empty(), c.refused().c_str());
  phase("configure", since(t));
  t = Clock::now();
  const LinShape &S = c.sized().once.S;
  const LinMatrix M = toy_matrix_in_range(S, c.sized().ranges.x, seed + 3);
  const Table rows = lin_table_rows(S, M);
  phase("witness", since(t));
  t = Clock::now();
  TestCoins table_coins(seed + 24), copy_coins(seed + 25), key_coins(seed + 44), link_coins(seed + 45);
  IndexCpu first(S.fold.index, rows, table_coins, c.configuration());
  IndexCpu further(c.sized().link.S.table, rows, copy_coins, c.configuration());
  phase("commit_tables", since(t));
  t = Clock::now();
  EngineCpu engine;
  const NonceSearch search = [&engine](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); };
  WfCpu ranges(c.sized().ranges.x, wf_matrix_of(S), [&M](u64 r, u64 col) { return M.at(r, col); });
  HeavyCpu products(S, M);
  Writer key_file, entry_file;
  BLK_REQUIRE(make_key(c, first, ranges, products, engine, key_coins, search, key_file), "make key");
  phase("commit_key", since(t));
  t = Clock::now();
  BLK_REQUIRE(make_entry(c, first, further, engine, link_coins, search, entry_file), "make entry");
  phase("commit_entry", since(t));
  t = Clock::now();
  save(out + "/key.bin", key_file.bytes());
  save(out + "/entry.bin", entry_file.bytes());
  phase("write_commitment", since(t));
  long done = 0;
  for (long b = 0; b < batches; b++) {
    t = Clock::now();
    const auto proofs = prove_batch(c, further, IndexName{further.commitment(), further.record()}, M, 1, REQUESTS, replies(), seed + 62 + 1000 * u64(b));
    const double s = since(t);
    if (proofs.size() != REQUESTS.size()) {
      std::printf("{\"refused\":\"prove_batch\",\"batch\":%ld,\"columns_left\":%llu}\n", b, (unsigned long long)further.columns_left());
      std::fflush(stdout);
      break;
    }
    phase("prove_batch", s, b);
    t = Clock::now();
    for (size_t i = 0; i < proofs.size(); i++) save(pf(out, b, i), proofs[i]);
    phase("write_proofs", since(t), b);
    done++;
  }
  std::printf("{\"summary\":\"prove\",\"batches\":%ld,\"columns_left\":%llu,\"peak_rss_kb\":%ld}\n", done, (unsigned long long)further.columns_left(), rss_kb());
  return done == batches ? 0 : 3;
}

static int do_verify(const std::string &dir, long batches) {
  auto t = Clock::now();
  const Configured c = configure(public_files(), toy_shapes);
  BLK_REQUIRE(c.refused().empty(), c.refused().c_str());
  phase("v_configure", since(t));
  t = Clock::now();
  const std::vector<u8> kb = load(dir + "/key.bin"), eb = load(dir + "/entry.bin");
  phase("v_read_commitment", since(t));
  const char *why = nullptr;
  TestedTable key, copy;
  t = Clock::now();
  Reader kr(kb.data(), kb.size());
  const bool key_ok = check_key(c, kr, key, why) != ProofVerdict::NO;
  phase("v_check_key", since(t));
  if (!key_ok) { std::printf("{\"reject\":\"key\",\"why\":\"%s\"}\n", why ? why : ""); return 1; }
  t = Clock::now();
  Reader er(eb.data(), eb.size());
  const bool entry_ok = check_entry(c, key, er, copy, why) != ProofVerdict::NO;
  phase("v_check_entry", since(t));
  if (!entry_ok) { std::printf("{\"reject\":\"entry\",\"why\":\"%s\"}\n", why ? why : ""); return 1; }
  long accepted = 0, rejected = 0;
  for (long b = 0; b < batches; b++) {
    double read_s = 0, check_s = 0;
    for (size_t i = 0; i < REQUESTS.size(); i++) {
      t = Clock::now();
      const std::vector<u8> p = load(pf(dir, b, i));
      read_s += since(t);
      t = Clock::now();
      Reader pr(p.data(), p.size());
      const bool ok = check_proof(c, copy, 1, REQUESTS[i], REQUESTS[i], replies()[i], pr, toy_links, nullptr, why) != ProofVerdict::NO;
      check_s += since(t);
      ok ? accepted++ : rejected++;
      if (!ok) std::printf("{\"reject\":\"proof\",\"batch\":%ld,\"i\":%zu,\"why\":\"%s\"}\n", b, i, why ? why : "");
    }
    phase("v_read_proofs", read_s, b);
    phase("v_check_proofs", check_s, b);
  }
  std::printf("{\"summary\":\"verify\",\"accepted\":%ld,\"rejected\":%ld,\"peak_rss_kb\":%ld}\n", accepted, rejected, rss_kb());
  return rejected == 0 && accepted == batches * long(REQUESTS.size()) ? 0 : 1;
}

int main(int argc, char **argv) {
  std::setvbuf(stdout, nullptr, _IOLBF, 0);
  const std::string mode = argc > 1 ? argv[1] : "";
  if (mode == "prove" && argc == 5) return do_prove(argv[2], std::stoull(argv[3]), std::stol(argv[4]));
  if (mode == "verify" && argc == 4) return do_verify(argv[2], std::stol(argv[3]));
  std::fprintf(stderr, "usage: phase_a prove <dir> <seed> <batches> | phase_a verify <dir> <batches>\n");
  return 2;
}
