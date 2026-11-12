// SPDX-License-Identifier: Apache-2.0
// Research-only window proof with an IN-PROOF boundary commitment (issue #93).
// One window = C DeltaNet SA/M1b tokens (lowering reused from qwen_handoff/lowering.h).
// The window proof opens an in-field sponge commitment of its incoming state/history/salt
// and computes the commitment of its outgoing state/history/salt, both inside the same
// product/affine proof. The verifier reads only: its statement (public descriptor, token
// inputs, pre-conv inputs, outputs), the incoming commitment, the claimed outgoing
// commitment and the proof. It never receives a boundary state.
// The sponge is Poseidon-SHAPED (width 12, rate 8, x^7, 8 full + 22 partial rounds, Cauchy
// MDS, SHA-256 counter constants). It is NOT a vetted parameter set; no hash security claimed.
#include "../qwen_handoff/sha256.h"
#include "../qwen_handoff/lowering.h"
#include <array>

constexpr int W = 12, RATE = 8, RF = 8, RP = 22, NROUND = RF + RP;
static F fu(u64 x) { return F{x % P}; }
static u64 le64(const u8 *p) { u64 x = 0; for (int i = 0; i < 8; i++) x |= u64(p[i]) << (8 * i); return x; }
static void putword(std::vector<u8> &out, i64 x) { u64 v; std::memcpy(&v, &x, 8); for (unsigned i = 0; i < 8; i++) out.push_back((v >> (8 * i)) & 255); }
struct SpongeParams { F mds[W][W]; F rc[NROUND][W]; };
static const SpongeParams &params() {
  static const SpongeParams sp = [] {
    SpongeParams s;
    for (int i = 0; i < W; i++) for (int j = 0; j < W; j++) s.mds[i][j] = inv(F{u64(i)} + F{u64(W + j)});
    for (int r = 0; r < NROUND; r++) for (int i = 0; i < W; i++) {
      std::string d = "fp-hidden-root-rc-v1"; std::vector<u8> m(d.begin(), d.end());
      const uint32_t ctr = uint32_t(r * W + i); for (int k = 0; k < 4; k++) m.push_back((ctr >> (8 * k)) & 255);
      auto h = sha256(m); s.rc[r][i] = fu(le64(h.data()));
    }
    return s;
  }();
  return sp;
}
static bool full_round(int r) { return r < RF / 2 || r >= RF / 2 + RP; }

// Linear form over table cells plus a constant, with the honest/witness value carried along.
struct Lin { std::vector<AffineTerm> t; F c{0}; F v{0}; };
static Lin konst(F x) { Lin l; l.c = x; l.v = x; return l; }
static Lin cell(unsigned row, u64 col, F value) { Lin l; l.t = {{row, col, F{1}}}; l.v = value; return l; }
static void add_scaled(Lin &a, const Lin &b, F k) {
  for (auto x : b.t) a.t.push_back({x.row, x.column, x.coefficient * k});
  a.c = a.c + b.c * k; a.v = a.v + b.v * k;
}

