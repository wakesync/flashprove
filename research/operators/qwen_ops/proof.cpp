// SPDX-License-Identifier: Apache-2.0
// Research-only committed-oracle relations, not a production verifier or a model proof.
#include <chrono>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "../qwen_deltanet/product.h"
#include "tables/pinned.h"
using namespace blk;
static void need(bool b,const char* msg) { if(!b) throw std::runtime_error(msg); }
static F fi(i64 x) { return x>=0 ? F{u64(x)} : F{P-u64(-x)}; }
static i64 floor2(i64 x,unsigned k) { i64 d=i64(1)<<k; return x/d - (x%d<0); }
struct Wire { u64 c; unsigned r; i64 v; };
struct Circuit {
  bool witness;
  std::vector<std::array<F,3>> cols;
  std::vector<WideRelation> rel;
  std::map<std::string,Wire> attacks;
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
  // Return a linear combination using bounded fan-in sums. All coefficients public.
  Wire sum(const std::vector<std::pair<Wire,i64>>& ts,i64 constant=0) {
    if(ts.size()>120) {
      std::vector<std::pair<Wire,i64>> small;
      for(size_t j=0;j<ts.size();j+=120) {
        std::vector<std::pair<Wire,i64>> chunk(ts.begin()+j,ts.begin()+std::min(ts.size(),j+120));
        small.push_back({sum(chunk),1});
      }
      return sum(small,constant);
    }
    i64 val=constant;
    if(witness) for(auto &t:ts) val+=t.first.v*t.second;
    auto out=cell(val); std::vector<AffineTerm> a{term(out)};
    for(auto &t:ts) a.push_back(term(t.first,-t.second));
    eq(a,constant); return out;
  }
  void range(Wire a,unsigned bits,i64 offset=0) {
    i64 n=witness?a.v+offset:0;
    need(!witness || (n>=0 && n<(i64(1)<<bits)),"range witness");
    std::vector<AffineTerm> t{term(a)};
    for(unsigned j=0;j<bits;j++) t.push_back(term(bit((n>>j)&1),-(i64(1)<<j)));
    eq(t,-offset);
  }
  Wire floor(Wire a,unsigned bits,const std::string& tag) {
    i64 q=witness?floor2(a.v,bits):0;
    auto out=cell(q); auto rem=cell(witness?a.v-q*(i64(1)<<bits):0);
    range(rem,bits); eq({term(a),term(out,-(i64(1)<<bits)),term(rem,-1)});
    if(!tag.empty()) {attacks[tag+"-quotient"]=out; attacks[tag+"-remainder"]=rem;}
    return out;
  }
  std::vector<Wire> selectors(Wire key) {
    need(!witness || (key.v>=0 && key.v<4096),"lookup domain");
    std::vector<Wire> sel; std::vector<std::pair<Wire,i64>> count,index;
    for(int i=0;i<4096;i++) {auto b=bit(key.v==i);sel.push_back(b);count.push_back({b,1});index.push_back({b,i});}
    eq({term(sum(count))},1); eq({term(sum(index)),term(key,-1)});
    attacks["selector"]=sel[witness?size_t(key.v):0];
    return sel;
  }
  Wire lookup(const std::vector<Wire>& sel,const int64_t* table) {
    std::vector<std::pair<Wire,i64>> ts;
    for(int i=0;i<4096;i++) ts.push_back({sel[i],table[i]});
    return sum(ts);
  }
};
static const int64_t* table(int op,int f) {
#define TABLESET(FB) {qtables::silu_f##FB, qtables::sigmoid_f##FB, qtables::softplus_f##FB, qtables::decay_half_f##FB, qtables::decay_one_f##FB, qtables::decay_two_f##FB, qtables::rsqrt_f##FB, qtables::l2_128_f##FB}
  static const int64_t* all[3][8]={TABLESET(12),TABLESET(14),TABLESET(16)};
  return all[(f-12)/2][op];
}
struct Input {int f=12; std::string op; std::vector<i64> x,y;};
static Circuit nonlinear(const Input& in,bool witness) {
  Circuit c(witness); int f=in.f; i64 step=i64(1)<<(f-8);
  auto x=c.cell(witness?in.x.at(0):0); c.attacks["input"]=x;
  auto q=c.floor(x,f-8,"grid"); auto key=c.sum({{q,1}},2048);
  auto sel=c.selectors(key);
  for(int i=0;i<6;i++) {auto y=c.lookup(sel,table(i,f)); c.eq({c.term(y)},in.y.at(i)); if(i==0)c.attacks["output"]=y;}
  (void)step;
  return c;
}
// One depthwise channel, T=4. x[0..2] is committed incoming history;
// x[3..6] is the four new inputs. Every use reads the same canonical cell.
static Circuit conv(const Input& in,bool witness) {
  Circuit c(witness); const int f=in.f; const i64 S=i64(1)<<f;
  std::vector<Wire> x,w;
  for(int i=0;i<11;i++) {
    auto a=c.cell(witness?in.x.at(i):0); c.range(a,f+1,S);
    (i<7?x:w).push_back(a);
  }
  c.attacks["input"]=x[0];
  for(int t=0;t<4;t++) {
    std::vector<std::pair<Wire,i64>> products;
    for(int j=0;j<4;j++) {
      auto p=c.mul(x[t+j],w[j]); products.push_back({p,1});
      if(t==0&&j==0) c.attacks["history-use"]={p.c,0,x[0].v};
    }
    auto y=c.floor(c.sum(products),f,t==0?"grid":"");
    c.range(y,f+4,8*S); c.eq({c.term(y)},in.y.at(t));
    if(t==0)c.attacks["output"]=y;
  }
  return c;
}
// One head. No gain, epsilon or additional q scale is silently supplied.
static Circuit norm(const Input& in,bool witness) {
  Circuit c(witness); const int f=in.f; const i64 S=i64(1)<<f;
  const int D=in.op=="l2"?128:256, logD=in.op=="l2"?7:8;
  std::vector<Wire> x; std::vector<std::pair<Wire,i64>> squares;
  for(int j=0;j<D;j++) {
    auto v=c.cell(witness?in.x.at(j):0);c.range(v,f+1,S);x.push_back(v);
    squares.push_back({c.mul(v,v),1});
  }
  c.attacks["input"]=x[0];
  auto mean_key=c.floor(c.sum(squares),2*f+logD-10,"energy");
  auto key=c.sum({{mean_key,1}},-256);
  auto sel=c.selectors(key);
  auto coefficient=c.lookup(sel,table(in.op=="l2"?7:6,f));
  c.attacks["table-output"]=coefficient;
  for(int j=0;j<D;j++) {
    auto y=c.floor(c.mul(x[j],coefficient),f,j==0?"grid":"");
    c.range(y,f+3,4*S); c.eq({c.term(y)},in.y.at(j));
    if(j==0)c.attacks["output"]=y;
  }
  return c;
}
// The public verifier dispatch is closed to a fixed operator set.
static Circuit build(const Input& in,bool witness) {
  need(in.f==12||in.f==14||in.f==16,"F unsupported");
  need(in.op=="nonlinear"||in.op=="conv"||in.op=="l2"||in.op=="rms","operator unsupported");
  size_t outputs=in.op=="nonlinear"?6:in.op=="conv"?4:in.op=="l2"?128:256;
  need(in.y.size()==outputs,"output count");
  for(auto y:in.y) need(y>=-(i64(8)<<in.f)&&y<(i64(9)<<in.f),"output class");
  if(in.op=="nonlinear")return nonlinear(in,witness);
  if(in.op=="conv")return conv(in,witness);
  return norm(in,witness);
}
static WideRun run_for(const Circuit& c) {
  unsigned L=1;while((u64(1)<<L)<c.cols.size())L++;
  Setting set=setting_goldilocks();set.hash_block_bytes=HASH_BLOCK_BYTES;set.target=10;set.set_work(ErrorKind::QUERY,Scope::REQUEST,6);
  auto run=wide_size(set,L,L+1,L+1,{{1,1,L,L},{0,0,L,L}},c.rel);
  // Different shape text changes the configuration digest, separating this harness from M1.
  run.product.shape.text += "operator-family qwen-bounded-integer-v1\n";
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
// This is the public entry: relation list is always verifier-owned and witness-free.
static bool verify(const Input& statement,const u8* data,size_t n) {
  try {auto c=build(statement,false);auto run=run_for(c);return wide_verify(run,data,n);}catch(const std::exception&){return false;}
}
static double elapsed(std::chrono::steady_clock::time_point a) {return std::chrono::duration<double>(std::chrono::steady_clock::now()-a).count();}
static Input fixture(std::string op,int f,int seed) {
  Input in;in.op=op;in.f=f;std::mt19937 rng(seed);i64 S=i64(1)<<f;
  if(op=="nonlinear") {
    in.x={i64(rng()%(16*S))-8*S};int key=int(floor2(in.x[0],f-8)+2048);
    for(int j=0;j<6;j++) in.y.push_back(table(j,f)[key]);
  } else if(op=="conv") {
    for(int i=0;i<11;i++)in.x.push_back(i64(rng()%(2*S))-S);
    for(int t=0;t<4;t++) {i64 num=0;for(int j=0;j<4;j++)num+=in.x[t+j]*in.x[7+j];in.y.push_back(floor2(num,f));}
  } else if(op=="l2"||op=="rms") {
    const int D=op=="l2"?128:256, logD=op=="l2"?7:8;
    i64 energy=0;
    for(int j=0;j<D;j++){i64 v=i64(rng()%(2*S))-S;in.x.push_back(v);energy+=v*v;}
    i64 key=floor2(energy,2*f+logD-10)-256;need(key>=0&&key<4096,"fixture norm domain");
    i64 coefficient=table(op=="l2"?7:6,f)[key];
    for(auto v:in.x)in.y.push_back(floor2(v*coefficient,f));
  }
  return in;
}
static void setrow(Table&t,Wire w,E v) {
  if(w.r==0){t.set(0,w.c,v);t.set(2,w.c,v*t.at(1,w.c));}
  else if(w.r==1){t.set(1,w.c,v);t.set(2,w.c,t.at(0,w.c)*v);}
  else throw std::runtime_error("attack row must be operand");
}
int main(int argc,char**argv) {try {
  need(argc==5,"usage: proof.bin nonlinear F seed honest|hostile");
  std::string mode=argv[4];int seed=std::stoi(argv[3]);auto in=fixture(argv[1],std::stoi(argv[2]),seed);
  auto c=build(in,true);auto public_c=build(in,false);Writer a,b;public_bytes(a,c.rel);public_bytes(b,public_c.rel);need(a.bytes()==b.bytes(),"witness-dependent relation");
  auto t=table_for(c);need(violated(c,t)==0,"honest relation mismatch");auto run=run_for(c);
  auto start=std::chrono::steady_clock::now();auto proof=prove(run,t,false,seed);double ps=elapsed(start);
  Input statement=in;statement.x.clear();start=std::chrono::steady_clock::now();bool ok=verify(statement,proof.data(),proof.size());double vs=elapsed(start);
  std::cout<<"{\"mode\":\"honest\",\"op\":\""<<in.op<<"\",\"F\":"<<in.f<<",\"seed\":"<<seed<<",\"accept\":"<<(ok?"true":"false")<<",\"columns\":"<<c.cols.size()<<",\"relations\":"<<c.rel.size()<<",\"proof_bytes\":"<<proof.size()<<",\"prove_s\":"<<ps<<",\"verify_s\":"<<vs<<"}"<<std::endl;need(ok,"honest rejected");
  if(mode!="hostile")return 0;
  int total=0,rejected=0;
  auto report=[&](std::string name,bool accepted,size_t violations,bool complete){total++;rejected+=!accepted;std::cout<<"{\"mode\":\"hostile\",\"op\":\""<<in.op<<"\",\"class\":\""<<name<<"\",\"complete_proof\":"<<(complete?"true":"false")<<",\"violations\":"<<violations<<",\"rejected\":"<<(accepted?"false":"true")<<"}"<<std::endl;};
  auto attack=[&](std::string name,std::function<void(Table&)> change){Table bad=t;change(bad);size_t v=violated(c,bad);need(v>0,"hostile did not violate relation");for(u64 j=0;j<bad.len;j++)need(bad.at(2,j)==bad.at(0,j)*bad.at(1,j),"hostile product broken");auto p=prove(run,bad,true,seed+1000);report(name,verify(statement,p.data(),p.size()),v,true);};
  Wire x=c.attacks.at("input"),y=c.attacks.at("output"),q=c.attacks.at("grid-quotient"),r=c.attacks.at("grid-remainder");
  if(in.op=="nonlinear")
    attack("wrong-table-row",[&](Table&z){setrow(z,q,z.at(q.r,q.c)+E::one());});
  if(in.op=="conv") {
    auto h=c.attacks.at("history-use");
    attack("wrong-history-use",[&](Table&z){setrow(z,h,z.at(h.r,h.c)+E::one());});
  }
  if(in.op=="l2"||in.op=="rms") {
    auto coeff=c.attacks.at("table-output");auto e=c.attacks.at("energy-quotient");
    attack("wrong-table-row",[&](Table&z){setrow(z,coeff,z.at(coeff.r,coeff.c)+E::one());});
    attack("mean-square-out-of-domain",[&](Table&z){setrow(z,e,E::from(fi(255)));});
  }
  attack("out-of-domain",[&](Table&z){setrow(z,x,E::from(fi((in.op=="nonlinear"?i64(8):i64(1))<<in.f)));});
  const int remainder_bits=in.op=="nonlinear"?in.f-8:in.f;
  attack("rounding-plus-one-compensated",[&](Table&z){setrow(z,q,z.at(q.r,q.c)+E::one());setrow(z,r,z.at(r.r,r.c)-E::from(fi(i64(1)<<remainder_bits)));});
  attack("sign-flip",[&](Table&z){setrow(z,x,E::zero()-z.at(x.r,x.c));});
  attack("wrong-output",[&](Table&z){setrow(z,y,z.at(y.r,y.c)+E::one());});
  auto changed=statement;changed.y[0]++;report("public-output",verify(changed,proof.data(),proof.size()),0,false);
  changed=statement;changed.f=14;report("scale-replay",verify(changed,proof.data(),proof.size()),0,false);
  auto bytes=proof.bytes();bytes[bytes.size()/2]^=1;report("byte-flip",verify(statement,bytes.data(),bytes.size()),0,false);
  report("truncated",verify(statement,proof.data(),proof.size()-1),0,false);
  bytes=proof.bytes();bytes.push_back(0);report("trailing",verify(statement,bytes.data(),bytes.size()),0,false);
  std::cout<<"{\"mode\":\"summary\",\"rejected\":"<<rejected<<",\"total\":"<<total<<"}"<<std::endl;return total==rejected?0:1;
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
