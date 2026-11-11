// SPDX-License-Identifier: Apache-2.0
// Research-only: issue #94, follow-ups of PR #67 (bounded Qwen operator relations).
// Not a production verifier and not a model proof. See README.md in this directory.
//
// This file includes ../qwen_ops/proof.cpp UNCHANGED (its main is renamed) and adds:
//  * profile v2 (`qwen-bounded-integer-v2`): the v1 profile text plus the two table manifest
//    SHA-256 values and the SHA-256 of the exact integer table bytes each operator reads. The v1
//    profile of PR #67 is not changed, so no committed PR #67 receipt changes.
//  * the reviewers' constructions of PR #67 as named cases (documented-gap controls that are
//    expected to be accepted, and hostile cases that are expected to be rejected);
//  * a per-round accounting dump of each profile's plan (blocks/numbers/accounting.h).
#define main qwen_ops_proof_main
#include "../qwen_ops/proof.cpp"
#undef main
#include <cstdio>
#include <sstream>
#include "numbers/accounting.h"
#include "../../../prover/weights_commitment/sha256.h"

// The manifests' SHA-256 as committed by PR #67 (research/operators/qwen_ops/tables/). run.py
// checks these constants against the files and every per-table hash below against the manifests.
static const char* MANIFEST_SHA="13eacc50c87e53bbda5d9dcbb11761c399e430e56eba7ed7877e15d8362c79dd";
static const char* ROTARY_MANIFEST_SHA="48fc90bb5e9c65cb66c21753f36b6da565bd2739c1a5bf057a7d78eeb97455a1";

struct NamedTable { std::string name; std::vector<int64_t> words; };
static std::string sha_words(const std::vector<int64_t>& w) {
  std::string b; b.reserve(w.size()*8);
  for(auto v:w) for(int i=0;i<8;i++) b.push_back(char((u64(v)>>(8*i))&0xff));
  Sha256 h; h.update(b.data(),b.size()); return h.hex();
}
static const char* NL_NAMES[6]={"silu","sigmoid","softplus","decay-half","decay-one","decay-two"};
// The tables an operator's relations read, as the verifier has them compiled in (pinned.h).
static std::vector<NamedTable> pinned_tables(const std::string& op,int f) {
  std::vector<NamedTable> t; auto F=std::to_string(f);
  auto add=[&](std::string n,const int64_t* p,size_t k){t.push_back({n+"-f"+F,std::vector<int64_t>(p,p+k)});};
  if(op=="nonlinear") for(int i=0;i<6;i++) add(NL_NAMES[i],table(i,f),4096);
  if(op=="l2") add("l2-128",table(7,f),4096);
  if(op=="rms") add("rsqrt",table(6,f),4096);
  if(op=="rotary") add("rotary",rotary_table(f),65536);
  return t;
}
struct Claim { std::string manifest=MANIFEST_SHA, rotary_manifest=ROTARY_MANIFEST_SHA; };
static std::string v2_text(const Circuit& c,const std::vector<NamedTable>& tabs,const Claim& claim) {
  std::string s="operator-family qwen-bounded-integer-v2\nprofile "+c.profile+"\n";
  s+="tables-manifest-sha256 "+claim.manifest+"\nrotary-manifest-sha256 "+claim.rotary_manifest+"\n";
  s+="tables-read";
  if(tabs.empty()) s+=" none";
  for(auto& t:tabs) s+=" "+t.name+"="+sha_words(t.words);
  return s+"\n";
}
// Same sizing as proof.cpp's run_for(); only the profile text differs.
static WideRun run_v2(const Circuit& c,const std::vector<NamedTable>& tabs,const Claim& claim=Claim()) {
  unsigned L=1;while((u64(1)<<L)<c.cols.size())L++;
  Setting set=setting_goldilocks();set.hash_block_bytes=HASH_BLOCK_BYTES;set.target=10;set.set_work(ErrorKind::QUERY,Scope::REQUEST,6);
  auto run=wide_size(set,L,L+1,L+1,{{1,1,L,L},{0,0,L,L}},c.rel);
  run.product.shape.text += v2_text(c,tabs,claim);
  need(run.product.plan->holds(),"plan refused"); return run;
}
// The v2 public verifier: relation list and table hashes are verifier-owned (compiled-in tables).
static bool verify_v2(const Input& statement,const u8* data,size_t n) {
  try {auto c=build(statement,false);auto run=run_v2(c,pinned_tables(statement.op,statement.f));return wide_verify(run,data,n);}catch(const std::exception&){return false;}
}
static std::string digest_hex(const WideRun& run) {
  Digest d=configuration_digest({run.product.shape.text}); char b[72]; std::string s;
  for(int i=0;i<8;i++){std::snprintf(b,sizeof b,"%08x",d.w[i]);s+=b;}
  return s;
}
// proof.cpp's nonlinear() with the six tables passed in, so a prover can use a different table.
static Circuit nonlinear_with(const Input& in,bool witness,const std::vector<NamedTable>& tabs) {
  Circuit c(witness); int f=in.f;
  auto x=c.cell(witness?in.x.at(0):0); c.attacks["input"]=x;
  auto q=c.floor(x,f-8,"grid"); auto key=c.sum({{q,1}},2048);
  auto sel=c.selectors(key);
  for(int i=0;i<6;i++) {auto y=c.lookup(sel,tabs[i].words.data()); c.eq({c.term(y)},in.y.at(i));}
  c.profile=in.op+" F="+std::to_string(in.f)+" position="+std::to_string(in.position);
  return c;
}

