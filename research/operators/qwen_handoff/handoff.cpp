// SPDX-License-Identifier: Apache-2.0
// Research-only joint proof: verifier reads its statement and proof, never witness files.
#include "sha256.h"
#include "lowering.h"

struct HandoffReader {
  std::vector<u8> raw; size_t pos = 0;
  explicit HandoffReader(const char *path) : raw(read_bytes(path)) {}
  std::vector<u8> bytes(size_t n) { check(n <= raw.size()-pos, "short input"); std::vector<u8> v(raw.begin()+pos,raw.begin()+pos+n); pos+=n; return v; }
  i64 word() { auto v=bytes(8); u64 x=0; for(unsigned i=0;i<8;i++) x|=u64(v[i])<<(8*i); i64 s; std::memcpy(&s,&x,8); return s; }
  std::vector<i64> words(size_t n) { std::vector<i64> v(n); for(auto &x:v)x=word(); return v; }
  void end() { check(pos==raw.size(), "trailing input"); }
};
struct HandoffStatement {
  int D,F,C,T; i64 request,layer,policy;
  std::vector<u8> raw, model,weights,root;
  std::vector<i64> S0,H0;
  std::vector<std::vector<i64>> inputs,preconv,outputs;
};
static void putword(std::vector<u8>& out,i64 x) { u64 v;std::memcpy(&v,&x,8);
  for(unsigned i=0;i<8;i++)out.push_back((v>>(8*i))&255); }
