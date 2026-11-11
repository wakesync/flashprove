// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <array>
#include "frame/check_key.h"
#include "../../operators/qwen_handoff/sha256.h"
namespace blk {
constexpr u64 TENSOR_KEY_LABEL=0x46525742;
constexpr u32 TENSOR_KEY_TAG=tag_of('F','P','W','B'), TENSOR_KEY_VERSION=1;
constexpr size_t TENSOR_KEY_HEADER=72;
using TensorWords=std::array<std::vector<F>,4>;
inline void tw_text(Writer &w,const std::string &s){w.put_bytes((const u8*)s.data(),s.size());}
inline void tw_lp(Writer &w,const std::string &s){w.put_u64(s.size());tw_text(w,s);}
inline Digest tw_sha(const Writer &w){const auto bytes=::sha256(w.bytes());Digest d;digest_from_bytes(bytes.data(),d);return d;}
inline std::string tw_hex(const Digest &d){u8 b[32];digest_to_bytes(d,b);std::string s;for(auto x:b){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
inline bool tw_value_ok(F x){return x.v<=1||x.v==P-1||x.v==P-2;}
// Source bytes are signed I64 LE, not the field residue's spelling.
inline u64 tw_signed_bits(F x){BLK_REQUIRE(tw_value_ok(x),"toy signed integer out of range");return x.v<=1?x.v:x.v==P-1?~u64(0):~u64(1);}
inline Digest tw_integers(const std::vector<F> &v){Writer w;for(auto x:v)w.put_u64(tw_signed_bits(x));return tw_sha(w);}
inline Digest tw_leaf(const std::string &name,const std::vector<F> &v){
  Writer w;const u8 zero=0;w.put_bytes(&zero,1);tw_text(w,"fp-wb-leaf-v1");tw_lp(w,name);tw_lp(w,"I64");
  tw_lp(w,"["+std::to_string(v.size())+"]");w.put(tw_integers(v));return tw_sha(w);
}
inline Digest tw_node(const Digest &l,const Digest &r){Writer w;const u8 one=1;w.put_bytes(&one,1);tw_text(w,"fp-wb-node-v1");w.put(l);w.put(r);return tw_sha(w);}
struct TensorManifest {
  TensorWords integers;
  std::array<std::string,4> names={"tensor.0","tensor.1","tensor.2","tensor.3"};
  std::string rule="signed-i64-identity-v1";
  Digest configuration{},checkpoint{},conversion{};
};
inline Digest tw_checkpoint(const TensorManifest &m){
  auto root=tw_node(tw_node(tw_leaf(m.names[0],m.integers[0]),tw_leaf(m.names[1],m.integers[1])),tw_node(tw_leaf(m.names[2],m.integers[2]),tw_leaf(m.names[3],m.integers[3])));
  Writer w;tw_text(w,"fp-wb-id-v1");w.put_u64(4);w.put(root);return tw_sha(w);
}
inline Digest tw_conversion(const TensorManifest &m){
  Writer w;tw_text(w,"fp-wb-small-key-conversion-v1");w.put(tw_checkpoint(m));tw_lp(w,m.rule);w.put(m.configuration);
  tw_lp(w,"signed I64 LE to Goldilocks; exponent=0; rows at fixed ascending indices");w.put_u64(4);
  for(unsigned r=0;r<4;++r){tw_lp(w,m.names[r]);w.put_u64(r);w.put_u64(m.integers[r].size());w.put_u64(0);w.put(tw_leaf(m.names[r],m.integers[r]));w.put(tw_integers(m.integers[r]));}
  return tw_sha(w);
}
inline const char *public_fault(const TensorManifest &m){
  if(m.rule!="signed-i64-identity-v1"&&m.rule!="signed-i64-identity-v2-equivalent")return "unsupported conversion";
  for(unsigned r=0;r<4;++r){
    if(m.names[r].empty()||(r&&m.names[r-1]>=m.names[r]))return "noncanonical names/order";
    if(m.integers[r].size()!=4)return "tensor shape";
    for(auto x:m.integers[r])if(!tw_value_ok(x))return "tensor integer range";
  }
  if(tw_checkpoint(m)!=m.checkpoint)return "held checkpoint root mismatch";
  if(tw_conversion(m)!=m.conversion)return "held conversion id mismatch";
  return nullptr;
}
inline void public_bytes(Writer &w,const TensorManifest &m){w.put(m.checkpoint);w.put(m.conversion);}
inline TensorManifest tw_manifest(const TensorWords &v,const Digest &configuration,bool debug=false,const std::string &rule="signed-i64-identity-v1"){
  TensorManifest m;m.integers=v;m.configuration=configuration;m.rule=rule;
  if(debug)for(auto &name:m.names)name="debug."+name;
  m.checkpoint=tw_checkpoint(m);m.conversion=tw_conversion(m);return m;
}
inline Digest tw_commitment(const KeyFixed &f,const IndexName &name){
  Digest root;BLK_REQUIRE(name.commitment.size()==32,"expected root commitment");digest_from_bytes(name.commitment.data(),root);
  const auto &shape=f.lin.fold.index;const auto full_name=index_name(root,shape,f.configuration);
  return published_id(f.configuration,full_name,record_seeds(shape,full_name),name.record.y);
}
inline std::vector<E> tw_point(const Digest &id,const Digest &conv,const std::string &name,unsigned bits){
  std::vector<E> z(bits);
  for(unsigned i=0;i<bits;++i)for(unsigned limb=0;limb<3;++limb)for(u64 retry=0;;++retry){
    Writer w;tw_text(w,"fp-wb-point-v2");w.put(id);w.put(conv);tw_lp(w,name);w.put_u64(i);w.put_u64(limb);w.put_u64(retry);
    const auto h=tw_sha(w);const u64 x=u64(h.w[0])+(u64(h.w[1])<<32);if(x<P){z[i].c[limb]=F{x};break;}
  }return z;
}
inline E tw_eval(const std::vector<F> &v,const std::vector<E> &z){
  BLK_REQUIRE(v.size()==(u64(1)<<z.size()),"evaluation shape");std::vector<E>a;for(auto x:v)a.push_back(E::from(x));
  for(auto x:z){for(size_t j=0;j<a.size()/2;++j)a[j]=a[2*j]+x*(a[2*j+1]-a[2*j]);a.resize(a.size()/2);}return a[0];
}
inline void tensor_append(std::vector<TensorRow> &pending,const KeyFixed &f,const IndexName &name,const TensorManifest &m,const TensorWords *dishonest){
  BLK_REQUIRE(f.lin.matrix_rows==4&&f.lin.k_col()==2&&m.configuration==f.configuration,"small-key layout/config mismatch");
  const auto id=tw_commitment(f,name);
  for(unsigned r=0;r<4;++r){
    TensorRow row;Tensor g;g.insert_choice(0,f.lin.k_row(),r);row.g.push_back(g);
    row.psi=tw_point(id,m.conversion,m.names[r],f.lin.k_col());
    row.target=tw_eval(dishonest?(*dishonest)[r]:m.integers[r],row.psi);
    pending.push_back(std::move(row));
  }
}
} // namespace blk