// ---- output ----
static int seed_g=0;
static void out_case(const std::string& name,const std::string& kind,const std::string& profile,bool accepted,bool complete,long violations,const std::string& extra="") {
  const bool expect_accept = kind=="gap-control"||kind=="positive";
  std::cout<<"{\"mode\":\"case\",\"seed\":"<<seed_g<<",\"case\":\""<<name<<"\",\"kind\":\""<<kind<<"\",\"profile\":\""<<profile
           <<"\",\"accepted\":"<<(accepted?"true":"false")<<",\"expected\":\""<<(expect_accept?"accept":"reject")
           <<"\",\"as_expected\":"<<((accepted==expect_accept)?"true":"false")<<",\"complete_proof\":"<<(complete?"true":"false")
           <<",\"violations\":"<<violations<<extra<<"}"<<std::endl;
}
static Input statement_of(Input in){in.x.clear();return in;}
static bool products_hold(const Table& t){for(u64 j=0;j<t.len;j++) if(!(t.at(2,j)==t.at(0,j)*t.at(1,j))) return false; return true;}
// Honest proof under v1 (proof.cpp's run_for) or v2, verified by that profile's public verifier.
struct Proved { Circuit c; Table t; Writer proof; long violations; };
static Proved prove_profile(const Input& in,bool v2,bool hostile,u64 coin) {
  auto c=build(in,true); auto t=table_for(c); long v=(long)violated(c,t);
  need(products_hold(t),"product equation broken");
  if(!hostile) need(v==0,"honest witness violates a relation");
  else need(v>0,"hostile did not violate relation");
  auto run=v2?run_v2(c,pinned_tables(in.op,in.f)):run_for(c);
  auto p=prove(run,t,hostile,coin);
  return {std::move(c),std::move(t),std::move(p),v};
}
static bool vfy(bool v2,const Input& st,const u8* d,size_t n){return v2?verify_v2(st,d,n):verify(st,d,n);}
static const char* pname(bool v2){return v2?"v2":"v1";}
static void set_bit_cell(Table& z,Wire w,i64 v){E e=E::from(fi(v));z.set(0,w.c,e);z.set(1,w.c,e);z.set(2,w.c,e*e);}
static i64 nl_key(const Input& in){return floor2(in.x[0],in.f-8)+2048;}
static i64 norm_key(const Input& in){const int logD=in.op=="l2"?7:8;i64 e=0;for(auto v:in.x)e+=v*v;return floor2(e,2*in.f+logD-10)-256;}

