#include <cstdio>
#include <cstdlib>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "product.h"
using namespace blk;
static void check(bool ok,const char *name) { if(!ok){std::fprintf(stderr,"FAIL: %s\n",name);std::exit(1);} }
// Bind TRUE topology/values, but use truthful NONZERO local targets for broken
// wires. All products and public coordinates still hold in these attacks.
static Writer malicious(const WireRun &run,const Table &abc) {
  EngineCpu engine; ToyCoins coins(789); Writer proof;
  Binder b(WIRE_LABEL,run.product.plan); auto in=wire_bind(b,run);
  ProverRounds ch(b,random_digest(coins),proof,[&engine](const ChainPrefix &p,unsigned bits){return engine.search_nonce(p,bits);});
  ProverContext pr(in.product.codes,ch,engine,coins);
  FoldMask mask; auto g=toy_prove_preamble(pr,in.product,abc,mask);
  coordinate_rows(pr.st,g,ch.get(in.coordinates));
  for(const auto &e:ch.get(in.equalities)) {
    Row row=wire_row(pr.st.group(g).members[0],e);
    row.target=abc.at(e.left_row,e.left_column)-abc.at(e.right_row,e.right_column);
    pr.st.add_row(g,std::move(row));
  }
  iopp_prove(pr,g,in.product.stages,in.product.choice,std::move(mask));
  ch.finish(); pr.st.require_all_tested(); return proof;
}
int main() {
  Setting set=setting_goldilocks(); set.hash_block_bytes=HASH_BLOCK_BYTES;
  set.target=10; set.set_work(ErrorKind::QUERY,Scope::REQUEST,6);
  const std::vector<StageChoice> stages={{1,1,8,8},{0,0,9,9}};
  const std::vector<Coordinate> coordinates={{0,0,F{2}},{1,0,F{3}},{2,2,F{120}}};
  const std::vector<WireEquality> wires={{2,0,0,1},{2,1,0,2}};
  auto run=wire_size(set,4,7,7,stages,coordinates,wires);
  check(run.product.plan->holds(),"wire plan holds");
  Table abc(1,3,16);
  for(u64 i=0;i<16;++i){abc.set(0,i,E::from(F{i+2}));abc.set(1,i,E::from(F{i+3}));}
  abc.set(0,1,E::from(F{6})); abc.set(0,2,E::from(F{24}));
  for(u64 i=0;i<16;++i) abc.set(2,i,abc.at(0,i)*abc.at(1,i));
  check(abc.at(2,0)==E::from(F{6}) && abc.at(2,1)==E::from(F{24}) && abc.at(2,2)==E::from(F{120}),"independent integer chain");
  // Exercise the actual builder, including cancellation and row-bit convention.
  for(const auto &e:std::vector<WireEquality>{{2,0,0,1},{2,1,0,2},{1,15,1,15},{0,3,2,3}}) {
    auto row=wire_row(0,e);
    for(u64 c=0;c<16;++c) for(u64 r=0;r<4;++r) {
      const int coefficient=int(r==e.left_row && c==e.left_column)-int(r==e.right_row && c==e.right_column);
      E want=coefficient==0?E::zero():(coefficient==1?E::one():-E::one());
      check(row.coefficient(0,Part::MAIN,r+4*c)==want,"independent wire coefficients");
      check(row.coefficient(1,Part::MAIN,r+4*c)==E::zero(),"no detached oracle");
      check(row.coefficient(0,Part::MASK,r+4*c)==E::zero(),"no mask claim");
    }
  }
  EngineCpu engine; ToyCoins coins(456); Writer proof;
  wire_prove(run,abc,engine,coins,proof);
  check(wire_verify(run,proof.data(),proof.size()),"honest linked product");
  // Exactly one edge is broken per attack; all public cells/products stay valid.
  for(size_t j=0;j<2;++j) {
    Table wrong=abc;
    if(j==0) {wrong.set(0,1,E::from(F{8}));wrong.set(1,1,E::from(F{3}));}
    else {wrong.set(0,2,E::from(F{30}));wrong.set(1,2,E::from(F{4}));}
    for(u64 i=0;i<16;++i) wrong.set(2,i,wrong.at(0,i)*wrong.at(1,i));
    for(const auto &c:coordinates) check(wrong.at(c.row,c.column)==E::from(c.value),"attack public values unchanged");
    for(size_t k=0;k<2;++k) {const auto &e=wires[k];check((wrong.at(e.left_row,e.left_column)==wrong.at(e.right_row,e.right_column))==(k!=j),"exactly one broken edge");}
    auto attack=malicious(run,wrong);
    check(attack.size()>0 && !wire_verify(run,attack.data(),attack.size()),"malicious shared-wire proof rejected");
  }
  for(size_t j=0;j<2;++j) for(unsigned field=0;field<4;++field) {
    auto changed=run; auto &e=changed.equalities[j];
    if(field==0)e.left_row=(e.left_row+1)%3;
    if(field==1)e.left_column^=1;
    if(field==2)e.right_row=(e.right_row+1)%3;
    if(field==3)e.right_column^=1;
    check(!wire_verify(changed,proof.data(),proof.size()),"topology mutation rejected");
  }
  auto changed=run; changed.coordinates[0].value=F{3};
  check(!wire_verify(changed,proof.data(),proof.size()),"public input mutation rejected");
  auto redundant=wires; redundant.push_back(wires[0]); redundant.push_back({0,1,2,0}); redundant.push_back({1,15,1,15});
  auto extra=wire_size(set,4,7,7,stages,coordinates,redundant);
  check(extra.product.plan->holds(),"redundant edge plan");
  Writer extra_proof; ToyCoins extra_coins(999); wire_prove(extra,abc,engine,extra_coins,extra_proof);
  check(wire_verify(extra,extra_proof.data(),extra_proof.size()),"redundant edges accepted");
  check(!run_verifier(WIRE_LABEL+1,run.product.plan,run,wire_bind,wire_decide,proof.data(),proof.size()),"wrong domain");
  auto prior=coordinate_size(set,4,7,7,stages,coordinates);
  check(!coordinate_verify(prior,proof.data(),proof.size()),"coordinate protocol rejects wire proof");
  Writer prior_proof; ToyCoins prior_coins(222); coordinate_prove(prior,abc,engine,prior_coins,prior_proof);
  check(!wire_verify(run,prior_proof.data(),prior_proof.size()),"wire protocol rejects coordinate proof");
  auto bytes=proof.bytes();size_t flips=0,cuts=0;
  for(size_t i=0;i<bytes.size();i+=97,++flips){bytes[i]^=1;check(!wire_verify(run,bytes.data(),bytes.size()),"corruption");bytes[i]^=1;}
  for(size_t n=0;n<bytes.size();n+=1+bytes.size()/40,++cuts)check(!wire_verify(run,bytes.data(),n),"truncation");
  check(!wire_verify(run,bytes.data(),bytes.size()-1),"last byte cut");
  bytes.push_back(0);check(!wire_verify(run,bytes.data(),bytes.size()),"trailing byte");
  std::printf("PASS: %zu proof bytes; 2 malicious one-edge proofs rejected; 8 topology mutations; public mutation; redundant/reverse/self edges; %zu flips; %zu cuts plus last byte; bidirectional domains; independent row checks\n",proof.size(),flips,cuts);
}
