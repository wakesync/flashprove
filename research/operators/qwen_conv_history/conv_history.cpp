// SPDX-License-Identifier: Apache-2.0
// Research-only: issue #35, conv1d carried-history binding on the toy profile of PR #67.
// Not a production verifier and not a model proof. See README.md in this directory.
//
// Two conv profiles share the PR #67 relation (one channel, four taps, three history words,
// four new inputs, floor by 2^F):
//  * "unbound": exactly the #67 statement (operator, F, four outputs). Kept as the named
//    negative control: the #67 replaced-history construction verifies here.
//  * "bound": the verifier additionally holds a tail root R (SHA-256, below). The statement
//    carries a public opening of the three incoming history words and of the three outgoing
//    tail words. The verifier checks H(opening)==R OUTSIDE the arithmetic proof, pins the
//    three history cells to the opening and the last three input cells to the outgoing
//    opening INSIDE the proof (one-term affine relations with verifier-owned targets), and
//    binds the root, segment index and both openings into the configuration text. On accept
//    it returns the next root H(F, segment+1, outgoing opening).
#include <array>
#include <chrono>
#include <cstring>
#include <functional>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "../qwen_deltanet/product.h"
#include "../../../prover/weights_commitment/sha256.h"
using namespace blk;
static void need(bool b,const char* msg) { if(!b) throw std::runtime_error(msg); }
static F fi(i64 x) { return x>=0 ? F{u64(x)} : F{P-u64(-x)}; }
static i64 floor2(i64 x,unsigned k) { i64 d=i64(1)<<k; return x/d - (x%d<0); }

// ---- tail root (verifier-owned, outside the proof) ----
using Root=std::array<uint8_t,32>;
static void le(std::string& s,u64 v,int n){for(int i=0;i<n;i++)s.push_back(char((v>>(8*i))&0xff));}
static Root tail_root(int f,u64 segment,const std::array<i64,3>& w) {
  std::string m="fp-conv-tail-v1"; m.push_back('\0');
  le(m,u64(f),4); le(m,segment,8); le(m,3,4);
  for(auto v:w) le(m,u64(v),8);
  Sha256 h; h.update(m.data(),m.size()); Root r; h.digest(r.data()); return r;
}
static std::string hex(const Root& r){static const char*d="0123456789abcdef";std::string s;for(auto b:r){s.push_back(d[b>>4]);s.push_back(d[b&15]);}return s;}

// ---- circuit (copied from research/operators/qwen_ops/proof.cpp, conv subset) ----
struct Wire { u64 c; unsigned r; i64 v; };
struct Circuit {
  bool witness; std::string profile;
  std::vector<std::array<F,3>> cols; std::vector<WideRelation> rel;
  explicit Circuit(bool w):witness(w) {}
  Wire cell(i64 x) { if(!witness) x=0; u64 c=cols.size(); cols.push_back({fi(x),F{0},F{0}}); return {c,0,x}; }
  AffineTerm term(Wire x,i64 k=1) {return {x.r,x.c,fi(k)};}
  void eq(std::vector<AffineTerm> ts,i64 rhs=0) { rel.push_back({std::move(ts),fi(rhs)}); }
  Wire mul(Wire a,Wire b) {
    u64 c=cols.size(); i64 v=witness?a.v*b.v:0;
    cols.push_back({fi(a.v),fi(b.v),fi(v)});
    eq({{0,c,F{1}},term(a,-1)}); eq({{1,c,F{1}},term(b,-1)});
    return {c,2,v};
  }
  Wire bit(i64 v) {
    if(!witness) v=0;
    u64 c=cols.size(); cols.push_back({fi(v),fi(v),fi(v*v)});
    eq({{0,c,F{1}},{1,c,fi(-1)}}); eq({{2,c,F{1}},{0,c,fi(-1)}});
    return {c,0,v};
  }
  Wire sum(const std::vector<std::pair<Wire,i64>>& ts,i64 constant=0) {
    i64 val=constant; if(witness) for(auto &t:ts) val+=t.first.v*t.second;
    auto out=cell(val); std::vector<AffineTerm> a{term(out)};
    for(auto &t:ts) a.push_back(term(t.first,-t.second));
    eq(a,constant); return out;
  }
  // Hostile witnesses may be out of range; the bits then take the low bits of n, so
  // every product gate still holds and only the affine reconstruction fails.
  void range(Wire a,unsigned bits,i64 offset=0) {
    i64 n=witness?a.v+offset:0;
    std::vector<AffineTerm> t{term(a)};
    for(unsigned j=0;j<bits;j++) t.push_back(term(bit((n>>j)&1),-(i64(1)<<j)));
    eq(t,-offset);
  }
  Wire floor(Wire a,unsigned bits) {
    i64 q=witness?floor2(a.v,bits):0;
    auto out=cell(q); auto rem=cell(witness?a.v-q*(i64(1)<<bits):0);
    range(rem,bits); eq({term(a),term(out,-(i64(1)<<bits)),term(rem,-1)});
    return out;
  }
};

