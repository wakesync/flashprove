// Profile B of experiments/20261111-7-cpu-phase-cost: stage 1 of
// research/operators/qwen_deltanet_m2_build (one Qwen Gated DeltaNet head, D = 128, T = 4, F = 12,
// two lookups, synthetic inputs, research security), split into a prover process that writes the
// public statement words and the proof, and an independent verifier process that reads only those
// two files and calls the unchanged entry point verify_stage1().
// stage1.cpp is included unchanged; its main() is renamed so that this file supplies the entry.
//
//   phase_b prove  <out_dir> <fixture.bin>...   one statement per fixture, in order
//   phase_b verify <out_dir> <count>             verify statements 0..count-1
#define main stage1_unused_main
#include "../../research/operators/qwen_deltanet_m2_build/stage1.cpp"
#undef main
#include <iterator>

using PClock = std::chrono::steady_clock;
static double since_b(PClock::time_point a) { return std::chrono::duration<double>(PClock::now() - a).count(); }
static void phase_b(const char *name, double s, long item) {
  std::printf("{\"phase\":\"%s\",\"batch\":%ld,\"s\":%.6f}\n", name, item, s);
  std::fflush(stdout);
}
static void save_b(const std::string &path, const void *p, size_t n) {
  std::ofstream f(path, std::ios::binary);
  f.write(reinterpret_cast<const char *>(p), std::streamsize(n));
  check(bool(f), "write artifact");
}
static std::vector<u8> load_b(const std::string &path) {
  std::ifstream f(path, std::ios::binary);
  check(bool(f), "read artifact");
  return std::vector<u8>(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
}
static std::string wf(const std::string &d, long i) { return d + "/words-" + std::to_string(i) + ".bin"; }
static std::string pf_b(const std::string &d, long i) { return d + "/proof-" + std::to_string(i) + ".bin"; }

static int prove_all(const std::string &out, int n, char **fixtures) {
  const HeadParams sh = shape1();
  for (int i = 0; i < n; i++) {
    auto t = PClock::now();
    const Fixture fx = load(fixtures[i]);
    check(fx.T == sh.T && fx.D == sh.D && fx.F == sh.F, "fixture shape");
    const Derived z = derived_of(fx);
    phase_b("read_input", since_b(t), i);
    t = PClock::now();
    const Built b = build(sh, z, false);
    check(!b.overflow && !b.refused, "honest witness fits");
    for (int k = 0; k < sh.T; k++) check(b.M[k] == fx.M[k] && b.delta[k] == fx.delta[k] && b.S[k] == fx.S[k] && b.o[k] == fx.o[k], "C++ lowering equals reference.py");
    check(same_relations(b, build(sh, z, true)), "witness-free derivation equals the prover's relation list");
    const Sized s = size_run(b);
    check(s.ok, "a plan holds");
    const Table tab = table_of(b);
    check(products_hold_all(tab) && violated(b.rel, tab) == 0, "honest table");
    phase_b("witness", since_b(t), i);
    t = PClock::now();
    Proved honest;
    check(two_prove(*s.run, tab, Hostile(), honest), "honest prove");
    phase_b("prove", since_b(t), i);
    t = PClock::now();
    const std::vector<u64> words = encode(fx);
    const std::vector<u8> pb = honest.proof.bytes();
    save_b(wf(out, i), words.data(), words.size() * sizeof(u64));
    save_b(pf_b(out, i), pb.data(), pb.size());
    phase_b("write_proof", since_b(t), i);
  }
  std::printf("{\"summary\":\"prove\",\"batches\":%d,\"peak_rss_kb\":%ld}\n", n, rss_kb());
  return 0;
}

static int verify_all(const std::string &dir, long n) {
  long accepted = 0, rejected = 0;
  for (long i = 0; i < n; i++) {
    auto t = PClock::now();
    const std::vector<u8> wb = load_b(wf(dir, i)), pb = load_b(pf_b(dir, i));
    check(wb.size() % sizeof(u64) == 0, "words file length");
    std::vector<u64> words(wb.size() / sizeof(u64));
    std::memcpy(words.data(), wb.data(), wb.size());
    phase_b("v_read", since_b(t), i);
    t = PClock::now();
    VerifyTiming tm;
    const Verdict v = verify_stage1(words, pb.data(), pb.size(), &tm);
    phase_b("v_verify_stage1", since_b(t), i);
    phase_b("v_inner_derive", tm.derive_s, i);
    phase_b("v_inner_proof_verifier", tm.verify_s, i);
    if (v == Verdict::ACCEPT) accepted++;
    else { rejected++; std::printf("{\"reject\":\"%s\",\"batch\":%ld,\"why\":\"%s\"}\n", stage_name(v), i, tm.why.c_str()); }
  }
  std::printf("{\"summary\":\"verify\",\"accepted\":%ld,\"rejected\":%ld,\"peak_rss_kb\":%ld}\n", accepted, rejected, rss_kb());
  return rejected == 0 && accepted == n ? 0 : 1;
}

int main(int argc, char **argv) {
  std::setvbuf(stdout, nullptr, _IOLBF, 0);
  const std::string mode = argc > 1 ? argv[1] : "";
  if (mode == "prove" && argc >= 4) return prove_all(argv[2], argc - 3, argv + 3);
  if (mode == "verify" && argc == 4) return verify_all(argv[2], std::stol(argv[3]));
  std::fprintf(stderr, "usage: phase_b prove <dir> <fixture>... | phase_b verify <dir> <count>\n");
  return 2;
}
