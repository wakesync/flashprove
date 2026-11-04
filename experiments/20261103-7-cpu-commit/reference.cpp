// CPU reference protocol fixture, not cp_commit/cp_prove or model inference.
#define BLK_PLANS_BY_HAND_FOR_A_TEST
#define BLK_TESTED_TABLE_FOR_A_TEST
#include "frame/check_entry.h"
#include "frame/check_key.h"
#include "frame/tests/seam_world.h"
#include "frame/tests/toy_matrix.h"
#include <chrono>
#include <fstream>
#include <ctime>
#include <iomanip>
#include <iostream>

#ifdef PROFILE_GENERATION
extern "C" void moncontrol(int);
#endif

static void save(const std::string &dir, const char *name, const std::vector<u8> &v) {
  std::ofstream f(dir + "/" + name, std::ios::binary);
  f.write(reinterpret_cast<const char *>(v.data()), v.size());
  BLK_REQUIRE(bool(f), "write artifact");
}
int main(int argc, char **argv) {
  if (argc != 3) return 2;
  const std::string out = argv[1];
  const u64 seed = std::stoull(argv[2]);
  using Clock = std::chrono::steady_clock;
  auto start = Clock::now(), last = start;
  const auto cpu_start = std::clock();
  std::cout << std::setprecision(9);
  auto lap = [&](const char *name) {
    const auto now = Clock::now();
    std::cout << name << " " << std::chrono::duration<double>(now-last).count() << "\n";
    last = now;
  };
  const std::vector<std::string> files = {seam_file(4), toy_model(3, {})};
  const Configured c = configure(files, toy_shapes);
  BLK_REQUIRE(c.refused().empty(), c.refused().c_str());
  lap("configure");
  const LinShape &S = c.sized().once.S;
  const LinMatrix M = toy_matrix_in_range(S, c.sized().ranges.x, seed + 3);
  TestCoins table_coins(seed + 24), copy_coins(seed + 25), key_coins(seed + 44), link_coins(seed + 45);
  IndexCpu first(S.fold.index, lin_table_rows(S, M), table_coins, c.configuration());
  IndexCpu further(c.sized().link.S.table, lin_table_rows(S, M), copy_coins, c.configuration());
  lap("tables");
  EngineCpu engine;
  const NonceSearch search = [&engine](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); };
  WfCpu ranges(c.sized().ranges.x, wf_matrix_of(S), [&M](u64 r, u64 col) { return M.at(r, col); });
  HeavyCpu products(S, M);
  Writer key_file, entry_file;
  BLK_REQUIRE(make_key(c, first, ranges, products, engine, key_coins, search, key_file), "make key");
  lap("make_key");
  BLK_REQUIRE(make_entry(c, first, further, engine, link_coins, search, entry_file), "make entry");
  lap("make_entry");
  const std::vector<std::vector<u8>> requests = {{1,2,3,4}, {5,6,7}, {8,9}};
  const std::vector<E> replies = {E::from(from_u64(1001)), E::from(from_u64(1002)), E::from(from_u64(1003))};
  const auto proofs = prove_batch(c, further, IndexName{further.commitment(), further.record()}, M, 1, requests, replies, seed + 62);
  BLK_REQUIRE(proofs.size() == 3, "prove batch");
  lap("prove_batch");
  std::cout << "total_generate " << std::chrono::duration<double>(Clock::now()-start).count() << "\n";
  std::cout << "cpu_generate " << double(std::clock()-cpu_start)/CLOCKS_PER_SEC << "\n";
#ifdef PROFILE_GENERATION
  moncontrol(0); // Profile generation only, not the validation below.
#endif
  TestedTable key, copy;
  const char *why = nullptr;
  Reader kr(key_file.bytes().data(), key_file.bytes().size());
  BLK_REQUIRE(check_key(c, kr, key, why) != ProofVerdict::NO, "verify key");
  Reader er(entry_file.bytes().data(), entry_file.bytes().size());
  BLK_REQUIRE(check_entry(c, key, er, copy, why) != ProofVerdict::NO, "verify entry");
  for (size_t i = 0; i < proofs.size(); ++i) {
    Reader pr(proofs[i].data(), proofs[i].size());
    BLK_REQUIRE(check_proof(c, copy, 1, requests[i], requests[i], replies[i], pr, toy_links, nullptr, why) != ProofVerdict::NO, "verify proof");
    auto bent = proofs[i]; bent.back() ^= 1;
    Reader bad(bent.data(), bent.size());
    BLK_REQUIRE(check_proof(c, copy, 1, requests[i], requests[i], replies[i], bad, toy_links, nullptr, why) == ProofVerdict::NO, "reject altered proof");
    save(out, ("proof" + std::to_string(i) + ".bin").c_str(), proofs[i]);
  }
  auto bent_key = key_file.bytes(); bent_key.back() ^= 1;
  Reader bk(bent_key.data(), bent_key.size()); TestedTable unused;
  BLK_REQUIRE(check_key(c, bk, unused, why) == ProofVerdict::NO, "reject altered key");
  auto bent_entry = entry_file.bytes(); bent_entry.back() ^= 1;
  Reader be(bent_entry.data(), bent_entry.size());
  BLK_REQUIRE(check_entry(c, key, be, unused, why) == ProofVerdict::NO, "reject altered entry");
  save(out, "key.bin", key_file.bytes()); save(out, "entry.bin", entry_file.bytes());
  save(out, "anchor.root", first.commitment()); save(out, "leaf.root", further.commitment());
  lap("verify_and_save");
  std::cout << "ok\n";
}
