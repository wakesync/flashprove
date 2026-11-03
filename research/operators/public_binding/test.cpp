#include <cstdio>
#include <cstdlib>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "product.h"
using namespace blk;
static void check(bool ok, const char *s) { if (!ok) { std::fprintf(stderr, "FAIL: %s\n", s); std::exit(1); } }
// Test-only dishonest prover: binds the REAL verifier statement, commits a valid
// product table with wrong coordinates, then supplies truthful coordinate targets
// to its local IOPP. No verifier code or guard is changed. Hash-only binding would
// accept this transcript if the verifier omitted the coordinate rows.
static Writer malicious(const CoordinateRun &run, const Table &abc) {
  EngineCpu engine; ToyCoins coins(333); Writer proof;
  Binder b(COORDINATE_LABEL, run.product.plan);
  auto in = coordinate_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&engine](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins);
  FoldMask mask; auto g = toy_prove_preamble(pr, in.product, abc, mask);
  auto lies = ch.get(in.coordinates);
  for (auto &c : lies) c.value = abc.at(c.row, c.column).c[0];
  coordinate_rows(pr.st, g, lies);
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask));
  ch.finish(); pr.st.require_all_tested(); return proof;
}
int main() {
  Setting set = setting_goldilocks(); set.hash_block_bytes = HASH_BLOCK_BYTES;
  set.target = 10; set.set_work(ErrorKind::QUERY, Scope::REQUEST, 6);
  auto run = coordinate_size(set, 4, 7, 7, {{1,1,8,8},{0,0,9,9}},
                             {{0,0,F{2}}, {1,15,F{18}}, {2,7,F{90}}});
  check(run.product.plan->holds(), "plan holds");
  Table abc(1,3,16);
  for (u64 i=0; i<16; ++i) {
    abc.set(0,i,E::from(F{i+2})); abc.set(1,i,E::from(F{i+3}));
    abc.set(2,i,abc.at(0,i)*abc.at(1,i));
  }
  // Independent integer remainder, not the library multiplication algorithm.
  for (u64 a : {0ULL,1ULL,2ULL,0xffffffff00000000ULL})
    for (u64 b : {0ULL,1ULL,19ULL,0xfffffffeffffffffULL})
      check((F{a}*F{b}).v == (u64)(((__uint128_t)a*b)%P), "independent field product");
  for (u64 i=0;i<16;++i) check(abc.at(2,i)==E::from(F{(i+2)*(i+3)}), "integer product table");
  // Check coordinate coefficient layout independently over every flattened entry.
  for (const auto &c : run.coordinates) {
    std::vector<E> point(4); for(unsigned j=0;j<4;++j) point[j]=(c.column>>j)&1?E::one():E::zero();
    Tensor t=Tensor::eq(point.data(),4); t.insert_choice(0,2,c.row);
    for(u64 i=0;i<64;++i) check(t.at(i)==(i==c.row+4*c.column?E::one():E::zero()), "coordinate unit vector");
  }
  EngineCpu engine; ToyCoins coins(123); Writer proof;
  coordinate_prove(run,abc,engine,coins,proof);
  const char *why=nullptr;
  check(coordinate_verify(run,proof.data(),proof.size(),&why), why?why:"honest proof");
  for(size_t j=0;j<run.coordinates.size();++j) {
    auto changed=run; changed.coordinates[j].value=changed.coordinates[j].value+F::one();
    check(!coordinate_verify(changed,proof.data(),proof.size()), "changed public value");
    changed=run; changed.coordinates[j].column ^= 1;
    check(!coordinate_verify(changed,proof.data(),proof.size()), "changed public column");
    changed=run; changed.coordinates[j].row=(changed.coordinates[j].row+1)%3;
    check(!coordinate_verify(changed,proof.data(),proof.size()), "changed public row");
  }
  // Each malicious table remains a*b=c everywhere, with one bound coordinate false.
  for(size_t j=0;j<run.coordinates.size();++j) {
    Table wrong=abc; auto c=run.coordinates[j];
    u64 r=c.row==2?0:c.row;
    wrong.set(r,c.column,wrong.at(r,c.column)+E::one());
    wrong.set(2,c.column,wrong.at(0,c.column)*wrong.at(1,c.column));
    auto attack=malicious(run,wrong);
    check(!coordinate_verify(run,attack.data(),attack.size()), "malicious wrong coordinate proof");
  }
  check(!run_verifier(COORDINATE_LABEL+1,run.product.plan,run,coordinate_bind,coordinate_decide,proof.data(),proof.size()), "domain separation");
  const auto original = toy_size(set,4,7,7,{{1,1,8,8},{0,0,9,9}});
  check(original.plan->holds(), "original toy plan");
  check(!toy_verify(original,proof.data(),proof.size()), "original toy cross-domain");
  auto bytes=proof.bytes(); size_t flips=0,cuts=0;
  for(size_t i=0;i<bytes.size();i+=97,++flips) { bytes[i]^=1; check(!coordinate_verify(run,bytes.data(),bytes.size()),"corruption"); bytes[i]^=1; }
  for(size_t n=0;n<bytes.size();n+=1+bytes.size()/40,++cuts) check(!coordinate_verify(run,bytes.data(),n),"truncation");
  check(!coordinate_verify(run,bytes.data(),bytes.size()-1),"last-byte truncation");
  bytes.push_back(0); check(!coordinate_verify(run,bytes.data(),bytes.size()),"appended byte");
  std::printf("PASS: %zu proof bytes; 3 malicious proofs rejected; 9 public mutations; %zu flips; %zu cuts plus last byte; domains; independent field/layout checks\n",proof.size(),flips,cuts);
}
