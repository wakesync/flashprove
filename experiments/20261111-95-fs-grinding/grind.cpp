// SPDX-License-Identifier: Apache-2.0
// Research-only grinding harness for issue #95 (PREREG.md in this directory). It does not prove
// or verify anything: it plans the research toy profile of research/operators/qwen_ops/proof.cpp
// (convolution, F = 12, target 10 bits, 6 bits of proof of work on the query rounds) with the
// unmodified library, takes one round that draws positions, and grinds the library's own
// Fiat-Shamir hash chain (blocks/chain/chain.h) at that round, counting how often the drawn
// positions all fall into a fixed set of A of the n positions (the attacker's agreeing set).
//
//   grind.bin plan                         every planned round, and the selected one, as JSON lines
//   grind.bin grind A|B|C seed tries [i]   one run of an arm on round i (default: the selected one)
//
// Arms. A: nonce grinding, one fixed prefix, consecutive nonces from a seeded start, every nonce
// that passes the work test is a try. B: message grinding, a fresh prover message for each try
// (standing for a re-commitment with fresh private coins), the first nonce from 0 that passes the
// work. C: arm B with no proof of work (w = 0), a control for the 2^w cost factor.
#define main qwen_ops_proof_main
#include "../../research/operators/qwen_ops/proof.cpp"
#undef main
#include "numbers/accounting.h"
#include <cmath>
#include <cstdio>

