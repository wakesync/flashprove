// SPDX-License-Identifier: Apache-2.0
// Research-only affine composition on the shared committed product oracle.
#pragma once
#include "../shared_wires/product.h"
namespace blk {
struct AffineTerm { u64 row, column; F coefficient; };
struct AffineRelation { std::vector<AffineTerm> terms; F target; };
inline void public_bytes(Writer &w,const AffineTerm &t) {
  public_bytes(w,t.row); public_bytes(w,t.column); public_bytes(w,t.coefficient);
}
inline void public_bytes(Writer &w,const AffineRelation &a) {
  public_bytes(w,a.terms); public_bytes(w,a.target);
}
inline const char *public_fault(const AffineRelation &a) {
  if(a.terms.empty() || a.terms.size()>8 || a.target.v>=P) return "invalid affine shape or target";
  for(const auto &t:a.terms)
    if(t.row>=3 || t.coefficient.v>=P) return "invalid affine term";
  return nullptr;
}
constexpr u64 AFFINE_LABEL=0x46504131ULL;
struct AffineRun { WireRun wire; std::vector<AffineRelation> relations; };
inline AffineRun affine_size(const Setting &set,unsigned log_len,unsigned log_n,
    unsigned mask_log_n,const std::vector<StageChoice> &further,
    std::vector<Coordinate> coordinates,std::vector<WireEquality> equalities,
    std::vector<AffineRelation> relations) {
  BLK_REQUIRE(!relations.empty() && relations.size()<=64,"affine count out of range");
  BLK_REQUIRE(log_len>=1 && log_len<=20,"affine length out of range");
  for(const auto &a:relations) {
    BLK_REQUIRE(!public_fault(a),"invalid affine relation");
    for(const auto &t:a.terms) BLK_REQUIRE(t.column<(u64(1)<<log_len),"affine column out of range");
  }
  // Reuse V4 validation, then reconstruct sizing with ALL linear rows included
  // in both initial GroupLoad and plan_iopp. No additional masking slots.
  auto wire=wire_size(set,log_len,log_n,mask_log_n,further,std::move(coordinates),std::move(equalities));
  wire.product=coordinate_size_plan(set,log_len,log_n,mask_log_n,further,
      wire.coordinates.size()+wire.equalities.size()+relations.size());
  wire.product.shape.text=toy_text("research-affine-product-v1",set,
      {{"public-coordinates",wire.coordinates.size()},{"wire-equalities",wire.equalities.size()},
       {"affine-relations",relations.size()},{"log-length",log_len},{"log-n",log_n},{"mask-log-n",mask_log_n}},further);
  return {std::move(wire),std::move(relations)};
}
struct AffinePublic { WirePublic wire; Public<std::vector<AffineRelation>> relations; };
inline AffinePublic affine_bind(Binder &b,const AffineRun &run) {
  auto wire=wire_bind(b,run.wire);
  auto relations=b.statement("sparse affine product relations v1",run.relations);
  return {wire,relations};
}
inline Row affine_row(OracleId oracle,const AffineRelation &a) {
  Row row; row.name="sparse affine product relation";
  for(const auto &t:a.terms) row.add_unit(oracle,Part::MAIN,t.row+4*t.column,E::from(t.coefficient));
  row.target=E::from(a.target); return row;
}
inline void affine_rows(Statement &st,GroupId g,const std::vector<AffineRelation> &relations) {
  BLK_REQUIRE(st.group(g).members.size()==1,"expected the product oracle only");
  const auto oracle=st.group(g).members[0];
  const unsigned bits=st.codes().base[st.group(g).code].log_ell();
  for(const auto &a:relations) {
    BLK_REQUIRE(!public_fault(a),"invalid affine relation");
    for(const auto &t:a.terms) BLK_REQUIRE(t.column<(u64(1)<<bits),"affine column out of range");
    st.add_row(g,affine_row(oracle,a));
  }
}
inline void affine_prove(const AffineRun &run,const Table &abc,Engine &engine,Coins &coins,Writer &proof) {
  Binder b(AFFINE_LABEL,run.wire.product.plan); auto in=affine_bind(b,run);
  ProverRounds ch(b,random_digest(coins),proof,[&engine](const ChainPrefix &p,unsigned bits){return engine.search_nonce(p,bits);});
  ProverContext pr(in.wire.product.codes,ch,engine,coins);
  FoldMask mask; auto g=toy_prove_preamble(pr,in.wire.product,abc,mask);
  coordinate_rows(pr.st,g,ch.get(in.wire.coordinates));
  wire_rows(pr.st,g,ch.get(in.wire.equalities));
  affine_rows(pr.st,g,ch.get(in.relations));
  iopp_prove(pr,g,in.wire.product.stages,in.wire.product.choice,std::move(mask));
  ch.finish(); pr.st.require_all_tested();
}
inline bool affine_decide(VerifierRounds &ch,const AffinePublic &in,Notes *notes) {
  VerifierContext vf(in.wire.product.codes,ch); vf.notes=notes;
  GroupId g=0; FoldMask mask;
  if(!toy_verify_preamble(vf,in.wire.product,g,mask)) return false;
  coordinate_rows(vf.st,g,ch.get(in.wire.coordinates));
  wire_rows(vf.st,g,ch.get(in.wire.equalities));
  affine_rows(vf.st,g,ch.get(in.relations));
  if(!iopp_verify(vf,g,in.wire.product.stages,in.wire.product.choice,std::move(mask))) return false;
  vf.st.require_all_tested(); return true;
}
inline bool affine_verify(const AffineRun &run,const u8 *proof,size_t bytes,const char **why=nullptr) {
  return run_verifier(AFFINE_LABEL,run.wire.product.plan,run,affine_bind,affine_decide,proof,bytes,why);
}
} // namespace blk
