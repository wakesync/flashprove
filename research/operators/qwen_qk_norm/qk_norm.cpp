// SPDX-License-Identifier: Apache-2.0
// Research-only: issue #35, per-head q/k RMSNorm (epsilon, learned per-channel gain) as proof
// constraints on the bounded affine product oracle of PR #67. Not a production verifier and not a
// model proof. See README.md in this directory and experiments/20261111-35-qk-rmsnorm/PREREG.md.
//
// Statement (public): F=12, D in {16,256}, Hq=2 q heads, Hk=1 k head, pre-norm integers x[h][j] in
// [-S,S) (S=2^F), q gains gq[j] and k gains gk[j] at scale 2^F with |g| < 2^(F+3), outputs y[h][j]
// with |y| < 2^(F+D2+4) where D2 = log2(D)/2. Heads 0..Hq-1 are q (gains gq), Hq.. are k (gains gk).
// Verifier constants: m=8, K=45, s=K-F-m-D2, epsN=round(4^m*D*1e-6*2^(2F)).
// Relation per head:
//   E = sum_j x_j^2
//   sigma = isqrt(4^m E + epsN):   e1 = 4^m E + epsN - sigma^2 >= 0,  e2 = sigma^2 + 2 sigma - 4^m E - epsN >= 0
//   R = floor(2^K / sigma):        R sigma + rr = 2^K,  0 <= rr,  sigma - 1 - rr >= 0
//   Z_j = floor(x_j R / 2^s):      x_j R = 2^s Z_j + rz_j,  0 <= rz_j < 2^s,  Z_j signed range
//   y_j = floor(g_j Z_j / 2^F):    g_j Z_j - ry_j = 2^F y_j,  0 <= ry_j < 2^F
// so y_j ~= g_j * x_j / sqrt(mean(x^2) + 1e-6 * S^2) at scale 2^F (RMSNorm with weight g).
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "../qwen_deltanet/product.h"
using namespace blk;
static void need(bool b,const char* msg) { if(!b) throw std::runtime_error(msg); }
static F fi(i64 x) { need(x!=std::numeric_limits<i64>::min(),"i64 min"); return x>=0 ? F{u64(x)} : F{P-u64(-x)}; }
static i64 floor_div(i64 a,i64 d) { i64 q=a/d; if((a%d!=0)&&((a<0)!=(d<0))) q--; return q; }
static i64 floor2(i64 x,unsigned k) { return floor_div(x,i64(1)<<k); }
static i64 isqrt64(i64 n) {
  need(n>=0,"isqrt negative");
  i64 r=i64(std::sqrt((long double)n));
  while(r>0 && r*r>n) r--;
  while((r+1)*(r+1)<=n) r++;
  return r;
}

// ---- verifier-pinned constants ----
constexpr int FB=12, HQ=2, HK=1, M=8, K=45, SIGMA_BITS=25, E_BITS=26, R_BITS=34;
struct Params { int D, D2, s; i64 epsN; };
static Params params(int D) {
  need(D==16||D==256,"D unsupported");
  Params p; p.D=D; p.D2=(D==16?2:4); p.s=K-FB-M-p.D2;
  // epsN = round(4^M * D * 1e-6 * 2^(2F)) = round(D * 2^40 / 10^6), exact integer rounding
  const i64 num=i64(D)*(i64(1)<<(2*M+2*FB)); p.epsN=(num+500000)/1000000;
  return p;
}