// Public statement. For "unbound" only f and y are used (the #67 statement).
struct CStmt {
  bool bound=false; int f=12; u64 segment=0;
  std::array<i64,3> in_open{}, out_open{};
  std::vector<i64> y;
};
// Witness: x[0..2] history, x[3..6] new inputs, x[7..10] taps (PR #67 layout).
static Circuit conv(const CStmt& st,const std::vector<i64>* wit) {
  Circuit c(wit!=nullptr); const int f=st.f; const i64 S=i64(1)<<f;
  std::vector<Wire> x,w;
  for(int i=0;i<11;i++) {
    auto a=c.cell(wit?wit->at(i):0); c.range(a,f+1,S);
    (i<7?x:w).push_back(a);
  }
  for(int t=0;t<4;t++) {
    std::vector<std::pair<Wire,i64>> products;
    for(int j=0;j<4;j++) products.push_back({c.mul(x[t+j],w[j]),1});
    auto y=c.floor(c.sum(products),f);
    c.range(y,f+4,8*S); c.eq({c.term(y)},st.y.at(t));
  }
  if(st.bound) {
    for(int j=0;j<3;j++) c.eq({c.term(x[j])},st.in_open[j]);      // carried history == verifier opening
    for(int j=0;j<3;j++) c.eq({c.term(x[4+j])},st.out_open[j]);   // outgoing tail == last three inputs
  }
  return c;
}
static void admit(const CStmt& st) {
  need(st.f==12||st.f==14||st.f==16,"F unsupported");
  need(st.y.size()==4,"output count");
  const i64 S=i64(1)<<st.f;
  for(auto y:st.y) need(y>=-8*S&&y<8*S,"output class");
  if(st.bound) {
    for(auto v:st.in_open) need(v>=-S&&v<S,"history opening class");
    for(auto v:st.out_open) need(v>=-S&&v<S,"tail opening class");
  }
}
static Circuit build(const CStmt& st,const std::vector<i64>* wit) {
  admit(st);
  Circuit c=conv(st,wit);
  std::ostringstream p;
  p<<"conv F="<<st.f<<" position=0";
  if(st.bound) {
    p<<" history=bound-v1 segment="<<st.segment<<" in-root="<<hex(tail_root(st.f,st.segment,st.in_open))
     <<" out-root="<<hex(tail_root(st.f,st.segment+1,st.out_open));
  }
  c.profile=p.str();
  return c;
}
static WideRun run_for(const Circuit& c) {
  unsigned L=1;while((u64(1)<<L)<c.cols.size())L++;
  Setting set=setting_goldilocks();set.hash_block_bytes=HASH_BLOCK_BYTES;set.target=10;set.set_work(ErrorKind::QUERY,Scope::REQUEST,6);
  auto run=wide_size(set,L,L+1,L+1,{{1,1,L,L},{0,0,L,L}},c.rel);
  run.product.shape.text += std::string("operator-family ")+(c.profile.find("bound-v1")!=std::string::npos?"qwen-conv-history-bound-v1":"qwen-bounded-integer-v1")+"\nprofile "+c.profile+"\n";
  need(run.product.plan->holds(),"plan refused"); return run;
}
static Table table_for(const Circuit& c) {
  u64 n=2;while(n<c.cols.size())n*=2;Table t(1,3,n);
  for(size_t j=0;j<c.cols.size();j++) for(int r=0;r<3;r++) t.set(r,j,E::from(c.cols[j][r]));
  return t;
}
static E eval(const WideRelation& r,const Table& t) {E v=E::zero();for(auto z:r.terms)v+=E::from(z.coefficient)*t.at(z.row,z.column);return v;}
static size_t violated(const Circuit& c,const Table& t) {size_t n=0;for(auto&r:c.rel)n+=!(eval(r,t)==E::from(r.target));return n;}
static Writer prove(const WideRun& run,const Table& t,bool hostile,u64 seed) {
  EngineCpu engine;ToyCoins coins(seed);Writer proof;Binder b(WIDE_LABEL,run.product.plan);auto in=wide_bind(b,run);
  ProverRounds ch(b,random_digest(coins),proof,[&](const ChainPrefix&p,unsigned bits){return engine.search_nonce(p,bits);});
  ProverContext pr(in.product.codes,ch,engine,coins);FoldMask mask;
  auto g=toy_prove_preamble(pr,in.product,t,mask);auto oracle=pr.st.group(g).members[0];
  for(auto&a:ch.get(in.relations)){auto row=wide_row(oracle,a);if(hostile)row.target=eval(a,t);pr.st.add_row(g,std::move(row));}
  iopp_prove(pr,g,in.product.stages,in.product.choice,std::move(mask));ch.finish();pr.st.require_all_tested();return proof;
}
// Unbound public entry (the #67 statement).
static bool verify_unbound(const CStmt& st,const u8* d,size_t n) {
  try {need(!st.bound,"unbound entry");auto c=build(st,nullptr);return wide_verify(run_for(c),d,n);}catch(const std::exception&){return false;}
}
// Bound public entry. `held` is the root the verifier already owns (genesis or previous accept).
static std::optional<Root> verify_bound(const Root& held,const CStmt& st,const u8* d,size_t n) {
  try {
    need(st.bound,"bound entry");
    admit(st);
    if(tail_root(st.f,st.segment,st.in_open)!=held) return std::nullopt;   // opening must match held root
    auto c=build(st,nullptr);
    if(!wide_verify(run_for(c),d,n)) return std::nullopt;
    return tail_root(st.f,st.segment+1,st.out_open);
  } catch(const std::exception&) { return std::nullopt; }
}

