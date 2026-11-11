// SPDX-License-Identifier: Apache-2.0
// Research-only. Stage 1 of experiments/20261109-32-qwen-deltanet-lookup-build: the two-lookup
// composition on the M1b statement (one Qwen Gated DeltaNet head, D = 128, T = 4, F = 12, public
// head output o, no conv, no norm). Every floor remainder is one or two 12-bit lookup keys instead
// of 12 or 24 exact bits. Usage:
//   stage1.bin <fixture.bin> honest    one honest proof through verify_stage1(); JSON lines
//   stage1.bin <fixture.bin> hostile   the honest run, then every registered hostile case
// The fixture is research/operators/qwen_deltanet/reference.py's (the M1 recipe).
#include "kit.h"

// The statement on the wire: T, D, F | S0[D*D] | per token: a, beta, k[D], v[D], q[D], o[D] | S_T[D*D]
struct Fixture {
  int T, D, F; std::vector<i64> S0, a, beta; std::vector<std::vector<i64>> k, v, q, M, delta, S, o;
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
#ifndef STAGE1_D
#define STAGE1_D 128  // a smaller D is a debug build only (smoke tests); every reported number is D = 128
#endif
static HeadParams shape1() { HeadParams hp; hp.T = 4, hp.D = STAGE1_D, hp.F = 12, hp.norm = false; return hp; }
static std::vector<u64> encode(const Fixture &z) {
  std::vector<u64> w = {u64(z.T), u64(z.D), u64(z.F)};
  for (auto s : z.S0) w.push_back(enc(s));
  for (int t = 0; t < z.T; t++) {
    w.push_back(enc(z.a[t])); w.push_back(enc(z.beta[t]));
    for (auto x : z.k[t]) w.push_back(enc(x));
    for (auto x : z.v[t]) w.push_back(enc(x));
    for (auto x : z.q[t]) w.push_back(enc(x));
    for (auto x : z.o[t]) w.push_back(enc(x));
  }
  for (auto s : z.S[z.T - 1]) w.push_back(enc(s));
  return w;
}
static size_t w_S0(const HeadParams &, size_t c) { return 3 + c; }
static size_t w_tok(const HeadParams &s, int t) { return 3 + size_t(s.D) * s.D + size_t(t) * (2 + 4 * s.D); }
static size_t w_a(const HeadParams &s, int t) { return w_tok(s, t); }
static size_t w_beta(const HeadParams &s, int t) { return w_tok(s, t) + 1; }
static size_t w_k(const HeadParams &s, int t, int i) { return w_tok(s, t) + 2 + i; }
static size_t w_v(const HeadParams &s, int t, int i) { return w_tok(s, t) + 2 + s.D + i; }
static size_t w_q(const HeadParams &s, int t, int i) { return w_tok(s, t) + 2 + 2 * s.D + i; }
static size_t w_o(const HeadParams &s, int t, int i) { return w_tok(s, t) + 2 + 3 * s.D + i; }
static size_t w_ST(const HeadParams &s, size_t c) { return w_tok(s, s.T) + c; }

// THE ENTRY POINT of stage 1. Untrusted: the statement words and the proof bytes. (1) the shape is
// the verifier's own; (2) every word is decoded as a canonical field element and read as an integer
// of its class; (3) every relation is derived from the decoded integers, with no witness; (4) the
// run is sized and the unchanged proof verifier runs. Every failure is a returned verdict.
// Classes: |S0|, |S_T| < 2^18; a, beta in [0, 2^F]; |k|, |q| <= 2^F; |v|, |o| < 2^31.
static Verdict verify_stage1(const std::vector<u64> &w, const u8 *proof, size_t bytes, VerifyTiming *tm = nullptr) {
  auto t0 = std::chrono::steady_clock::now();
  const HeadParams sh = shape1();
  const size_t DD = size_t(sh.D) * sh.D, want = 3 + DD + size_t(sh.T) * (2 + 4 * sh.D) + DD;
  if (w.size() != want) { if (tm) tm->why = "statement length"; return Verdict::DECODE; }
  if (w[0] != u64(sh.T) || w[1] != u64(sh.D) || w[2] != u64(sh.F)) { if (tm) tm->why = "header differs from the verifier's shape"; return Verdict::DECODE; }
  const i64 one = i64(1) << sh.F;
  Derived z; size_t p = 3; bool ok = true;
  auto take = [&](size_t n, i64 lo, i64 hi) { std::vector<i64> r(n, 0); for (size_t i = 0; i < n && ok; i++) ok = decode(w[p++], lo, hi, r[i]); return r; };
  z.S0 = take(DD, -(BOUND - 1), BOUND - 1);
  for (int t = 0; t < sh.T && ok; t++) {
    z.a.push_back(take(1, 0, one)[0]); z.beta.push_back(take(1, 0, one)[0]);
    z.k.push_back(take(sh.D, -one, one)); z.v.push_back(take(sh.D, -(VBOUND - 1), VBOUND - 1));
    z.q.push_back(take(sh.D, -one, one)); z.o.push_back(take(sh.D, -(VBOUND - 1), VBOUND - 1));
  }
  if (ok) z.ST = take(DD, -(BOUND - 1), BOUND - 1);
  if (!ok) { if (tm) tm->why = "a public word is non-canonical or outside its class"; return Verdict::DECODE; }
  if (tm) tm->derive_s = secs(t0);
  return derive_and_verify(sh, z, proof, bytes, tm);
}
static Derived derived_of(const Fixture &f) {
  Derived z; z.S0 = f.S0; z.ST = f.S[f.T - 1]; z.a = f.a; z.beta = f.beta; z.k = f.k; z.v = f.v; z.q = f.q; z.o = f.o; return z;
}

int main(int argc, char **argv) {
  check(argc == 3, "usage: stage1.bin <fixture.bin> honest|hostile");
  const std::string mode = argv[2];
  const HeadParams sh = shape1();
  const Fixture fx = load(argv[1]);
  check(fx.T == sh.T && fx.D == sh.D && fx.F == sh.F, "fixture shape");
  const Derived z = derived_of(fx);
  auto t0 = std::chrono::steady_clock::now();
  const Built b = build(sh, z, false);
  check(!b.overflow && !b.refused, "honest witness fits");
  for (int t = 0; t < sh.T; t++) check(b.M[t] == fx.M[t] && b.delta[t] == fx.delta[t] && b.S[t] == fx.S[t] && b.o[t] == fx.o[t], "C++ lowering equals reference.py");
  check(same_relations(b, build(sh, z, true)), "witness-free derivation equals the prover's relation list");
  print_counts(b);
  const Sized s = size_run(b);
  check(s.ok, "a plan holds");
  const Table tab = table_of(b);
  check(products_hold_all(tab) && violated(b.rel, tab) == 0, "honest table");
  const double build_s = secs(t0);
  auto tp = std::chrono::steady_clock::now();
  Proved honest; check(two_prove(*s.run, tab, Hostile(), honest), "honest prove");
  const double prove_s = secs(tp);
  const std::vector<u64> words = encode(fx);
  const std::vector<u8> pb = honest.proof.bytes();
  VerifyTiming tm; const Verdict st = verify_stage1(words, pb.data(), pb.size(), &tm);
  const std::vector<E> al = alphas_of(tm.notes);
  std::printf("{\"mode\":\"honest\",\"accept\":%s,\"stage\":\"%s\",\"statement_words\":%zu,\"proof_bytes\":%zu,\"build_s\":%.3f,\"prove_s\":%.3f,\"derive_s\":%.3f,\"verify_s\":%.3f,\"peak_rss_kb\":%ld,"
              "\"lookup_alphas\":%zu,\"alpha_digit\":\"%s\",\"alpha_remainder\":\"%s\",\"alphas_differ\":%s,\"digit_lookup_bytes\":%zu,\"remainder_lookup_bytes\":%zu}\n",
              st == Verdict::ACCEPT ? "true" : "false", stage_name(st), words.size(), pb.size(), build_s, prove_s, tm.derive_s, tm.verify_s, rss_kb(),
              al.size(), al.size() > 0 ? hex_of(al[0]).c_str() : "", al.size() > 1 ? hex_of(al[1]).c_str() : "", al.size() == 2 && !(al[0] == al[1]) ? "true" : "false",
              honest.digit_end - honest.digit_begin, honest.rem_end - honest.rem_begin);
  std::fflush(stdout);
  check(st == Verdict::ACCEPT, "honest accepted by verify_stage1");
  if (mode != "hostile") return 0;

  Suite S;
  const i64 one = i64(1) << sh.F;
  auto entry = [&](const std::vector<u8> &p) { return verify_stage1(words, p.data(), p.size()); };
  // A complete hostile proof on a tampered table (every product gate holds), against the honest statement.
  auto complete = [&](const char *cls, const char *what, const std::function<void(Edit &)> &tamper, Hostile h = Hostile(), Verdict want = Verdict::PROOF) {
    Table bad = tab; Edit e{b, bad}; tamper(e); h.on = true;
    check(products_hold_all(bad), "attack preserves every product gate");
    const size_t viol = violated(b.rel, bad);
    Proved pr; check(two_prove(*s.run, bad, h, pr), "hostile prove (a combination left its window: use rng_mode 1)");
    const std::vector<u8> bytes = pr.proof.bytes();
    VerifyTiming t2; const Verdict v = verify_stage1(words, bytes.data(), bytes.size(), &t2);
    std::printf("{\"mode\":\"hostile-note\",\"attack\":\"%s\",\"wrapped_combinations\":%llu,\"keys_outside_table\":%llu}\n", what, (unsigned long long)pr.wrapped, (unsigned long long)pr.uncounted);
    S.report(cls, what, v, want, (long long)viol, t2.why.c_str());
  };
  const int tt = 1;
  // CONTROL (added after the PREREG; listed as a deviation). The hostile prover's own code path
  // (research RNG copy, forgiving sumchecks, true local targets) with NO tamper must be ACCEPTED.
  // Without it, a broken research prover would make every rejection below meaningless.
  complete("control-research-prover", "research prover path, honest witness, no tamper (must be accepted)", [&](Edit &) {}, Hostile(), Verdict::ACCEPT);
  // ---- the M1b suite (#63), ported: remainders are keys now ----
  complete("c1-state", "S_1[0,0] += 1", [&](Edit &e) { e.gate_a(b.state0[0], 1); });
  complete("c1-state", "S_3[0,0] += 1", [&](Edit &e) { e.gate_a(b.state0[2], 1); });
  complete("c2-state-floor-preserving", "S_2[0,0] += 1, remainder key -= 2^F (leaves the table), range cell consistent",
           [&](Edit &e) { e.gate_a(b.state0[tt], 1); e.cell(b.state0_key[tt], -one); e.cell(b.state0_rc[tt], 1); });
  complete("c3-decay", "token-1 decay gate operand a += 1", [&](Edit &e) { e.gate_b(b.g1_first[0], 1); });
  complete("c4-beta", "token-1 beta gate operand += 1", [&](Edit &e) { e.gate_b(b.g6_first[0], 1); });
  complete("c5-memory-floor", "M[0] += 1 (range cell +1, v-M operand -= 1), low remainder key -= 2^2F",
           [&](Edit &e) { e.gate_a(b.g6_first[0], -1); e.cell(b.M_rc[0], 1); e.cell(b.M_key[0], -(one * one)); });
  complete("c5-memory-floor", "M[0] += 1, high remainder key -= 2^F",
           [&](Edit &e) { e.gate_a(b.g6_first[0], -1); e.cell(b.M_rc[0], 1); e.cell(b.M_key[0] + 1, -one); });
  complete("c5-delta-floor", "delta[0] += 1 (delta_lo range cell +1), remainder key -= 2^F",
           [&](Edit &e) { e.gate_b(b.d_cell[0], 1); e.cell(b.dlo_rc[0], 1); e.cell(b.d_key[0], -one); });
  complete("c6-range", "S_1[0,0] remainder key moved by 1 (stays in the table)", [&](Edit &e) { e.cell(b.state0_key[0], e.key(b.state0_key[0]) < KEYS - 1 ? 1 : -1); });
  { Hostile h; h.rng_mode = 2; complete("c6-range", "RNG low digit of cell row 0, combination 0, moved by 1 (honest witness)", [&](Edit &) {}, h); }
  { Hostile h; h.rng_mode = 1; complete("c9-limb", "delta_lo += 32 * 2^18, delta_hi -= 32 (identity preserved, delta_lo outside 2^23)", [&](Edit &e) { e.cell(b.dlo_rc[0], 32 * BOUND); e.cell(b.dhi_rc[0], -32); }, h); }
  complete("c9-limb", "delta_hi += 1 alone", [&](Edit &e) { e.cell(b.dhi_rc[0], 1); });
  complete("c9-limb", "delta_lo += 1 alone", [&](Edit &e) { e.cell(b.dlo_rc[0], 1); });
  { Hostile h; h.rng_mode = 1; complete("c10-state-out-of-range", "S_2[0,0] += 2^24 (range cell too), remainder key -= 2^(F+24)",
      [&](Edit &e) { e.gate_a(b.state0[tt], i64(1) << 24); e.cell(b.state0_rc[tt], i64(1) << 24); e.cell(b.state0_key[tt], -(i64(1) << (sh.F + 24))); }, h); }
  // ---- lookup-specific cases ----
  // The M floor's remainder is lo + 2^12 hi. Re-split: lo += 2^12, hi -= 1. NO relation is violated,
  // so only the remainder lookup can reject it.
  const auto resplit = [&](Edit &e) { e.cell(b.M_key[0], KEYS); e.cell(b.M_key[0] + 1, -1); };
  complete("l1-out-of-table", "M remainder re-split (lo += 2^12, hi -= 1), 0 relations violated, out-of-table keys left uncounted", resplit);
  complete("l1-out-of-table", "S_1[0,0] remainder key set to 2^12 alone (first value outside the table)", [&](Edit &e) { e.cell(b.state0_key[0], KEYS - e.key(b.state0_key[0])); });
  // Multiplicities as integers, edited, written back as bits.
  const auto bump = [](const LkpPublic &L, std::vector<E> &bits, u64 row, i64 d) {
    u64 c = 0; for (unsigned j = 0; j < (1u << L.mu); j++) if (bits[j + (row << L.mu)] == E::one()) c |= u64(1) << j;
    c = u64(i64(c) + d);
    for (unsigned j = 0; j < (1u << L.mu); j++) bits[j + (row << L.mu)] = ((c >> j) & 1) ? E::one() : E::zero();
  };
  { Hostile h; h.bits_edit = [&](const LkpPublic &L, std::vector<E> &bits, u64 uncounted) { bump(L, bits, 0, (i64)uncounted); };
    complete("l2-wrong-multiplicity", "the same re-split, every out-of-table key counted at table row 0 (the sum of multiplicities is right)", resplit, h); }
  { Hostile h; h.bits_edit = [&](const LkpPublic &L, std::vector<E> &bits, u64) { bump(L, bits, 0, -1); bump(L, bits, 1, 1); };
    complete("l2-wrong-multiplicity", "honest witness, one count moved from table row 0 to row 1 (sum preserved)", [&](Edit &) {}, h); }
  { Hostile h; h.bits_edit = [&](const LkpPublic &, std::vector<E> &bits, u64) { bits[0] = E::one() - bits[0]; };
    complete("l2-wrong-multiplicity", "honest witness, bit 0 of table row 0's multiplicity flipped", [&](Edit &) {}, h); }
  { Hostile h; h.bits_edit = [&](const LkpPublic &, std::vector<E> &bits, u64) { bits[5] = E::from(from_u64(2)); };
    complete("l2-wrong-multiplicity", "honest witness, one multiplicity entry set to 2 (not a bit)", [&](Edit &) {}, h); }
  { Hostile h; h.swap_rows01 = true; complete("l3-swapped-table-rows", "honest witness, prover's table has rows 0 and 1 exchanged", [&](Edit &) {}, h); }
  { Hostile h; h.swap_rows01 = true; h.bits_edit = [&](const LkpPublic &L, std::vector<E> &bits, u64) { for (unsigned j = 0; j < (1u << L.mu); j++) std::swap(bits[j], bits[j + (u64(1) << L.mu)]); };
    complete("l3-swapped-table-rows", "the same, with the two rows' multiplicities exchanged to match the prover's table", [&](Edit &) {}, h); }
  // ---- H1: the two instances ----
  { Hostile h; h.alpha_replay = true; complete("h1-alpha-replay", "honest witness, remainder lookup built with the DIGIT lookup's alpha", [&](Edit &) {}, h); }
  { Hostile h; h.alpha_replay = true; h.bits_edit = [&](const LkpPublic &L, std::vector<E> &bits, u64 uncounted) { bump(L, bits, 0, (i64)uncounted); };
    complete("h1-alpha-replay", "re-split witness (false lookup), remainder lookup built with the DIGIT lookup's alpha", resplit, h); }
  { const u64 shift = u64(1) << (s.run->rem.mu + s.run->rem.d);
    check(s.run->planes_first + shift + rng_planes_places(s.run->rem) + 64 <= (u64(1) << b.L), "room for the moved planes");
    Hostile h; h.planes_shift = shift; complete("h1-planes-place", "honest witness, remainder multiplicities committed one block after the bound place", [&](Edit &) {}, h); }
  { Hostile h; h.planes_shift = 0; h.bits_edit = [&](const LkpPublic &, std::vector<E> &bits, u64) { std::fill(bits.begin(), bits.end(), E::zero()); };
    complete("h1-planes-place", "honest witness, remainder multiplicities not committed at all (zeros at the bound place)", [&](Edit &) {}, h); }
  check(honest.digit_end == honest.rem_begin && honest.digit_begin < honest.digit_end && honest.rem_begin < honest.rem_end, "the two lookups' transcripts are adjacent byte ranges");
  S.report("h1-splice", "remainder lookup's transcript bytes overwritten by the digit lookup's", entry(overwritten(pb, honest.rem_begin, honest.rem_end, honest.digit_begin, honest.digit_end)), Verdict::PROOF);
  S.report("h1-splice", "digit lookup's transcript bytes overwritten by the remainder lookup's", entry(overwritten(pb, honest.digit_begin, honest.digit_end, honest.rem_begin, honest.rem_end)), Verdict::PROOF);
  S.report("h1-splice", "the two lookups' transcripts exchanged", entry(exchanged(pb, honest.digit_begin, honest.digit_end, honest.rem_end)), Verdict::PROOF);
  {  // the honest proof under a verifier that binds the two instances' inputs under exchanged item names
    const Built vb = build(sh, z, true); const Sized vs = size_run(vb);
    const bool acc = run_verifier(TWO_LABEL, vs.run->product.plan, *vs.run, two_bind_relabelled, two_decide, pb.data(), pb.size());
    S.report("h1-relabel-control", "honest proof, verifier binds the two lookups' public inputs under exchanged item names", acc ? Verdict::ACCEPT : Verdict::PROOF, Verdict::PROOF);
    const bool acc2 = run_verifier(LOOKUP_LABEL, vs.run->product.plan, *vs.run, two_bind, two_decide, pb.data(), pb.size());
    S.report("c8-bytes", "honest proof verified under the M1b chain label", acc2 ? Verdict::ACCEPT : Verdict::PROOF, Verdict::PROOF);
  }
  // ---- c7: public mutations, as changed statement words against the honest proof ----
  auto with = [&](size_t idx, u64 word) { auto w = words; w[idx] = word; return w; };
  auto mutate = [&](const char *what, size_t idx, i64 cur, i64 hi) {
    S.report("c7-public", what, verify_stage1(with(idx, enc(cur < hi ? cur + 1 : cur - 1)), pb.data(), pb.size()), Verdict::PROOF);
  };
  mutate("public S0[0,0] changed by 1", w_S0(sh, 0), fx.S0[0], BOUND - 1);
  mutate("public a_1 changed by 1", w_a(sh, 0), fx.a[0], one);
  mutate("public beta_1 changed by 1", w_beta(sh, 0), fx.beta[0], one);
  mutate("public k_1[0] changed by 1", w_k(sh, 0, 0), fx.k[0][0], one);
  mutate("public v_1[0] changed by 1", w_v(sh, 0, 0), fx.v[0][0], VBOUND - 1);
  mutate("public q_1[0] changed by 1", w_q(sh, 0, 0), fx.q[0][0], one);
  mutate("public o_4[0] changed by 1", w_o(sh, sh.T - 1, 0), fx.o[sh.T - 1][0], VBOUND - 1);
  mutate("public S_4[0,0] changed by 1", w_ST(sh, 0), fx.S[sh.T - 1][0], BOUND - 1);
  // ---- c8: bytes ----
  { std::vector<u8> bytes = pb; const size_t n = bytes.size();
    for (int k = 0; k < 12; k++) { const size_t i = (n * (2 * k + 1)) / 24; bytes[i] ^= 1; S.report("c8-bytes", "flip one bit", entry(bytes), Verdict::PROOF); bytes[i] ^= 1; }
    for (int k = 0; k < 9; k++) { const size_t cut = k == 8 ? n - 1 : (n * k) / 8; S.report("c8-bytes", "truncate", entry(std::vector<u8>(bytes.begin(), bytes.begin() + cut)), Verdict::PROOF); }
    bytes.push_back(0); S.report("c8-bytes", "trailing byte", entry(bytes), Verdict::PROOF); }
  // ---- admission (the #66 cases, on the stage 1 words) ----
  const u64 HALF = (P + 1) / 2;
  struct Cls { const char *name; size_t idx; i64 out_pos, out_neg; };
  const std::vector<Cls> cls = {{"S0", w_S0(sh, 0), BOUND, -BOUND}, {"a", w_a(sh, 1), one + 1, -1}, {"beta", w_beta(sh, 1), one + 1, -1}, {"k", w_k(sh, 1, 0), one + 1, -one - 1},
      {"v", w_v(sh, 1, 0), VBOUND, -VBOUND}, {"q", w_q(sh, 1, 0), one + 1, -one - 1}, {"o", w_o(sh, sh.T - 1, 0), VBOUND, -VBOUND}, {"S_T", w_ST(sh, 0), BOUND, -BOUND}};
  for (const Cls &c : cls) {
    S.report("huge-element", std::string(c.name) + " = (p+1)/2", verify_stage1(with(c.idx, HALF), pb.data(), pb.size()), Verdict::DECODE);
    S.report("class-bound", std::string(c.name) + " = first value outside class (+)", verify_stage1(with(c.idx, enc(c.out_pos)), pb.data(), pb.size()), Verdict::DECODE);
    S.report("class-bound", std::string(c.name) + " = first value outside class (-)", verify_stage1(with(c.idx, enc(c.out_neg)), pb.data(), pb.size()), Verdict::DECODE);
  }
  S.report("non-canonical", "a_0 word = a_0 + p", verify_stage1(with(w_a(sh, 0), words[w_a(sh, 0)] + P), pb.data(), pb.size()), Verdict::DECODE);
  S.report("header", "T word = 5", verify_stage1(with(0, 5), pb.data(), pb.size()), Verdict::DECODE);
  S.report("header", "F word = 10", verify_stage1(with(2, 10), pb.data(), pb.size()), Verdict::DECODE);
  { auto w = words; w.push_back(0); S.report("length", "one trailing word", verify_stage1(w, pb.data(), pb.size()), Verdict::DECODE); }
  { auto w = words; w.pop_back(); S.report("length", "one word short", verify_stage1(w, pb.data(), pb.size()), Verdict::DECODE); }
  for (int sign = 0; sign < 2; sign++) {  // every class at its extreme (one sign; alternating signs)
    auto w = words;
    for (size_t c = 0; c < size_t(sh.D) * sh.D; c++) w[w_S0(sh, c)] = enc(sign && (c & 1) ? -(BOUND - 1) : BOUND - 1), w[w_ST(sh, c)] = enc(BOUND - 1);
    for (int t = 0; t < sh.T; t++) {
      w[w_a(sh, t)] = enc(one); w[w_beta(sh, t)] = enc(one);
      for (int i = 0; i < sh.D; i++) { w[w_k(sh, t, i)] = enc(one); w[w_q(sh, t, i)] = enc(one); w[w_v(sh, t, i)] = enc(sign && (i & 1) ? -(VBOUND - 1) : VBOUND - 1); w[w_o(sh, t, i)] = enc(VBOUND - 1); }
    }
    S.report("derive-extremes", sign ? "every class at its extreme, alternating signs" : "every class at its extreme, one sign", verify_stage1(w, pb.data(), pb.size()), Verdict::PROOF);
  }
  { auto w = words; u64 st2 = 0x9e3779b97f4a7c15ULL;
    auto rnd = [&](i64 lo, i64 hi) { st2 ^= st2 << 13; st2 ^= st2 >> 7; st2 ^= st2 << 17; return lo + i64(st2 % u64(hi - lo + 1)); };
    for (size_t c = 0; c < size_t(sh.D) * sh.D; c++) w[w_S0(sh, c)] = enc(rnd(-(BOUND - 1), BOUND - 1)), w[w_ST(sh, c)] = enc(rnd(-(BOUND - 1), BOUND - 1));
    for (int t = 0; t < sh.T; t++) {
      w[w_a(sh, t)] = enc(rnd(0, one)); w[w_beta(sh, t)] = enc(rnd(0, one));
      for (int i = 0; i < sh.D; i++) { w[w_k(sh, t, i)] = enc(rnd(-one, one)); w[w_q(sh, t, i)] = enc(rnd(-one, one)); w[w_v(sh, t, i)] = enc(rnd(-(VBOUND - 1), VBOUND - 1)); w[w_o(sh, t, i)] = enc(rnd(-(VBOUND - 1), VBOUND - 1)); }
    }
    S.report("derive-random", "every word uniform in its class (fixed xorshift seed)", verify_stage1(w, pb.data(), pb.size()), Verdict::PROOF); }
  S.report("in-class", "o_T[0] and S0[0] both changed by 1", verify_stage1([&] { auto w = with(w_o(sh, sh.T - 1, 0), enc(fx.o[sh.T - 1][0] + 1)); w[w_S0(sh, 0)] = enc(fx.S0[0] + (fx.S0[0] < BOUND - 1 ? 1 : -1)); return w; }(), pb.data(), pb.size()), Verdict::PROOF);
  // R9 (#63 review): o_T[j]' = o_T[j] - 2^-F mod p is a field element that is no small integer. The
  // entry rejects the statement at decode, whatever proof comes with it.
  { const u64 oprime = (fi(fx.o[sh.T - 1][0]) - inv(F{u64(one)})).v;
    S.report("r9", "o_T[0] replaced by o_T[0] - 2^-F mod p", verify_stage1(with(w_o(sh, sh.T - 1, 0), oprime), pb.data(), pb.size()), Verdict::DECODE); }
  S.summary();
  return S.as_expected == S.total ? 0 : 1;
}
