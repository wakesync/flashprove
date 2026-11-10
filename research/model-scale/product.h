// SPDX-License-Identifier: Apache-2.0
// Research-only: the SAME committed product oracle with public coordinates, shared wires and sparse
// affine rows (research/operators/{public_binding,shared_wires,affine_rows}), without their fixed
// 64-claim caps, so generated slices of real-model shape can be sized and measured. Row
// constructors (coordinate_rows, wire_rows, affine_rows) are reused unchanged; only sizing, the
// public file text and the transcript label are new. Not a serving protocol.
#pragma once
#include "../operators/affine_rows/product.h"
namespace blk {
constexpr u64 KDA_SCALE_LABEL = 0x4b445331ULL;  // "KDS1": proofs of other domains are rejected
struct ScaleRun {
  ToyRun product;
  std::vector<Coordinate> coordinates;
  std::vector<WireEquality> equalities;
  std::vector<AffineRelation> relations;
};
inline ScaleRun scale_size(const Setting &set, unsigned log_len, unsigned log_n, unsigned mask_log_n,
                           const std::vector<StageChoice> &further, std::vector<Coordinate> coordinates,
                           std::vector<WireEquality> equalities, std::vector<AffineRelation> relations) {
  BLK_REQUIRE(log_len >= 1 && log_len <= 30, "scale length out of range");
  BLK_REQUIRE(!coordinates.empty() && !equalities.empty() && !relations.empty(), "every claim kind is used");
  const u64 length = u64(1) << log_len;
  for (const auto &c : coordinates) BLK_REQUIRE(!public_fault(c) && c.column < length, "coordinate out of range");
  for (const auto &e : equalities)
    BLK_REQUIRE(!public_fault(e) && e.left_column < length && e.right_column < length, "wire out of range");
  for (const auto &a : relations) {
    BLK_REQUIRE(!public_fault(a), "invalid affine relation");
    for (const auto &t : a.terms) BLK_REQUIRE(t.column < length, "affine column out of range");
  }
  // ALL linear claims count in the first stage's GroupLoad and in plan_iopp's batching, as before.
  const u64 claims = coordinates.size() + equalities.size() + relations.size();
  ScaleRun run{coordinate_size_plan(set, log_len, log_n, mask_log_n, further, claims), std::move(coordinates),
               std::move(equalities), std::move(relations)};
  run.product.shape.text = toy_text("research-kda-scale-product-v1", set,
      {{"public-coordinates", run.coordinates.size()}, {"wire-equalities", run.equalities.size()},
       {"affine-relations", run.relations.size()}, {"log-length", log_len}, {"log-n", log_n}, {"mask-log-n", mask_log_n}},
      further);
  return run;
}
struct ScalePublic {
  ToyPublic product;
  Public<std::vector<Coordinate>> coordinates;
  Public<std::vector<WireEquality>> equalities;
  Public<std::vector<AffineRelation>> relations;
};
inline ScalePublic scale_bind(Binder &b, const ScaleRun &run) {
  auto product = toy_bind_run(b, run.product);
  auto coordinates = b.statement("public product coordinates v1", run.coordinates);
  auto equalities = b.statement("shared product wires v1", run.equalities);
  auto relations = b.statement("sparse affine product relations v1", run.relations);
  return {product, coordinates, equalities, relations};
}
inline bool scale_decide(VerifierRounds &ch, const ScalePublic &in, Notes *notes) {
  VerifierContext vf(in.product.codes, ch); vf.notes = notes;
  GroupId g = 0; FoldMask mask;
  if (!toy_verify_preamble(vf, in.product, g, mask)) return false;
  coordinate_rows(vf.st, g, ch.get(in.coordinates));
  wire_rows(vf.st, g, ch.get(in.equalities));
  affine_rows(vf.st, g, ch.get(in.relations));
  if (!iopp_verify(vf, g, in.product.stages, in.product.choice, std::move(mask))) return false;
  vf.st.require_all_tested(); return true;
}
inline bool scale_verify(const ScaleRun &run, const u8 *proof, size_t bytes, const char **why = nullptr, u64 label = KDA_SCALE_LABEL) {
  return run_verifier(label, run.product.plan, run, scale_bind, scale_decide, proof, bytes, why);
}
} // namespace blk