// ---- proving helpers ----
struct Proved { Writer proof; size_t columns=0, relations=0; double prove_s=0; };
static double since(std::chrono::steady_clock::time_point a){return std::chrono::duration<double>(std::chrono::steady_clock::now()-a).count();}
static Proved prove_honest(const CStmt& st,const std::vector<i64>& wit,u64 seed) {
  auto c=build(st,&wit); auto pub=build(st,nullptr);
  Writer a,b; public_bytes(a,c.rel); public_bytes(b,pub.rel); need(a.bytes()==b.bytes(),"witness-dependent relation");
  auto t=table_for(c); need(violated(c,t)==0,"honest relation mismatch");
  auto run=run_for(c); auto s=std::chrono::steady_clock::now(); Proved p; p.proof=prove(run,t,false,seed); p.prove_s=since(s);
  p.columns=c.cols.size(); p.relations=c.rel.size(); return p;
}
// Complete malicious proof: witness `wit` against statement `st`; product gates hold,
// prover-side affine targets are replaced by locally true values. Must violate >=1 relation.
static Writer prove_malicious(const CStmt& st,const std::vector<i64>& wit,u64 seed,size_t& viol) {
  auto c=build(st,&wit); auto t=table_for(c); viol=violated(c,t);
  need(viol>0,"hostile did not violate relation");
  for(u64 j=0;j<t.len;j++) need(t.at(2,j)==t.at(0,j)*t.at(1,j),"hostile product broken");
  return prove(run_for(c),t,true,seed);
}
static std::vector<i64> outputs(const std::vector<i64>& x,int f) {
  std::vector<i64> y; for(int t=0;t<4;t++){i64 num=0;for(int j=0;j<4;j++)num+=x[t+j]*x[7+j];y.push_back(floor2(num,f));} return y;
}

