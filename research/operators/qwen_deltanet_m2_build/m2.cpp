// SPDX-License-Identifier: Apache-2.0
// Research-only. Stage 2 of experiments/20261109-32-qwen-deltanet-lookup-build: the M2 head of the
// PR #66 design on the two-lookup run. One V head of a Gated DeltaNet layer, D = 128, T = 16,
// F = 12, SYNTHETIC inputs and constants. Proved: the recurrence and the gated RMSNorm of the
// witness head output o. Recomputed by the verifier from public integers and pinned tables
// (public_stage.h): conv with the public history H, SiLU, q/k L2 norm, the gates, the norm
// coefficient cg. As PR #66 section 0 says, every input is public here, so this statement is a
// rehearsal of the machinery, not a useful proof. Usage:
//   m2.bin <fixture.bin> check     no proof: witness against reference_m2.py, relations on the honest
//                                  table, counts, and every tamper's violated-relation count
//   m2.bin <fixture.bin> honest    one honest proof through verify_m2(); JSON lines
//   m2.bin <fixture.bin> hostile   the honest run, then every hostile case
#include "kit.h"
#include "public_stage.h"

static HeadParams shape2() { HeadParams hp; hp.T = 16, hp.D = 128, hp.F = 12, hp.norm = true; return hp; }
struct Fixture2 {
  HeadConsts hc; PublicIn in;
  std::vector<i64> a, beta; std::vector<std::vector<i64>> k, v, q, cg, M, delta, S, o, w, y;
};
static Fixture2 load2(const char *path, const HeadParams &hp) {
  std::ifstream f(path, std::ios::binary); check(bool(f), "open fixture");
  std::vector<i64> w; i64 x; while (f.read((char *)&x, 8)) w.push_back(x);
  size_t p = 0; auto take = [&](size_t n) { check(p + n <= w.size(), "fixture short"); std::vector<i64> r(w.begin() + p, w.begin() + p + n); p += n; return r; };
  Fixture2 z; auto h = take(3); check(h[0] == hp.T && h[1] == hp.D && h[2] == hp.F, "fixture shape");
  const size_t D = hp.D;
  z.hc.W = take(3 * D * 4); z.hc.dt_bias = take(1)[0];
  for (i64 g : take(D)) z.hc.G.push_back((__int128)g);
  z.in.S0 = take(D * D); z.in.H = take(9 * D);
  for (int t = 0; t < hp.T; t++) { z.in.xq.push_back(take(D)); z.in.xk.push_back(take(D)); z.in.xv.push_back(take(D)); z.in.ar.push_back(take(1)[0]); z.in.br.push_back(take(1)[0]); z.in.z.push_back(take(D)); }
  for (int t = 0; t < hp.T; t++) {
    z.a.push_back(take(1)[0]); z.beta.push_back(take(1)[0]); z.k.push_back(take(D)); z.v.push_back(take(D)); z.q.push_back(take(D)); z.cg.push_back(take(D));
    z.M.push_back(take(D)); z.delta.push_back(take(D)); z.S.push_back(take(D * D)); z.o.push_back(take(D)); z.w.push_back(take(D)); z.y.push_back(take(D));
  }
  check(p == w.size(), "fixture trailing data");
  z.in.ST = z.S[hp.T - 1]; z.in.y = z.y;
  return z;
}
// The statement on the wire: T, D, F | S0[D*D] | H[9D] | per token: xq[D], xk[D], xv[D], ar, br, z[D], y[D] | S_T[D*D]
static std::vector<u64> encode2(const HeadParams &hp, const PublicIn &in) {
  std::vector<u64> w = {u64(hp.T), u64(hp.D), u64(hp.F)};
  auto put = [&](const std::vector<i64> &v) { for (i64 x : v) w.push_back(enc(x)); };
  put(in.S0); put(in.H);
  for (int t = 0; t < hp.T; t++) { put(in.xq[t]); put(in.xk[t]); put(in.xv[t]); w.push_back(enc(in.ar[t])); w.push_back(enc(in.br[t])); put(in.z[t]); put(in.y[t]); }
  put(in.ST);
  return w;
}
static size_t w_S0(const HeadParams &, size_t c) { return 3 + c; }
static size_t w_H(const HeadParams &s, size_t i) { return 3 + size_t(s.D) * s.D + i; }
static size_t w_tok(const HeadParams &s, int t) { return 3 + size_t(s.D) * s.D + 9 * size_t(s.D) + size_t(t) * (5 * s.D + 2); }
static size_t w_xq(const HeadParams &s, int t, int i) { return w_tok(s, t) + i; }
static size_t w_xk(const HeadParams &s, int t, int i) { return w_tok(s, t) + s.D + i; }
static size_t w_xv(const HeadParams &s, int t, int i) { return w_tok(s, t) + 2 * s.D + i; }
static size_t w_ar(const HeadParams &s, int t) { return w_tok(s, t) + 3 * s.D; }
static size_t w_br(const HeadParams &s, int t) { return w_tok(s, t) + 3 * s.D + 1; }
static size_t w_z(const HeadParams &s, int t, int i) { return w_tok(s, t) + 3 * s.D + 2 + i; }
static size_t w_y(const HeadParams &s, int t, int i) { return w_tok(s, t) + 4 * s.D + 2 + i; }
static size_t w_ST(const HeadParams &s, size_t c) { return w_tok(s, s.T) + c; }

