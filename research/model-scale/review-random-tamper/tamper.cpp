// Review-only tamper harness (not pushed). Reuses run.cpp's loader/prover, adds RANDOM-site attacks.
//   tamper FIXTURE.bin TARGET WORK LOG_LEN <plan args...> -- NATTACK SEED
#define main run_main
#include "run.cpp"
#undef main
#include <random>

int main(int argc, char **argv) {
  int sep = 0; for (int i = 1; i < argc; ++i) if (!std::strcmp(argv[i], "--")) sep = i;
  check(sep && sep + 2 < argc, "usage");
  const int nattack = std::atoi(argv[sep + 1]); std::mt19937_64 rng(std::strtoull(argv[sep + 2], nullptr, 10));
  argc = sep;
  Setting set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES;
  set.target = (unsigned)std::atoi(argv[2]); set.set_work(ErrorKind::QUERY, Scope::REQUEST, (unsigned)std::atoi(argv[3]));
  const unsigned L = (unsigned)std::atoi(argv[4]), log_n = (unsigned)std::atoi(argv[5]), mask_log_n = (unsigned)std::atoi(argv[6]), stages = (unsigned)std::atoi(argv[7]);
  check(argc == 8 + 4 * (int)stages, "stage arguments");
  std::vector<StageChoice> further;
  for (unsigned i = 0; i < stages; ++i)
    further.push_back({(unsigned)std::atoi(argv[8 + 4 * i]), (unsigned)std::atoi(argv[9 + 4 * i]), (unsigned)std::atoi(argv[10 + 4 * i]), (unsigned)std::atoi(argv[11 + 4 * i])});
  Fixture fx = load(argv[1], L);
  auto run = scale_size(set, L, log_n, mask_log_n, further, fx.coordinates, fx.wires, fx.relations);
  check(run.product.plan->holds(), "plan");
  const u64 n = fx.h[2];
  Writer honest = prove(run, fx.t, false, 101); check(verify(run, honest.data(), honest.size()), "honest");
  // honest prover via the hostile path on the TRUE table must still verify (sanity: hostile path is not trivially broken)
  { Writer h2 = prove(run, fx.t, true, 555); check(verify(run, h2.data(), h2.size()), "hostile-path on honest table verifies"); }
  unsigned acc_cell = 0, acc_stmt_aff = 0, acc_stmt_wire = 0, acc_stmt_coord = 0, rej = 0;
  for (int k = 0; k < nattack; ++k) {
    // (a) random cell in a random USED column, rows a or b changed by a random delta, c recomputed so a*b=c holds
    { auto bad = fx.t; const u64 col = rng() % n; const unsigned row = rng() % 2; const u64 d = 1 + rng() % 1000;
      bad.set(row, col, bad.at(row, col) + E::from(F{d})); bad.set(2, col, bad.at(0, col) * bad.at(1, col));
      auto attack = prove(run, bad, true, 1000 + k);
      if (verify(run, attack.data(), attack.size())) { ++acc_cell; std::printf("{\"ACCEPTED\":\"cell\",\"col\":%llu,\"row\":%u}\n", (unsigned long long)col, row); } else ++rej; }
    // (b) honest proof against a statement with one RANDOM affine target +1
    { auto bad = run; auto &r = bad.relations[rng() % bad.relations.size()]; r.target = F{(r.target.v + 1) % P};
      if (verify(bad, honest.data(), honest.size())) ++acc_stmt_aff; else ++rej; }
    // (c) honest proof against a statement with one RANDOM wire redirected to another column
    { auto bad = run; auto &w = bad.equalities[rng() % bad.equalities.size()]; w.right_column = (w.right_column + 1 + rng() % (n - 1)) % n;
      if (verify(bad, honest.data(), honest.size())) ++acc_stmt_wire; else ++rej; }
    // (d) honest proof with the published coordinate moved to another column (same value)
    { auto bad = run; bad.coordinates[0].column = (bad.coordinates[0].column + 1 + rng() % (n - 1)) % n;
      if (fx.t.at(bad.coordinates[0].row, bad.coordinates[0].column) == E::from(bad.coordinates[0].value)) { /* same value by chance, skip */ }
      else if (verify(bad, honest.data(), honest.size())) ++acc_stmt_coord; else ++rej; }
  }
  std::printf("{\"n_columns\":%llu,\"attacks_per_kind\":%d,\"rejected\":%u,\"accepted_cell\":%u,\"accepted_affine_target\":%u,\"accepted_wire_redirect\":%u,\"accepted_coord_move\":%u}\n",
              (unsigned long long)n, nattack, rej, acc_cell, acc_stmt_aff, acc_stmt_wire, acc_stmt_coord);
  return (acc_cell + acc_stmt_aff + acc_stmt_wire + acc_stmt_coord) ? 1 : 0;
}
