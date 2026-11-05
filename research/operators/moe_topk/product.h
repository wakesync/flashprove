// SPDX-License-Identifier: Apache-2.0
// Research-only: qwen_deltanet/product.h (wide affine rows on the shared committed product
// oracle, toy PSC/IOPP) with two changes, and only these, for the MoE top-k routing slice:
//  * up to 512 terms per relation (an E <= 384 term one-hot gather plus its carrier);
//  * its own transcript label and plan text, so proofs cannot be replayed across the
//    affine / KDA / DeltaNet / MoE research relations.
// Every relation is bound into the first query and counted in BOTH GroupLoad and
// plan_iopp through coordinate_size_plan, exactly like affine_size().
#pragma once
#include "../affine_rows/product.h"
namespace blk {
constexpr u64 MOE_LABEL=0x46504d4bULL; // "FPMK": distinct transcript domain from affine/KDA/DeltaNet proofs
struct WideRelation { std::vector<AffineTerm> terms; F target; };
inline void public_bytes(Writer &w,const WideRelation &a) { public_bytes(w,a.terms); public_bytes(w,a.target); }
inline const char *public_fault(const WideRelation &a);
inline const char *wide_fault(const WideRelation &a) {
  if(a.terms.empty() || a.terms.size()>512 || a.target.v>=P) return "invalid wide relation shape or target";
  for(const auto &t:a.terms) if(t.row>=3 || t.coefficient.v>=P) return "invalid wide relation term";
  return nullptr;
}
inline const char *public_fault(const WideRelation &a) { return wide_fault(a); }
inline Row wide_row(OracleId oracle,const WideRelation &a) {
  Row row; row.name="wide sparse affine product relation";
  for(const auto &t:a.terms) row.add_unit(oracle,Part::MAIN,t.row+4*t.column,E::from(t.coefficient));
  row.target=E::from(a.target); return row;
}
struct WideRun { ToyRun product; std::vector<WideRelation> relations; };
inline WideRun wide_size(const Setting &set,unsigned log_len,unsigned log_n,unsigned mask_log_n,
    const std::vector<StageChoice> &further,std::vector<WideRelation> relations) {
  BLK_REQUIRE(!relations.empty() && relations.size()<=(u64(1)<<23),"wide relation count out of range");
  BLK_REQUIRE(log_len>=1 && log_len<=22,"wide length out of range");
  for(const auto &a:relations) {
    BLK_REQUIRE(!wide_fault(a),"invalid wide relation");
    for(const auto &t:a.terms) BLK_REQUIRE(t.column<(u64(1)<<log_len),"wide column out of range");
  }
  auto product=coordinate_size_plan(set,log_len,log_n,mask_log_n,further,relations.size());
  product.shape.text=toy_text("research-moe-topk-wide-affine-product-v1",set,
      {{"affine-relations",relations.size()},{"log-length",log_len},{"log-n",log_n},{"mask-log-n",mask_log_n}},further);
  return {std::move(product),std::move(relations)};
}
struct WidePublic { ToyPublic product; Public<std::vector<WideRelation>> relations; };
inline WidePublic wide_bind(Binder &b,const WideRun &run) {
  auto product=toy_bind_run(b,run.product);
  auto relations=b.statement("wide sparse affine product relations v1",run.relations);
  return {product,relations};
}
inline void wide_rows(Statement &st,GroupId g,const std::vector<WideRelation> &relations) {
  BLK_REQUIRE(st.group(g).members.size()==1,"expected the product oracle only");
  const auto oracle=st.group(g).members[0];
  const unsigned bits=st.codes().base[st.group(g).code].log_ell();
  for(const auto &a:relations) {
    BLK_REQUIRE(!wide_fault(a),"invalid wide relation");
    for(const auto &t:a.terms) BLK_REQUIRE(t.column<(u64(1)<<bits),"wide column out of range");
    st.add_row(g,wide_row(oracle,a));
  }
}
inline bool wide_decide(VerifierRounds &ch,const WidePublic &in,Notes *notes) {
  VerifierContext vf(in.product.codes,ch); vf.notes=notes;
  GroupId g=0; FoldMask mask;
  if(!toy_verify_preamble(vf,in.product,g,mask)) return false;
  wide_rows(vf.st,g,ch.get(in.relations));
  if(!iopp_verify(vf,g,in.product.stages,in.product.choice,std::move(mask))) return false;
  vf.st.require_all_tested(); return true;
}
inline bool wide_verify(const WideRun &run,const u8 *proof,size_t bytes,const char **why=nullptr) {
  return run_verifier(MOE_LABEL,run.product.plan,run,wide_bind,wide_decide,proof,bytes,why);
}
} // namespace blk