// THE ENTRY POINT of stage 2. hc is the verifier's own configuration (the head's fixed constants).
// Untrusted: the statement words and the proof bytes.
//  (1) the shape is the verifier's own; the header must equal it and the word count must be exact;
//  (2) every word is decoded as a canonical field element and read as an integer of its class:
//      |S0|, |S_T| < 2^18; |H|, |xq|, |xk|, |xv| < 2^31; |ar|, |br|, |z| < 2^20; |y| < 2^31;
//  (3) the public-only stage is recomputed (public_stage.h), and every derived coefficient is
//      checked against its bound, |cg| < 2^24 among them, BEFORE any relation or field conversion;
//  (4) every relation is derived from those integers with no witness;
//  (5) the run is sized and the unchanged proof verifier runs.
// Every failure is a returned verdict (decode, derive, derive-build, proof). Nothing here ends the process.
static Verdict verify_m2(const HeadConsts &hc, const std::vector<u64> &w, const u8 *proof, size_t bytes, VerifyTiming *tm = nullptr) {
  auto t0 = std::chrono::steady_clock::now();
  const HeadParams sh = shape2();
  const size_t D = sh.D, DD = D * D, want = 3 + DD + 9 * D + size_t(sh.T) * (5 * D + 2) + DD;
  if (w.size() != want) { if (tm) tm->why = "statement length"; return Verdict::DECODE; }
  if (w[0] != u64(sh.T) || w[1] != u64(sh.D) || w[2] != u64(sh.F)) { if (tm) tm->why = "header differs from the verifier's shape"; return Verdict::DECODE; }
  PublicIn in; size_t p = 3; bool ok = true;
  auto take = [&](size_t n, i64 bound) { std::vector<i64> r(n, 0); for (size_t i = 0; i < n && ok; i++) ok = decode(w[p++], -(bound - 1), bound - 1, r[i]); return r; };
  in.S0 = take(DD, BOUND); in.H = take(9 * D, VBOUND);
  for (int t = 0; t < sh.T && ok; t++) {
    in.xq.push_back(take(D, VBOUND)); in.xk.push_back(take(D, VBOUND)); in.xv.push_back(take(D, VBOUND));
    in.ar.push_back(take(1, ZBOUND)[0]); in.br.push_back(take(1, ZBOUND)[0]); in.z.push_back(take(D, ZBOUND)); in.y.push_back(take(D, VBOUND));
  }
  if (ok) in.ST = take(DD, BOUND);
  if (!ok) { if (tm) tm->why = "a public word is non-canonical or outside its class"; return Verdict::DECODE; }
  Derived z; const PubStage st = public_stage(sh, hc, in, z);
  if (!st.ok) { if (tm) tm->why = st.why; return Verdict::DERIVE; }
  if (tm) tm->derive_s = secs(t0);
  return derive_and_verify(sh, z, proof, bytes, tm);
}
static bool same_derived(const Derived &x, const Derived &y) { return x.a == y.a && x.beta == y.beta && x.k == y.k && x.v == y.v && x.q == y.q && x.cg == y.cg; }

