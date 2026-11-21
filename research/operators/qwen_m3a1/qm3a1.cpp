// SPDX-License-Identifier: Apache-2.0
// Research-only (issue #229, M3a-1 weight side). Not a serving protocol.
//
// One Gated DeltaNet head's weights in a committed table (IndexCpu, blocks/iop/index_cpu.h), the
// 1,666 weights that the head's trace reads as cells of the research product oracle
// (research/operators/qwen_deltanet/product.h) with their DESIGN 6.2 class, and the tie between
// the two: one point psi drawn on the trace chain after the trace oracle's root and the table's
// name, one linear claim on the trace cells (sum_i eq(psi, i) w_i = v) and one LIN claim on row 0
// of the table (blocks/iop/lin.h; row 0 at psi = v), checked under TableTest::ONE_TIME.
// No existing file is changed; LIN's chains follow blocks/iop/tests/lin_world.h.
//
// Usage: qm3a1.bin <M.i32> honest <seed>
//        qm3a1.bin <M.i32> case <name>       one registered hostile or completeness case (seed 1)
// Prints one JSON line per proof.
#define BLK_PLANS_BY_HAND_FOR_A_TEST
#define BLK_TESTED_TABLE_FOR_A_TEST
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <memory>
#include <string>
#include <sys/resource.h>
#include <vector>

#include "iop/tests/lin_world.h"
#include "toy/toy_coins.h"
#include "../qwen_deltanet/product.h"

using namespace blk;

static void need(bool ok, const char *s) { if (!ok) { std::fprintf(stderr, "FAIL: %s\n", s); std::exit(1); } }
static F fi(i64 x) { return x >= 0 ? F{u64(x)} : F{P - u64(-x)}; }
static double secs(std::chrono::steady_clock::time_point a) { return std::chrono::duration<double>(std::chrono::steady_clock::now() - a).count(); }
static long rss_kb() { rusage u; getrusage(RUSAGE_SELF, &u); return u.ru_maxrss; }

// ---- public layout ----
constexpr u64 ROWS = 595, COLS = 8192;
constexpr unsigned KCOL = 13;  // column bits of the matrix
constexpr u64 NCELLS = 1666, NTAPS = 1536, NGAIN = 128, CA_AT = 1664, DT_AT = 1665;
constexpr u64 TIE_LABEL = 0x46504d31ULL;  // "FPM1": this lane's own transcript domain
static unsigned class_bits(u64 i) { return i == DT_AT ? 18 : 13; }
static i64 class_offset(u64 i) { return i == DT_AT ? (i64(1) << 17) : 4096; }

// Columns of the product oracle: cell i at column i, (a, b, c) = (w_i, 0, 0); then the bits of
// every cell, each column (b, b, b), so b * b = b once a = b and c = a hold.
struct Layout { std::vector<u64> bit_first; u64 columns = 0; unsigned log_len = 0; };
static Layout layout() {
  Layout L; u64 c = NCELLS;
  for (u64 i = 0; i < NCELLS; i++) L.bit_first.push_back(c), c += class_bits(i);
  L.columns = c; while ((u64(1) << L.log_len) < c) L.log_len++;
  return L;
}
static std::vector<WideRelation> relations(const Layout &L) {
  std::vector<WideRelation> r;
  for (u64 i = 0; i < NCELLS; i++) {
    WideRelation a;  // w_i - sum_k 2^k bit_k = -offset
    a.terms.push_back({0, i, F{1}});
    for (unsigned k = 0; k < class_bits(i); k++) a.terms.push_back({0, L.bit_first[i] + k, fi(-(i64(1) << k))});
    a.target = fi(-class_offset(i));
    r.push_back(a);
  }
  for (u64 i = 0; i < NCELLS; i++)
    for (unsigned k = 0; k < class_bits(i); k++) {
      const u64 c = L.bit_first[i] + k;
      r.push_back({{{0, c, F{1}}, {1, c, fi(-1)}}, F{0}});
      r.push_back({{{0, c, F{1}}, {2, c, fi(-1)}}, F{0}});
    }
  return r;
}
// Honest decomposition of (w + offset) mod 2^bits: a value out of class gets bits of another
// value, so its class relation is false.
static Table trace_table(const Layout &L, const std::vector<i64> &cells) {
  Table t(1, 3, u64(1) << L.log_len);
  for (u64 i = 0; i < NCELLS; i++) {
    t.set(0, i, E::from(fi(cells[i])));
    const unsigned nb = class_bits(i);
    const u64 s = u64(cells[i] + class_offset(i)) & ((u64(1) << nb) - 1);
    for (unsigned k = 0; k < nb; k++) { const E b = E::from(F{(s >> k) & 1}); for (int r = 0; r < 3; r++) t.set(r, L.bit_first[i] + k, b); }
  }
  return t;
}