// ---- fixtures ----
// Chain: h0 (3), segment-1 inputs (4), segment-2 inputs (4), taps (4), uniform in [-S,S).
struct Seg2 { int f; std::vector<i64> w1,w2; CStmt s1,s2; Root r0; };
static Seg2 make_chain(int f,int seed) {
  std::mt19937 rng(seed+35000); i64 S=i64(1)<<f; auto r=[&]{return i64(rng()%(2*S))-S;};
  std::vector<i64> h0(3),a(4),b(4),k(4); for(auto&v:h0)v=r(); for(auto&v:a)v=r(); for(auto&v:b)v=r(); for(auto&v:k)v=r();
  Seg2 c; c.f=f;
  c.w1={h0[0],h0[1],h0[2],a[0],a[1],a[2],a[3],k[0],k[1],k[2],k[3]};
  c.w2={a[1],a[2],a[3],b[0],b[1],b[2],b[3],k[0],k[1],k[2],k[3]};
  auto mk=[&](const std::vector<i64>& w,u64 seg){CStmt s;s.bound=true;s.f=f;s.segment=seg;
    for(int j=0;j<3;j++){s.in_open[j]=w[j];s.out_open[j]=w[4+j];} s.y=outputs(w,f); return s;};
  c.s1=mk(c.w1,0); c.s2=mk(c.w2,1); c.r0=tail_root(f,0,c.s1.in_open); return c;
}
// PR #67 history-control construction, verbatim arithmetic from qwen_ops/proof.cpp.
static void c67(int seed,std::vector<i64>& orig,std::vector<i64>& repl,int f=12) {
  std::mt19937 rng(seed); i64 S=i64(1)<<f; orig.clear();
  for(int i=0;i<11;i++) orig.push_back(i64(rng()%(2*S))-S);
  for(int j=0;j<7;j++) orig[j]/=2;
  for(int j=7;j<11;j++) orig[j]=S/2;
  repl=orig; repl[0]++; repl[1]--; repl[4]++; repl[5]--;
}

// ---- report ----
static int total=0, bad=0;
static void out(const std::string& arm,const std::string& sub,int seed,bool accepted,bool expect_accept,const std::string& extra="") {
  total++; bool ok=accepted==expect_accept; bad+=!ok;
  std::cout<<"{\"arm\":\""<<arm<<"\",\"sub\":\""<<sub<<"\",\"seed\":"<<seed<<",\"accepted\":"<<(accepted?"true":"false")
           <<",\"expected_accept\":"<<(expect_accept?"true":"false")<<",\"as_registered\":"<<(ok?"true":"false")<<extra<<"}"<<std::endl;
}
static std::string vstr(size_t v){return ",\"complete_proof\":true,\"violations\":"+std::to_string(v);}