#include "followup_cases.h"

int main(int argc, char **argv) {
  check(argc == 3, "usage: m2.bin <fixture.bin> check|honest|hostile");
  const std::string mode = argv[2];
  const HeadParams hp = shape2(); const int D = hp.D, T = hp.T; const i64 one = i64(1) << hp.F;
  if (mode == "control") {
    Suite S; followup_cases(S,hp,true); S.summary();
    return S.as_expected == S.total ? 0 : 1;
  }
  const Fixture2 fx = load2(argv[1], hp);
  auto t0 = std::chrono::steady_clock::now();
  Derived z; const PubStage ps = public_stage(hp, fx.hc, fx.in, z);
  check(ps.ok, ps.why);
  for (int t = 0; t < T; t++) check(z.a[t] == fx.a[t] && z.beta[t] == fx.beta[t] && z.k[t] == fx.k[t] && z.v[t] == fx.v[t] && z.q[t] == fx.q[t] && z.cg[t] == fx.cg[t], "C++ public stage equals reference_m2.py");
  const Built b = build(hp, z, false);
  check(!b.overflow, "honest witness arithmetic fits i64"); check(!b.refused, b.why);
  for (int t = 0; t < T; t++) check(b.M[t] == fx.M[t] && b.delta[t] == fx.delta[t] && b.S[t] == fx.S[t] && b.o[t] == fx.o[t] && b.w[t] == fx.w[t] && b.y[t] == fx.y[t], "C++ lowering equals reference_m2.py");
  check(same_relations(b, build(hp, z, true)), "witness-free derivation equals the prover's relation list");
  print_counts(b);
  const Table tab = table_of(b);
  check(products_hold_all(tab) && violated(b.rel, tab) == 0, "honest table");
  const double build_s = secs(t0);
  const std::vector<u64> words = encode2(hp, fx.in);
  // The honest proof comes first, before the hostile suite's extra statements are built, so that the
  // honest run's peak RSS and timings do not include them. `check` mode proves nothing.
  Sized s; Proved honest; std::vector<u8> pb;
  if (mode != "check") {
  s = size_run(b);
  check(s.ok, "a plan holds");
  auto tp = std::chrono::steady_clock::now();
  check(two_prove(*s.run, tab, Hostile(), honest), "honest prove");
  const double prove_s = secs(tp);
  pb = honest.proof.bytes();
  VerifyTiming tm; const Verdict st = verify_m2(fx.hc, words, pb.data(), pb.size(), &tm);
  const std::vector<E> al = alphas_of(tm.notes);
  std::printf("{\"mode\":\"honest\",\"accept\":%s,\"stage\":\"%s\",\"statement_words\":%zu,\"proof_bytes\":%zu,\"build_s\":%.3f,\"prove_s\":%.3f,\"derive_s\":%.3f,\"verify_s\":%.3f,\"peak_rss_kb\":%ld,"
              "\"lookup_alphas\":%zu,\"alpha_digit\":\"%s\",\"alpha_remainder\":\"%s\",\"alphas_differ\":%s,\"digit_lookup_bytes\":%zu,\"remainder_lookup_bytes\":%zu}\n",
              st == Verdict::ACCEPT ? "true" : "false", stage_name(st), words.size(), pb.size(), build_s, prove_s, tm.derive_s, tm.verify_s, rss_kb(),
              al.size(), al.size() > 0 ? hex_of(al[0]).c_str() : "", al.size() > 1 ? hex_of(al[1]).c_str() : "", al.size() == 2 && !(al[0] == al[1]) ? "true" : "false",
              honest.digit_end - honest.digit_begin, honest.rem_end - honest.rem_begin);
  std::fflush(stdout);
  check(st == Verdict::ACCEPT, "honest accepted by verify_m2");
  if (mode != "hostile") return 0;
  }

  // ---- the tampers (each keeps every product gate; "violated" counts the affine relations it breaks) ----
  struct Case { const char *cls; const char *what; std::function<void(Edit &)> tamper; Hostile h; Verdict want; };
  std::vector<Case> cases;
  const int tt = 1; const Built::NormIdx &ix = b.norm[tt];
  const i64 sg = ix.sigma, Rc = ix.Rc, o0 = b.o[tt][0], cg0 = z.cg[tt][0];
  cases.push_back({"control-research-prover", "research prover path, honest witness, no tamper (must be accepted)", [](Edit &) {}, Hostile(), Verdict::ACCEPT});
  cases.push_back({"n1-sigma", "sigma + 1 at token 2, e1, e2, rr and the gap shifted so that every relation holds",
      [&](Edit &e) { e.gate_ab(ix.gss, 1); e.gate_b(ix.grs, 1); e.cell(ix.sk[0], 1); e.cell(ix.e1k[0], -(2 * sg + 1)); e.cell(ix.e2k[0], 2 * sg + 3); e.cell(ix.rrk[0], -Rc); e.cell(ix.gk[0], 1 + Rc); }, Hostile(), Verdict::PROOF});
  cases.push_back({"n2-reciprocal", "Rc + 1 at token 2, rr, the gap and every w remainder shifted so that every relation holds",
      [&](Edit &e) { e.gate_a(ix.grs, 1); e.cell(ix.rk[0], 1); e.cell(ix.rrk[0], -sg); e.cell(ix.gk[0], sg); for (int j = 0; j < D; j++) { e.gate_b(ix.orr[j], 1); e.cell(ix.rw_key[j], b.o[tt][j]); } }, Hostile(), Verdict::PROOF});
  cases.push_back({"n3-w", "w[0] + 1 at token 2, its remainder -= 2^24 and the y remainder += cg so that every relation holds",
      [&](Edit &e) { e.cell(ix.w_rc[0], 1); e.cell(ix.rw_key[0], -(i64(1) << 24)); e.cell(ix.ry_key[0], cg0); }, Hostile(), Verdict::PROOF});
  cases.push_back({"n4-o", "o[0] + 1 at token 2 with its floor preserved (remainder -= 2^F), e1, e2 and the w remainder shifted",
      [&](Edit &e) { e.cell(ix.o_rc[0], 1); e.cell(ix.o_key[0], -one); e.gate_ab(ix.oo[0], 1); e.cell(ix.e1k[0], 2 * o0 + 1); e.cell(ix.e2k[0], -(2 * o0 + 1)); e.gate_a(ix.orr[0], 1); e.cell(ix.rw_key[0], Rc); }, Hostile(), Verdict::PROOF});
  cases.push_back({"n5-limb-resplit", "sigma's limbs re-split at token 2 (lo += 2^12, hi -= 1): 0 relations violated, only the remainder lookup can reject",
      [&](Edit &e) { e.cell(ix.sk[0], KEYS); e.cell(ix.sk[1], -1); }, Hostile(), Verdict::PROOF});
  cases.push_back({"c2-state-floor-preserving", "S_2[0,0] += 1, remainder key -= 2^F (leaves the table), range cell consistent",
      [&](Edit &e) { e.gate_a(b.state0[tt], 1); e.cell(b.state0_key[tt], -one); e.cell(b.state0_rc[tt], 1); }, Hostile(), Verdict::PROOF});
  { Hostile h; h.rng_mode = 1; cases.push_back({"c9-limb", "delta_lo += 32 * 2^18, delta_hi -= 32 (identity preserved, delta_lo outside 2^23)",
      [&](Edit &e) { e.cell(b.dlo_rc[0], 32 * BOUND); e.cell(b.dhi_rc[0], -32); }, h, Verdict::PROOF}); }

  // ---- the cg boundary statement: the verifier's gain for channel 0 set so that cg = 2^24 - 1 ----
  // The gain is per channel, so it applies at every token: z of channel 0 is set to 16 at every token
  // (the pinned SiLU table gives 8 there), and cg = floor(G * 8 / 4096) = 2^24 - 1 at all 16 tokens.
  HeadConsts hc_edge = fx.hc; hc_edge.G[0] = ((__int128)CGBOUND - 1) * 512;
  PublicIn in_edge = fx.in; for (int t = 0; t < T; t++) in_edge.z[t][0] = 16;
  check(m2tables::silu_f12[2049] == 8, "the pinned SiLU table gives 8 at input 16");
  Derived z_edge; { const PubStage s2 = public_stage(hp, hc_edge, in_edge, z_edge); check(s2.ok, s2.why); }
  { i64 most = 0; for (int t = 0; t < T; t++) { check(z_edge.cg[t][0] == CGBOUND - 1, "the boundary statement has cg = 2^24 - 1 on channel 0"); for (int j = 0; j < D; j++) most = std::max<i64>(most, std::llabs(z_edge.cg[t][j])); }
    check(most == CGBOUND - 1, "2^24 - 1 is the boundary statement's largest |cg|"); }
  { const Built b0 = build(hp, z_edge, false); check(!b0.overflow && !b0.refused, "boundary witness"); in_edge.y = b0.y; z_edge.y = b0.y; }
  const Built b_edge = build(hp, z_edge, false);
  check(!b_edge.overflow && !b_edge.refused, "boundary witness");
  const Table tab_edge = table_of(b_edge);
  check(products_hold_all(tab_edge) && violated(b_edge.rel, tab_edge) == 0, "boundary table");
  HeadConsts hc_over = hc_edge; hc_over.G[0] = (__int128)CGBOUND * 512;  // cg = 2^24
  const std::vector<u64> words_edge = encode2(hp, in_edge);

  // A changed public input that changes a recomputed value: the least power-of-two increment that does.
  // (A change below a table's input step can leave every recomputed value as it was: then the derived
  // statement is the SAME statement, and it is true.)
  auto first_change = [&](const std::function<void(PublicIn &, i64)> &apply, i64 from, i64 &d_out, PublicIn &out) {
    for (i64 d = from; d <= (i64(1) << 22); d *= 2) {
      PublicIn in2 = fx.in; apply(in2, d); Derived z2;
      if (public_stage(hp, fx.hc, in2, z2).ok && !same_derived(z, z2)) { d_out = d; out = in2; return true; }
    }
    return false;
  };
  i64 dH = 0, dq = 0, dar = 0, dz = 0; PublicIn inH, inq, inar, inz;
  const size_t hidx = size_t(2) * D + 0;  // tau = 0 (token -1), conv 2 (v), channel 0
  check(first_change([&](PublicIn &i, i64 d) { i.H[hidx] += d; }, 1, dH, inH), "a changed H that changes a recomputed value");
  check(first_change([&](PublicIn &i, i64 d) { i.xq[3][0] += d; }, 1, dq, inq), "a changed xq that changes a recomputed value");
  check(first_change([&](PublicIn &i, i64 d) { i.ar[2] += d; }, 1, dar, inar), "a changed ar that changes a recomputed value");
  check(first_change([&](PublicIn &i, i64 d) { i.z[2][0] += d; }, 1, dz, inz), "a changed z that changes a recomputed value");
  PublicIn inH1 = fx.in; inH1.H[hidx] += 1; Derived zH1; const bool h1_same = public_stage(hp, fx.hc, inH1, zH1).ok && same_derived(z, zH1);

  if (mode == "check") {
    for (const Case &c : cases) { Table bad = tab; Edit e{b, bad}; c.tamper(e);
      std::printf("{\"mode\":\"tamper-check\",\"class\":\"%s\",\"products_hold\":%s,\"violated_relations\":%zu}\n", c.cls, products_hold_all(bad) ? "true" : "false", violated(b.rel, bad)); }
    std::printf("{\"mode\":\"check\",\"ok\":true,\"build_s\":%.3f,\"statement_words\":%zu,\"sigma\":%lld,\"Rc\":%lld,\"cg_edge\":%lld,\"dH\":%lld,\"dxq\":%lld,\"dar\":%lld,\"dz\":%lld,\"H_plus_1_same_statement\":%s,\"peak_rss_kb\":%ld}\n",
                build_s, words.size(), (long long)sg, (long long)Rc, (long long)z_edge.cg[0][0], (long long)dH, (long long)dq, (long long)dar, (long long)dz, h1_same ? "true" : "false", rss_kb());
    return 0;
  }

  Suite S;
  auto V = [&](const std::vector<u64> &w) { return verify_m2(fx.hc, w, pb.data(), pb.size()); };
  auto with = [&](size_t idx, u64 word) { auto w = words; w[idx] = word; return w; };
  // ---- H4: the conv history, and the other recomputed inputs ----
  S.report("h4-history", "H changed in class by " + std::to_string(dH) + " (the least power of two that changes a recomputed value)", V(encode2(hp, inH)), Verdict::PROOF);
  if (h1_same) S.report("h4-history-same-statement", "H changed by 1, no recomputed value changes: the derived statement is the same, and true (accept expected)", V(encode2(hp, inH1)), Verdict::ACCEPT);
  S.report("h4-public", "xq changed in class by " + std::to_string(dq), V(encode2(hp, inq)), Verdict::PROOF);
  S.report("h4-public", "ar changed in class by " + std::to_string(dar), V(encode2(hp, inar)), Verdict::PROOF);
  S.report("h4-public", "z changed in class by " + std::to_string(dz), V(encode2(hp, inz)), Verdict::PROOF);
  S.report("h4-public", "y_16[0] changed by 1", V(with(w_y(hp, T - 1, 0), enc(fx.y[T - 1][0] + 1))), Verdict::PROOF);
  S.report("h4-public", "S0[0,0] changed by 1", V(with(w_S0(hp, 0), enc(fx.in.S0[0] + (fx.in.S0[0] < BOUND - 1 ? 1 : -1)))), Verdict::PROOF);
  S.report("h4-public", "S_T[0,0] changed by 1", V(with(w_ST(hp, 0), enc(fx.in.ST[0] + (fx.in.ST[0] < BOUND - 1 ? 1 : -1)))), Verdict::PROOF);
  // ---- admission of the derived norm coefficient (fourth review of PR #66) ----
  { Sized se = size_run(b_edge); check(se.ok, "a plan holds (boundary)");
    Proved pe; check(two_prove(*se.run, tab_edge, Hostile(), pe), "boundary prove");
    const std::vector<u8> eb = pe.proof.bytes();
    S.report("cg-boundary", "largest |cg| = 2^24 - 1, honest proof of that statement (accept expected)", verify_m2(hc_edge, words_edge, eb.data(), eb.size()), Verdict::ACCEPT);
    S.report("cg-boundary", "the same statement and proof, the verifier's gain one step up: cg = 2^24", verify_m2(hc_over, words_edge, eb.data(), eb.size()), Verdict::DERIVE); }
  for (int e = 52; e <= 62; e++)
    for (int variant = 0; variant < 2; variant++) {
      // The verifier's gain for channel 0 is 2^(e + 9), and z of channel 0 is 16 at every token, so
      // cg = 2^e on channel 0 at all tokens. With w = 2^12 there is a y in class and a remainder in
      // [0, 2^12) with cg w - r = 2^F y mod p, though the integer floor is 2^e: a modular alias of
      // the norm's last floor equation. That y is planted at one token (the first or the last).
      // WHAT THIS CASE SHOWS: the admission check fires on such a configuration, before derivation.
      // WHAT IT DOES NOT SHOW: no forged proof of an alias was built (with the check removed, the
      // honest proof used here would still be rejected, at the proof stage, since it proves another
      // statement). The alias itself is the fourth review's algebra, recomputed here per case.
      const int tok = variant ? T - 1 : 0;
      HeadConsts hc = fx.hc; hc.G[0] = (__int128)1 << (e + 9);
      auto w = words; for (int t = 0; t < T; t++) w[w_z(hp, t, 0)] = enc(16);
      F m = F{1}; for (int i = 0; i < e + 12; i++) m = m + m;  // 2^e * 2^12 mod p
      const F inv_one = inv(F{u64(one)}); bool alias = false; i64 ya = 0, ra = 0;
      for (i64 r = 0; r < one && !alias; r++) { const u64 yv = ((m - F{u64(r)}) * inv_one).v; const i64 ys = yv > P / 2 ? -(i64)(P - yv) : (i64)yv; if (ys > -VBOUND && ys < VBOUND) alias = true, ya = ys, ra = r; }
      if (alias) w[w_y(hp, tok, 0)] = enc(ya);
      std::printf("{\"mode\":\"alias-note\",\"cg_log2\":%d,\"token\":%d,\"alias_exists\":%s,\"alias_y\":%lld,\"alias_remainder\":%lld}\n", e, tok, alias ? "true" : "false", (long long)ya, (long long)ra);
      S.report("cg-large-gain-alias", "cg = 2^" + std::to_string(e) + " on channel 0, y at token " + std::to_string(tok) + " set to the modular alias (guard regression; no forged proof built)", verify_m2(hc, w, pb.data(), pb.size()), Verdict::DERIVE);
    }
  S.report("admit-domain", "ar = 2^19 (in class, outside the decay table's domain)", V(with(w_ar(hp, 1), enc(i64(1) << 19))), Verdict::DERIVE);
  S.report("admit-domain", "br = -2^19 (in class, outside the sigmoid table's domain)", V(with(w_br(hp, 1), enc(-(i64(1) << 19)))), Verdict::DERIVE);
  S.report("admit-domain", "z = 2^19 (in class, outside the SiLU table's domain)", V(with(w_z(hp, 1, 0), enc(i64(1) << 19))), Verdict::DERIVE);
  S.report("admit-domain", "xq = 2^30 (in class, conv output outside the SiLU table's domain)", V(with(w_xq(hp, 1, 0), enc(i64(1) << 30))), Verdict::DERIVE);
  { auto w = words; for (int t = 0; t < T; t++) for (int i = 0; i < D; i++) w[w_xq(hp, t, i)] = w[w_xk(hp, t, i)] = w[w_xv(hp, t, i)] = enc(VBOUND - 1);
    S.report("admit-domain", "every pre-conv input at its class extreme", V(w), Verdict::DERIVE); }
  { auto w = words; u64 st2 = 0x9e3779b97f4a7c15ULL;
    auto rnd = [&](i64 bound) { st2 ^= st2 << 13; st2 ^= st2 >> 7; st2 ^= st2 << 17; return -(bound - 1) + i64(st2 % u64(2 * bound - 1)); };
    for (size_t i = 3; i < w.size(); i++) w[i] = enc(rnd(BOUND));  // every word in every class (2^18 is the narrowest)
    S.report("derive-random", "every word uniform in (-2^18, 2^18), inside every class", V(w), Verdict::DERIVE); }
  { auto w = words; for (size_t c = 0; c < size_t(D) * D; c++) w[w_S0(hp, c)] = enc((c & 1) ? -(BOUND - 1) : BOUND - 1), w[w_ST(hp, c)] = enc(BOUND - 1);
    for (int t = 0; t < T; t++) for (int i = 0; i < D; i++) w[w_y(hp, t, i)] = enc((i & 1) ? -(VBOUND - 1) : VBOUND - 1);
    S.report("derive-extremes", "S0, S_T and y at their class extremes, honest pre-conv inputs", V(w), Verdict::PROOF); }
  // ---- decode ----
  const u64 HALF = (P + 1) / 2;
  struct Cls { const char *name; size_t idx; i64 bound; };
  const std::vector<Cls> cls = {{"S0", w_S0(hp, 0), BOUND}, {"H", w_H(hp, 5), VBOUND}, {"xq", w_xq(hp, 1, 0), VBOUND}, {"xk", w_xk(hp, 1, 0), VBOUND}, {"xv", w_xv(hp, 1, 0), VBOUND},
      {"ar", w_ar(hp, 1), ZBOUND}, {"br", w_br(hp, 1), ZBOUND}, {"z", w_z(hp, 1, 0), ZBOUND}, {"y", w_y(hp, T - 1, 0), VBOUND}, {"S_T", w_ST(hp, 0), BOUND}};
  for (const Cls &c : cls) {
    S.report("huge-element", std::string(c.name) + " = (p+1)/2", V(with(c.idx, HALF)), Verdict::DECODE);
    S.report("class-bound", std::string(c.name) + " = first value outside class (+)", V(with(c.idx, enc(c.bound))), Verdict::DECODE);
    S.report("class-bound", std::string(c.name) + " = first value outside class (-)", V(with(c.idx, enc(-c.bound))), Verdict::DECODE);
  }
  { size_t i = w_ar(hp, 0); while (words[i] >= (u64(1) << 32)) i++; S.report("non-canonical", "a small word + p", V(with(i, words[i] + P)), Verdict::DECODE); }
  S.report("header", "T word = 17", V(with(0, 17)), Verdict::DECODE);
  S.report("header", "F word = 10", V(with(2, 10)), Verdict::DECODE);
  { auto w = words; w.push_back(0); S.report("length", "one trailing word", V(w), Verdict::DECODE); }
  { auto w = words; w.pop_back(); S.report("length", "one word short", V(w), Verdict::DECODE); }
  S.report("r9", "y_16[0] replaced by y_16[0] - 2^-F mod p", V(with(w_y(hp, T - 1, 0), (fi(fx.y[T - 1][0]) - inv(F{u64(one)})).v)), Verdict::DECODE);
  // ---- bytes ----
  { std::vector<u8> bytes = pb; const size_t n = bytes.size();
    auto entry = [&](const std::vector<u8> &p) { return verify_m2(fx.hc, words, p.data(), p.size()); };
    for (int k = 0; k < 4; k++) { const size_t i = (n * (2 * k + 1)) / 8; bytes[i] ^= 1; S.report("c8-bytes", "flip one bit", entry(bytes), Verdict::PROOF); bytes[i] ^= 1; }
    for (int k = 0; k < 3; k++) { const size_t cut = k == 2 ? n - 1 : (n * (k + 1)) / 3; S.report("c8-bytes", "truncate", entry(std::vector<u8>(bytes.begin(), bytes.begin() + cut)), Verdict::PROOF); }
    bytes.push_back(0); S.report("c8-bytes", "trailing byte", entry(bytes), Verdict::PROOF);
    check(honest.digit_end == honest.rem_begin, "the two lookups' transcripts are adjacent");
    S.report("h1-splice", "the two lookups' transcripts exchanged", entry(exchanged(pb, honest.digit_begin, honest.digit_end, honest.rem_end)), Verdict::PROOF);
    S.report("h1-splice", "remainder lookup's transcript bytes overwritten by the digit lookup's", entry(overwritten(pb, honest.rem_begin, honest.rem_end, honest.digit_begin, honest.digit_end)), Verdict::PROOF); }
  // ---- complete hostile proofs ----
  for (const Case &c : cases) {
    Table bad = tab; Edit e{b, bad}; c.tamper(e); Hostile h = c.h; h.on = true;
    check(products_hold_all(bad), "attack preserves every product gate");
    const size_t viol = violated(b.rel, bad);
    Proved pr; check(two_prove(*s.run, bad, h, pr), "hostile prove");
    const std::vector<u8> bytes = pr.proof.bytes();
    VerifyTiming t2; const Verdict v = verify_m2(fx.hc, words, bytes.data(), bytes.size(), &t2);
    std::printf("{\"mode\":\"hostile-note\",\"attack\":\"%s\",\"wrapped_combinations\":%llu,\"keys_outside_table\":%llu}\n", c.what, (unsigned long long)pr.wrapped, (unsigned long long)pr.uncounted);
    S.report(c.cls, c.what, v, c.want, (long long)viol, t2.why.c_str());
  }
  followup_cases(S,hp,false);
  S.summary();
  return S.as_expected == S.total ? 0 : 1;
}