// ---- the trace chain ----
struct TraceRun { ToyRun product; std::vector<WideRelation> relations; IndexName table; explicit TraceRun(const Setting &s) : product(s) {} };
struct TraceBound { ToyPublic product; Public<std::vector<WideRelation>> relations; Public<IndexName> table; };
struct TieOut { std::vector<E> psi; E v = E::zero(); };
static TraceBound trace_bind(Binder &b, const TraceRun &run) {
  TraceBound x; x.product = toy_bind_run(b, run.product);
  x.relations = b.statement("weight cell class relations v1", run.relations);
  x.table = b.statement("weight table", run.table);
  return x;
}
// As coordinate_size_plan (research/operators/public_binding/product.h), with the relations, one
// tie row, the tie point (13 draws) and the tie value (1 scalar) before the proximity test.
static TraceRun trace_size(const Setting &set, unsigned log_len, std::vector<WideRelation> rel, const IndexName &table) {
  TraceRun run(set);
  const unsigned log_n = log_len + 1, mask_log_n = log_len + 1;
  const std::vector<StageChoice> further = {{1, 1, log_len, log_len}, {0, 0, log_len, log_len}};
  const u64 rows = toy_rows_batched(set) + rel.size() + 1;
  run.product.shape.text = toy_text("research-qwen-m3a1-weight-cells-v1", set, {{"relations", rel.size()}, {"log-length", log_len}, {"log-n", log_n}, {"mask-log-n", mask_log_n}, {"cells", NCELLS}}, further);
  Plan plan(set);
  GroupSize g; g.name = "a, b, c"; g.k = 2, g.h = 0;
  g.main.name = "rows", g.main.log_n = log_n, g.main.ell = u64(1) << log_len;
  const u64 masks = 1 + 2 * u64(log_len) + 2 + 2;
  g.mask.name = "mask row", g.mask.log_n = mask_log_n, g.mask.over_E = true;
  g.mask.ell = pow2_at_least(std::max<u64>(masks + set.samples, 2 * g.k + 1 - g.h));
  u64 t = 0;
  for (int turn = 0; turn < 16; turn++) {
    g.main.r = g.mask.r = tail_for(set, t);
    GroupLoad load; load.cube_bits = stage_cube_bits(g); load.batched_rows = rows;
    g = size_group(set, plan.scope(), g, load);
    if (analysis(set, g).bad()) { plan.refuse("no slack"); run.product.plan = plan.finish(); return run; }
    const u64 more = plan_positions(plan, analysis(set, g).at.agree, Bound(Real::two_to(-(long)set.target - 30)));
    if (more <= t) break;
    t = more;
  }
  const std::vector<Stage> stages = solve_stages(plan, g, t, further);
  if (plan.refused()) { run.product.plan = plan.finish(); return run; }
  run.product.stages = iopp_stages(stages, run.product.shape.codes);
  if (const char *fault = iopp_sized_fault(run.product.shape.codes, run.product.stages, stages)) { plan.refuse(fault); run.product.plan = plan.finish(); return run; }
  plan_chain_start(plan, "trace", true);
  toy_plan_preamble(plan, run.product.shape, run.product.stages, {g});
  plan_join(plan, "weight tie point", KCOL);
  plan_scalars(plan, "weight tie value", "weight tie", 1);
  plan_iopp(plan, g.name, stages, tree_sizes(run.product.shape.codes, toy_first_message(OracleNotice{run.product.shape.oracle(), 0}, run.product.stages)), rows, 0, true);
  run.product.plan = plan.finish();
  run.relations = std::move(rel); run.table = table;
  return run;
}
static Row tie_row(OracleId o, const std::vector<E> &psi, const E &v) {
  Row r; r.name = "weight cells at the tie point";
  for (u64 i = 0; i < NCELLS; i++) r.add_unit(o, Part::MAIN, 0 + 4 * i, eq_index(i, psi.data(), KCOL));
  r.target = v; return r;
}
static E row_local(const Row &r, const Table &t) {  // units only (wide rows and the tie row)
  E x = E::zero(); for (const Unit &u : r.units) x += u.coeff * t.at(u.index % 4, u.index / 4); return x;
}
enum class VFrom { TRACE, TABLE };
static Writer trace_prove(const TraceRun &run, const Table &tab, const std::vector<F> &row0, VFrom vfrom, bool local, u64 seed, TieOut &out) {
  EngineCpu engine; ToyCoins coins(1000 + seed); Writer proof;
  Binder b(TIE_LABEL, run.product.plan); const TraceBound in = trace_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins); FoldMask mask;
  const GroupId g = toy_prove_preamble(pr, in.product, tab, mask); const OracleId o = pr.st.group(g).members[0];
  for (const auto &a : ch.get(in.relations)) { Row row = wide_row(o, a); if (local) row.target = row_local(row, tab); pr.st.add_row(g, std::move(row)); }
  std::vector<E> psi(KCOL);
  { AlgebraicDraw from = ch.close_algebraic(R_JOIN); for (E &z : psi) z = from.draw(); }
  E v = E::zero();
  if (vfrom == VFrom::TRACE) for (u64 i = 0; i < NCELLS; i++) v += eq_index(i, psi.data(), KCOL) * tab.at(0, i);
  else v = mle_eval(row0.data(), row0.size(), psi.data(), KCOL);
  ch.send(v);
  Row tie = tie_row(o, psi, v); if (local) tie.target = row_local(tie, tab); pr.st.add_row(g, std::move(tie));
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask)); ch.finish(); pr.st.require_all_tested();
  out.psi = psi, out.v = v;
  return proof;
}
static bool trace_decide(VerifierRounds &ch, const TraceBound &in, TieOut &out, Notes *notes) {
  VerifierContext vf(in.product.codes, ch); vf.notes = notes;
  GroupId g = 0; FoldMask mask;
  if (!toy_verify_preamble(vf, in.product, g, mask)) return false;
  const OracleId o = vf.st.group(g).members[0];
  wide_rows(vf.st, g, ch.get(in.relations));
  std::vector<E> psi(KCOL);
  { AlgebraicDraw from = ch.close_algebraic(R_JOIN); for (E &z : psi) z = from.draw(); }
  E v; if (!ch.recv(v)) return false;
  vf.st.add_row(g, tie_row(o, psi, v));
  if (!iopp_verify(vf, g, in.product.stages, in.product.choice, std::move(mask))) return false;
  vf.st.require_all_tested();
  out.psi = psi, out.v = v; return true;
}

