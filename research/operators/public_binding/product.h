// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0
// Research derivative of blocks/toy/product.h. Not a serving protocol.
#pragma once
#include "toy/product.h"
namespace blk {
struct Coordinate {
  u64 row, column;
  F value;
};
inline void public_bytes(Writer &w, const Coordinate &c) {
  public_bytes(w, c.row); public_bytes(w, c.column); public_bytes(w, c.value);
}
inline const char *public_fault(const Coordinate &c) {
  return c.row >= 3 || c.value.v >= P ? "invalid public coordinate" : nullptr;
}
constexpr u64 COORDINATE_LABEL = 0x46504331ULL;
inline ToyRun coordinate_size_plan(const Setting &set, unsigned log_len, unsigned log_n, unsigned mask_log_n,
                       const std::vector<StageChoice> &further, u64 coordinates) {
  ToyRun run(set);
  run.shape.text = toy_text("research-public-coordinate-product-v1", set, {{"public-coordinates", coordinates}, {"log-length", log_len}, {"log-n", log_n}, {"mask-log-n", mask_log_n}}, further);
  Plan plan(set);
  GroupSize g;
  g.name = "a, b, c";
  g.k = 2, g.h = 0; // three rows in a table of four; one mask row
  g.main.name = "rows", g.main.log_n = log_n, g.main.ell = u64(1) << log_len;
  const u64 masks = 1 + 2 * u64(log_len) + 2 + 2; // what PSC takes: the hiding polynomial's coefficients and two inner masks
  g.mask.name = "mask row", g.mask.log_n = mask_log_n, g.mask.over_E = true;
  g.mask.ell = pow2_at_least(std::max<u64>(masks + set.samples, 2 * g.k + 1 - g.h));
  // The random tails must hide as many positions as are drawn, and that number depends on the
  // rate, so on the tails: t rises from 0 until it settles.
  u64 t = 0;
  for (int turn = 0; turn < 16; turn++) {
    g.main.r = g.mask.r = tail_for(set, t);
    GroupLoad load;
    load.cube_bits = stage_cube_bits(g);
    load.batched_rows = (toy_rows_batched(set) + coordinates);
    g = size_group(set, plan.scope(), g, load);
    if (analysis(set, g).bad()) {  // size_group has found no m
      plan.refuse("no slack holds the first stage's rounds at the target");
      return run.plan = plan.finish(), run;
    }
    const u64 more = plan_positions(plan, analysis(set, g).at.agree, Bound(Real::two_to(-(long)set.target - 30)));
    if (more <= t) break;
    t = more;
  }
  const std::vector<Stage> stages = solve_stages(plan, g, t, further);
  if (plan.refused()) return run.plan = plan.finish(), run;
  run.stages = iopp_stages(stages, run.shape.codes);
  if (const char *fault = iopp_sized_fault(run.shape.codes, run.stages, stages)) return plan.refuse(fault), run.plan = plan.finish(), run; // required before `plan_iopp` (see blocks/iop/iopp.h)
  plan_chain_start(plan, "toy run", true);
  toy_plan_preamble(plan, run.shape, run.stages, {g});
  plan_iopp(plan, g.name, stages, tree_sizes(run.shape.codes, toy_first_message(OracleNotice{run.shape.oracle(), 0}, run.stages)),
            (toy_rows_batched(set) + coordinates), 0, true);
  return run.plan = plan.finish(), run;
}

struct CoordinateRun {
  ToyRun product;
  std::vector<Coordinate> coordinates;
};
// Only this sizing entry point is supported. Count drives BOTH first-stage load
// and plan_iopp batching; no extra masks or protocol messages are consumed.
inline CoordinateRun coordinate_size(const Setting &set, unsigned log_len, unsigned log_n,
                                     unsigned mask_log_n, const std::vector<StageChoice> &further,
                                     std::vector<Coordinate> coordinates) {
  BLK_REQUIRE(log_len >= 1 && log_len <= 20, "coordinate length out of range");
  BLK_REQUIRE(!coordinates.empty() && coordinates.size() <= 64, "coordinate count out of range");
  for (const auto &c : coordinates) {
    BLK_REQUIRE(!public_fault(c) && c.column < (u64(1) << log_len), "coordinate out of range");
  }
  return {coordinate_size_plan(set, log_len, log_n, mask_log_n, further, coordinates.size()), std::move(coordinates)};
}
struct CoordinatePublic {
  ToyPublic product;
  Public<std::vector<Coordinate>> coordinates;
};
inline CoordinatePublic coordinate_bind(Binder &b, const CoordinateRun &run) {
  auto product = toy_bind_run(b, run.product);
  return {product, b.statement("public product coordinates v1", run.coordinates)};
}
inline void coordinate_rows(Statement &st, GroupId g, const std::vector<Coordinate> &coordinates) {
  // The returned product group has exactly the committed abc oracle, not the
  // first fold's separately sent mask oracle. Never commit a second witness.
  BLK_REQUIRE(st.group(g).members.size() == 1, "expected the product oracle only");
  const OracleId o = st.group(g).members[0];
  const unsigned bits = st.codes().base[st.group(g).code].log_ell();
  for (const auto &c : coordinates) {
    BLK_REQUIRE(!public_fault(c) && c.column < (u64(1) << bits), "coordinate out of range");
    std::vector<E> point(bits);
    for (unsigned j = 0; j < bits; ++j) point[j] = (c.column >> j) & 1 ? E::one() : E::zero();
    Row r;
    r.name = "public product coordinate";
    r.add(o, Part::MAIN, toy_row_at(st, o, c.row, point, E::one()));
    r.target = E::from(c.value);
    st.add_row(g, std::move(r));
  }
}
inline void coordinate_prove(const CoordinateRun &run, const Table &abc, Engine &engine, Coins &coins, Writer &proof) {
  Binder b(COORDINATE_LABEL, run.product.plan);
  const auto in = coordinate_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&engine](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins);
  FoldMask mask;
  const GroupId g = toy_prove_preamble(pr, in.product, abc, mask);
  coordinate_rows(pr.st, g, ch.get(in.coordinates));
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask));
  ch.finish(); pr.st.require_all_tested();
}
inline bool coordinate_decide(VerifierRounds &ch, const CoordinatePublic &in, Notes *notes) {
  VerifierContext vf(in.product.codes, ch); vf.notes = notes;
  GroupId g = 0; FoldMask mask;
  if (!toy_verify_preamble(vf, in.product, g, mask)) return false;
  coordinate_rows(vf.st, g, ch.get(in.coordinates));
  if (!iopp_verify(vf, g, in.product.stages, in.product.choice, std::move(mask))) return false;
  vf.st.require_all_tested(); return true;
}
inline bool coordinate_verify(const CoordinateRun &run, const u8 *proof, size_t bytes, const char **why = nullptr) {
  return run_verifier(COORDINATE_LABEL, run.product.plan, run, coordinate_bind, coordinate_decide, proof, bytes, why);
}
} // namespace blk
