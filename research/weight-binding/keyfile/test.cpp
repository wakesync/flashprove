// SPDX-License-Identifier: Apache-2.0
// The same explicitly test-only switches as blocks/frame/tests/small_key_test.cpp.
#define BLK_WF_ROWS_FOR_A_TEST 1
#define BLK_KEY_UNDER_FOR_A_TEST 1
#define BLK_PLANS_BY_HAND_FOR_A_TEST
#define BLK_TESTED_TABLE_FOR_A_TEST
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include "iop/tests/wf_small_world.h"
#include "key_adapter.h"
using namespace blk;
namespace fs=std::filesystem;
static void require(bool ok,const std::string &s){if(!ok)throw std::runtime_error(s);}
static F signed_value(int i){return i<0?-from_u64(-i):from_u64(i);}
static TensorWords fixture(bool debug){TensorWords v;for(unsigned r=0;r<4;++r)for(unsigned i=0;i<4;++i)v[r].push_back(signed_value(int((r+(debug?2*i+1:i))%4)-2));return v;}
static LinMatrix matrix(const TensorWords &v){LinMatrix M{4,4,{}};for(const auto &row:v)for(auto x:row)M.a.push_back(x);return M;}
static WfWorld world(bool bound){
  auto w=wf_small_whole_world();
  if(bound){
    Plan first=toy_empty_plan();lin_plan_send(first,w.lin.codes,{w.lin.input});
    wf_toy_plan(first,w.lin.codes,w.wf,wf_matrix_of(w.lin.S),WF_SMALL_LIN.draws);
    plan_member_rows(first,"rows on the table",w.pending+4,w.lin.S.k_col());
    lin_plan_send(first,w.lin.codes,lin_message_w(w.lin.S));lin_plan_seal(first);w.lin.first=first;
  }return w;
}
static KeyUnder under(const WfWorld &w){
  KeyFixed f;f.configuration=w.lin.configuration;f.codes=w.lin.codes;f.lin=w.lin.S;f.index_masks=w.lin.input;f.ranges=w.wf;f.binding=w.lin.binding;
  require(!key_fault(f),"fixed key parameters");return KeyUnder(KeyPlans{w.lin.first,w.lin.shared,w.lin.second},f);
}
static Writer make(const WfWorld &w,const TensorManifest &m,const TensorWords &words,u64 seed,bool bound,bool dishonest=false){
  auto u=under(w);auto M=matrix(words);TestCoins commit_coins(seed+100000);
  IndexCpu index(w.lin.S.fold.index,lin_table_rows(w.lin.S,M),commit_coins);
  WfCpu ranges(w.wf,wf_matrix_of(w.lin.S),[&M](u64 r,u64 c){return M.at(r,c);});
  HeavyCpu products(w.lin.S,M);EngineCpu engine;TestCoins coins(seed);Writer proof;
  bool made=bound?tensor_make_native(u,m,dishonest?&words:nullptr,index,ranges,products,engine,coins,nullptr,proof)
                 :make_key_under(u,index,ranges,products,engine,coins,nullptr,proof);
  require(made&&!proof.bytes().empty(),"complete key creation");
  if(!bound)return proof;
  Writer file;put_word(file,TENSOR_KEY_TAG);put_word(file,TENSOR_KEY_VERSION);file.put(m.checkpoint);file.put(m.conversion);file.put_bytes(proof.data(),proof.size());return file;
}
struct Decision{bool accepted=false,native_attempted=false,native_accepted=false;std::string reason,stage;};
static Decision verify(const WfWorld &w,const TensorManifest &m,const Writer &file,bool bound){
  Decision d;auto u=under(w);
  if(bound){if(auto f=public_fault(m)){d.reason=f;d.stage="manifest setup";return d;}if(m.configuration!=u.fixed.configuration){d.reason="configuration";return d;}}
  Reader r(file.data(),file.size());Digest checkpoint{},conversion{};
  if(bound){u32 tag=0,version=0;if(!get_word(r,tag)||!get_word(r,version)||tag!=TENSOR_KEY_TAG||version!=TENSOR_KEY_VERSION||!r.get(checkpoint)||!r.get(conversion)){d.reason="extension header";d.stage="parser";return d;}}
  TestedTable key;IndexKey research_key;const char *why=nullptr,*place=nullptr;d.native_attempted=true;
  d.native_accepted=bound?tensor_check_native(u,m,r,research_key,why,nullptr,&place):check_key_under(u,r,key,why,nullptr,&place);
  if(!d.native_accepted){d.reason=why?why:"native reject";d.stage=place?place:"native";return d;}
  if(bound&&(checkpoint!=m.checkpoint||conversion!=m.conversion)){d.reason="extension ids";d.stage="header after native";return d;}
  d.accepted=true;d.reason="accepted";d.stage="all chains";return d;
}
static void save(const fs::path &p,const Writer &w){require(!fs::exists(p),"refuse overwrite");std::ofstream f(p,std::ios::binary);f.write((const char*)w.data(),w.size());require(bool(f),"write artifact");}
static std::string quoted(const std::string &s){std::string o="\"";for(char c:s){if(c=='"'||c=='\\')o+='\\';if(c=='\n')o+="\\n";else o+=c;}return o+'"';}
struct Recorder{
  fs::path out;u64 seed;bool all=true;std::vector<std::string> rows;
  void record(const std::string &arm,const WfWorld &w,const TensorManifest &m,const Writer &key,bool bound,bool expected){
    auto start=std::chrono::steady_clock::now();auto d=verify(w,m,key,bound);double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    bool pass=d.accepted==expected&&d.native_attempted&&d.native_accepted==expected;all&=pass;save(out/(arm+".key"),key);
    std::ostringstream s;s<<std::setprecision(12)<<"{\"arm\":"<<quoted(arm)<<",\"seed\":"<<seed<<",\"accepted\":"<<d.accepted<<",\"expected\":"<<expected
      <<",\"native_attempted\":"<<d.native_attempted<<",\"native_accepted\":"<<d.native_accepted<<",\"pass\":"<<pass<<",\"verify_ms\":"<<ms
      <<",\"key_bytes\":"<<key.size()<<",\"native_key_bytes\":"<<key.size()-(bound?TENSOR_KEY_HEADER:0)<<",\"stage\":"<<quoted(d.stage)<<",\"reason\":"<<quoted(d.reason)<<"}";rows.push_back(s.str());
  }
};
static Writer frombytes(const std::vector<u8>&b){Writer w;w.put_bytes(b.data(),b.size());return w;}
static void debug_checks(const WfWorld &w,const TensorManifest &m,const Writer &key){
  auto z=tw_point(m.checkpoint,m.conversion,m.names[0],2);E direct=E::zero();
  for(unsigned i=0;i<4;++i){E eq=E::one();for(unsigned j=0;j<2;++j)eq=eq*((i>>j)&1?z[j]:E::one()-z[j]);direct+=eq*E::from(m.integers[0][i]);}
  require(direct==tw_eval(m.integers[0],z),"MLE independent direct sum");
  for(unsigned row=0;row<4;++row){Tensor g;g.insert_choice(0,2,row);for(unsigned j=0;j<4;++j)require(g.at(j)==(j==row?E::one():E::zero()),"fixed row placement");}
  auto b=key.bytes();b[4]^=1;require(!verify(w,m,frombytes(b),true).accepted,"wrong extension version");
  b=key.bytes();b.push_back(0);require(!verify(w,m,frombytes(b),true).accepted,"trailing byte");
  for(size_t cut:{size_t(0),size_t(7),size_t(71),key.size()-1}){b=key.bytes();b.resize(cut);require(!verify(w,m,frombytes(b),true).accepted,"truncation");}
  b=key.bytes();b[8]^=1;auto d=verify(w,m,frombytes(b),true);require(!d.accepted&&d.native_accepted,"untrusted header root not trusted");
  auto stale=m;stale.checkpoint.w[0]^=1;require(!verify(w,stale,key,true).native_attempted,"stale held root");
  stale=m;stale.conversion.w[0]^=1;require(!verify(w,stale,key,true).native_attempted,"stale conversion");
  stale=m;std::swap(stale.names[0],stale.names[1]);require(!verify(w,stale,key,true).native_attempted,"noncanonical ordering");
  b=key.bytes();b[b.size()/2]^=1;require(!verify(w,m,frombytes(b),true).accepted,"corrupt proof");
  require(tw_hex(tw_sha(Writer()))=="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","SHA256 empty KAT");
}
static int verify_file(int argc,char **argv){
  require(argc==6,"usage: test.bin verify KEY SEED original|other|conversion bound|legacy");
  const u64 seed=std::stoull(argv[3]);const bool debug=seed==9001;
  require(debug||(seed>=1001&&seed<=1010),"known fixture seed required");
  const std::string profile=argv[4],kind=argv[5];require(kind=="bound"||kind=="legacy","key kind");
  const bool bound=kind=="bound";auto w=world(bound);auto words=fixture(debug);
  if(profile=="other"){
    words[0][0]=words[0][0]==F::one()?signed_value(-2):words[0][0]+F::one();
    words[2][1]=words[2][1]==F::one()?signed_value(-2):words[2][1]+F::one();
  }else require(profile=="original"||profile=="conversion","held fixture profile");
  auto m=tw_manifest(words,w.lin.configuration,debug,profile=="conversion"?"signed-i64-identity-v2-equivalent":"signed-i64-identity-v1");
  const fs::path path=argv[2];require(fs::file_size(path)<=8*1024*1024,"research key file size cap");
  std::ifstream f(path,std::ios::binary);std::vector<u8> bytes((std::istreambuf_iterator<char>(f)),{});require(!f.bad(),"read key file");
  auto d=verify(w,m,frombytes(bytes),bound);
  std::cout<<"{\"accepted\":"<<d.accepted<<",\"native_attempted\":"<<d.native_attempted<<",\"native_accepted\":"<<d.native_accepted
    <<",\"stage\":"<<quoted(d.stage)<<",\"reason\":"<<quoted(d.reason)<<",\"held_checkpoint\":"<<quoted(tw_hex(m.checkpoint))<<",\"held_conversion\":"<<quoted(tw_hex(m.conversion))<<"}\n";
  return d.accepted?0:1;
}
int main(int argc,char **argv)try{
  if(argc>1&&std::string(argv[1])=="verify")return verify_file(argc,argv);
  require(argc==3,"usage: test.bin FRESH_OUT SEED");u64 seed=std::stoull(argv[2]);bool debug=seed==9001;
  require(debug||(seed>=1001&&seed<=1010),"registered seeds or separate debug fixture only");
  fs::path out=argv[1];require(!fs::exists(out),"fresh output directory required");fs::create_directories(out);
  auto bound=world(true),base=world(false);auto v=fixture(debug),one=v,two=v,order=v;
  one[0][0]=one[0][0]==F::one()?signed_value(-2):one[0][0]+F::one();two=one;two[2][1]=two[2][1]==F::one()?signed_value(-2):two[2][1]+F::one();std::swap(order[0],order[1]);
  auto m=tw_manifest(v,bound.lin.configuration,debug);Recorder rec{out,seed,true,{}};
  auto honest=make(bound,m,v,seed,true),legacy=make(base,m,v,seed,false);
  if(seed%2)rec.record("legacy-honest",base,m,legacy,false,true);
  rec.record("bound-honest",bound,m,honest,true,true);
  if(!(seed%2))rec.record("legacy-honest",base,m,legacy,false,true);
  for(auto &x:std::vector<std::pair<std::string,TensorWords>>{{"one-tensor-swapped",one},{"two-tensors-swapped",two},{"tensor-order-permuted",order}}){
    auto attack=make(bound,m,x.second,seed,true,true);rec.record(x.first,bound,m,attack,true,false);
    rec.record(x.first+"-honest-control",bound,m,honest,true,true);
    auto unbound=make(base,m,x.second,seed,false);rec.record(x.first+"-legacy-control",base,m,unbound,false,true);
  }
  auto other=tw_manifest(two,bound.lin.configuration,debug);auto alt=make(bound,other,two,seed,true);
  rec.record("other-checkpoint-honest-control",bound,other,alt,true,true);
  rec.record("manifest-root-other-checkpoint",bound,other,honest,true,false);
  auto conv=tw_manifest(v,bound.lin.configuration,debug,"signed-i64-identity-v2-equivalent");auto cv=make(bound,conv,v,seed,true);
  rec.record("conversion-id-honest-control",bound,conv,cv,true,true);
  rec.record("conversion-id-mismatch",bound,conv,honest,true,false);
  if(debug)debug_checks(bound,m,honest);
  std::ofstream f(out/"results.json");f<<"{\"seed\":"<<seed<<",\"debug\":"<<debug<<",\"checkpoint_id\":"<<quoted(tw_hex(m.checkpoint))<<",\"conversion_id\":"<<quoted(tw_hex(m.conversion))
    <<",\"other_checkpoint_id\":"<<quoted(tw_hex(other.checkpoint))<<",\"equivalent_conversion_id\":"<<quoted(tw_hex(conv.conversion))<<",\"extension_header_bytes\":"<<TENSOR_KEY_HEADER<<",\"records\":[\n";
  for(size_t i=0;i<rec.rows.size();++i){f<<(i?",\n":"")<<rec.rows[i];}
  f<<"\n],\"pass\":"<<rec.all<<"}\n";require(bool(f),"write results");
  std::cout<<(rec.all?"PASS":"FAIL")<<": "<<rec.rows.size()<<" arms; seed="<<seed<<" debug="<<debug<<"\n";return rec.all?0:1;
}catch(const std::exception&e){std::cerr<<"ERROR: "<<e.what()<<"\n";return 2;}