// ---- LIN on the table (chains as blocks/iop/tests/lin_world.h, own first-chain statement) ----
static const LinCase LCASE = {"qwen m3a1 head table", 7, 6, ROWS, 0, 1, 24, 1, 2, 4096, 4096, 4096, true, 1, 0, 12, false};
struct FirstBound { LinPublic lin; Public<OracleNotice> input; Public<LinBindingShape> binding; Public<std::vector<E>> psi; Public<E> v; };
static FirstBound bind_first(Binder &b, const LinWorld &w, const IndexName &table, const std::vector<E> &psi, const E &v) {
  FirstBound x; b.configuration(w.configuration);
  lin_bind_parameters(b, w.codes, w.S, x.lin);
  x.input = b.parameter("a request's mask message", w.input), x.binding = b.parameter("the binding tree", w.binding);
  lin_bind_table(b, table, x.lin);
  x.psi = b.statement("weight tie point", psi), x.v = b.statement("weight tie value", v);
  return x;
}
static Tensor row0_weight(const LinShape &S) { Tensor t; t.scalar = E::one(); t.insert_choice(0, S.k_row(), 0); return t; }
static LinView lin_prove(const LinWorld &w, IndexCpu &index, const std::vector<F> &row0, const TieOut &tie, u64 seed) {
  const LinShape &S = w.S; TestCoins coins(5000 + seed); EngineCpu engine; LinView view;
  const IndexName table{index.commitment(), index.record()};
  LinBinding binding(w.binding, w.configuration, coins);
  std::unique_ptr<LinBegun> begun; need(lin_begin(index, S, begun), "LIN: the table's tails cover a batch");
  Writer first_w, second_w, shared_w, path_w;
  Binder b(1, w.first); const FirstBound x = bind_first(b, w, table, tie.psi, tie.v);
  ProverRounds ch(b, toy_random_bytes(seed + 100), first_w);
  ProverContext P(x.lin.codes, ch, engine, coins);
  std::vector<OracleDraft> drafts; drafts.push_back(lin_draft(P, ch.get(x.input).shape, false, ch.get(x.input).leaf_class, {}));
  const OracleId input = send_prove(P, std::move(drafts))[0];
  LinClaim claim; claim.g.push_back(row0_weight(S)); claim.psi = ch.get(x.psi);
  std::vector<E> wc(COLS); for (u64 j = 0; j < COLS; j++) wc[j] = E::from(row0[j]);
  claim.target = ch.get(x.v);
  claim.add_mask(P.st.masks(input).take(), E::zero());  // joins the request's mask message to its group; no weight
  ch.send(claim.target);
  LinFirst lf = lin_first_prove(P, x.lin, std::move(claim), wc);
  Sealed seal; need(ch.seal(R_SEAL, seal), "seal"); ch.finish();
  binding.put(0, seal.digest());
  Binder sb(LIN_LABEL_SHARED, w.shared); sb.configuration(w.configuration);
  const LinPublic sx = lin_bind_shared(sb, w.codes, w.S, table, binding.root());
  ProverRounds sch(sb, Digest{}, shared_w); ProverContext SP(sx.codes, sch, engine, coins);
  LinShared shared; lin_shared_prove(SP, sx, w.test, index, std::move(begun), shared);
  lin_shared_tests_prove(SP, sx, shared);
  Sealed shared_seal; need(sch.seal(R_SEAL, shared_seal), "shared seal"); sch.finish(); SP.st.require_all_tested();
  Binder b2(LIN_LABEL_SECOND, w.second); b2.configuration(w.configuration); lin_bind_second(b2, seal, shared_seal);
  ProverRounds ch2(b2, toy_random_bytes(seed + 200), second_w);
  ProverContext P2 = lin_go_on(std::move(P), ch2);
  const LinSecond second = lin_second_prove(P2, x.lin, lf, SP, shared);
  lin_second_tests_prove(P2, x.lin, lf, second); ch2.finish(); P2.st.require_all_tested();
  binding.write_path(path_w, 0); lin_release(SP, shared);
  view.target = tie.v; view.first = first_w.bytes(), view.path = path_w.bytes(), view.shared = shared_w.bytes(), view.second = second_w.bytes();
  return view;
}
// The verifier's LIN side: psi and v as its own trace verification produced them.
static bool lin_check(const LinWorld &w, const IndexKey &key, const TieOut &tie, const LinView &view, const char *&reason) {
  const IndexName table{key.commitment(), key.rec};
  const TableRead read(key);  // ONE_TIME: the committer's own test; any reader
  Reader fb(view.first.data(), view.first.size());
  Binder b(1, w.first); const FirstBound x = bind_first(b, w, table, tie.psi, tie.v);
  VerifierSession session; VerifierRounds ch(b, fb, session); VerifierContext V(x.lin.codes, ch);
  std::vector<OracleId> ids;
  if (!send_verify(V, std::vector<OracleNotice>{ch.get(x.input)}, ids)) return reason = "LIN first part: the input message", false;
  LinClaim claim; claim.g.push_back(row0_weight(w.S)); claim.psi = ch.get(x.psi);
  if (!ch.recv(claim.target)) return reason = "LIN first part: the target", false;
  if (claim.target != ch.get(x.v)) return reason = "LIN first part: the target is not the trace chain's tie value", false;
  claim.add_mask(V.st.masks(ids[0]).take(), E::zero());
  LinFirst first;
  if (!lin_first_verify(V, x.lin, std::move(claim), first)) return reason = "LIN first part", false;
  Sealed seal; if (!ch.seal(R_SEAL, seal) || !ch.finish()) return reason = "LIN first part: its end", false;
  Reader path(view.path.data(), view.path.size()); LinBindingRoot root;
  if (!lin_binding_root(path, ch.get(x.binding), ch.configuration(), seal.digest(), root) || !path.at_end()) return reason = "LIN path", false;
  Reader sbytes(view.shared.data(), view.shared.size());
  Binder sb(LIN_LABEL_SHARED, w.shared); sb.configuration(w.configuration);
  const LinPublic sx = lin_bind_shared(sb, w.codes, w.S, table, root);
  VerifierRounds sch(sb, sbytes, session); VerifierContext SV(sx.codes, sch); LinShared shared;
  if (!lin_shared_verify(SV, sx, w.test, read, shared)) return reason = "LIN shared part", false;
  if (!lin_shared_tests_verify(SV, sx, shared)) return reason = "LIN shared part: a proximity test", false;
  Sealed shared_seal; if (!sch.seal(R_SEAL, shared_seal) || !sch.finish()) return reason = "LIN shared part: its end", false;
  SV.st.require_all_tested();
  Reader b2bytes(view.second.data(), view.second.size());
  Binder b2(LIN_LABEL_SECOND, w.second); b2.configuration(w.configuration); lin_bind_second(b2, seal, shared_seal);
  VerifierRounds ch2(b2, b2bytes, session); VerifierContext V2 = lin_go_on(std::move(V), ch2); LinSecond second;
  if (!lin_second_verify(V2, x.lin, first, SV, shared, second)) return reason = "LIN second part", false;
  if (!lin_second_tests_verify(V2, x.lin, first, second)) return reason = "LIN second part: a proximity test", false;
  if (!ch2.finish()) return reason = "LIN second part: its end", false;
  V2.st.require_all_tested();
  if (!session.accepted()) return reason = "LIN: the session is not accepted", false;
  reason = "accepted"; return true;
}

