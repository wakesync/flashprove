#include <cstdio>
#include <cstdlib>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "product.h"
using namespace blk;
static void check(bool ok,const char *s){if(!ok){std::fprintf(stderr,"FAIL: %s\n",s);std::exit(1);}}
static E evaluate(const AffineRelation &a,const Table &abc){
  E sum=E::zero();for(const auto &t:a.terms)sum+=E::from(t.coefficient)*abc.at(t.row,t.column);return sum;
}
// Complete adversarial prover binds the TRUE relation but substitutes its own
// truthful local target. Products, public cells and existing wires are untouched.
static Writer malicious(const AffineRun &run,const Table &abc){
  EngineCpu engine;ToyCoins coins(789);Writer proof;
  Binder b(AFFINE_LABEL,run.wire.product.plan);auto in=affine_bind(b,run);
  ProverRounds ch(b,random_digest(coins),proof,[&engine](const ChainPrefix &p,unsigned bits){return engine.search_nonce(p,bits);});
  ProverContext pr(in.wire.product.codes,ch,engine,coins);
  FoldMask mask;auto g=toy_prove_preamble(pr,in.wire.product,abc,mask);
  coordinate_rows(pr.st,g,ch.get(in.wire.coordinates));wire_rows(pr.st,g,ch.get(in.wire.equalities));
  for(const auto &a:ch.get(in.relations)){
    auto row=affine_row(pr.st.group(g).members[0],a);row.target=evaluate(a,abc);pr.st.add_row(g,std::move(row));
  }
  iopp_prove(pr,g,in.wire.product.stages,in.wire.product.choice,std::move(mask));
  ch.finish();pr.st.require_all_tested();return proof;
}
int main(int argc,char **argv){
  Setting set=setting_goldilocks();set.hash_block_bytes=HASH_BLOCK_BYTES;
  set.target=10;set.set_work(ErrorKind::QUERY,Scope::REQUEST,6);
  const std::vector<StageChoice> stages={{1,1,8,8},{0,0,9,9}};
  const std::vector<Coordinate> coordinates={{0,0,F{2}},{1,0,F{3}},{2,2,F{120}}};
  const std::vector<WireEquality> wires={{2,0,0,1},{2,1,0,2}};
  // a[3] - 2*c[0] - 3*b[0] = 5. This is a FIELD relation, not integer range enforcement.
  const AffineRelation relation={{{0,3,F{1}},{2,0,F{P-2}},{1,0,F{P-3}}},F{5}};
  if(argc==2){
    auto relations=std::vector<AffineRelation>{relation};
    const unsigned which=unsigned(std::atoi(argv[1]));
    if(which==0)relations.clear();
    if(which==1)relations.resize(65,relation);
    if(which==2)relations[0].terms.clear();
    if(which==3)relations[0].terms.resize(9,relation.terms[0]);
    if(which==4)relations[0].target=F{P};
    if(which==5)relations[0].terms[0].coefficient=F{P};
    if(which==6)relations[0].terms[0].row=3;
    if(which==7)relations[0].terms[0].column=16;
    (void)affine_size(set,4,7,7,stages,coordinates,wires,relations);
    return 2; // Invalid trusted constructors MUST abort, not return.
  }
  auto run=affine_size(set,4,7,7,stages,coordinates,wires,{relation});
  check(run.wire.product.plan->holds(),"affine plan holds");
  Table abc(1,3,16);
  for(u64 i=0;i<16;++i){abc.set(0,i,E::from(F{i+2}));abc.set(1,i,E::from(F{i+3}));}
  abc.set(0,1,E::from(F{6}));abc.set(0,2,E::from(F{24}));abc.set(0,3,E::from(F{26}));
  for(u64 i=0;i<16;++i)abc.set(2,i,abc.at(0,i)*abc.at(1,i));
  check(26-2*6-3*3==5 && evaluate(relation,abc)==E::from(F{5}),"independent integer fixture");
  // Check actual row indexing and duplicate cancellation, including zero terms.
  auto cancel=relation;cancel.terms.push_back({0,3,F{P-1}});cancel.terms.push_back({1,15,F{0}});
  for(const auto &a:std::vector<AffineRelation>{relation,cancel}){
    auto row=affine_row(0,a);check(row.target==E::from(F{5}),"row target");
    for(u64 c=0;c<16;++c)for(u64 r=0;r<4;++r){
      E want=E::zero();
      if(r==0&&c==3&&a.terms.size()==3)want=E::one();
      if(r==2&&c==0)want=-E::from(F{2});
      if(r==1&&c==0)want=-E::from(F{3});
      check(row.coefficient(0,Part::MAIN,r+4*c)==want,"independent coefficients");
      check(row.coefficient(1,Part::MAIN,r+4*c)==E::zero(),"no detached oracle");
      check(row.coefficient(0,Part::MASK,r+4*c)==E::zero(),"no mask coefficients");
    }
  }
  EngineCpu engine;ToyCoins coins(456);Writer proof;affine_prove(run,abc,engine,coins,proof);
  check(affine_verify(run,proof.data(),proof.size()),"honest affine proof");
  for(u64 delta: {u64(1),u64(7)}){
    Table wrong=abc;wrong.set(0,3,E::from(F{26+delta}));wrong.set(2,3,wrong.at(0,3)*wrong.at(1,3));
    for(u64 i=0;i<16;++i)check(wrong.at(2,i)==wrong.at(0,i)*wrong.at(1,i),"attack products");
    for(const auto &c:coordinates)check(wrong.at(c.row,c.column)==E::from(c.value),"attack public cells");
    for(const auto &w:wires)check(wrong.at(w.left_row,w.left_column)==wrong.at(w.right_row,w.right_column),"attack wires");
    check(evaluate(relation,wrong)!=E::from(relation.target),"only affine fails");
    auto attack=malicious(run,wrong);check(attack.size()>0&&!affine_verify(run,attack.data(),attack.size()),"complete malicious affine proof rejected");
  }
  for(unsigned j=0;j<4;++j){auto changed=run;auto &a=changed.relations[0];
    if(j==0)a.terms[0].row=1;
    if(j==1)a.terms[0].column=4;
    if(j==2)a.terms[0].coefficient=F{2};
    if(j==3)a.target=F{6};
    check(!affine_verify(changed,proof.data(),proof.size()),"affine statement mutation");
  }
  auto prior=wire_size(set,4,7,7,stages,coordinates,wires);Writer prior_proof;ToyCoins pc(222);
  wire_prove(prior,abc,engine,pc,prior_proof);
  check(!affine_verify(run,prior_proof.data(),prior_proof.size()),"wire proof rejected by affine");
  check(!wire_verify(prior,proof.data(),proof.size()),"affine proof rejected by wire");
  check(!run_verifier(AFFINE_LABEL+1,run.wire.product.plan,run,affine_bind,affine_decide,proof.data(),proof.size()),"wrong label");
  // Full upper bound: 64 coordinates + 64 wires + 64 affine rows, 8 terms each.
  auto redundant=relation;while(redundant.terms.size()<8)redundant.terms.push_back({1,15,F{0}});
  auto many=affine_size(set,4,7,7,stages,std::vector<Coordinate>(64,coordinates[0]),
      std::vector<WireEquality>(64,wires[0]),std::vector<AffineRelation>(64,redundant));
  check(many.wire.product.plan->holds(),"maximum count plan");Writer mp;ToyCoins mc(333);
  affine_prove(many,abc,engine,mc,mp);check(affine_verify(many,mp.data(),mp.size()),"maximum counts proof");
  auto bytes=proof.bytes();size_t flips=0,cuts=0;
  for(size_t i=0;i<bytes.size();i+=97,++flips){bytes[i]^=1;check(!affine_verify(run,bytes.data(),bytes.size()),"corruption");bytes[i]^=1;}
  for(size_t n=0;n<bytes.size();n+=1+bytes.size()/40,++cuts)check(!affine_verify(run,bytes.data(),n),"truncation");
  check(!affine_verify(run,bytes.data(),bytes.size()-1),"last byte cut");bytes.push_back(0);check(!affine_verify(run,bytes.data(),bytes.size()),"trailing byte");
  std::printf("PASS: %zu proof bytes; 2 complete affine-only malicious proofs rejected; 4 statement mutations; max 64/64/64 counts and 8 terms; %zu flips; %zu cuts plus last byte; bidirectional domains; independent coefficients\n",proof.size(),flips,cuts);
}