// ---- circuit ----
struct Wire { u64 c; unsigned r; };
struct Circuit {
  bool witness; std::string profile;
  std::vector<std::array<F,3>> cols; std::vector<WideRelation> rel;
  explicit Circuit(bool w):witness(w) {}
  AffineTerm term(Wire x,i64 k=1) { return {x.r,x.c,fi(k)}; }
  void eq(std::vector<AffineTerm> ts,i64 rhs=0) { rel.push_back({std::move(ts),fi(rhs)}); }
  Wire cell(i64 x) { if(!witness) x=0; u64 c=cols.size(); cols.push_back({fi(x),F{0},F{0}}); return {c,0}; }
  // product gate (a, b, a*b); returns column index. Operands are linked by the caller.
  u64 gate(i64 a,i64 b) { if(!witness) a=b=0; u64 c=cols.size(); cols.push_back({fi(a),fi(b),fi(a)*fi(b)}); return c; }
  Wire bit(i64 v) {
    if(!witness) v=0;
    u64 c=cols.size(); cols.push_back({fi(v),fi(v),fi(v)*fi(v)});
    eq({{0,c,F{1}},{1,c,fi(-1)}}); eq({{2,c,F{1}},{0,c,fi(-1)}});
    return {c,0};
  }
  // a + offset in [0, 2^bits). A hostile out-of-range value still gets bits (low bits of its
  // two's complement), so every product gate holds and only the reconstruction fails.
  void range(Wire a,i64 aval,unsigned bits,i64 offset=0) {
    u64 n=witness?u64(aval)+u64(offset):0;
    std::vector<AffineTerm> t{term(a)};
    for(unsigned j=0;j<bits;j++) t.push_back(term(bit(i64((n>>j)&1)),-(i64(1)<<j)));
    eq(t,-offset);
  }
  // out = sum_i w_i * coef_i, bounded fan-in (<= 120 terms per relation).
  Wire sum(const std::vector<std::pair<Wire,i64>>& ts,const std::vector<i64>& vals) {
    if(ts.size()>120) {
      std::vector<std::pair<Wire,i64>> small; std::vector<i64> sv;
      for(size_t j=0;j<ts.size();j+=120) {
        size_t e=std::min(ts.size(),j+120);
        std::vector<std::pair<Wire,i64>> ch(ts.begin()+j,ts.begin()+e); std::vector<i64> cv(vals.begin()+j,vals.begin()+e);
        i64 v=0; for(size_t i=0;i<ch.size();i++) v+=cv[i]*ch[i].second;
        small.push_back({sum(ch,cv),1}); sv.push_back(v);
      }
      return sum(small,sv);
    }
    i64 v=0; for(size_t i=0;i<ts.size();i++) v+=vals[i]*ts[i].second;
    auto out=cell(v); std::vector<AffineTerm> a{term(out)};
    for(auto &t:ts) a.push_back(term(t.first,-t.second));
    eq(a,0); return out;
  }
};

struct Stmt { int f=FB, D=16; std::vector<std::vector<i64>> x; std::vector<i64> gq, gk; std::vector<std::vector<i64>> y; };
struct HeadWit { std::vector<i64> x, g, Z, y; i64 sigma=0, R=0; };

static void admit(const Stmt& st) {
  need(st.f==FB,"F unsupported");
  auto p=params(st.D); const i64 S=i64(1)<<st.f, GB=i64(1)<<(st.f+3), YB=i64(1)<<(st.f+p.D2+4);
  need(st.x.size()==size_t(HQ+HK)&&st.y.size()==size_t(HQ+HK),"head count");
  need(st.gq.size()==size_t(st.D)&&st.gk.size()==size_t(st.D),"gain length");
  for(auto g:st.gq) need(g>-GB&&g<GB,"q gain bound");
  for(auto g:st.gk) need(g>-GB&&g<GB,"k gain bound");
  for(int h=0;h<HQ+HK;h++) {
    need(st.x[h].size()==size_t(st.D)&&st.y[h].size()==size_t(st.D),"head dim");
    for(auto v:st.x[h]) need(v>=-S&&v<S,"input class");
    for(auto v:st.y[h]) need(v>-YB&&v<YB,"output class");
  }
}