// ---- one statement, end to end ----
struct World {
  Layout L; std::vector<WideRelation> rel; LinWorld lw; Setting set;
  World() : lw(lin_world(LCASE, TableTest::ONE_TIME)) {
    L = layout(); rel = relations(L);
    set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES; set.target = 10; set.set_work(ErrorKind::QUERY, Scope::REQUEST, 6);
    need(!lin_fault(lw.codes, lw.S), "LIN shape");
  }
};
static Table table_rows(const LinShape &S, const std::vector<i64> &M) {
  LinMatrix lm{ROWS, COLS, {}}; lm.a.resize(ROWS * COLS);
  for (u64 i = 0; i < ROWS * COLS; i++) lm.a[i] = fi(M[i]);
  return lin_table_rows(S, lm);
}
struct Committed { std::unique_ptr<IndexCpu> index; IndexKey key; };
static Committed commit(const World &W, const std::vector<i64> &M, u64 coin) {
  Committed c; TestCoins coins(coin);
  c.index.reset(new IndexCpu(W.lw.S.fold.index, table_rows(W.lw.S, M), coins));
  c.key = c.index->key();
  need(!index_key_fault(c.key), "an honest key is refused");
  return c;
}
static void emit(const char *mode, const std::string &name, bool trace_ok, const char *trace_why, bool lin_ok, const char *lin_why, const World &W,
                 size_t trace_bytes, size_t lin_bytes, double commit_s, double prove_s, double verify_s) {
  std::printf("{\"mode\":\"%s\",\"case\":\"%s\",\"accepted\":%s,\"trace_accepted\":%s,\"trace_why\":\"%s\",\"lin_accepted\":%s,\"lin_why\":\"%s\","
              "\"cells\":%llu,\"product_columns_used\":%llu,\"log_length\":%u,\"relations\":%zu,\"table_matrix\":[%llu,%llu],\"table_rows\":%llu,\"table_ell\":%zu,\"table_log_n\":%u,"
              "\"trace_proof_bytes\":%zu,\"lin_proof_bytes\":%zu,\"commit_s\":%.3f,\"prove_s\":%.3f,\"verify_s\":%.3f,\"peak_rss_kb\":%ld}\n",
              mode, name.c_str(), trace_ok && lin_ok ? "true" : "false", trace_ok ? "true" : "false", trace_why ? trace_why : "accepted", lin_ok ? "true" : "false", lin_why,
              (unsigned long long)NCELLS, (unsigned long long)W.L.columns, W.L.log_len, W.rel.size(), (unsigned long long)ROWS, (unsigned long long)COLS,
              (unsigned long long)W.lw.S.fold.index.rows(), W.lw.S.fold.index.code.ell, W.lw.S.fold.index.code.log_n, trace_bytes, lin_bytes, commit_s, prove_s, verify_s, rss_kb());
  std::fflush(stdout);
}
// prove under (cells, table M) and verify against `key` (default: the proving table's key).
static void run_case(const World &W, const char *mode, const std::string &name_of_case, const std::vector<i64> &cells, const std::vector<i64> &M, VFrom vfrom, bool local,
                     u64 seed, const std::vector<i64> *verify_M = nullptr, u64 verify_coin = 0) {
  auto t0 = std::chrono::steady_clock::now();
  Committed c = commit(W, M, 77 + seed);
  Committed other; if (verify_M) other = commit(W, *verify_M, verify_coin);
  const IndexKey &vkey = verify_M ? other.key : c.key;
  const double commit_s = secs(t0);
  std::vector<F> row0(COLS); for (u64 j = 0; j < COLS; j++) row0[j] = fi(M[j]);
  const Table tab = trace_table(W.L, cells);
  auto tp = std::chrono::steady_clock::now();
  const IndexName name{c.index->commitment(), c.index->record()};
  TraceRun run = trace_size(W.set, W.L.log_len, W.rel, name);
  need(run.product.plan->holds(), "trace plan holds");
  TieOut tie; Writer tp_bytes = trace_prove(run, tab, row0, vfrom, local, seed, tie);
  LinView view = lin_prove(W.lw, *c.index, row0, tie, seed);
  const double prove_s = secs(tp);
  // The verifier: its own trace run, bound to the key it holds.
  auto tv = std::chrono::steady_clock::now();
  const IndexName vname{vkey.commitment(), vkey.rec};
  TraceRun vrun = trace_size(W.set, W.L.log_len, W.rel, vname);
  TieOut vt; const char *twhy = nullptr;
  const bool tok = run_verifier(TIE_LABEL, vrun.product.plan, vrun, trace_bind, trace_decide, tp_bytes.data(), tp_bytes.size(), vt, &twhy);
  const char *lwhy = "not run: the trace chain was refused"; bool lok = false;
  if (tok) lok = lin_check(W.lw, vkey, vt, view, lwhy);
  const double verify_s = secs(tv);
  const size_t lin_bytes = view.first.size() + view.path.size() + view.shared.size() + view.second.size();
  emit(mode, name_of_case, tok, twhy, lok, lwhy, W, tp_bytes.size(), lin_bytes, commit_s, prove_s, verify_s);
}

