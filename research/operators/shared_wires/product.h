// SPDX-License-Identifier: Apache-2.0
// Research composition of public_binding/product.h and upstream product PSC/IOPP.
#pragma once
#include "../public_binding/product.h"
namespace blk {
struct WireEquality {
  u64 left_row, left_column, right_row, right_column;
};
inline void public_bytes(Writer &w, const WireEquality &e) {
  public_bytes(w,e.left_row); public_bytes(w,e.left_column);
  public_bytes(w,e.right_row); public_bytes(w,e.right_column);
}
inline const char *public_fault(const WireEquality &e) {
  return e.left_row >= 3 || e.right_row >= 3 ? "invalid wire row" : nullptr;
}
constexpr u64 WIRE_LABEL = 0x46505731ULL;
struct WireRun {
  ToyRun product;
  std::vector<Coordinate> coordinates;
  std::vector<WireEquality> equalities;
};
inline WireRun wire_size(const Setting &set, unsigned log_len, unsigned log_n,
                         unsigned mask_log_n, const std::vector<StageChoice> &further,
                         std::vector<Coordinate> coordinates, std::vector<WireEquality> equalities) {
  BLK_REQUIRE(log_len >= 1 && log_len <= 20, "wire length out of range");
  BLK_REQUIRE(!coordinates.empty() && coordinates.size() <= 64, "coordinate count out of range");
  BLK_REQUIRE(!equalities.empty() && equalities.size() <= 64, "wire count out of range");
  const u64 length = u64(1) << log_len;
  for (const auto &c : coordinates)
    BLK_REQUIRE(!public_fault(c) && c.column < length, "coordinate out of range");
  for (const auto &e : equalities)
    BLK_REQUIRE(!public_fault(e) && e.left_column < length && e.right_column < length, "wire out of range");
  // Count BOTH kinds of linear claims in GroupLoad and plan_iopp. No new masks.
  auto product = coordinate_size_plan(set,log_len,log_n,mask_log_n,further,coordinates.size()+equalities.size());
  product.shape.text = toy_text("research-shared-wire-product-v1",set,
      {{"public-coordinates",coordinates.size()},{"wire-equalities",equalities.size()},
       {"log-length",log_len},{"log-n",log_n},{"mask-log-n",mask_log_n}},further);
  return {std::move(product),std::move(coordinates),std::move(equalities)};
}
struct WirePublic {
  ToyPublic product;
  Public<std::vector<Coordinate>> coordinates;
  Public<std::vector<WireEquality>> equalities;
};
inline WirePublic wire_bind(Binder &b, const WireRun &run) {
  auto product = toy_bind_run(b,run.product);
  auto coordinates = b.statement("public product coordinates v1",run.coordinates);
  auto equalities = b.statement("shared product wires v1",run.equalities);
  return {product,coordinates,equalities};
}
inline Row wire_row(OracleId oracle, const WireEquality &e) {
  Row row; row.name = "shared product wire";
  // Product PSC has three real rows padded to four: row bits are low.
  row.add_unit(oracle,Part::MAIN,e.left_row+4*e.left_column,E::one());
  row.add_unit(oracle,Part::MAIN,e.right_row+4*e.right_column,-E::one());
  row.target = E::zero();
  return row;
}
inline void wire_rows(Statement &st, GroupId g, const std::vector<WireEquality> &equalities) {
  BLK_REQUIRE(st.group(g).members.size()==1,"expected the product oracle only");
  const auto oracle = st.group(g).members[0];
  const unsigned bits = st.codes().base[st.group(g).code].log_ell();
  for (const auto &e : equalities) {
    BLK_REQUIRE(!public_fault(e) && e.left_column < (u64(1)<<bits) && e.right_column < (u64(1)<<bits),"wire out of range");
    st.add_row(g,wire_row(oracle,e));
  }
}
inline void wire_prove(const WireRun &run, const Table &abc, Engine &engine, Coins &coins, Writer &proof) {
  Binder b(WIRE_LABEL,run.product.plan); const auto in=wire_bind(b,run);
  ProverRounds ch(b,random_digest(coins),proof,[&engine](const ChainPrefix &p,unsigned bits){return engine.search_nonce(p,bits);});
  ProverContext pr(in.product.codes,ch,engine,coins);
  FoldMask mask; const auto g=toy_prove_preamble(pr,in.product,abc,mask);
  coordinate_rows(pr.st,g,ch.get(in.coordinates));
  wire_rows(pr.st,g,ch.get(in.equalities));
  iopp_prove(pr,g,in.product.stages,in.product.choice,std::move(mask));
  ch.finish(); pr.st.require_all_tested();
}
inline bool wire_decide(VerifierRounds &ch, const WirePublic &in, Notes *notes) {
  VerifierContext vf(in.product.codes,ch); vf.notes=notes;
  GroupId g=0; FoldMask mask;
  if (!toy_verify_preamble(vf,in.product,g,mask)) return false;
  coordinate_rows(vf.st,g,ch.get(in.coordinates));
  wire_rows(vf.st,g,ch.get(in.equalities));
  if (!iopp_verify(vf,g,in.product.stages,in.product.choice,std::move(mask))) return false;
  vf.st.require_all_tested(); return true;
}
inline bool wire_verify(const WireRun &run,const u8 *proof,size_t bytes,const char **why=nullptr) {
  return run_verifier(WIRE_LABEL,run.product.plan,run,wire_bind,wire_decide,proof,bytes,why);
}
} // namespace blk