// Rotary helper: find inputs in [-S,S) whose rotation at (C,U) floors to (a,b) exactly.
static bool rot_solve(i64 C,i64 U,int f,i64 a,i64 b,i64& x0,i64& x1) {
  const i64 S=i64(1)<<f; const double s=double(S);
  double r0=(double(a)*C+double(b)*U)/s, r1=(double(b)*C-double(a)*U)/s;
  for(i64 d0=-4;d0<=4;d0++) for(i64 d1=-4;d1<=4;d1++) {
    i64 u=i64(std::floor(r0))+d0, v=i64(std::floor(r1))+d1;
    if(u<-S||u>=S||v<-S||v>=S) continue;
    if(floor2(u*C-v*U,f)==a && floor2(v*C+u*U,f)==b){x0=u;x1=v;return true;}
  }
  return false;
}

static int suite(int seed) {
  seed_g=seed; const int f=12; const i64 S=i64(1)<<f; const u64 coin=u64(seed);
  const char* OPS[5]={"nonlinear","conv","l2","rms","rotary"};
  // Positive controls and profile cross-replay.
  for(auto op:OPS) {
    auto in=fixture(op,f,seed); auto st=statement_of(in);
    auto a=prove_profile(in,false,false,coin), b=prove_profile(in,true,false,coin);
    out_case(std::string("P-honest-v1-")+op,"positive","v1",verify(st,a.proof.data(),a.proof.size()),true,0);
    out_case(std::string("P-honest-v2-")+op,"positive","v2",verify_v2(st,b.proof.data(),b.proof.size()),true,0);
    out_case(std::string("R-profile-v1-proof-under-v2-")+op,"hostile","v2",verify_v2(st,a.proof.data(),a.proof.size()),true,0);
    out_case(std::string("R-profile-v2-proof-under-v1-")+op,"hostile","v1",verify(st,b.proof.data(),b.proof.size()),true,0);
    // Same tables and relations, claimed manifest hash with its first hex digit changed.
    Claim cl; cl.manifest[0]=cl.manifest[0]=='0'?'1':'0';
    auto run=run_v2(b.c,pinned_tables(op,f),cl); auto p=prove(run,b.t,false,coin);
    out_case(std::string("T-manifest-hash-only-")+op,"hostile","v2",verify_v2(st,p.data(),p.size()),true,0);
    // Impossible public output, complete proof by target substitution.
    auto bad=in;
    if(in.op=="nonlinear") bad.y[1]=2*S; else if(in.op=="conv") bad.y[0]=6*S; else if(in.op=="rotary") bad.y[64]=S; else bad.y[0]=5*S;
    for(bool v2:{false,true}){auto h=prove_profile(bad,v2,true,coin+1000);auto bst=statement_of(bad);
      out_case(std::string("R-impossible-output-")+op,"hostile",pname(v2),vfy(v2,bst,h.proof.data(),h.proof.size()),true,h.violations);}
    bad=in; bad.y.back()+=3;
    for(bool v2:{false,true}){auto h=prove_profile(bad,v2,true,coin+1000);auto bst=statement_of(bad);
      out_case(std::string("R-last-target-plus-3-")+op,"hostile",pname(v2),vfy(v2,bst,h.proof.data(),h.proof.size()),true,h.violations);}
  }
  for(bool v2:{false,true}) {
    const char* pr=pname(v2);
    // C-conv-chosen-outputs (opus #1): taps (0,0,0,-S), x[t+3]=-y[t], history 0.
    {Input in;in.op="conv";in.f=f;in.y={S,-S+1,1234,-77};in.x={0,0,0};
     for(int t=0;t<4;t++)in.x.push_back(-in.y[t]);
     for(i64 w:{i64(0),i64(0),i64(0),-S})in.x.push_back(w);
     auto h=prove_profile(in,v2,false,coin);
     out_case("C-conv-chosen-outputs","gap-control",pr,vfy(v2,statement_of(in),h.proof.data(),h.proof.size()),true,0);}
    // C-conv-other-kernel (opus #2): fixture outputs, taps all -S, history searched so that
    // x[t+3] = -y[t] - (x[t]+x[t+1]+x[t+2]) stays in [-S,S).
    // Solved directly: with taps -S each output is minus its window sum, so x[t+4]=x[t]-(y[t+1]-y[t]);
    // x[0..2] are placed in their feasible intervals so that x[3]=-y[0]-x[0]-x[1]-x[2] is in range.
    {auto fx=fixture("conv",f,seed); bool found=false; int tries=0; Input in=fx;
     i64 lo[3],hi[3]; bool feas=true;
     for(int i=0;i<3;i++){i64 d=fx.y[i+1]-fx.y[i]; lo[i]=std::max(-S,-S+d); hi[i]=std::min(S-1,S-1+d); feas=feas&&lo[i]<=hi[i];}
     for(i64 x3=0; feas&&!found&&x3>=-S; x3=(x3>0?-x3:-x3+1)) { if(x3>=S) continue; tries++;
       i64 D=-fx.y[0]-x3, L=lo[0]+lo[1]+lo[2], H=hi[0]+hi[1]+hi[2]; if(D<L||D>H) continue;
       i64 rest=D-L; for(int i=0;i<3;i++){i64 add=std::min(rest,hi[i]-lo[i]); in.x[i]=lo[i]+add; rest-=add;}
       in.x[3]=x3; for(int t=0;t<3;t++) in.x[t+4]=in.x[t]-(fx.y[t+1]-fx.y[t]);
       for(int j=7;j<11;j++)in.x[j]=-S;
       bool ok=true; for(int j=0;j<7;j++) ok=ok&&in.x[j]>=-S&&in.x[j]<S;
       for(int t=0;t<4;t++){i64 num=0;for(int j=0;j<4;j++)num+=in.x[t+j]*in.x[7+j]; ok=ok&&floor2(num,f)==fx.y[t];}
       found=ok; if(tries>4*S) break; }
     if(found){auto h=prove_profile(in,v2,false,coin);
       out_case("C-conv-other-kernel","gap-control",pr,vfy(v2,statement_of(in),h.proof.data(),h.proof.size()),true,0,",\"history_tries\":"+std::to_string(tries));}
     else {
       // No witness with taps all -S: the window sums -y would need inputs outside [-S,S). Recorded
       // as not applicable (registered in the PREREG amendment), not as an acceptance or a rejection.
       std::ostringstream o; o<<",\"not_applicable\":true,\"interval_feasible\":"<<(feas?"true":"false")<<",\"outputs\":["<<fx.y[0]<<","<<fx.y[1]<<","<<fx.y[2]<<","<<fx.y[3]<<"]";
       std::cout<<"{\"mode\":\"case\",\"seed\":"<<seed_g<<",\"case\":\"C-conv-other-kernel\",\"kind\":\"not-applicable\",\"profile\":\""<<pr<<"\",\"accepted\":false,\"expected\":\"none\",\"as_expected\":true,\"complete_proof\":false,\"violations\":0"<<o.str()<<"}"<<std::endl;}}
    // C-conv-negate-all (astra): negate the seven inputs and four taps; products, so outputs, unchanged.
    {auto in=fixture("conv",f,seed); bool ok=true; for(auto& v:in.x){v=-v; ok=ok&&v<S;}
     if(ok){auto h=prove_profile(in,v2,false,coin);
       out_case("C-conv-negate-all","gap-control",pr,vfy(v2,statement_of(in),h.proof.data(),h.proof.size()),true,0);}
     else out_case("C-conv-negate-all","gap-control",pr,false,false,0,",\"not_applicable_minus_S\":true");}
    // C-rotary-near-target (opus #4): position 517, random target words in [-S/2,S/2).
    {Input in;in.op="rotary";in.f=f;in.position=517;std::mt19937 rng(seed*104729+3);
     for(int j=0;j<256;j++)in.y.push_back(i64(rng()%S)-S/2);
     in.x=in.y; const auto tab=rotary_table(f)+64*517; int exact=0,moved=0;
     for(int j=0;j<32;j++){i64 C=tab[2*j],U=tab[2*j+1],u,v;
       if(rot_solve(C,U,f,in.y[j],in.y[j+32],u,v)){exact++;in.x[j]=u;in.x[j+32]=v;continue;}
       bool done=false;
       for(int m=1;m<=2&&!done;m++) for(i64 da=-m;da<=m&&!done;da++) for(i64 db=-m;db<=m&&!done;db++){
         if(std::llabs(da)+std::llabs(db)!=m) continue;
         if(rot_solve(C,U,f,in.y[j]+da,in.y[j+32]+db,u,v)){in.y[j]+=da;in.y[j+32]+=db;in.x[j]=u;in.x[j+32]=v;moved+=int(std::llabs(da)+std::llabs(db));done=true;}}
       need(done,"rotary pair not reachable within 2 unit moves");}
     auto h=prove_profile(in,v2,false,coin);
     out_case("C-rotary-near-target","gap-control",pr,vfy(v2,statement_of(in),h.proof.data(),h.proof.size()),true,0,
              ",\"pairs_exact\":"+std::to_string(exact)+",\"word_units_moved\":"+std::to_string(moved));}
    // Selector constructions on the nonlinear and RMS lookups (opus #7/#8, astra Boolean cases).
    for(std::string op:{"nonlinear","rms"}) {
      auto in=fixture(op,f,seed); auto c=build(in,true); auto t=table_for(c); auto run=v2?run_v2(c,pinned_tables(op,f)):run_for(c);
      i64 k=op=="nonlinear"?nl_key(in):norm_key(in); Wire sk=c.attacks.at("selector"); u64 base=sk.c-u64(k);
      auto at=[&](i64 i){return Wire{base+u64(i),0,0};};
      auto run_attack=[&](const std::string& name,std::function<void(Table&)> ch){
        Table bad=t; ch(bad); long v=(long)violated(c,bad); need(v>0,"hostile did not violate relation"); need(products_hold(bad),"product equation broken");
        auto p=prove(run,bad,true,coin+1000); out_case(name+"-"+op,"hostile",pr,vfy(v2,statement_of(in),p.data(),p.size()),true,v);};
      // (2,-1) at (i, 2i-k), selected cell 0: sum 1 and index k kept.
      i64 i1=k+2<4096?k+1:k-1, i2=2*i1-k;
      run_attack("R-selector-nonboolean",[&](Table&z){set_bit_cell(z,at(k),0);set_bit_cell(z,at(i1),2);set_bit_cell(z,at(i2),-1);});
      run_attack("R-selector-two-hot",[&](Table&z){set_bit_cell(z,at(k+1<4096?k+1:k-1),1);});
    }
    // R-rotary-cos-sin-swap (opus #16): outputs and witness of the swapped rotation, complete proof.
    {auto in=fixture("rotary",f,seed); const auto tab=rotary_table(f)+64*in.position;
     for(int j=0;j<32;j++){i64 U=tab[2*j],C=tab[2*j+1];
       in.y[j]=floor2(in.x[j]*C-in.x[j+32]*U,f); in.y[j+32]=floor2(in.x[j+32]*C+in.x[j]*U,f);}
     auto h=prove_profile(in,v2,true,coin+1000);
     out_case("R-rotary-cos-sin-swap","hostile",pr,vfy(v2,statement_of(in),h.proof.data(),h.proof.size()),true,h.violations);}
    // Statement replays and byte damage on honest proofs.
    {auto in=fixture("rotary",f,seed); auto h=prove_profile(in,v2,false,coin);
     auto in7=in; in7.position=(in.position+7)%1024; for(int j=0;j<32;j++){const auto tb=rotary_table(f)+64*in7.position;i64 C=tb[2*j],U=tb[2*j+1];
       in7.y[j]=floor2(in.x[j]*C-in.x[j+32]*U,f); in7.y[j+32]=floor2(in.x[j+32]*C+in.x[j]*U,f);}
     auto h7=prove_profile(in7,v2,false,coin);
     out_case("R-rotary-position-plus-7","hostile",pr,vfy(v2,statement_of(in),h7.proof.data(),h7.proof.size()),true,0);}
    {auto in=fixture("nonlinear",f,seed); auto h=prove_profile(in,v2,false,coin); auto st=statement_of(in);
     auto s16=st; s16.f=16; out_case("R-nonlinear-f12-as-f16","hostile",pr,vfy(v2,s16,h.proof.data(),h.proof.size()),true,0);
     auto sp=st; std::swap(sp.y[0],sp.y[1]); out_case("R-nonlinear-permuted-outputs","hostile",pr,vfy(v2,sp,h.proof.data(),h.proof.size()),true,0);}
    {auto a=fixture("conv",f,seed), b=fixture("conv",f,seed+1000); auto h=prove_profile(a,v2,false,coin);
     out_case("R-conv-cross-seed-statement","hostile",pr,vfy(v2,statement_of(b),h.proof.data(),h.proof.size()),true,0);
     out_case("R-conv-empty-proof","hostile",pr,vfy(v2,statement_of(a),nullptr,0),false,0);}
    {auto in=fixture("l2",f,seed); auto a=prove_profile(in,v2,false,coin), b=prove_profile(in,v2,false,coin+77);
     auto x=a.proof.bytes(); auto y=b.proof.bytes(); std::vector<u8> s(x.begin(),x.begin()+x.size()/2); s.insert(s.end(),y.begin()+std::min(y.size(),x.size()/2),y.end());
     bool differs=(s!=x)&&(s!=y);
     out_case("R-l2-salt-splice","hostile",pr,vfy(v2,statement_of(in),s.data(),s.size()),true,0,std::string(",\"splice_differs_from_both\":")+(differs?"true":"false"));}
    {auto in=fixture("rms",f,seed); auto h=prove_profile(in,v2,false,coin); auto st=statement_of(in);
     auto x=h.proof.bytes(); x[0]^=1; out_case("R-rms-first-byte","hostile",pr,vfy(v2,st,x.data(),x.size()),true,0);
     x=h.proof.bytes(); x.back()^=1; out_case("R-rms-last-byte","hostile",pr,vfy(v2,st,x.data(),x.size()),true,0);
     auto l2=st; l2.op="l2"; l2.y.resize(128); out_case("R-rms-as-l2","hostile",pr,vfy(v2,l2,h.proof.data(),h.proof.size()),true,0);}
  }
  // T-nonlinear-other-table: one silu row the fixture does not select changed by +1; the public
  // outputs are the same. The prover's circuit and profile use the changed table.
  {auto in=fixture("nonlinear",f,seed); auto tabs=pinned_tables("nonlinear",f); i64 k=nl_key(in); size_t row=size_t(k==0?1:k-1);
   tabs[0].words[row]+=1; auto st=statement_of(in);
   auto c=nonlinear_with(in,true,tabs); auto t=table_for(c); need(violated(c,t)==0,"other-table witness");
   auto p2=prove(run_v2(c,tabs),t,false,coin); auto p1=prove(run_for(c),t,false,coin);
   auto pinned=run_v2(build(st,false),pinned_tables("nonlinear",f)), other=run_v2(build(st,false),tabs);
   bool differ=digest_hex(pinned)!=digest_hex(other);
   out_case("T-nonlinear-other-table","hostile","v2",verify_v2(st,p2.data(),p2.size()),true,0,std::string(",\"v2_digest_differs\":")+(differ?"true":"false"));
   out_case("T-nonlinear-other-table","hostile","v1",verify(st,p1.data(),p1.size()),true,0);}
  return 0;
}