int main(int argc, char **argv) {
  need(argc == 4, "usage: qm3a1.bin <M.i32> honest <seed> | case <name>");
  std::ifstream f(argv[1], std::ios::binary); need(bool(f), "open M.i32");
  std::vector<int32_t> raw(ROWS * COLS); f.read((char *)raw.data(), raw.size() * 4); need(f.gcount() == (std::streamsize)(raw.size() * 4), "M.i32 size");
  std::vector<i64> M(raw.begin(), raw.end());
  std::vector<i64> cells(M.begin(), M.begin() + NCELLS);
  for (u64 j = NCELLS; j < COLS; j++) need(M[j] == 0, "row 0 is zero past the cells");
  World W;
  const std::string mode = argv[2], arg = argv[3];
  if (mode == "honest") {
    const u64 seed = std::strtoull(arg.c_str(), nullptr, 10);
    need(seed >= 1, "seed >= 1");
    run_case(W, "honest", "honest", cells, M, VFrom::TRACE, false, seed);
    return 0;
  }
  need(mode == "case", "mode: honest | case");
  auto with_cell = [&](u64 i, i64 value, bool trace, bool table, std::vector<i64> &c2, std::vector<i64> &M2) {
    c2 = cells, M2 = M;
    if (trace) c2[i] = value;
    if (table) M2[i] = value;
  };
  std::vector<i64> c2, M2;
  if (arg == "H1-other-root-one-tap") {
    with_cell(0, cells[0] + 1, false, true, c2, M2);
    run_case(W, "hostile", arg, cells, M, VFrom::TRACE, false, 1, &M2, 991);
  } else if (arg == "H1b-other-root-same-weights") {
    run_case(W, "hostile", arg, cells, M, VFrom::TRACE, false, 1, &M, 992);
  } else if (arg == "H2a-tap-changed-v-from-trace") {
    with_cell(0, cells[0] + 1, true, false, c2, M2);
    run_case(W, "hostile", arg, c2, M, VFrom::TRACE, false, 1);
  } else if (arg == "H2b-tap-changed-v-from-table") {
    with_cell(0, cells[0] + 1, true, false, c2, M2);
    run_case(W, "hostile", arg, c2, M, VFrom::TABLE, true, 1);
  } else if (arg == "H3-gain-2^50-trace-and-table") {
    with_cell(NTAPS, i64(1) << 50, true, true, c2, M2);
    run_case(W, "hostile", arg, c2, M2, VFrom::TRACE, true, 1);
  } else if (arg == "H4-gain-in-class-not-the-tables") {
    with_cell(NTAPS, cells[NTAPS] + 1, true, false, c2, M2);
    run_case(W, "hostile", arg, c2, M, VFrom::TRACE, false, 1);
  } else if (arg == "H5-dt-2^17") {
    with_cell(DT_AT, i64(1) << 17, true, true, c2, M2);
    run_case(W, "hostile", arg, c2, M2, VFrom::TRACE, true, 1);
  } else if (arg == "H6-table-row0-pad-nonzero") {
    M2 = M; M2[NCELLS] = 1;
    run_case(W, "hostile", arg, cells, M2, VFrom::TRACE, false, 1);
  } else if (arg == "C1-dt-78848") {
    with_cell(DT_AT, 78848, true, true, c2, M2);
    run_case(W, "completeness", arg, c2, M2, VFrom::TRACE, false, 1);
  } else if (arg == "C2-dt-minus-23424") {
    with_cell(DT_AT, -23424, true, true, c2, M2);
    run_case(W, "completeness", arg, c2, M2, VFrom::TRACE, false, 1);
  } else if (arg == "C3-dt-2^17-minus-1") {
    with_cell(DT_AT, (i64(1) << 17) - 1, true, true, c2, M2);
    run_case(W, "completeness", arg, c2, M2, VFrom::TRACE, false, 1);
  } else {
    need(false, "unknown case");
  }
  return 0;
}