static void suite(int seed) {
  const int f=12; const u64 s=u64(seed);
  // honest-chain, plus descriptive sizes and times
  auto ch=make_chain(f,seed);
  auto p1=prove_honest(ch.s1,ch.w1,s), p2=prove_honest(ch.s2,ch.w2,s+1);
  auto t0=std::chrono::steady_clock::now(); auto r1=verify_bound(ch.r0,ch.s1,p1.proof.data(),p1.proof.size()); double v1=since(t0);
  bool chain_ok=r1.has_value() && *r1==tail_root(f,1,ch.s2.in_open);
  std::optional<Root> r2; if(r1) r2=verify_bound(*r1,ch.s2,p2.proof.data(),p2.proof.size());
  chain_ok=chain_ok&&r2.has_value();
  {std::ostringstream e; e<<",\"columns\":"<<p1.columns<<",\"relations\":"<<p1.relations<<",\"proof_bytes\":"<<p1.proof.size()<<",\"prove_s\":"<<p1.prove_s<<",\"verify_s\":"<<v1;
   out("honest-chain","two-segment",seed,chain_ok,true,e.str());}
  // unbound descriptive sizes for the same segment-1 witness
  {CStmt u; u.f=f; u.y=ch.s1.y; auto pu=prove_honest(u,ch.w1,s);
   auto t=std::chrono::steady_clock::now(); bool a=verify_unbound(u,pu.proof.data(),pu.proof.size()); double vu=since(t);
   std::ostringstream e; e<<",\"columns\":"<<pu.columns<<",\"relations\":"<<pu.relations<<",\"proof_bytes\":"<<pu.proof.size()<<",\"prove_s\":"<<pu.prove_s<<",\"verify_s\":"<<vu;
   out("honest-unbound","segment-1",seed,a,true,e.str());}

  // c67 negative control on the unbound profile
  std::vector<i64> o,rp; c67(seed,o,rp,f);
  auto yo=outputs(o,f), yr=outputs(rp,f); need(yo==yr,"c67 construction must preserve outputs");
  {CStmt u; u.f=f; u.y=yo;
   auto pa=prove_honest(u,o,s), pb=prove_honest(u,rp,s);
   out("c67-unbound","original",seed,verify_unbound(u,pa.proof.data(),pa.proof.size()),true);
   out("c67-unbound","replacement",seed,verify_unbound(u,pb.proof.data(),pb.proof.size()),true);}
  // c67 against the bound profile; verifier holds the original history's root
  {auto mk=[&](const std::vector<i64>& w){CStmt b;b.bound=true;b.f=f;b.segment=0;for(int j=0;j<3;j++){b.in_open[j]=w[j];b.out_open[j]=w[4+j];}b.y=yo;return b;};
   CStmt so=mk(o), sr=mk(rp); Root held=tail_root(f,0,so.in_open);
   auto po=prove_honest(so,o,s);
   out("c67-bound","original-accepted",seed,verify_bound(held,so,po.proof.data(),po.proof.size()).has_value(),true);
   auto pr=prove_honest(sr,rp,s);
   out("c67-bound","a-replacement-own-opening",seed,verify_bound(held,sr,pr.proof.data(),pr.proof.size()).has_value(),false);
   size_t v; auto pm=prove_malicious(so,rp,s+1000,v);
   out("c67-bound","b-replacement-under-original-opening",seed,verify_bound(held,so,pm.data(),pm.size()).has_value(),false,vstr(v));}

  Root r1true=tail_root(f,1,ch.s2.in_open);
  // tail-splice: segment 2 from zero history instead of segment 1's tail
  {auto w=ch.w2; w[0]=w[1]=w[2]=0; CStmt z=ch.s2; z.in_open={0,0,0}; z.y=outputs(w,f);
   auto pz=prove_honest(z,w,s+2);
   out("tail-splice","statement-zero-opening",seed,verify_bound(r1true,z,pz.proof.data(),pz.proof.size()).has_value(),false);
   CStmt zs=z; zs.in_open=ch.s2.in_open; size_t v; auto pm=prove_malicious(zs,w,s+1002,v);
   out("tail-splice","malicious-under-true-opening",seed,verify_bound(r1true,zs,pm.data(),pm.size()).has_value(),false,vstr(v));}
  // out-tail-lie: segment 1 publishes an outgoing opening that is not its last three inputs
  {CStmt l=ch.s1; l.out_open[0]=(l.out_open[0]+1<(i64(1)<<f))?l.out_open[0]+1:l.out_open[0]-1;
   out("out-tail-lie","honest-proof-lying-statement",seed,verify_bound(ch.r0,l,p1.proof.data(),p1.proof.size()).has_value(),false);
   size_t v; auto pm=prove_malicious(l,ch.w1,s+1003,v);
   out("out-tail-lie","malicious-lying-statement",seed,verify_bound(ch.r0,l,pm.data(),pm.size()).has_value(),false,vstr(v));}
  // history-reorder: segment 2 witness uses the carried tail reversed
  {auto w=ch.w2; std::swap(w[0],w[2]); CStmt rs=ch.s2; rs.y=outputs(w,f);
   if(w==ch.w2) { std::cout<<"{\"arm\":\"history-reorder\",\"sub\":\"not-applicable-palindrome\",\"seed\":"<<seed<<"}"<<std::endl; }
   else {
     CStmt ro=rs; std::swap(ro.in_open[0],ro.in_open[2]); auto pr=prove_honest(ro,w,s+4);
     out("history-reorder","statement-reordered-opening",seed,verify_bound(r1true,ro,pr.proof.data(),pr.proof.size()).has_value(),false);
     size_t v; auto pm=prove_malicious(rs,w,s+1004,v);
     out("history-reorder","malicious-under-true-opening",seed,verify_bound(r1true,rs,pm.data(),pm.size()).has_value(),false,vstr(v));
   }}
  // cross-scale-root: root computed with F14 over the same words, offered to the F12 chain
  {Root r14=tail_root(14,1,ch.s2.in_open);
   out("cross-scale-root","f14-root-held-by-f12-verifier",seed,verify_bound(r14,ch.s2,p2.proof.data(),p2.proof.size()).has_value(),false);
   CStmt s14=ch.s2; s14.f=14; // F14 statement with F12 proof
   out("cross-scale-root","f12-proof-f14-statement",seed,verify_bound(r14,s14,p2.proof.data(),p2.proof.size()).has_value(),false);}
  // proof-transplant: segment 1 proof with segment 2 statement (and vice versa)
  out("proof-transplant","p1-with-s2",seed,verify_bound(r1true,ch.s2,p1.proof.data(),p1.proof.size()).has_value(),false);
  out("proof-transplant","p2-with-s1",seed,verify_bound(ch.r0,ch.s1,p2.proof.data(),p2.proof.size()).has_value(),false);
  // segment-replay: segment 1 again when the verifier holds R1; also with relabelled segment index
  out("segment-replay","s1-again",seed,verify_bound(r1true,ch.s1,p1.proof.data(),p1.proof.size()).has_value(),false);
  // Relabelled index: the verifier is given a root that matches the relabelled opening, so only
  // the proof's own binding of the segment index (configuration text) can reject it.
  {CStmt rl=ch.s1; rl.segment=1;
   out("segment-replay","s1-relabelled-index-proof-bound",seed,verify_bound(tail_root(f,1,rl.in_open),rl,p1.proof.data(),p1.proof.size()).has_value(),false);}
  std::cout<<"{\"arm\":\"summary\",\"seed\":"<<seed<<",\"checks\":"<<total<<",\"not_as_registered\":"<<bad<<"}"<<std::endl;
}

int main(int argc,char**argv) { try {
  need(argc==3&&std::string(argv[1])=="suite","usage: conv_history.bin suite <seed>");
  suite(std::stoi(argv[2]));
  return bad==0?0:1;
} catch(const std::exception&e) { std::cerr<<"error: "<<e.what()<<std::endl; return 2; } }