// Configuration digests and per-table hashes, for run.py to check against the manifests.
static int digests() {
  for(std::string op:{"nonlinear","conv","l2","rms","rotary"}) for(int f:{12,14,16}) {
    auto in=fixture(op,f,1); auto c=build(statement_of(in),false); auto tabs=pinned_tables(op,f);
    auto r1=run_for(c), r2=run_v2(c,tabs);
    std::cout<<"{\"mode\":\"digest\",\"op\":\""<<op<<"\",\"F\":"<<f<<",\"position\":"<<in.position<<",\"v1\":\""<<digest_hex(r1)<<"\",\"v2\":\""<<digest_hex(r2)<<"\",\"tables\":{";
    for(size_t i=0;i<tabs.size();i++) std::cout<<(i?",":"")<<"\""<<tabs[i].name<<"\":\""<<sha_words(tabs[i].words)<<"\"";
    std::cout<<"},\"manifest_claim\":\""<<MANIFEST_SHA<<"\",\"rotary_manifest_claim\":\""<<ROTARY_MANIFEST_SHA<<"\"}"<<std::endl;
  }
  return 0;
}

// Per-round accounting of one profile's plan. The plan does not depend on the profile text, so
// v1 and v2 share it; both texts are sized by the same call.
static int accounting(const std::string& op,int f,int seed) {
  auto in=fixture(op,f,seed); auto c=build(statement_of(in),false); auto run=run_for(c); const Planned& p=run.product.plan;
  const Real unit=p->capped(); Real sum;
  for(auto& r:p->rounds_) {
    Real e=p->whole_error(r,unit);
    if(!e.zero()) sum=Real::add(sum,Real::mul(Real::mul(e,Real(r.count),Dir::UP),Real::two_to(-(long)r.work_bits),Dir::UP),Dir::UP);
    std::printf("{\"mode\":\"round\",\"op\":\"%s\",\"F\":%d,\"name\":\"%s\",\"where\":\"%s\",\"count\":%llu,\"work_bits\":%u,\"error_bits\":%.10f,\"holds\":%s}\n",
      op.c_str(),f,r.name.c_str(),r.where.c_str(),(unsigned long long)r.count,r.work_bits,e.zero()?-1.0:bits_of(e),p->holds(r,unit)?"true":"false");
  }
  auto a=account(p);
  std::printf("{\"mode\":\"account\",\"op\":\"%s\",\"F\":%d,\"seed\":%d,\"position\":%d,\"columns\":%zu,\"relations\":%zu,\"rounds\":%llu,\"queries\":%llu,\"holds\":%s,\"largest_error_bits_with_work\":%.10f,\"weakest_without_work_bits\":%.10f,\"diagnostic_sum_bits_with_work\":%.10f,\"diagnostic_sum_bits_without_work\":%.10f,\"diagnostic_sum_value\":%.17g,\"recomputed_sum_bits\":%.10f}\n",
    op.c_str(),f,seed,in.position,c.cols.size(),c.rel.size(),(unsigned long long)a.rounds,(unsigned long long)a.queries,a.holds?"true":"false",
    a.groups.empty()?0.0:a.groups[0].all(),a.lists.bits,a.sum,a.sum_lists,sum.value(),bits_of(sum));
  std::fflush(stdout);
  std::printf("--- print_accounting ---\n"); print_rounds(a); print_accounting(a,(op+" F="+std::to_string(f)).c_str(),true,100);
  return 0;
}

int main(int argc,char** argv) { try {
  need(argc>=2,"usage: follow.bin suite SEED | digests | accounting OP F SEED");
  std::string m=argv[1];
  if(m=="suite"){need(argc==3,"suite SEED");return suite(std::stoi(argv[2]));}
  if(m=="digests") return digests();
  if(m=="accounting"){need(argc==5,"accounting OP F SEED");return accounting(argv[2],std::stoi(argv[3]),std::stoi(argv[4]));}
  need(false,"unknown mode"); return 2;
} catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 3;} }