// Builds the relation list (witness-free if wit==nullptr). All targets and coefficients come from
// the statement and the pinned constants; the witness only fills cell values.
static Circuit build(const Stmt& st,const std::vector<HeadWit>* wit) {
  admit(st);
  const auto p=params(st.D); const int f=st.f, D=st.D; const bool W=wit!=nullptr;
  Circuit c(W);
  const i64 four_m=i64(1)<<(2*M), twoK=i64(1)<<K, twoS=i64(1)<<p.s, twoF=i64(1)<<f;
  const unsigned zbits=unsigned(f+p.D2+2); const i64 zoff=i64(1)<<(f+p.D2+1);
  for(int h=0;h<HQ+HK;h++) {
    const auto& g=h<HQ?st.gq:st.gk;
    HeadWit w; if(W) w=wit->at(h); else { w.x.assign(D,0); w.g.assign(D,0); w.Z.assign(D,0); w.y.assign(D,0); }
    // inputs: gate (x, x, x^2), row 0 pinned to the public x, row 1 tied to row 0
    std::vector<u64> xg; std::vector<std::pair<Wire,i64>> sq; std::vector<i64> sqv;
    for(int j=0;j<D;j++) {
      u64 a=c.gate(w.x[j],w.x[j]); xg.push_back(a);
      c.eq({{0,a,F{1}}},st.x[h][j]);
      c.eq({{1,a,F{1}},{0,a,fi(-1)}});
      sq.push_back({{a,2},1}); sqv.push_back(w.x[j]*w.x[j]);
    }
    i64 E=0; for(auto v:sqv) E+=v;
    auto Ec=c.sum(sq,sqv);
    // sigma: gate (sigma, sigma, sigma^2), range SIGMA_BITS
    u64 ss=c.gate(w.sigma,w.sigma);
    c.eq({{1,ss,F{1}},{0,ss,fi(-1)}});
    c.range({ss,0},w.sigma,SIGMA_BITS);
    const i64 N=four_m*E+p.epsN;
    const i64 e1=N-w.sigma*w.sigma, e2=w.sigma*w.sigma+2*w.sigma-N;
    auto e1c=c.cell(e1); c.range(e1c,e1,E_BITS);
    auto e2c=c.cell(e2); c.range(e2c,e2,E_BITS);
    c.eq({c.term(Ec,four_m),{2,ss,fi(-1)},c.term(e1c,-1)},-p.epsN);          // 4^m E + epsN - sigma^2 = e1
    c.eq({{2,ss,F{1}},{0,ss,fi(2)},c.term(Ec,-four_m),c.term(e2c,-1)},p.epsN);  // sigma^2 + 2 sigma - 4^m E - epsN = e2
    // R: gate (R, sigma, R sigma), range R_BITS
    u64 rs=c.gate(w.R,w.sigma);
    c.eq({{1,rs,F{1}},{0,ss,fi(-1)}});
    c.range({rs,0},w.R,R_BITS);
    const i64 rr=twoK-w.R*w.sigma, gap=w.sigma-1-rr;
    auto rrc=c.cell(rr); c.range(rrc,rr,SIGMA_BITS);
    auto gpc=c.cell(gap); c.range(gpc,gap,SIGMA_BITS);
    c.eq({{2,rs,F{1}},c.term(rrc)},twoK);                         // R sigma + rr = 2^K
    c.eq({{0,ss,F{1}},c.term(rrc,-1),c.term(gpc,-1)},1);          // sigma - 1 - rr = gap
    for(int j=0;j<D;j++) {
      u64 xr=c.gate(w.x[j],w.R);
      c.eq({{0,xr,F{1}},{0,xg[j],fi(-1)}});
      c.eq({{1,xr,F{1}},{0,rs,fi(-1)}});
      const i64 rz=w.x[j]*w.R-twoS*w.Z[j];
      auto Zc=c.cell(w.Z[j]); c.range(Zc,w.Z[j],zbits,zoff);
      auto rzc=c.cell(rz); c.range(rzc,rz,unsigned(p.s));
      c.eq({{2,xr,F{1}},c.term(Zc,-twoS),c.term(rzc,-1)});         // x R = 2^s Z + rz
      const i64 ry=w.g[j]*w.Z[j]-twoF*w.y[j];
      auto ryc=c.cell(ry); c.range(ryc,ry,unsigned(f));
      c.eq({c.term(Zc,g[j]),c.term(ryc,-1)},twoF*st.y[h][j]);       // g Z - ry = 2^F y (g, y public)
    }
  }
  std::ostringstream pr;
  pr<<"qk-rmsnorm F="<<f<<" D="<<D<<" Hq="<<HQ<<" Hk="<<HK<<" m="<<M<<" K="<<K<<" s="<<p.s<<" epsN="<<p.epsN;
  c.profile=pr.str();
  return c;
}
static WideRun run_for(const Circuit& c) {
  unsigned L=1;while((u64(1)<<L)<c.cols.size())L++;
  Setting set=setting_goldilocks();set.hash_block_bytes=HASH_BLOCK_BYTES;set.target=10;set.set_work(ErrorKind::QUERY,Scope::REQUEST,6);
  auto run=wide_size(set,L,L+1,L+1,{{1,1,L,L},{0,0,L,L}},c.rel);
  run.product.shape.text+="operator-family qwen-qk-rmsnorm-v1\nprofile "+c.profile+"\n";
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
// Public entry: witness-free derivation from the statement only.
static bool verify(const Stmt& st,const u8* d,size_t n) {
  try { auto c=build(st,nullptr); return wide_verify(run_for(c),d,n); } catch(const std::exception&) { return false; }
}

// ---- witness ----
static void from_Z(HeadWit& w,int f) { for(size_t j=0;j<w.x.size();j++) w.y[j]=floor2(w.g[j]*w.Z[j],unsigned(f)); }
static void from_R(HeadWit& w,const Params& p,int f) { for(size_t j=0;j<w.x.size();j++) w.Z[j]=floor2(w.x[j]*w.R,unsigned(p.s)); from_Z(w,f); }
static void from_sigma(HeadWit& w,const Params& p,int f) { w.R=w.sigma>0?(i64(1)<<K)/w.sigma:0; from_R(w,p,f); }
static i64 energy(const std::vector<i64>& x) { i64 e=0; for(auto v:x) e+=v*v; return e; }
static HeadWit honest_head(const std::vector<i64>& x,const std::vector<i64>& g,const Params& p,int f) {
  HeadWit w; w.x=x; w.g=g; w.Z.assign(x.size(),0); w.y.assign(x.size(),0);
  w.sigma=isqrt64((i64(1)<<(2*M))*energy(x)+p.epsN); from_sigma(w,p,f); return w;
}
static std::vector<HeadWit> honest_wit(const Stmt& st) {
  auto p=params(st.D); std::vector<HeadWit> w;
  for(int h=0;h<HQ+HK;h++) w.push_back(honest_head(st.x[h],h<HQ?st.gq:st.gk,p,st.f));
  return w;
}

// ---- fixtures ----
static const char* DISTS[]={"uniform","outlier","low","unit-spike","zero"};
static Stmt fixture(int D,int seed,const std::string& dist) {
  int di=0; while(DISTS[di]!=dist) di++;
  std::mt19937_64 rng(u64(seed)*1000003ULL+u64(D)*101ULL+u64(di));
  const i64 S=i64(1)<<FB;
  auto uni=[&](i64 lo,i64 hi){ return lo+i64(rng()%u64(hi-lo)); };  // [lo,hi)
  Stmt st; st.D=D; st.x.assign(HQ+HK,std::vector<i64>(D,0));
  for(int h=0;h<HQ+HK;h++) for(int j=0;j<D;j++) {
    i64& v=st.x[h][j];
    if(dist=="uniform") v=uni(-S,S);
    else if(dist=="outlier") v=(j==int((u64(seed)+u64(h))%u64(D)))?S-1:uni(-S/64,S/64);
    else if(dist=="low") v=uni(-4,5);
    else if(dist=="unit-spike") v=(j==0)?1:0;
    else v=0;
  }
  for(int j=0;j<D;j++) st.gq.push_back(uni(S/2,2*S));
  for(int j=0;j<D;j++) st.gk.push_back(uni(S/2,2*S));
  auto w=honest_wit(st); for(auto& hw:w) st.y.push_back(hw.y);
  return st;
}

// ---- report ----
static int total=0, bad=0;
static std::string D_ARM;
static void out(const std::string& cls,const std::string& kind,int seed,bool accepted,bool expect,const std::string& extra="") {
  total++; bool ok=accepted==expect; bad+=!ok;
  std::cout<<"{\"arm\":\""<<D_ARM<<"\",\"case\":\""<<cls<<"\",\"kind\":\""<<kind<<"\",\"seed\":"<<seed
           <<",\"accepted\":"<<(accepted?"true":"false")<<",\"expected_accept\":"<<(expect?"true":"false")
           <<",\"as_registered\":"<<(ok?"true":"false")<<extra<<"}"<<std::endl;
}
static double since(std::chrono::steady_clock::time_point a){return std::chrono::duration<double>(std::chrono::steady_clock::now()-a).count();}

struct Honest { Writer proof; size_t cols, rels; double ps, vs; bool ok; };
static Honest prove_honest(const Stmt& st,u64 seed) {
  auto w=honest_wit(st); auto c=build(st,&w); auto pub=build(st,nullptr);
  Writer a,b; public_bytes(a,c.rel); public_bytes(b,pub.rel); need(a.bytes()==b.bytes(),"witness-dependent relation");
  auto t=table_for(c); need(violated(c,t)==0,"honest relation mismatch");
  auto run=run_for(c); Honest h; auto s=std::chrono::steady_clock::now(); h.proof=prove(run,t,false,seed); h.ps=since(s);
  s=std::chrono::steady_clock::now(); h.ok=verify(st,h.proof.data(),h.proof.size()); h.vs=since(s);
  h.cols=c.cols.size(); h.rels=c.rel.size(); return h;
}
// Complete malicious proof of witness `w` against statement `st`.
static void complete(const std::string& cls,int seed,const Stmt& st,const std::vector<HeadWit>& w,u64 coin) {
  auto c=build(st,&w); auto t=table_for(c); size_t v=violated(c,t);
  need(v>0,("hostile did not violate relation: "+cls).c_str());
  for(u64 j=0;j<t.len;j++) need(t.at(2,j)==t.at(0,j)*t.at(1,j),"hostile product broken");
  auto pr=prove(run_for(c),t,true,coin);
  out(cls,"complete",seed,verify(st,pr.data(),pr.size()),false,",\"violations\":"+std::to_string(v));
}
static void dump_fixture(std::ostream& fx,const std::string& dist,int seed,const Stmt& st) {
  auto p=params(st.D);
  fx<<"{\"arm\":\""<<D_ARM<<"\",\"dist\":\""<<dist<<"\",\"seed\":"<<seed<<",\"F\":"<<st.f<<",\"D\":"<<st.D<<",\"Hq\":"<<HQ<<",\"Hk\":"<<HK
    <<",\"m\":"<<M<<",\"K\":"<<K<<",\"s\":"<<p.s<<",\"epsN\":"<<p.epsN;
  auto arr=[&](const std::vector<i64>& v){fx<<"[";for(size_t i=0;i<v.size();i++)fx<<(i?",":"")<<v[i];fx<<"]";};
  auto arr2=[&](const std::vector<std::vector<i64>>& v){fx<<"[";for(size_t i=0;i<v.size();i++){if(i)fx<<",";arr(v[i]);}fx<<"]";};
  fx<<",\"x\":"; arr2(st.x); fx<<",\"gq\":"; arr(st.gq); fx<<",\"gk\":"; arr(st.gk); fx<<",\"y\":"; arr2(st.y); fx<<"}\n";
}

static void suite(int D,int seed,const std::string& fixpath) {
  D_ARM="D"+std::to_string(D); const u64 s=u64(seed)*100; const auto p=params(D); const int f=FB;
  std::ofstream fx(fixpath); need(bool(fx),"fixture file");
  std::map<std::string,Stmt> fix; std::map<std::string,Honest> hp;
  for(int di=0;di<5;di++) {
    const std::string d=DISTS[di];
    fix[d]=fixture(D,seed,d); dump_fixture(fx,d,seed,fix[d]);
    hp[d]=prove_honest(fix[d],s+u64(di));
    std::ostringstream e; e<<",\"dist\":\""<<d<<"\",\"columns\":"<<hp[d].cols<<",\"relations\":"<<hp[d].rels<<",\"proof_bytes\":"<<hp[d].proof.size()
      <<",\"prove_s\":"<<hp[d].ps<<",\"verify_s\":"<<hp[d].vs;
    out("honest",d,seed,hp[d].ok,true,e.str());
  }
  for(auto& yh:fix["zero"].y) for(auto v:yh) need(v==0,"zero head output not zero");
  const Stmt& U=fix["uniform"]; const auto& PU=hp["uniform"].proof; const auto W=honest_wit(U);
  size_t js=0; for(int j=0;j<D;j++) if(std::llabs(W[0].Z[j])>std::llabs(W[0].Z[js])) js=size_t(j);
  u64 coin=s+50;
  // 1 wrong-scale complete
  { i64 step=1; std::vector<HeadWit> w;
    for(;;) { w=W; w[0].g[js]+=step; from_Z(w[0],f); if(w[0].y[js]!=W[0].y[js]) break; step*=2; need(step<(i64(1)<<12),"gain step"); }
    Stmt st=U; st.y[0]=w[0].y; complete("wrong-scale",seed,st,w,coin++);
    std::cout<<"{\"arm\":\""<<D_ARM<<"\",\"note\":\"wrong-scale-step\",\"seed\":"<<seed<<",\"channel\":"<<js<<",\"step\":"<<step<<"}"<<std::endl; }
  // 2 wrong-scale statement
  { Stmt st=U; st.gq[js]+=1; out("wrong-scale","statement",seed,verify(st,PU.data(),PU.size()),false); }
  // 3 gain-swap complete
  { auto w=W; Stmt st=U; for(int h=0;h<HQ;h++){ w[h].g=U.gk; from_Z(w[h],f); st.y[h]=w[h].y; }
    need(st.y!=U.y,"gain swap changed nothing"); complete("gain-swap",seed,st,w,coin++); }
  // 4 gain-over-bound statement
  { Stmt st=U; st.gq[0]=i64(1)<<(f+3); out("gain-over-bound","statement",seed,verify(st,PU.data(),PU.size()),false); }
  // 5,6 isqrt +-1
  for(int dlt:{1,-1}) { auto w=W; w[0].sigma+=dlt; from_sigma(w[0],p,f); Stmt st=U; st.y[0]=w[0].y;
    complete(dlt>0?"isqrt-plus-one":"isqrt-minus-one",seed,st,w,coin++); }
  // 7,8 division remainder outside [0, sigma)
  for(int dlt:{-1,1}) { auto w=W; w[0].R+=dlt; from_R(w[0],p,f); Stmt st=U; st.y[0]=w[0].y;
    complete(dlt<0?"div-rem-over":"div-rem-under",seed,st,w,coin++); }
  // 9 floor remainder outside [0, 2^s)
  { auto w=W; w[0].Z[js]+=1; from_Z(w[0],f); Stmt st=U; st.y[0]=w[0].y; complete("floor-rem-over",seed,st,w,coin++); }
  // 10 swapped-head statement
  { Stmt st=U; std::swap(st.y[0],st.y[1]); out("swapped-head","statement",seed,verify(st,PU.data(),PU.size()),false); }
  // 11 swapped-head complete: head 0 normalises xq[1], head 1 normalises xq[0]
  { auto w=W; w[0]=honest_head(U.x[1],U.gq,p,f); w[1]=honest_head(U.x[0],U.gq,p,f); Stmt st=U; st.y[0]=w[0].y; st.y[1]=w[1].y;
    complete("swapped-head",seed,st,w,coin++); }
  // 12 wrong-vector complete: q head 0 output is the q-norm of the k vector
  { auto w=W; w[0]=honest_head(U.x[HQ],U.gq,p,f); Stmt st=U; st.y[0]=w[0].y; complete("wrong-vector",seed,st,w,coin++); }
  // 13 shared-coefficient complete: head 0 reuses head 1's sigma and R
  { auto w=W; w[0].sigma=W[1].sigma; w[0].R=W[1].R; from_R(w[0],p,f); Stmt st=U; st.y[0]=w[0].y;
    complete("shared-coefficient",seed,st,w,coin++); }
  // 14 epsilon dropped: zero head with sigma 0; unit-spike head with sigma = isqrt(4^m * E)
  { const Stmt& Z0=fix["zero"]; auto w=honest_wit(Z0); w[0].sigma=0; w[0].R=0; from_R(w[0],p,f);
    complete("zero-no-eps",seed,Z0,w,coin++); }
  { const Stmt& SP=fix["unit-spike"]; auto w=honest_wit(SP); w[0].sigma=isqrt64((i64(1)<<(2*M))*energy(SP.x[0])); from_sigma(w[0],p,f);
    Stmt st=SP; st.y[0]=w[0].y; complete("spike-no-eps",seed,st,w,coin++); }
  // 15 statement and byte mutations
  { Stmt st=U; st.y[0][0]+=1; out("wrong-output","statement",seed,verify(st,PU.data(),PU.size()),false); }
  { auto b=PU.bytes(); b[b.size()/2]^=1; out("byte-flip","statement",seed,verify(U,b.data(),b.size()),false); }
  out("truncated","statement",seed,verify(U,PU.data(),PU.size()-1),false);
  { auto b=PU.bytes(); b.push_back(0); out("trailing","statement",seed,verify(U,b.data(),b.size()),false); }
  { Stmt other=fixture(D==16?256:16,seed,"uniform"); out("dim-replay","statement",seed,verify(other,PU.data(),PU.size()),false); }
  { Stmt st=U; st.f=14; out("scale-replay","statement",seed,verify(st,PU.data(),PU.size()),false); }
  std::cout<<"{\"arm\":\""<<D_ARM<<"\",\"case\":\"summary\",\"seed\":"<<seed<<",\"checks\":"<<total<<",\"not_as_registered\":"<<bad<<"}"<<std::endl;
}

int main(int argc,char**argv) { try {
  need(argc==5&&std::string(argv[1])=="suite","usage: qk_norm.bin suite <D> <seed> <fixture.jsonl>");
  suite(std::stoi(argv[2]),std::stoi(argv[3]),argv[4]);
  return bad==0?0:1;
} catch(const std::exception&e) { std::cerr<<"error: "<<e.what()<<std::endl; return 2; } }
