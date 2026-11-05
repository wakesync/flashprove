// SPDX-License-Identifier: Apache-2.0
// Research-only: the wide affine product oracle of research/operators/qwen_deltanet/product.h,
// composed with RNG, the approximate range check (blocks/iop/rng.h, with its LKP digit lookup),
// in ONE proximity-test group. Messages, in order on the channel:
//   0  a, b, c        the product oracle (toy PSC: a b = c), one mask row (PSC's and LKP's masks)
//   1  fold mask      of the first IOPP stage (toy_first_message)
//   2  digits         RNG's digits of Psi = Y Theta, two rows, no mask row
//   3  multiplicities RNG's lookup planes, one row, no mask row
// The RNG cells Y are entries of row a of message 0 itself (lanes = 1): each RNG matrix is one
// LaidBlock in row 0 of the product table. So the range-checked integers ARE the product-oracle
// cells that the affine relations and product gates read; no wiring relation ties them.
// Sizing follows blocks/iop/tests/rng_world.h and blocks/toy/product.h.
#pragma once
#include "../qwen_deltanet/product.h"
#include "iop/rng.h"
namespace blk {
constexpr u64 LOOKUP_LABEL = 0x46504c4bULL;  // own transcript domain
// The RNG region: matrices of `columns` columns laid at place first_place[mu] of row a.
// Cell (i, c) of matrix mu is product column first_place[mu] + c * rows[mu] + i.
struct RegionSpec {
  std::vector<u64> rows;         // per matrix, a power of two
  std::vector<u64> first_place;  // per matrix, aligned to rows * columns
  u64 columns = 16;
  unsigned b0 = 12, b1 = 11;     // digits: window 2D = 2^(b0+b1)
};
inline RngShape lk_rng_shape(const Setting &set, unsigned combinations, const RegionSpec &rs, unsigned log_len) {
  RngShape S;
  S.lanes = 1, S.log_radix = rs.b0 + rs.b1 + 1, S.digit_bits[0] = rs.b0, S.digit_bits[1] = rs.b1, S.combinations = combinations;
  for (size_t mu = 0; mu < rs.rows.size(); mu++) {
    RngMatrix m; m.rows = rs.rows[mu], m.columns = rs.columns, m.packed = 0;
    LaidBlock b; b.first_i = 0, b.bits_i = ceil_log2(m.rows), b.first_c = 0, b.bits_c = ceil_log2(rs.columns);
    b.first_row = 0, b.row_bits = 0, b.first_place = rs.first_place[mu], b.place_bits = b.bits_i + b.bits_c, b.i_is_low = true;
    m.laid = {b}; S.matrices.push_back(m);
  }
  S.digit_columns = pow2_at_least(S.cell_rows());
  OracleShape d; d.name = "digits", d.code = 0, d.main_rows = 2, d.main_deg = 1, d.mask_rows = 0, d.answers = set.samples;
  OracleShape p; p.name = "multiplicities", p.code = 0, p.main_rows = 1, p.main_deg = 1, p.mask_rows = 0, p.answers = set.samples;
  S.digits = OracleNotice{d, 0}; S.multiplicities = OracleNotice{p, 0};
  const u64 Np = S.step();
  for (u64 c = 0; c < 2 * S.digit_columns; c++)
    for (u64 first = 0; first < combinations;) {  // aligned power-of-two pieces of [0, N)
      unsigned bits = 0;
      while (first + (u64(2) << bits) <= combinations && (first & ((u64(2) << bits) - 1)) == 0) bits++;
      LaidBlock b; b.first_i = first, b.bits_i = bits, b.first_c = c, b.bits_c = 0, b.i_is_low = true;
      b.first_row = c / S.digit_columns, b.row_bits = 0, b.first_place = (c % S.digit_columns) * Np + first, b.place_bits = bits;
      S.digits_laid.push_back(b); first += u64(1) << bits;
    }
  BLK_REQUIRE(S.digit_columns * Np <= (u64(1) << log_len), "lookup: digits do not fit a row");
  S.digits_in = 2, S.masks_from = 0;
  return S;
}
// The linear claims that RNG leaves (LKP's, the key row, RNG's own): as rng_world.h rows_left().
inline u64 lk_rng_rows(const RngShape &R) { const LkpPublic L = rng_lookup(R); return (L.planes() - 1) + L.parts[0] + L.d + 4 + 1 + 1; }

struct LookupRun { ToyRun product; RngShape range; std::vector<WideRelation> relations; };
inline LookupRun lookup_size(const Setting &set, unsigned log_len, unsigned log_n, unsigned mask_log_n,
    const std::vector<StageChoice> &further, std::vector<WideRelation> relations, const RegionSpec &rs) {
  BLK_REQUIRE(!relations.empty() && relations.size() <= (u64(1) << 23), "lookup: relation count out of range");
  BLK_REQUIRE(log_len >= 1 && log_len <= 22, "lookup: length out of range");
  for (const auto &a : relations) {
    BLK_REQUIRE(!wide_fault(a), "invalid wide relation");
    for (const auto &t : a.terms) BLK_REQUIRE(t.column < (u64(1) << log_len), "wide column out of range");
  }
  LookupRun run{ToyRun(set), RngShape(), std::move(relations)};
  Plan plan(set);
  run.range = lk_rng_shape(set, rng_combinations(plan), rs, log_len);
  const RngShape &R = run.range;
  const LkpPublic L = rng_lookup(R);
  const u64 rows = toy_rows_batched(set) + run.relations.size() + lk_rng_rows(R) + 2 * set.samples;
  GroupSize g;
  g.name = "a, b, c, digits, multiplicities";
  g.k = 3, g.h = 0;  // 4 + 2 + 1 main rows in a table of 8; one mask row
  g.main.name = "rows", g.main.log_n = log_n, g.main.ell = u64(1) << log_len;
  const u64 masks = 1 + 2 * u64(log_len) + 2 + 2 + lkp_masks(L);
  g.mask.name = "mask row", g.mask.log_n = mask_log_n, g.mask.over_E = true;
  g.mask.ell = pow2_at_least(std::max<u64>(masks + set.samples, 2 * g.k + 1 - g.h));
  u64 t = 0;
  for (int turn = 0; turn < 16; turn++) {
    g.main.r = g.mask.r = tail_for(set, t);
    GroupLoad load; load.cube_bits = stage_cube_bits(g); load.batched_rows = rows;
    g = size_group(set, plan.scope(), g, load);
    if (analysis(set, g).bad()) { plan.refuse("no slack holds the first stage's rounds at the target"); run.product.plan = plan.finish(); return run; }
    const u64 more = plan_positions(plan, analysis(set, g).at.agree, Bound(Real::two_to(-(long)set.target - 30)));
    if (more <= t) break;
    t = more;
  }
  const std::vector<Stage> stages = solve_stages(plan, g, t, further);
  if (plan.refused()) { run.product.plan = plan.finish(); return run; }
  Codes &codes = run.product.shape.codes;
  run.product.stages = iopp_stages(stages, codes);
  if (const char *fault = iopp_sized_fault(codes, run.product.stages, stages)) { plan.refuse(fault); run.product.plan = plan.finish(); return run; }
  plan_chain_start(plan, "lookup run", true);
  toy_plan_preamble(plan, run.product.shape, run.product.stages, {g});
  plan_rng(plan, "range check", R.all_columns());
  const std::vector<OracleNotice> own = {R.digits, R.multiplicities};
  plan_send(plan, "digits", {SampleSize{Send::cube(codes, R.digits.shape).bits, {g}}, SampleSize{Send::cube(codes, R.multiplicities.shape).bits, {g}}},
            (unsigned)tree_sizes(codes, own).size());
  plan_lookup(plan, "digits", LookupSize{L.parts[0], L.d, L.mu, true, L.live});
  plan_bat_sigma(plan, "range check", R.equations());
  std::vector<TreeSize> trees = tree_sizes(codes, toy_first_message(OracleNotice{run.product.shape.oracle(), 0}, run.product.stages));
  for (const TreeSize &x : tree_sizes(codes, own)) trees.push_back(x);
  plan_iopp(plan, g.name, stages, trees, rows, 0, true);
  std::vector<std::pair<const char *, u64>> words = {{"affine-relations", run.relations.size()}, {"log-length", log_len}, {"log-n", log_n}, {"mask-log-n", mask_log_n},
      {"rng-columns", rs.columns}, {"rng-b0", rs.b0}, {"rng-b1", rs.b1}, {"rng-combinations", R.combinations}};
  for (size_t mu = 0; mu < rs.rows.size(); mu++) words.push_back({"rng-matrix-rows", rs.rows[mu]}), words.push_back({"rng-matrix-place", rs.first_place[mu]});
  run.product.shape.text = toy_text("research-wide-affine-product-rng-v1", set, words, further);
  run.product.plan = plan.finish();
  return run;
}
struct LookupPublic { ToyPublic product; Public<RngShape> range; Public<RngWeights> weights; Public<std::vector<WideRelation>> relations; };
inline LookupPublic lookup_bind(Binder &b, const LookupRun &run) {
  LookupPublic in;
  in.product = toy_bind_run(b, run.product);
  in.range = b.parameter("range check", run.range);
  in.weights = b.parameter("weights of the reads", RngWeights());
  in.relations = b.statement("wide sparse affine product relations v1", run.relations);
  return in;
}
inline bool lookup_decide(VerifierRounds &ch, const LookupPublic &in, Notes *notes) {
  VerifierContext vf(in.product.codes, ch); vf.notes = notes;
  GroupId g = 0; FoldMask mask;
  if (!toy_verify_preamble(vf, in.product, g, mask)) return false;
  wide_rows(vf.st, g, ch.get(in.relations));
  RngOutput out;
  if (!rng_verify(vf, in.range, ch.get(in.weights), g, out)) return false;
  E x; vf.st.add_row(g, rng_row(vf, in.range, out, x));
  if (!iopp_verify(vf, g, in.product.stages, in.product.choice, std::move(mask))) return false;
  vf.st.require_all_tested(); return true;
}
inline bool lookup_verify(const LookupRun &run, const u8 *proof, size_t bytes, const char **why = nullptr) {
  return run_verifier(LOOKUP_LABEL, run.product.plan, run, lookup_bind, lookup_decide, proof, bytes, why);
}

// A research copy of rng_prove() (blocks/iop/rng.h) for HOSTILE provers. mode 0: as rng_prove
// (returns false if a combination leaves its window). mode 1: a combination outside [-D, D) is
// wrapped into it (the only way to send in-range digits for it), so RNG's batched equation is
// false. mode 2: honest, then the first low digit is moved by one (kept inside its range).
inline bool rng_prove_research(ProverContext &P, const Public<RngShape> &fixed, const RngWeights &phi, const std::vector<std::vector<i64>> &cells, GroupId group, RngOutput &out, int mode, u64 *wrapped = nullptr) {
  const RngShape &S = P.ch.get(fixed);
  rng_shape_check(P.st, S), rng_weights_check(S, phi);
  const Public<LkpPublic> look = fixed.derive(rng_lookup);
  const LkpPublic &L = P.ch.get(look);
  out.phi = phi;
  out.theta = rng_theta(P.ch, S);
  const u64 N = S.combinations, DC = S.digit_columns;
  const i64 D = i64(1) << (S.digit_bits[0] + S.digit_bits[1] - 1);
  Table digits(S.digits.shape.main_deg, S.digits.shape.main_rows, P.st.codes().base[S.digits.shape.code].ell);
  std::vector<E> keys(L.all_keys(), E::zero());
  u64 column = 0, cell_row = 0; bool bumped = false;
  for (size_t mu = 0; mu < S.matrices.size(); mu++) {
    const RngMatrix &m = S.matrices[mu];
    for (u64 i = 0; i < m.rows; i++)
      for (u64 u = 0; u < N; u++) {
        __int128 wide = 0;  // hostile cells may be any field element (read as signed 64-bit)
        for (u64 c = 0; c < m.columns; c++) wide += (__int128)cells[mu][i * m.columns + c] * out.theta[(column + c) * N + u];
        if (wide < -D || wide >= D) {
          if (mode != 1) return false;
          wide = ((wide + D) % (2 * D) + 2 * D) % (2 * D) - D;
          if (wrapped) ++*wrapped;
        }
        const i64 psi = (i64)wide;
        const i64 shifted = psi + D;
        i64 lo = shifted & ((i64(1) << S.digit_bits[0]) - 1), hi = (shifted - lo) >> S.digit_bits[0];
        if (mode == 2 && !bumped) { lo = lo + 1 < (i64(1) << S.digit_bits[0]) ? lo + 1 : lo - 1; bumped = true; }
        laid_set(digits, S.digits_laid, u, cell_row + i, E::from(from_i64(lo)));
        laid_set(digits, S.digits_laid, u, DC + cell_row + i, E::from(from_i64(hi)));
        keys[0 + 2 * (cell_row + i + DC * u)] = E::from(from_i64(lo)), keys[1 + 2 * (cell_row + i + DC * u)] = E::from(from_i64(hi));
      }
    column += m.columns, cell_row += m.rows;
  }
  std::vector<E> bits;
  BLK_REQUIRE(lkp_count(L, keys, bits), "RNG research copy: a digit outside its range");
  Table planes(S.multiplicities.shape.main_deg, S.multiplicities.shape.main_rows, P.st.codes().base[S.multiplicities.shape.code].ell);
  for (const std::pair<unsigned, unsigned> &block : lkp_live_blocks(L.planes()))
    for (u64 t = 0; t < u64(1) << L.d; t++)
      for (u64 j = 0; j < u64(1) << block.second; j++) planes.set(0, ((u64)block.first << L.d) + j + (t << block.second), bits[block.first + j + (t << L.mu)]);
  std::vector<OracleDraft> drafts(2);
  drafts[0].shape = S.digits.shape, drafts[0].leaf_class = S.digits.leaf_class, drafts[0].main = P.engine.put(digits);
  drafts[1].shape = S.multiplicities.shape, drafts[1].leaf_class = S.multiplicities.leaf_class, drafts[1].main = P.engine.put(planes);
  for (OracleDraft &d : drafts) if (d.shape.mask_rows) d.mask = Send::fresh_mask(P.st.codes(), d.shape, P.coins);
  const std::vector<OracleId> ids = send_prove(P, std::move(drafts));
  BLK_REQUIRE(ids[0] == S.digits_in && ids[1] == S.digits_in + 1, "RNG research copy: message numbers");
  out.digits = ids[0];
  P.st.join(group, ids[0]), P.st.join(group, ids[1]);
  out.row_owed = true, out.channel = &P.ch;
  LkpCpu heavy(L, std::move(keys), std::move(bits));
  LkpOutput left;
  lkp_prove(P, look, heavy, rng_planes_at(P.st, S, L), S.masks_from, group, left);
  out.shift = left.theta, out.alpha = left.alpha, out.rows = std::move(left.rows);
  Row on_keys = rng_key_row(P.st, S, left.keys.take());
  out.rows.push_back(on_keys);
  P.st.add_row(group, std::move(on_keys));
  return true;
}
}  // namespace blk