struct Circuit {
  Built &b;
  size_t sbox_cols = 0, lin_cols = 0, hash_rel = 0;
  u64 col(F a, F c) { b.cols.push_back({a, c, a * c}); return b.cols.size() - 1; }
  void rel(std::vector<AffineTerm> t, F target) {
    // Merge repeated (row, column) terms and drop zero coefficients: one term per cell.
    std::vector<AffineTerm> m;
    for (auto x : t) {
      bool found = false;
      for (auto &y : m) if (y.row == x.row && y.column == x.column) { y.coefficient = y.coefficient + x.coefficient; found = true; break; }
      if (!found) m.push_back(x);
    }
    std::vector<AffineTerm> nz;
    for (auto x : m) if (x.coefficient.v != 0) nz.push_back(x);
    check(!nz.empty() && nz.size() <= 256, "hash relation shape");
    b.rel.push_back({std::move(nz), target}); hash_rel++;
  }
  void link(u64 c, const Lin &L) {  // row0(c) - L = L.c
    std::vector<AffineTerm> t = {{0, c, F{1}}};
    for (auto x : L.t) t.push_back({x.row, x.column, F{0} - x.coefficient});
    rel(std::move(t), L.c);
  }
  void eq(u64 c1, unsigned r1, u64 c2, unsigned r2) { rel({{r1, c1, F{1}}, {r2, c2, F{0} - F{1}}}, F{0}); }
  Lin sbox(const Lin &y) {
    const F v = y.v, v2 = v * v, v3 = v2 * v, v4 = v2 * v2;
    u64 c1 = col(v, v); link(c1, y); eq(c1, 1, c1, 0);        // (y, y, y^2)
    u64 c2 = col(v2, v); eq(c2, 0, c1, 2); eq(c2, 1, c1, 0);  // (y^2, y, y^3)
    u64 c3 = col(v2, v2); eq(c3, 0, c1, 2); eq(c3, 1, c1, 2); // (y^2, y^2, y^4)
    u64 c4 = col(v4, v3); eq(c4, 0, c3, 2); eq(c4, 1, c2, 2); // (y^4, y^3, y^7)
    sbox_cols += 4; return cell(2, c4, v4 * v3);
  }
  Lin materialise(const Lin &L) { u64 c = col(L.v, F{0}); link(c, L); lin_cols++; return cell(0, c, L.v); }
  void perm(Lin s[W]) {
    const auto &p = params();
    for (int r = 0; r < NROUND; r++) {
      const bool full = full_round(r);
      for (int i = 0; i < W; i++) { s[i].c = s[i].c + p.rc[r][i]; s[i].v = s[i].v + p.rc[r][i]; }
      for (int i = 0; i < (full ? W : 1); i++) s[i] = sbox(s[i]);
      Lin t[W];
      for (int i = 0; i < W; i++) for (int j = 0; j < W; j++) add_scaled(t[i], s[j], p.mds[i][j]);
      if (!full) for (int i = 1; i < W; i++) t[i] = materialise(t[i]);
      for (int i = 0; i < W; i++) s[i] = std::move(t[i]);
    }
  }
  int perms = 0;
  std::array<Lin, 4> commit(std::vector<Lin> words, const std::array<F, 4> &cap) {
    Lin s[W];
    for (int i = 0; i < 4; i++) s[RATE + i] = konst(cap[i]);
    words.push_back(konst(F{1}));
    while (words.size() % RATE) words.push_back(konst(F{0}));
    for (size_t blk = 0; blk < words.size(); blk += RATE) {
      for (int i = 0; i < RATE; i++) add_scaled(s[i], words[blk + i], F{1});
      perm(s); perms++;
    }
    return {s[0], s[1], s[2], s[3]};
  }
  void pin(const Lin &L, F target) { rel(L.t, target - L.c); }
};

