// SPDX-License-Identifier: Apache-2.0
// Research-only PROTOTYPE for the M2 design (experiments/20261105-32-qwen-deltanet-m2-design, H5):
// a verifier entry point that takes the public statement as 64-bit words, decodes and range-checks
// every integer itself, derives every relation target from the decoded integers, and only then runs
// the unchanged proof verifier (lookup.h). There is no separate admissible() a caller can skip, and
// no entry point that accepts caller-built relations.
// The statement is the M1b one (one head, D = 128, T = 4, F = 12), plus the conv history block that
// the M2 statement adds (DESIGN.md section 2, post-review #66): the last 3 pre-conv inputs of each of
// the head's 384 conv channels before token 0, public and class-bounded. The M1b relations do not
// read it (M1b has no conv; in M2 the verifier's conv recompute reads it), so here it tests decode
// and admission only. Usage:
//   admit_proto.bin <fixture.bin> honest     prove from the fixture; verify_from_words; one JSON line
//   admit_proto.bin <fixture.bin> hostile    honest run + every pre-registered hostile encoding
#include "m1b_builder.h"

// The statement on the wire, in this order:
//   T, D, F | S0[D*D] | H[3 * 3D] | per token t: a, beta, k[D], v[D], q[D], o[D] | S_T[D*D]
// H[tau * 3D + ch] = pre-conv input of channel ch at token -1 - tau (tau = 0, 1, 2; ch < 3D: the
// q, k and v channels). The verifier fixes the shape (T, D, F) itself; the header must equal it.
struct Shape { int T = 4, D = 128, F = 12; };
constexpr i64 XBOUND = i64(1) << 31;  // pre-conv inputs, as xq, xk, xv in DESIGN.md section 2
static size_t hist_words(const Shape &s) { return size_t(3) * 3 * s.D; }
static u64 enc(i64 x) { return fi(x).v; }
// Honest conv history for the M1b fixture: filler values in class (the first 3 * 3D entries of S0,
// times 2^12). Nothing in the M1b relation list reads them.
static std::vector<i64> history_of(const Fixture &z) {
  std::vector<i64> h(size_t(3) * 3 * z.D);
  for (size_t i = 0; i < h.size(); i++) h[i] = z.S0[i % z.S0.size()] * 4096;
  return h;
}
static std::vector<u64> encode(const Fixture &z) {
  std::vector<u64> w = {u64(z.T), u64(z.D), u64(z.F)};
  for (auto s : z.S0) w.push_back(enc(s));
  for (auto x : history_of(z)) w.push_back(enc(x));
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
static size_t w_S0(const Shape &, size_t c) { return 3 + c; }
static size_t w_H(const Shape &s, size_t i) { return 3 + size_t(s.D) * s.D + i; }
static size_t w_tok(const Shape &s, int t) { return 3 + size_t(s.D) * s.D + hist_words(s) + size_t(t) * (2 + 4 * s.D); }
static size_t w_a(const Shape &s, int t) { return w_tok(s, t); }
static size_t w_beta(const Shape &s, int t) { return w_tok(s, t) + 1; }
static size_t w_k(const Shape &s, int t, int i) { return w_tok(s, t) + 2 + i; }
static size_t w_v(const Shape &s, int t, int i) { return w_tok(s, t) + 2 + s.D + i; }
static size_t w_q(const Shape &s, int t, int i) { return w_tok(s, t) + 2 + 2 * s.D + i; }
static size_t w_o(const Shape &s, int t, int i) { return w_tok(s, t) + 2 + 3 * s.D + i; }
static size_t w_ST(const Shape &s, size_t c) { return w_tok(s, s.T) + c; }

// DERIVE: the relation derivation or sizing refused (a reject, never a process exit). With in-class
// inputs and the witness-free derivation it should not happen; it is a verdict so that it cannot
// become exit(1) or undefined behaviour.
enum class Verdict { ACCEPT, DECODE, DERIVE, PROOF };
static const char *stage_name(Verdict x) { return x == Verdict::ACCEPT ? "accept" : x == Verdict::DECODE ? "decode" : x == Verdict::DERIVE ? "derive" : "proof"; }
struct VerifyTiming { double decode_s = 0, derive_s = 0, verify_s = 0; std::string why; };

// One word as a signed integer of a class: canonical (< p), then lo <= x <= hi. A word above p/2
// reads as negative. P / 2 rounds down, so the word (p - 1) / 2 is the largest positive integer and
// (p + 1) / 2 the most negative one.
static bool decode(u64 w, i64 lo, i64 hi, i64 &out) {
  if (w >= P) return false;
  const i64 x = w > P / 2 ? -(i64)(P - w) : (i64)w;
  if (x < lo || x > hi) return false;
  out = x; return true;
}
// Sizing as in the M1b test, a function of the derived statement only (the M1b schedule held at its
// first try in #63; a schedule search would also be a pure function of the shape).
struct Sized { LookupRun run; unsigned L = 0; bool ok = true; };
static Sized size_run(const Built &b) {
  unsigned L = 1; while ((u64(1) << L) < b.cols.size()) L++;
  {
    Setting s0 = setting_goldilocks(); s0.target = 10; s0.set_work(ErrorKind::QUERY, Scope::REQUEST, 6);
    const unsigned N0 = rng_combinations(s0, Scope::REQUEST);
    const u64 dc = pow2_at_least(b.rc_rows), np = pow2_at_least(N0);
    RngShape probe; probe.digit_bits[0] = 12, probe.digit_bits[1] = 11, probe.combinations = N0, probe.digit_columns = dc;
    const LkpPublic lk = rng_lookup(probe);
    while ((u64(1) << L) < std::max<u64>(dc * np, rng_planes_places(lk))) L++;
  }
  Setting set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES; set.target = 10; set.set_work(ErrorKind::QUERY, Scope::REQUEST, 6);
  RegionSpec rs; rs.rows = {b.rc_rows}; rs.first_place = {b.rc_base}; rs.columns = RCOLS;
  const std::vector<StageChoice> further = {{1, 1, L, L}, {0, 0, L, L}};
  Sized s{lookup_size(set, L, L + 1, L + 1, further, b.rel, rs), L};
  s.ok = s.run.product.plan->holds();  // the caller decides: the prover stops, the verifier rejects
  return s;
}
// The verifier's sizing: the shape alone fixes L, the region and the relation count (the M2 build
// fixes them as constants), so lookup_size()'s guards cannot fire on any statement that decoded.
// They are checked here first anyway, so that a reject is returned instead of a BLK_REQUIRE exit.
static bool size_preconditions(const Built &b) {
  if (b.rel.empty() || b.rel.size() > (u64(1) << 23)) return false;
  unsigned L = 1; while ((u64(1) << L) < b.cols.size()) L++;
  if (L > 22) return false;
  for (const auto &a : b.rel) {
    if (wide_fault(a)) return false;
    for (const auto &t : a.terms) if (t.column >= b.cols.size()) return false;
  }
  return true;
}

// THE ENTRY POINT. Everything a caller supplies is untrusted: the statement words and the proof bytes.
// (1) fix the shape; (2) decode every word as a canonical field element and read it as an integer of
// its class, rejecting anything outside; (3) derive every relation target from the decoded integers
// (relation-only build, no witness: see m1b_builder.h); (4) size and run the unchanged proof
// verifier. Every failure is a returned verdict; nothing here exits the process.
// Class bounds (the M1b admit, now inside the verifier): |S0|, |S_T| < 2^18; a, beta in [0, 2^F];
// |k|, |q| <= 2^F; |v|, |o| < 2^31; conv history |H| < 2^31.
static Verdict verify_from_words(const Shape &sh, const std::vector<u64> &w, const u8 *proof, size_t bytes, VerifyTiming *tm = nullptr) {
  auto t0 = std::chrono::steady_clock::now();
  const size_t DD = size_t(sh.D) * sh.D, want = 3 + DD + hist_words(sh) + size_t(sh.T) * (2 + 4 * sh.D) + DD;
  if (w.size() != want) { if (tm) tm->why = "statement length"; return Verdict::DECODE; }
  if (w[0] != u64(sh.T) || w[1] != u64(sh.D) || w[2] != u64(sh.F)) { if (tm) tm->why = "header differs from the verifier's shape"; return Verdict::DECODE; }
  const i64 one = i64(1) << sh.F;
  Fixture z; z.T = sh.T, z.D = sh.D, z.F = sh.F;
  size_t p = 3; bool ok = true;
  auto take = [&](size_t n, i64 lo, i64 hi) { std::vector<i64> r(n, 0); for (size_t i = 0; i < n && ok; i++) ok = decode(w[p++], lo, hi, r[i]); return r; };
  z.S0 = take(DD, -(BOUND - 1), BOUND - 1);
  const std::vector<i64> H = take(hist_words(sh), -(XBOUND - 1), XBOUND - 1);  // M2: read by the conv recompute
  (void)H;
  for (int t = 0; t < sh.T && ok; t++) {
    z.a.push_back(take(1, 0, one)[0]); z.beta.push_back(take(1, 0, one)[0]);
    z.k.push_back(take(sh.D, -one, one)); z.v.push_back(take(sh.D, -(VBOUND - 1), VBOUND - 1));
    z.q.push_back(take(sh.D, -one, one)); z.o.push_back(take(sh.D, -(VBOUND - 1), VBOUND - 1));
  }
  std::vector<i64> ST = ok ? take(DD, -(BOUND - 1), BOUND - 1) : std::vector<i64>();
  if (!ok) { if (tm) tm->why = "a public word is non-canonical or outside its class"; return Verdict::DECODE; }
  if (tm) tm->decode_s = secs(t0);
  // The builder reads z.S[T-1] as the public final state and z.o as targets; z.M, z.delta, z.S[< T-1]
  // are not read by the relation list. Shapes only.
  z.S.assign(sh.T, std::vector<i64>(DD, 0)); z.S[sh.T - 1] = ST;
  auto t1 = std::chrono::steady_clock::now();
  Built b = build(z, true);
  if (!size_preconditions(b)) { if (tm) tm->why = "derived statement outside the sizing guards"; return Verdict::DERIVE; }
  Sized s = size_run(b);
  if (!s.ok) { if (tm) tm->why = "no plan holds for the derived statement"; return Verdict::DERIVE; }
  if (tm) tm->derive_s = secs(t1);
  auto t2 = std::chrono::steady_clock::now();
  const char *why = nullptr;
  const bool acc = lookup_verify(s.run, proof, bytes, &why);
  if (tm) { tm->verify_s = secs(t2); tm->why = acc ? "" : (why ? why : "proof verifier"); }
  return acc ? Verdict::ACCEPT : Verdict::PROOF;
}

// Control for the derive-overflow cases: would the FIRST prototype's verifier path (the full witness
// recurrence with its checks off) overflow i64 on this statement? Same arithmetic as build(), with
// every product and sum checked. Returns the token at which the first overflow happens, or -1.
static int old_path_overflow_token(const Fixture &z) {
  const int D = z.D; const i64 one = i64(1) << z.F; std::vector<i64> S = z.S0, Sn(size_t(D) * D);
  auto mul = [](i64 a, i64 b, bool &bad) { i64 r; bad |= __builtin_mul_overflow(a, b, &r); return r; };
  auto add = [](i64 a, i64 b, bool &bad) { i64 r; bad |= __builtin_add_overflow(a, b, &r); return r; };
  for (int t = 0; t < z.T; t++) {
    bool bad = false; std::vector<i64> delta(D);
    for (int j = 0; j < D; j++) {
      i64 Pj = 0; for (int i = 0; i < D; i++) Pj = add(Pj, mul(S[i * D + j], z.k[t][i], bad), bad);
      const i64 aP = mul(Pj, z.a[t], bad); const i64 M = fdiv(aP, one * one);
      delta[j] = fdiv(mul(add(z.v[t][j], -M, bad), z.beta[t], bad), one);
    }
    for (int i = 0; i < D; i++) for (int j = 0; j < D; j++) Sn[i * D + j] = fdiv(add(mul(z.a[t], S[i * D + j], bad), mul(z.k[t][i], delta[j], bad), bad), one);
    for (int j = 0; j < D; j++) { i64 s = 0; for (int i = 0; i < D; i++) s = add(s, mul(Sn[i * D + j], z.q[t][i], bad), bad); }
    if (bad) return t;
    S = Sn;
  }
  return -1;
}
// The words of a statement, decoded without class checks (the hostile statements below are in class).
static Fixture fixture_of_words(const Shape &sh, const std::vector<u64> &w) {
  auto rd = [](u64 x) { return x > P / 2 ? -(i64)(P - x) : (i64)x; };
  Fixture z; z.T = sh.T, z.D = sh.D, z.F = sh.F; const size_t DD = size_t(sh.D) * sh.D;
  for (size_t c = 0; c < DD; c++) z.S0.push_back(rd(w[w_S0(sh, c)]));
  for (int t = 0; t < sh.T; t++) {
    z.a.push_back(rd(w[w_a(sh, t)])); z.beta.push_back(rd(w[w_beta(sh, t)]));
    std::vector<i64> k, v, q, o;
    for (int i = 0; i < sh.D; i++) k.push_back(rd(w[w_k(sh, t, i)])), v.push_back(rd(w[w_v(sh, t, i)])), q.push_back(rd(w[w_q(sh, t, i)])), o.push_back(rd(w[w_o(sh, t, i)]));
    z.k.push_back(k); z.v.push_back(v); z.q.push_back(q); z.o.push_back(o);
  }
  return z;
}

static Table table_of(const Built &b, unsigned L) {
  Table tab(1, 3, u64(1) << L);
  for (size_t c = 0; c < b.cols.size(); c++) for (int r = 0; r < 3; r++) tab.set(r, c, E::from(b.cols[c][r]));
  return tab;
}

int main(int argc, char **argv) {
  check(argc == 3, "usage: admit_proto.bin <fixture.bin> honest|hostile");
  const std::string mode = argv[2];
  const Shape sh;
  auto z = load(argv[1]);
  check(z.T == sh.T && z.D == sh.D && z.F == sh.F, "fixture shape");
  // Prover side, unchanged from M1b: witness from the fixture, cell by cell against reference.py.
  Built b = build(z);
  for (int t = 0; t < z.T; t++) check(b.M[t] == z.M[t] && b.delta[t] == z.delta[t] && b.S[t] == z.S[t] && b.o[t] == z.o[t], "C++ lowering equals reference.py");
  Sized s = size_run(b);
  check(s.ok, "plan holds (M1b schedule)");
  Table tab = table_of(b, s.L);
  check(products_hold_all(tab) && violated(b.rel, tab) == 0, "honest table");
  {  // the witness-free derivation gives the prover's relation list exactly (columns, terms, targets)
    const Built v = build(z, true);
    bool same = v.cols.size() == b.cols.size() && v.rel.size() == b.rel.size();
    for (size_t i = 0; same && i < b.rel.size(); i++) {
      same = v.rel[i].target.v == b.rel[i].target.v && v.rel[i].terms.size() == b.rel[i].terms.size();
      for (size_t k = 0; same && k < b.rel[i].terms.size(); k++)
        same = v.rel[i].terms[k].row == b.rel[i].terms[k].row && v.rel[i].terms[k].column == b.rel[i].terms[k].column && v.rel[i].terms[k].coefficient.v == b.rel[i].terms[k].coefficient.v;
    }
    check(same, "witness-free derivation equals the prover's relation list");
  }
  auto tp = std::chrono::steady_clock::now(); Writer proof = prove(s.run, b, tab, false); const double prove_s = secs(tp);
  const std::vector<u64> words = encode(z);
  auto pb = proof.bytes();
  VerifyTiming tm; const Verdict st = verify_from_words(sh, words, pb.data(), pb.size(), &tm);
  std::printf("{\"mode\":\"honest\",\"accept\":%s,\"stage\":\"%s\",\"statement_words\":%zu,\"proof_bytes\":%zu,\"prove_s\":%.3f,\"decode_s\":%.4f,\"derive_s\":%.3f,\"verify_s\":%.3f,\"peak_rss_kb\":%ld}\n",
              st == Verdict::ACCEPT ? "true" : "false", stage_name(st), words.size(), pb.size(), prove_s, tm.decode_s, tm.derive_s, tm.verify_s, rss_kb());
  std::fflush(stdout);
  check(st == Verdict::ACCEPT, "honest accepted by verify_from_words");
  if (mode != "hostile") return 0;

  int as_expected = 0, total = 0;
  auto report = [&](const char *cls, const std::string &what, Verdict got, Verdict want) {
    total++; const bool good = got == want; as_expected += good;
    std::printf("{\"mode\":\"hostile\",\"class\":\"%s\",\"attack\":\"%s\",\"rejected\":%s,\"stage\":\"%s\",\"expected_stage\":\"%s\",\"as_expected\":%s}\n",
                cls, what.c_str(), got != Verdict::ACCEPT ? "true" : "false", stage_name(got), stage_name(want), good ? "true" : "false");
    std::fflush(stdout);
  };
  auto with = [&](size_t idx, u64 word) { auto w = words; w[idx] = word; return w; };
  const u64 HALF = (P + 1) / 2;  // the huge field element: about 2^63 in magnitude as a signed read
  const i64 one = i64(1) << sh.F;
  struct Cls { const char *name; size_t idx; i64 out_pos; i64 out_neg; };
  // One element per class; out_pos / out_neg = the first integers outside the class on each side.
  const std::vector<Cls> cls = {
      {"S0", w_S0(sh, 0), BOUND, -BOUND}, {"a", w_a(sh, 1), one + 1, -1}, {"beta", w_beta(sh, 1), one + 1, -1}, {"k", w_k(sh, 1, 0), one + 1, -one - 1},
      {"v", w_v(sh, 1, 0), VBOUND, -VBOUND}, {"q", w_q(sh, 1, 0), one + 1, -one - 1}, {"o", w_o(sh, sh.T - 1, 0), VBOUND, -VBOUND}, {"S_T", w_ST(sh, 0), BOUND, -BOUND},
      {"H (conv history)", w_H(sh, 3 * sh.D * 2 + 5), XBOUND, -XBOUND}};
  for (const Cls &c : cls) {
    report("huge-element", std::string(c.name) + " = (p+1)/2", verify_from_words(sh, with(c.idx, HALF), pb.data(), pb.size()), Verdict::DECODE);
    report("class-bound", std::string(c.name) + " = first value outside class (+)", verify_from_words(sh, with(c.idx, enc(c.out_pos)), pb.data(), pb.size()), Verdict::DECODE);
    report("class-bound", std::string(c.name) + " = first value outside class (-)", verify_from_words(sh, with(c.idx, enc(c.out_neg)), pb.data(), pb.size()), Verdict::DECODE);
  }
  {
    const size_t idx = w_a(sh, 0); check(words[idx] < (u64(1) << 32), "a is small");
    report("non-canonical", "a_0 word = a_0 + p (second encoding of the same element)", verify_from_words(sh, with(idx, words[idx] + P), pb.data(), pb.size()), Verdict::DECODE);
    const size_t io = w_o(sh, 0, 0);
    if (words[io] < (u64(1) << 32)) report("non-canonical", "o_0[0] word = o_0[0] + p", verify_from_words(sh, with(io, words[io] + P), pb.data(), pb.size()), Verdict::DECODE);
    size_t ih = w_H(sh, 0); while (words[ih] >= (u64(1) << 32)) ih++;
    report("non-canonical", "H word = H + p (conv history)", verify_from_words(sh, with(ih, words[ih] + P), pb.data(), pb.size()), Verdict::DECODE);
  }
  // Derive-step hostile cases (post-review #66 should-fix 3): in-class but inconsistent statements
  // whose witness, if the verifier computed it, overflows i64 within T = 4 tokens (|S0| near 2^18,
  // k = q = 2^F, a = beta = 2^F, |v| near 2^31: a P_j is about 2^49 at token 0 and 2^62 at token 1,
  // and a P_j passes 2^63 at token 2: signed-overflow UB in the old witness path). The witness-free derivation must not crash or exit: it returns a verdict, and the
  // proof verifier rejects (the honest proof does not prove this statement).
  {
    auto w = words;
    for (size_t c = 0; c < size_t(sh.D) * sh.D; c++) w[w_S0(sh, c)] = enc((c & 1) ? BOUND - 1 : -(BOUND - 1));
    for (int t = 0; t < sh.T; t++) {
      w[w_a(sh, t)] = enc(one); w[w_beta(sh, t)] = enc(one);
      for (int i = 0; i < sh.D; i++) { w[w_k(sh, t, i)] = enc(one); w[w_q(sh, t, i)] = enc(one); w[w_v(sh, t, i)] = enc((i & 1) ? VBOUND - 1 : -(VBOUND - 1)); w[w_o(sh, t, i)] = enc(VBOUND - 1); }
    }
    std::printf("{\"mode\":\"derive-overflow-detail\",\"old_path_first_overflow_token\":%d}\n", old_path_overflow_token(fixture_of_words(sh, w)));
    report("derive-overflow", "every class at its extreme (old witness path: i64 overflow)", verify_from_words(sh, w, pb.data(), pb.size()), Verdict::PROOF);
  }
  {
    auto w = words; u64 st = 0x9e3779b97f4a7c15ULL;
    auto rnd = [&](i64 lo, i64 hi) { st ^= st << 13; st ^= st >> 7; st ^= st << 17; return lo + i64(st % u64(hi - lo + 1)); };
    for (size_t c = 0; c < size_t(sh.D) * sh.D; c++) w[w_S0(sh, c)] = enc(rnd(-(BOUND - 1), BOUND - 1));
    for (size_t i = 0; i < hist_words(sh); i++) w[w_H(sh, i)] = enc(rnd(-(XBOUND - 1), XBOUND - 1));
    for (int t = 0; t < sh.T; t++) {
      w[w_a(sh, t)] = enc(rnd(0, one)); w[w_beta(sh, t)] = enc(rnd(0, one));
      for (int i = 0; i < sh.D; i++) { w[w_k(sh, t, i)] = enc(rnd(-one, one)); w[w_q(sh, t, i)] = enc(rnd(-one, one)); w[w_v(sh, t, i)] = enc(rnd(-(VBOUND - 1), VBOUND - 1)); w[w_o(sh, t, i)] = enc(rnd(-(VBOUND - 1), VBOUND - 1)); }
    }
    for (size_t c = 0; c < size_t(sh.D) * sh.D; c++) w[w_ST(sh, c)] = enc(rnd(-(BOUND - 1), BOUND - 1));
    std::printf("{\"mode\":\"derive-random-detail\",\"old_path_first_overflow_token\":%d}\n", old_path_overflow_token(fixture_of_words(sh, w)));
    report("derive-random", "every word uniform in its class (fixed xorshift seed)", verify_from_words(sh, w, pb.data(), pb.size()), Verdict::PROOF);
  }
  // Conv history in class but changed: nothing in the M1b relation list reads it, so this ACCEPTS
  // here. Recorded as a control, not a defence: in M2 the conv recompute reads H, so k, q, v change
  // and the proof verifier must reject. That case belongs to the M2 build's H4 suite.
  report("history-control", "H[0] += 1 in class (M1b reads no history: accept expected here)", verify_from_words(sh, with(w_H(sh, 0), enc(history_of(z)[0] + 1)), pb.data(), pb.size()), Verdict::ACCEPT);
  report("header", "T word = 5", verify_from_words(sh, with(0, 5), pb.data(), pb.size()), Verdict::DECODE);
  report("header", "F word = 10", verify_from_words(sh, with(2, 10), pb.data(), pb.size()), Verdict::DECODE);
  { auto w = words; w.push_back(0); report("length", "one trailing word", verify_from_words(sh, w, pb.data(), pb.size()), Verdict::DECODE); }
  { auto w = words; w.pop_back(); report("length", "one word short", verify_from_words(sh, w, pb.data(), pb.size()), Verdict::DECODE); }
  // Controls: in-class but wrong public values pass decode and the proof verifier rejects them.
  report("in-class", "o_T[0] += 1 (valid integer, wrong)", verify_from_words(sh, with(w_o(sh, sh.T - 1, 0), enc(z.o[sh.T - 1][0] + 1)), pb.data(), pb.size()), Verdict::PROOF);
  report("in-class", "S0[0] += 1 (valid integer, wrong)", verify_from_words(sh, with(w_S0(sh, 0), enc(z.S0[0] + 1)), pb.data(), pb.size()), Verdict::PROOF);

  // R9 (#63 review): o_T[j]' = o_T[j] - 2^-F (mod p), a field element that is not a small integer.
  // 2^F o' = 2^F o - 1, so the output floor's relation holds with remainder r + 1. Pick j with
  // r < 2^F - 1, re-decompose r + 1 into F honest bits, and prove the changed relation HONESTLY:
  // 0 violated relations, a complete proof. Control: the current path (caller-built relations,
  // admissible() skipped, lookup_verify) accepts it. Test: verify_from_words rejects it at decode.
  {
    int j = -1; for (int x = 0; x < sh.D; x++) if (b.o_rem_last[x] < one - 1) { j = x; break; }
    check(j >= 0, "an output remainder below 2^F - 1");
    Built bad = b; Table tbad = tab;
    const i64 r1 = b.o_rem_last[j] + 1;
    for (int i = 0; i < sh.F; i++) { const u64 c = b.o_rbits_last[j][i]; const E x = E::from(fi((r1 >> i) & 1)); tbad.set(0, c, x); tbad.set(1, c, x); tbad.set(2, c, x * x); }
    bad.rel[b.o_rel_last[j]].target = bad.rel[b.o_rel_last[j]].target + F{1};  // -2^F o' = -2^F o + 1
    check(products_hold_all(tbad), "R9 table products");
    const size_t viol = violated(bad.rel, tbad);
    Sized sbad = size_run(bad);
    Writer p9 = prove(sbad.run, bad, tbad, false);
    auto b9 = p9.bytes();
    const bool caller_path = lookup_verify(sbad.run, b9.data(), b9.size());
    const u64 oprime = (fi(z.o[sh.T - 1][j]) - inv(F{u64(one)})).v;
    std::printf("{\"mode\":\"r9-detail\",\"j\":%d,\"o\":%lld,\"o_prime_word\":\"%llu\",\"violated_relations\":%zu}\n", j, (long long)z.o[sh.T - 1][j], (unsigned long long)oprime, viol);
    report("r9-control", "current path: lookup_verify with caller-built relations, admissible() skipped", caller_path ? Verdict::ACCEPT : Verdict::PROOF, Verdict::ACCEPT);
    report("r9", "verify_from_words on the R9 statement and R9 proof", verify_from_words(sh, with(w_o(sh, sh.T - 1, j), oprime), b9.data(), b9.size()), Verdict::DECODE);
  }
  std::printf("{\"mode\":\"hostile-summary\",\"as_expected\":%d,\"total\":%d,\"peak_rss_kb\":%ld}\n", as_expected, total, rss_kb());
  return as_expected == total ? 0 : 1;
}