namespace {

struct Picked {
  size_t index = 0;
  u64 before = 0;  // chain rounds before this one (counts of repeated rounds added)
  const PlanRound *r = nullptr;
  double bits = 0;  // minus log2 of the round's whole error, work not counted
};

WideRun profile_run() {
  Input in = fixture("conv", 12, 1);
  Circuit c = build(in, true);
  return run_for(c);
}

std::string esc(const std::string &s) {
  std::string o;
  for (char ch : s) {
    if (ch == '"' || ch == '\\') o.push_back('\\');
    o.push_back(ch);
  }
  return o;
}

// The round of kind POSITIONS with the largest error without work; or round `want` if given.
Picked pick(const Planned &p, long want) {
  Picked best;
  const Real unit = p->capped();
  u64 before = 0;
  for (size_t i = 0; i < p->rounds_.size(); ++i) {
    const PlanRound &r = p->rounds_[i];
    const double bits = bits_of(p->whole_error(r, unit));
    const bool eligible = r.kind == RoundKind::POSITIONS && r.draw_positions > 0;
    if (want >= 0 ? (long)i == want : (eligible && (!best.r || bits < best.bits))) best.index = i, best.before = before, best.r = &r, best.bits = bits;
    before += r.count;
  }
  need(best.r && best.r->kind == RoundKind::POSITIONS, "no such round of positions");
  return best;
}

int do_plan() {
  WideRun run = profile_run();
  const Planned &p = run.product.plan;
  const Real unit = p->capped();
  const char *kinds[] = {"EMPTY", "ALGEBRAIC", "EPSILON", "SEED", "POSITIONS", "BITS", "SEAL", "RECORD"};
  const char *whys[] = {"FIELD", "SAMPLE", "CLOSENESS", "QUERY", "SMALL", "ZERO"};
  for (size_t i = 0; i < p->rounds_.size(); ++i) {
    const PlanRound &r = p->rounds_[i];
    std::printf("{\"mode\":\"round\",\"index\":%zu,\"name\":\"%s\",\"where\":\"%s\",\"kind\":\"%s\",\"why\":\"%s\",\"count\":%llu,\"work_bits\":%u,"
                "\"bits_without_work\":%.6f,\"draw_positions\":%llu,\"log_n\":%u,\"draw_E\":%llu,\"message_bytes\":%zu}\n",
                i, esc(r.name).c_str(), esc(r.where).c_str(), kinds[(int)r.kind], whys[(int)r.why], (unsigned long long)r.count, r.work_bits,
                bits_of(p->whole_error(r, unit)), (unsigned long long)r.draw_positions, r.log_n, (unsigned long long)r.draw_E, r.message_bytes);
  }
  const Picked k = pick(p, -1);
  std::printf("{\"mode\":\"selected\",\"index\":%zu,\"chain_round\":%llu,\"name\":\"%s\",\"where\":\"%s\",\"bits_without_work\":%.6f,\"work_bits\":%u,\"t\":%llu,\"log_n\":%u,"
              "\"target\":%u,\"holds\":%s,\"rounds\":%llu}\n",
              k.index, (unsigned long long)(k.before + 1), esc(k.r->name).c_str(), esc(k.r->where).c_str(), k.bits, k.r->work_bits,
              (unsigned long long)k.r->draw_positions, k.r->log_n, p->set.target, p->holds() ? "true" : "false", (unsigned long long)p->rounds());
  std::fflush(stdout);
  print_accounting(account(p), "qwen_ops conv F=12 (toy research profile)", false, 12);
  return 0;
}

// The chain at the round's query: a first query of this profile, then empty rounds up to the
// round before. The values that lead up to the round are fixed per run; only what the prover
// controls at the round is varied.
Chain chain_before(const WideRun &run, u64 before, u64 seed) {
  FirstQuery q;
  q.label = WIDE_LABEL;
  q.parameters = configuration_digest({run.product.shape.text});
  q.statement.assign(8, 0);
  for (int i = 0; i < 8; i++) q.statement[i] = (u8)(seed >> (8 * i));
  q.salted = true, q.salt_in_proof = true;
  std::mt19937_64 g(seed * 0x9E3779B97F4A7C15ULL + 7);
  for (int i = 0; i < 8; i++) q.salt.w[i] = (u32)g();
  Chain c(q);
  for (u64 i = 0; i < before; i++) c.round(ChainKind::EMPTY);
  return c;
}

int do_grind(char arm, u64 seed, u64 tries, long want) {
  need(arm == 'A' || arm == 'B' || arm == 'C', "arm A, B or C");
  WideRun run = profile_run();
  const Planned &p = run.product.plan;
  const Picked k = pick(p, want);
  const unsigned w = arm == 'C' ? 0 : k.r->work_bits, log_n = k.r->log_n;
  const u64 t = k.r->draw_positions, n = u64(1) << log_n;
  const double e = std::exp2(-k.bits), a = std::pow(e, 1.0 / (double)t);
  const u64 A = (u64)std::floor(a * (double)n);
  const double p0 = std::pow((double)A / (double)n, (double)t);
  const size_t words = std::max<size_t>(1, (k.r->message_bytes + 7) / 8);
  const Chain base = chain_before(run, k.before, seed);
  std::mt19937_64 g(seed * 0xD1B54A32D192ED03ULL + (u64)arm);
  auto make_prefix = [&]() {
    ChainAbsorb m = base.message();
    for (size_t i = 0; i < words; i++) m.push_u64(g());
    return Chain::prefix(m, ChainKind::POSITIONS, w);
  };
  u64 done = 0, forges = 0, nonces = 0, position_draws = 0;
  const auto start = std::chrono::steady_clock::now();
  ChainPrefix fixed = make_prefix();
  u64 nonce = arm == 'A' ? (g() >> 8) : 0;
  while (done < tries) {
    ChainPrefix pre = fixed;
    if (arm != 'A') pre = make_prefix(), nonce = 0;
    Chain c = base;
    for (;;) {
      nonces++;
      const u64 at = nonce++;
      if (w == 0) {
        c.step(pre, 0, 0);
        break;
      }
      if (c.step(pre, at, w)) break;
    }
    done++;
    bool all = true;
    for (u64 j = 0; j < t; j++) {
      const u64 x = c.draw_position(log_n);
      position_draws++;
      if (x >= A) all = false;  // keep drawing: every position of the round is drawn, as by the verifier
    }
    forges += all;
  }
  const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
  std::printf("{\"mode\":\"grind\",\"arm\":\"%c\",\"seed\":%llu,\"round_index\":%zu,\"round\":\"%s\",\"where\":\"%s\",\"t\":%llu,\"log_n\":%u,\"work_bits\":%u,"
              "\"bits_without_work\":%.6f,\"e\":%.9g,\"a\":%.9f,\"A\":%llu,\"n\":%llu,\"p0\":%.9g,\"message_words\":%zu,\"tries\":%llu,\"forges\":%llu,"
              "\"nonces\":%llu,\"position_draws\":%llu,\"wall_s\":%.3f}\n",
              arm, (unsigned long long)seed, k.index, esc(k.r->name).c_str(), esc(k.r->where).c_str(), (unsigned long long)t, log_n, w, k.bits, e, a,
              (unsigned long long)A, (unsigned long long)n, p0, words, (unsigned long long)done, (unsigned long long)forges, (unsigned long long)nonces,
              (unsigned long long)position_draws, secs);
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  try {
    const std::string mode = argc > 1 ? argv[1] : "";
    if (mode == "plan" && argc == 2) return do_plan();
    if (mode == "grind" && (argc == 5 || argc == 6))
      return do_grind(argv[2][0], std::stoull(argv[3]), std::stoull(argv[4]), argc == 6 ? std::stol(argv[5]) : -1);
    std::fprintf(stderr, "usage: grind.bin plan | grind A|B|C seed tries [round_index]\n");
    return 2;
  } catch (const std::exception &x) {
    std::fprintf(stderr, "%s\n", x.what());
    return 1;
  }
}