struct WinStatement {
  int D, F, C, N, k; i64 request, layer, policy;
  std::vector<u8> raw, model, weights, cin_raw, cout_raw;
  std::array<blk::F, 4> cin, cout;
  std::vector<std::vector<i64>> inputs, preconv, outputs;
};
struct WReader {
  std::vector<u8> raw; size_t pos = 0;
  explicit WReader(const char *path) : raw(read_bytes(path)) {}
  std::vector<u8> bytes(size_t n) { check(n <= raw.size() - pos, "short input"); std::vector<u8> v(raw.begin() + pos, raw.begin() + pos + n); pos += n; return v; }
  i64 word() { auto v = bytes(8); i64 s; u64 x = le64(v.data()); std::memcpy(&s, &x, 8); return s; }
  u64 uword() { auto v = bytes(8); return le64(v.data()); }
  std::vector<i64> words(size_t n) { std::vector<i64> v(n); for (auto &x : v) x = word(); return v; }
  void end() { check(pos == raw.size(), "trailing input"); }
};
static std::array<blk::F, 4> read_commitment(const char *path, std::vector<u8> &raw) {
  WReader r(path); std::array<blk::F, 4> c;
  for (auto &x : c) { u64 v = r.uword(); check(v < P, "commitment word not canonical"); x = blk::F{v}; }
  r.end(); raw = r.raw; return c;
}
static std::array<blk::F, 4> ctx_cap(i64 Fb, i64 D, i64 C, i64 N, i64 req, i64 layer, i64 policy, i64 boundary,
                                    const std::vector<u8> &model, const std::vector<u8> &weights) {
  std::string d = "fp-hidden-root-ctx-v1"; std::vector<u8> m(d.begin(), d.end());
  for (i64 x : {Fb, D, C, N, req, layer, policy, boundary}) putword(m, x);
  m.insert(m.end(), model.begin(), model.end()); m.insert(m.end(), weights.begin(), weights.end());
  auto h = sha256(m); std::array<blk::F, 4> c;
  for (int i = 0; i < 4; i++) c[i] = fu(le64(h.data() + 8 * i));
  return c;
}
static WinStatement read_statement(const char *path, const char *cin, const char *cout) {
  WReader r(path); check(r.bytes(8) == std::vector<u8>({'F', 'P', 'H', 'R', '0', '0', '0', '1'}), "statement tag");
  auto h = r.words(8);
  check(h[0] >= 1 && h[0] <= 32 && h[1] == 12 && h[2] >= 1 && h[2] <= 16 && h[3] >= 1 && h[3] <= 64 && h[4] >= 0 && h[4] < h[3] &&
        h[5] >= 0 && h[5] < (1LL << 30) && h[6] >= 0 && h[6] < 64 && h[7] == 1, "supported statement domain");
  WinStatement s; s.D = h[0]; s.F = h[1]; s.C = h[2]; s.N = h[3]; s.k = h[4]; s.request = h[5]; s.layer = h[6]; s.policy = h[7];
  s.model = r.bytes(32); s.weights = r.bytes(32);
  for (int t = 0; t < s.C; t++) s.inputs.push_back(r.words(2 + 3 * s.D));
  for (int t = 0; t < s.C; t++) s.preconv.push_back(r.words(3 * s.D));
  for (auto &v : s.preconv) for (auto x : v) check(x >= -(1LL << 20) && x < (1LL << 20), "preconv input range");
  for (int t = 0; t < s.C; t++) s.outputs.push_back(r.words(s.D));
  r.end(); s.raw = r.raw;
  s.cin = read_commitment(cin, s.cin_raw); s.cout = read_commitment(cout, s.cout_raw);
  return s;
}
struct WinPart { Fixture z; std::vector<i64> Hin; i64 salt_in = 0, salt_out = 0; std::vector<std::vector<i64>> x; std::array<blk::F, 4> cap_in, cap_out; };
static WinPart template_part(const WinStatement &s) {
  WinPart p; p.z.T = s.C; p.z.D = s.D; p.z.F = s.F; p.z.S0 = std::vector<i64>(s.D * s.D);
  p.Hin = std::vector<i64>(9 * s.D);
  const i64 one = 1LL << s.F;
  for (int t = 0; t < s.C; t++) {
    const auto &v = s.inputs[t];
    check(v[0] >= 0 && v[0] <= one && v[1] >= 0 && v[1] <= one, "gate input range");
    for (int j = 0; j < s.D; j++) check(v[2 + j] >= -one && v[2 + j] <= one && v[2 + s.D + j] > -VBOUND && v[2 + s.D + j] < VBOUND && v[2 + 2 * s.D + j] >= -one && v[2 + 2 * s.D + j] <= one, "token input range");
    for (auto o : s.outputs[t]) check(o > -VBOUND && o < VBOUND, "output range");
    p.z.a.push_back(v[0]); p.z.beta.push_back(v[1]);
    p.z.k.emplace_back(v.begin() + 2, v.begin() + 2 + s.D); p.z.v.emplace_back(v.begin() + 2 + s.D, v.begin() + 2 + 2 * s.D); p.z.q.emplace_back(v.begin() + 2 + 2 * s.D, v.end());
    p.z.M.emplace_back(s.D, 0); p.z.delta.emplace_back(s.D, 0); p.z.S.emplace_back(s.D * s.D, 0); p.z.o.push_back(s.outputs[t]); p.x.push_back(s.preconv[t]);
  }
  p.cap_in = ctx_cap(s.F, s.D, s.C, s.N, s.request, s.layer, s.policy, s.k, s.model, s.weights);
  p.cap_out = ctx_cap(s.F, s.D, s.C, s.N, s.request, s.layer, s.policy, s.k + 1, s.model, s.weights);
  return p;
}
static WinPart read_part(const WinStatement &s, const std::string &dir) {
  WinPart p; p.z = load((dir + "/w.fx").c_str());
  check(p.z.D == s.D && p.z.T == s.C && p.z.F >= 1 && p.z.F <= 16, "witness layout");
  p.z.F = s.F;  // circuit arithmetic is always the verifier's F; reference values may come from F13
  WReader r((dir + "/w.packet").c_str());
  p.Hin = r.words(9 * s.D); p.salt_in = r.word(); p.salt_out = r.word();
  for (int t = 0; t < s.C; t++) p.x.push_back(r.words(3 * s.D));
  for (auto &c : p.cap_in) c = fu(r.uword());
  for (auto &c : p.cap_out) c = fu(r.uword());
  r.end(); return p;
}
struct WinBuilt { Built out; std::array<blk::F, 4> in_hash, out_hash; size_t hash_cols = 0, hash_rel = 0, perms = 0, recurrence_cols = 0, recurrence_rel = 0; };
static WinBuilt window(const WinStatement &s, const WinPart &p) {
  WinBuilt w; Built &out = w.out; const int D = s.D, DD = D * D;
  Built b = build(p.z);
  const u64 nonrange = b.core_cols - b.rcv.size();
  out.cols.assign(b.cols.begin(), b.cols.begin() + nonrange); out.rcv = b.rcv;
  const auto &last = b.state_col.back();
  for (auto r : b.rel) {
    bool initial = false, final = false;
    if (r.terms.size() == 1 && r.terms[0].row == 0 && r.terms[0].coefficient == blk::F{1}) {
      const u64 k = r.terms[0].column; initial = k < u64(2 * DD) && k % 2 == 0;
      final = std::find(last.begin(), last.end(), k) != last.end();
    }
    if (initial || final) continue;  // boundary states are never public: bound by the commitments below
    for (auto &t : r.terms) if (t.column >= b.rc_base) t.column = RTAG + t.column - b.rc_base;
    out.rel.push_back(std::move(r));
  }
  w.recurrence_cols = out.cols.size() + out.rcv.size(); w.recurrence_rel = out.rel.size();
  auto col = [&](i64 x) { out.cols.push_back({fi(x), blk::F{0}, blk::F{0}}); return u64(out.cols.size() - 1); };
  auto pin = [&](u64 c, i64 v) { out.rel.push_back({{{0, c, blk::F{1}}}, fi(v)}); };
  auto eq = [&](u64 a, u64 c) { out.rel.push_back({{{0, a, blk::F{1}}, {0, c, fi(-1)}}, blk::F{0}}); };
  // Incoming state: first-token decay-gate cells (row 0) carry S_in. Range-check them (RNG cells).
  std::vector<Lin> win, wout;
  for (int c = 0; c < DD; c++) {
    const u64 g = 2 * c; const i64 v = p.z.S0[c];
    check(v > -BOUND && v < BOUND, "incoming state outside its contract");
    const u64 idx = out.rcv.size(); out.rcv.push_back(v);
    out.rel.push_back({{{0, g, blk::F{1}}, {0, RTAG + idx, fi(-1)}}, blk::F{0}});
    win.push_back(cell(0, g, fi(v)));
  }
  std::vector<u64> hin, hout, xs;
  for (auto x : p.Hin) { hin.push_back(col(x)); win.push_back(cell(0, hin.back(), fi(x))); }
  const u64 sin = col(p.salt_in); win.push_back(cell(0, sin, fi(p.salt_in)));
  for (int t = 0; t < s.C; t++) for (int j = 0; j < 3 * D; j++) { xs.push_back(col(p.x[t][j])); pin(xs.back(), s.preconv[t][j]); }
  // Outgoing state: last token's output-gate cells (row 0) carry S_out.
  for (int c = 0; c < DD; c++) wout.push_back(cell(0, last[c], fi(p.z.S.back()[c])));
  for (int tap = 0; tap < 3; tap++) for (int j = 0; j < 3 * D; j++) {
    const int at = s.C + tap;
    const i64 v = at < 3 ? p.Hin[at * 3 * D + j] : p.x[at - 3][j];
    hout.push_back(col(v)); eq(hout.back(), at < 3 ? hin[at * 3 * D + j] : xs[(at - 3) * 3 * D + j]);
    wout.push_back(cell(0, hout.back(), fi(v)));
  }
  const u64 sout = col(p.salt_out); wout.push_back(cell(0, sout, fi(p.salt_out)));
  // In-field commitments. Capacity constants: the verifier's context (template) or the prover's (witness).
  Circuit cc{out};
  auto ci = cc.commit(win, p.cap_in);
  for (int i = 0; i < 4; i++) { cc.pin(ci[i], s.cin[i]); w.in_hash[i] = ci[i].v; }
  auto co = cc.commit(wout, p.cap_out);
  for (int i = 0; i < 4; i++) { cc.pin(co[i], s.cout[i]); w.out_hash[i] = co[i].v; }
  w.hash_cols = cc.sbox_cols + cc.lin_cols; w.hash_rel = cc.hash_rel; w.perms = cc.perms;
  // Range region, as qwen_handoff joint().
  out.core_cols = out.cols.size() + out.rcv.size(); out.rc_rows = pow2_at_least((out.rcv.size() + RCOLS - 1) / RCOLS);
  const u64 size = out.rc_rows * RCOLS; out.rc_base = (out.cols.size() + size - 1) / size * size;
  out.cols.resize(out.rc_base + size, {blk::F{0}, blk::F{0}, blk::F{0}});
  for (u64 k = 0; k < out.rcv.size(); k++) { out.cols[out.rc_base + k] = {fi(out.rcv[k]), blk::F{0}, blk::F{0}}; out.rc.push_back(out.rc_base + k); }
  for (auto &r : out.rel) for (auto &t : r.terms) if (t.column >= RTAG) t.column = t.column - RTAG + out.rc_base;
  return w;
}
static std::string hex4(const std::array<blk::F, 4> &c) {
  std::string s; char buf[20];
  for (int i = 0; i < 4; i++) { std::snprintf(buf, sizeof buf, "%016llx", (unsigned long long)c[i].v); s += buf; }
  return s;
}
static double now_s() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
int main(int argc, char **argv) {
  check(argc == 7, "usage: window.bin prove|hostile|verify|count statement c_in c_out witness-dir-or-dash proof");
  const std::string mode = argv[1];
  const double t0 = now_s();
  WinStatement s = read_statement(argv[2], argv[3], argv[4]);
  WinBuilt canonical = window(s, template_part(s));
  std::vector<u8> hdr = {'F', 'P', 'H', 'R'};
  hdr.insert(hdr.end(), s.raw.begin(), s.raw.end()); hdr.insert(hdr.end(), s.cin_raw.begin(), s.cin_raw.end()); hdr.insert(hdr.end(), s.cout_raw.begin(), s.cout_raw.end());
  Sized sz = size_chunk(canonical.out, hdr);
  if (mode == "verify") {
    auto pf = read_bytes(argv[6]); const char *why = nullptr; bool ok = chunk_verify(sz.cr, pf.data(), pf.size(), &why);
    std::printf("{\"accept\":%s,\"check\":\"proof-verifier\",\"why\":\"%s\",\"verify_s\":%.6f}\n", ok ? "true" : "false", why ? why : "", now_s() - t0);
    return ok ? 0 : 1;
  }
  size_t terms = 0, maxterms = 0;
  for (auto &r : canonical.out.rel) { terms += r.terms.size(); maxterms = std::max(maxterms, r.terms.size()); }
  auto counts = [&](std::FILE *f) {
    std::fprintf(f, "\"core_columns\":%llu,\"aligned_columns\":%zu,\"relations\":%zu,\"relation_terms\":%zu,\"max_terms\":%zu,\"range_cells\":%zu,\"hash_columns\":%zu,\"hash_relations\":%zu,\"permutations\":%zu,\"recurrence_columns\":%zu,\"recurrence_relations\":%zu,\"log_len\":%u",
                 (unsigned long long)canonical.out.core_cols, canonical.out.cols.size(), canonical.out.rel.size(), terms, maxterms, canonical.out.rcv.size(),
                 canonical.hash_cols, canonical.hash_rel, canonical.perms, canonical.recurrence_cols, canonical.recurrence_rel, sz.L);
  };
  if (mode == "count") { std::printf("{"); counts(stdout); std::printf("}\n"); return 0; }
  check(mode == "prove" || mode == "hostile", "mode");
  WinBuilt witness = window(s, read_part(s, argv[5]));
  check(witness.out.cols.size() == canonical.out.cols.size() && witness.out.rc_base == canonical.out.rc_base && witness.out.rc_rows == canonical.out.rc_rows &&
        witness.out.rel.size() == canonical.out.rel.size(), "fixed layout");
  Table t = table_of(witness.out, sz.L); check(products_hold_all(t), "all products hold");
  const size_t bad = violated(canonical.out.rel, t);
  if (mode == "prove") check(bad == 0, "honest relations");
  const double t1 = now_s();
  auto pf = prove(sz.cr, witness.out, t, mode == "hostile"); write_bytes(argv[6], pf.bytes());
  const double t2 = now_s();
  bool ok = chunk_verify(sz.cr, pf.data(), pf.size());
  std::printf("{\"accept\":%s,\"check\":\"proof-verifier\",\"violated_relations\":%zu,\"products_hold\":true,\"proof_bytes\":%zu,\"prove_s\":%.6f,\"setup_s\":%.6f,\"in_hash\":\"%s\",\"out_hash\":\"%s\",",
              ok ? "true" : "false", bad, pf.size(), t2 - t1, t1 - t0, hex4(witness.in_hash).c_str(), hex4(witness.out_hash).c_str());
  counts(stdout); std::printf("}\n");
  return 0;
}