static HandoffStatement read_statement(const char *path) {
  HandoffReader r(path); check(r.bytes(8)==std::vector<u8>({'F','P','H','A','N','D','0','1'}),"statement tag");
  auto h=r.words(8); check(h[0]>=1 && h[0]<=32 && h[1]==12 && h[2]>=1 && h[2]<=16 && h[3]==2*h[2] && h[4]>=0 && h[4]< (1LL<<30) && h[5]>=0 && h[5]<64 && h[6]==1 && h[7]==2,"supported statement domain");
  HandoffStatement s; s.D=h[0];s.F=h[1];s.C=h[2];s.T=h[3];s.request=h[4];s.layer=h[5];s.policy=h[6];
  s.model=r.bytes(32);s.weights=r.bytes(32);s.root=r.bytes(32);s.S0=r.words(s.D*s.D);s.H0=r.words(9*s.D);
  for(auto x:s.S0)check(x>-BOUND && x<BOUND,"initial state range");
  for(auto x:s.H0)check(x>=-(1LL<<20) && x<(1LL<<20),"history input range");
  for(int t=0;t<s.T;t++)s.inputs.push_back(r.words(2+3*s.D));
  for(int t=0;t<s.T;t++)s.preconv.push_back(r.words(3*s.D));
  for(auto &v:s.preconv)for(auto x:v)check(x>=-(1LL<<20) && x<(1LL<<20),"preconv input range");
  for(int t=0;t<s.T;t++)s.outputs.push_back(r.words(s.D));
  r.end();s.raw=r.raw;
  std::string domain="fp-handoff-initial-v1"; std::vector<u8> opening(domain.begin(),domain.end());
  for(auto x:s.S0)putword(opening,x);
  for(auto x:s.H0)putword(opening,x);
  auto digest=sha256(opening);
  check(std::equal(s.root.begin(),s.root.end(),digest.begin()),"verifier initial root opening");return s;
}
static std::vector<i64> descriptor(const HandoffStatement&s,int c) {
  std::vector<i64> v={s.F,s.D,s.C,s.T,s.request,s.layer,s.policy,2,c,c*s.C,s.C};
  for(auto x:s.model)v.push_back(x);
  for(auto x:s.weights)v.push_back(x);
  return v;
}
struct HandoffPart {Fixture z;std::vector<i64> desc,Hin,Hout;std::vector<std::vector<i64>> x;};
static HandoffPart template_part(const HandoffStatement&s,int c) {
  HandoffPart p;p.desc=descriptor(s,c);p.z.T=s.C;p.z.D=s.D;p.z.F=s.F;
  p.z.S0=c?std::vector<i64>(s.D*s.D):s.S0;
  p.Hin=std::vector<i64>(9*s.D);p.Hout=p.Hin;
  for(int t=0;t<s.C;t++) {
    const auto &v=s.inputs[c*s.C+t];i64 one=1LL<<s.F;
    check(v[0]>=0 && v[0]<=one && v[1]>=0 && v[1]<=one,"gate input range");
    for(int j=0;j<s.D;j++)check(v[2+j]>=-one && v[2+j]<=one && v[2+s.D+j]>-VBOUND && v[2+s.D+j]<VBOUND && v[2+2*s.D+j]>=-one && v[2+2*s.D+j]<=one,"token input range");
    for(auto o:s.outputs[c*s.C+t])check(o>-VBOUND && o<VBOUND,"output range");
    p.z.a.push_back(v[0]);p.z.beta.push_back(v[1]);
    p.z.k.emplace_back(v.begin()+2,v.begin()+2+s.D);p.z.v.emplace_back(v.begin()+2+s.D,v.begin()+2+2*s.D);p.z.q.emplace_back(v.begin()+2+2*s.D,v.end());
    p.z.M.emplace_back(s.D,0);p.z.delta.emplace_back(s.D,0);p.z.S.emplace_back(s.D*s.D,0);p.z.o.push_back(s.outputs[c*s.C+t]);p.x.push_back(s.preconv[c*s.C+t]);
  }return p;
}
static HandoffPart read_part(const HandoffStatement&s,int c,const std::string& dir) {
  HandoffPart p;p.z=load((dir+"/c"+std::to_string(c)+".fx").c_str());
  check(p.z.D==s.D && p.z.T==s.C && p.z.F>=1 && p.z.F<=16,"witness fixed-slot layout");
  // The circuit's arithmetic is always verifier F; witness reference values can be from F13.
  p.z.F=s.F;HandoffReader r((dir+"/c"+std::to_string(c)+".packet").c_str());
  p.desc=r.words(75);p.Hin=r.words(9*s.D);p.Hout=r.words(9*s.D);
  for(int t=0;t<s.C;t++)p.x.push_back(r.words(3*s.D));
  r.end();
  return p;
}
static Built joint(const HandoffStatement&s,const std::vector<HandoffPart>& parts) {
  Built out;std::vector<std::vector<u64>> first(2),last(2),hin(2),hout(2);
  auto col=[&](i64 x) {out.cols.push_back({fi(x),F{0},F{0}});return u64(out.cols.size()-1);};
  auto pin=[&](u64 c,i64 value){out.rel.push_back({{{0,c,F{1}}},fi(value)});};
  auto eq=[&](u64 a,u64 b){out.rel.push_back({{{0,a,F{1}},{0,b,fi(-1)}},F{0}});};
  for(int c=0;c<2;c++) {
    const HandoffPart &p=parts[c];Built b=build(p.z);const u64 base=out.cols.size(),rcbase=out.rcv.size();
    const u64 nonrange=b.core_cols-b.rcv.size();out.cols.insert(out.cols.end(),b.cols.begin(),b.cols.begin()+nonrange);
    out.rcv.insert(out.rcv.end(),b.rcv.begin(),b.rcv.end());
    for(int j=0;j<s.D*s.D;j++){first[c].push_back(base+2*j);last[c].push_back(base+b.state_col.back()[j]);}
    for(auto r:b.rel) {
      // Remove both chunks' public final-state pins and only chunk 1's public initial pins.
      bool initial=false,final=false;
      if(r.terms.size()==1 && r.terms[0].row==0 && r.terms[0].coefficient==F{1}) {
        u64 k=r.terms[0].column;initial=k<u64(2*s.D*s.D) && k%2==0;
        final=std::find(b.state_col.back().begin(),b.state_col.back().end(),k)!=b.state_col.back().end();
      }
      if(final || (c==1 && initial))continue;
      for(auto &t:r.terms)t.column=t.column>=b.rc_base?RTAG+rcbase+t.column-b.rc_base:base+t.column;
      out.rel.push_back(std::move(r));
    }
    auto expected=descriptor(s,c);check(p.desc.size()==expected.size(),"descriptor width");
    for(size_t j=0;j<p.desc.size();j++)pin(col(p.desc[j]),expected[j]);
    for(auto x:p.Hin)hin[c].push_back(col(x));
  for(auto x:p.Hout)hout[c].push_back(col(x));
    std::vector<std::vector<u64>> xs;
    for(int t=0;t<s.C;t++){std::vector<u64> row;
  for(int j=0;j<3*s.D;j++){u64 k=col(p.x[t][j]);pin(k,s.preconv[c*s.C+t][j]);row.push_back(k);}xs.push_back(row);}
    // Three-tap history output equals the suffix of history input followed by the chunk inputs.
    for(int tap=0;tap<3;tap++)for(int j=0;j<3*s.D;j++) {
      const int at=s.C+tap;
      eq(hout[c][tap*3*s.D+j],at<3?hin[c][at*3*s.D+j]:xs[at-3][j]);
    }
  }
  for(int j=0;j<s.D*s.D;j++)eq(first[1][j],last[0][j]);
  for(int j=0;j<9*s.D;j++){pin(hin[0][j],s.H0[j]);eq(hin[1][j],hout[0][j]);}
  out.core_cols=out.cols.size()+out.rcv.size();out.rc_rows=pow2_at_least((out.rcv.size()+RCOLS-1)/RCOLS);
  const u64 size=out.rc_rows*RCOLS;out.rc_base=(out.cols.size()+size-1)/size*size;
  out.cols.resize(out.rc_base+size,{F{0},F{0},F{0}});
  for(u64 k=0;k<out.rcv.size();k++){out.cols[out.rc_base+k]={fi(out.rcv[k]),F{0},F{0}};out.rc.push_back(out.rc_base+k);}
  for(auto &r:out.rel)for(auto &t:r.terms)if(t.column>=RTAG)t.column=t.column-RTAG+out.rc_base;
  return out;
}
int main(int argc,char**argv) {
  check(argc==5,"usage: handoff.bin prove|hostile|verify|count statement witness-dir-or-dash proof");
  const std::string mode=argv[1];HandoffStatement s=read_statement(argv[2]);
  Built canonical=joint(s,{template_part(s,0),template_part(s,1)});
  // Own domain, distinct from the legacy chunk header; all expected inputs originate in s.
  std::vector<u8> hdr={'F','P','9','3'};hdr.insert(hdr.end(),s.raw.begin(),s.raw.end());
  Sized sz=size_chunk(canonical,hdr);
  if(mode=="verify") {
    auto pf=read_bytes(argv[4]);const char *why=nullptr;bool ok=chunk_verify(sz.cr,pf.data(),pf.size(),&why);
    std::printf("{\"accept\":%s,\"check\":\"proof-verifier\",\"why\":\"%s\"}\n",ok?"true":"false",why?why:"");return ok?0:1;
  }
  size_t terms=0;
  for(auto&r:canonical.rel)terms+=r.terms.size();
  if(mode=="count") {std::printf("{\"core_columns\":%llu,\"aligned_columns\":%zu,\"relations\":%zu,\"relation_terms\":%zu,\"range_cells\":%zu,\"T\":%d}\n",(unsigned long long)canonical.core_cols,canonical.cols.size(),canonical.rel.size(),terms,canonical.rcv.size(),s.T);return 0;}
  check(mode=="prove" || mode=="hostile","mode");
  Built witness=joint(s,{read_part(s,0,argv[3]),read_part(s,1,argv[3])});
  check(witness.cols.size()==canonical.cols.size() && witness.rc_base==canonical.rc_base && witness.rc_rows==canonical.rc_rows,"fixed layout");
  Table t=table_of(witness,sz.L);check(products_hold_all(t),"all products hold");const size_t bad=violated(canonical.rel,t);
  if(mode=="prove")check(bad==0,"honest relations");
  auto pf=prove(sz.cr,witness,t,mode=="hostile");write_bytes(argv[4],pf.bytes());
  bool ok=chunk_verify(sz.cr,pf.data(),pf.size());
  std::printf("{\"accept\":%s,\"check\":\"proof-verifier\",\"violated_relations\":%zu,\"products_hold\":true,\"core_columns\":%llu,\"aligned_columns\":%zu,\"relations\":%zu,\"relation_terms\":%zu,\"range_cells\":%zu,\"proof_bytes\":%zu,\"T\":%d}\n",ok?"true":"false",bad,(unsigned long long)canonical.core_cols,canonical.cols.size(),canonical.rel.size(),terms,canonical.rcv.size(),pf.size(),s.T);
  return 0;
}
