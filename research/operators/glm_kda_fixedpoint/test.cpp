#include <cstdio>
#include <cstdlib>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "../affine_rows/product.h"
using namespace blk;
#include "fixture.h"
constexpr u64 LABEL=0x474b4631;
static void check(bool ok,const char*s){if(!ok){std::fprintf(stderr,"FAIL: %s\n",s);std::exit(1);}}
static E eval(const AffineRelation&a,const Table&t){E x=E::zero();for(auto z:a.terms)x+=E::from(z.coefficient)*t.at(z.row,z.column);return x;}
static Writer prove(const AffineRun&run,const Table&t,bool hostile){
 EngineCpu engine;ToyCoins coins(100);Writer proof;Binder b(LABEL,run.wire.product.plan);auto in=affine_bind(b,run);
 ProverRounds ch(b,random_digest(coins),proof,[&](const ChainPrefix&p,unsigned bits){return engine.search_nonce(p,bits);});
 ProverContext pr(in.wire.product.codes,ch,engine,coins);FoldMask mask;
 auto g=toy_prove_preamble(pr,in.wire.product,t,mask);auto oracle=pr.st.group(g).members[0];
 coordinate_rows(pr.st,g,ch.get(in.wire.coordinates));
 for(auto w:ch.get(in.wire.equalities)){auto row=wire_row(oracle,w);if(hostile)row.target=t.at(w.left_row,w.left_column)-t.at(w.right_row,w.right_column);pr.st.add_row(g,std::move(row));}
 for(auto a:ch.get(in.relations)){auto row=affine_row(oracle,a);if(hostile)row.target=eval(a,t);pr.st.add_row(g,std::move(row));}
 iopp_prove(pr,g,in.wire.product.stages,in.wire.product.choice,std::move(mask));ch.finish();pr.st.require_all_tested();return proof;
}
static bool verify(const AffineRun&r,const Writer&p){return run_verifier(LABEL,r.wire.product.plan,r,affine_bind,affine_decide,p.data(),p.size());}
int main(){
 Setting set=setting_goldilocks();set.hash_block_bytes=HASH_BLOCK_BYTES;set.target=10;set.set_work(ErrorKind::QUERY,Scope::REQUEST,6);
 auto run=affine_size(set,6,9,9,{{1,1,9,9},{0,0,10,10}},coordinates,wires,relations);
 check(run.wire.product.plan->holds(),"plan");auto t=fixture();
 for(auto a:relations)check(eval(a,t)==E::from(a.target),"reference affine");
 for(auto w:wires)check(t.at(w.left_row,w.left_column)==t.at(w.right_row,w.right_column),"reference reuse");
 auto proof=prove(run,t,false);check(verify(run,proof),"honest staged-floor scalar KDA");
 // Complete malicious provers preserve products and public endpoints, while
 // lying about each private range bit or quotient/remainder storage cell.
 for(unsigned col:attack_columns){
  auto bad=t;bad.set(0,col,bad.at(0,col)+E::one());bad.set(2,col,bad.at(0,col)*bad.at(1,col));
  for(auto c:coordinates)check(bad.at(c.row,c.column)==E::from(c.value),"attack preserves public endpoints");
  for(unsigned i=0;i<64;++i)check(bad.at(2,i)==bad.at(0,i)*bad.at(1,i),"attack preserves products");
  auto attack=prove(run,bad,true);check(!verify(run,attack),"complete false-transition proof rejected");
 }
 // Preserve a*b=4*q+r while using negative/oversized remainders or a
 // quotient outside signed range. First case is truncation toward zero for -9/4.
 for(int shift:{1,-1,16}){
  auto bad=t;
  auto dq=E::from(shift>0?F{u64(shift)}:-F{u64(-shift)});
  bad.set(0,FIRST_Q,bad.at(0,FIRST_Q)+dq);bad.set(2,FIRST_Q,bad.at(0,FIRST_Q));
  bad.set(0,FIRST_R,bad.at(0,FIRST_R)-E::from(F{4})*dq);bad.set(2,FIRST_R,bad.at(0,FIRST_R));
  for(auto c:coordinates)check(bad.at(c.row,c.column)==E::from(c.value),"paired attack preserves public endpoints");
  for(unsigned i=0;i<64;++i)check(bad.at(2,i)==bad.at(0,i)*bad.at(1,i),"paired attack preserves products");
  check(!verify(run,prove(run,bad,true)),"paired quotient/remainder attack rejected");
 }
 for(size_t i=0;i<coordinates.size();++i){auto changed=run;changed.wire.coordinates[i].value=F{(coordinates[i].value.v+1)%P};check(!verify(changed,proof),"public mutation rejected");}
 auto bytes=proof.bytes();size_t cuts=0,flips=0;
 for(size_t i=0;i<bytes.size();i+=113){bytes[i]^=1;check(!run_verifier(LABEL,run.wire.product.plan,run,affine_bind,affine_decide,bytes.data(),bytes.size()),"flip");bytes[i]^=1;++flips;}
 for(size_t i=0;i<bytes.size();i+=1+bytes.size()/30){check(!run_verifier(LABEL,run.wire.product.plan,run,affine_bind,affine_decide,bytes.data(),i),"cut");++cuts;}
 check(!affine_verify(run,proof.data(),proof.size()),"generic affine domain rejects KDA proof");
 bytes.push_back(0);check(!run_verifier(LABEL,run.wire.product.plan,run,affine_bind,affine_decide,bytes.data(),bytes.size()),"trailing byte");
 std::printf("PASS: %zu proof bytes; 56 product gates; signed staged-floor scalar KDA; 50 complete hostile proofs rejected; 22 public mutations; %zu flips; %zu cuts; domain and trailing-byte rejection\n",proof.size(),flips,cuts);
}
