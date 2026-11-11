// SPDX-License-Identifier: Apache-2.0
// Follow-up cases, all use verify_m2. Included after that entry is defined.
// No test-only bypass in the normal verifier. The control binary disables ONLY cg admission.
struct SparseCase { HeadConsts hc; PublicIn in; };
static SparseCase sparse_case(const HeadParams &hp) {
  SparseCase c; const int D=hp.D, T=hp.T;
  c.hc.W.assign(12*D,0); c.hc.G.assign(D,0);
  for(int k=0;k<3*D;k++) c.hc.W[4*k]=4096;
  c.in.S0.assign(D*D,0); c.in.ST=c.in.S0; c.in.H.assign(9*D,0);
  c.in.xq.assign(T,std::vector<i64>(D,0)); c.in.xk=c.in.xq; c.in.xv=c.in.xq;
  c.in.z=c.in.xq; c.in.y=c.in.xq; c.in.ar.assign(T,0); c.in.br.assign(T,0);
  return c;
}
static Verdict fresh_proof(const HeadParams &hp, SparseCase c, std::string &why) {
  Derived z; PubStage ps=public_stage(hp,c.hc,c.in,z);
  if(!ps.ok) {why=ps.why;return Verdict::DERIVE;}
  Built b=build(hp,z,false);
  if(b.overflow || b.refused) {why=b.why;return Verdict::DERIVE_BUILD;}
  c.in.ST=b.S.back(); c.in.y=b.y; z.ST=c.in.ST; z.y=c.in.y;
  b=build(hp,z,false); Table tab=table_of(b);
  if(b.overflow || b.refused || !products_hold_all(tab) || violated(b.rel,tab)) {why="boundary witness construction failed";return Verdict::DERIVE_BUILD;}
  Sized sz=size_run(b); if(!sz.ok) {why="boundary sizing failed";return Verdict::DERIVE_BUILD;}
  Proved pr; if(!two_prove(*sz.run,tab,Hostile(),pr)) {why="boundary prover failed";return Verdict::PROOF;}
  auto bytes=pr.proof.bytes(); VerifyTiming tm;
  Verdict got=verify_m2(c.hc,encode2(hp,c.in),bytes.data(),bytes.size(),&tm);why=tm.why;return got;
}
static void followup_cases(Suite &S,const HeadParams &hp,bool control) {
  auto reject=[&](const char *cls,const std::string &name,const SparseCase &c) {
    VerifyTiming tm; auto w=encode2(hp,c.in);
    Verdict v=verify_m2(c.hc,w,nullptr,0,&tm);
    S.report(cls,name,v,Verdict::DERIVE,-1,tm.why.c_str());
  };
  if(!control) {
    { auto c=sparse_case(hp); for(auto &z:c.in.z) z[0]=16;
      c.hc.G[0]=-(__int128)(CGBOUND-1)*512;
      std::string why; Verdict v=fresh_proof(hp,c,why);
      S.report("cg-boundary-neg","cg = -(2^24-1), honest zero-state proof",v,Verdict::ACCEPT,-1,why.c_str());
      c.hc.G[0]=-(__int128)CGBOUND*512;
      reject("cg-boundary-neg","cg = -2^24",c);
    }
    { auto c=sparse_case(hp); c.in.xv[0][0]=16; c.hc.silu[2049]=VBOUND-1;
      // k=0 keeps state zero even for v at its boundary. The delta split is in contract.
      std::string why; Verdict v=fresh_proof(hp,c,why);
      S.report("v-boundary","corrupted SiLU copy: v = 2^31-1, honest proof",v,Verdict::ACCEPT,-1,why.c_str());
      c.hc.silu[2049]=VBOUND; reject("v-boundary","corrupted SiLU copy: v = 2^31",c);
      c.hc.silu[2049]=-VBOUND; reject("v-boundary","corrupted SiLU copy: v = -2^31",c);
    }
    for(int gate=0;gate<2;gate++) for(i64 value: {-1LL,4097LL}) {
      auto c=sparse_case(hp); (gate ? c.hc.sigmoid:c.hc.decay)[2048]=value;
      reject("derive-class",std::string(gate?"beta":"a")+" table entry = "+std::to_string(value),c);
    }
    {auto c=sparse_case(hp); c.in.xk[0][0]=4096;c.hc.k_numerator_scale=8192; reject("derive-class","k numerator constant doubled",c);}
    {auto c=sparse_case(hp); c.in.xq[0][0]=4096;c.hc.q_divisor_scale=1;c.hc.q_numerator_scale=8192; reject("derive-class","q constants corrupted",c);}
    {auto c=sparse_case(hp);
      // Review #66 case 19: exact accumulator 2^64-2^32, floor /4096 near 2^52.
      c.hc.W[8*hp.D]=(i64(1)<<32); c.hc.W[8*hp.D+1]=(i64(1)<<32); c.hc.W[8*hp.D+2]=(i64(1)<<31);
      c.in.xv[0][0]=VBOUND-1;c.in.H[2*hp.D]=VBOUND-1;c.in.H[5*hp.D]=2;
      reject("recompute-overflow","review conv accumulator: taps (2^32,2^32,2^31,0), inputs (2^31-1,2^31-1,2,0)",c);
    }
    {auto c=sparse_case(hp);c.hc.silu[2049]=764531127;
      for(auto &x:c.in.xk) std::fill(x.begin(),x.end(),16);
      reject("recompute-overflow","review L2 sum: all 128 u = 764531127 (corrupted SiLU copy)",c);
    }
    {auto c=sparse_case(hp);c.hc.silu[2049]=i64(1)<<39;c.in.xq[0][0]=16;
      reject("recompute-overflow","q numerator u=2^39: checked square rejects before numerator (corrupted SiLU copy)",c);
    }
  }
  // Design part A's compatible derived statements: q0=362, a=4096, beta=0, k=v=0,
  // S00=ceil(o0*4096/362), constant state, o0 in {4096,8192}, cg0=2^52..2^62.
  // The design uses unclamped floating tables outside this build's domain. Adapter: verifier
  // copies decay[2048]=4096 and sigmoid[2048]=0, z0=16, G0=cg*512. This is explicit
  // synthetic configuration, not a claim those raw design inputs fit the pinned tables.
  for(i64 ov: {4096LL,8192LL}) for(int e=52;e<=62;e++) {
    auto c=sparse_case(hp); c.hc.decay[2048]=4096;c.hc.sigmoid[2048]=0;
    c.in.S0[0]=(ov*4096+361)/362;c.in.ST=c.in.S0;
    for(int t=0;t<hp.T;t++) {c.in.xq[t][0]=4096;c.in.z[t][0]=16;}
    const i64 cg=i64(1)<<e; c.hc.G[0]=(__int128)cg*512;
    const u64 residue=(fi(cg)*fi(4096)).v;
    const i64 signed_residue=residue>P/2?-(i64)(P-residue):(i64)residue;
    const i64 ya=fdiv(signed_residue,4096),ra=signed_residue-ya*4096;
    for(auto &y:c.in.y)y[0]=ya;
    const std::string name="design A o0="+std::to_string(ov)+", cg0=2^"+std::to_string(e);
    if(!control) {reject("cg-alias-design-A",name,c);continue;}
#ifdef M2_CONTROL_NO_CG_CHECK
    // Construct the honest recurrence/norm witness at cg=0 first, avoiding a host product
    // cg*w beyond i64. Only the final y remainder and public y become the modular alias.
    auto safe=c;safe.hc.G[0]=0;for(auto &y:safe.in.y)y[0]=0;
    Derived zs;auto ps=public_stage(hp,safe.hc,safe.in,zs);
    Built b=build(hp,zs,false); bool ok=ps.ok && !b.overflow && !b.refused;
    for(int t=0;t<hp.T;t++)ok=ok && b.o[t][0]==ov && b.w[t][0]==4096 && b.S[t]==c.in.S0;
    Derived za;ps=public_stage(hp,c.hc,c.in,za);Built relations=build(hp,za,true);
    Table tab=table_of(b);
    for(int t=0;t<hp.T;t++)tab.set(0,b.place(b.norm[t].ry_key[0]),E::from(fi(ra)));
    ok=ok && ps.ok && !relations.overflow && products_hold_all(tab) && violated(relations.rel,tab)==0;
    VerifyTiming tm;Verdict v=Verdict::DERIVE_BUILD;
    if(ok) {Sized sz=size_run(relations);Proved pr;
      if(sz.ok && two_prove(*sz.run,tab,Hostile(),pr)) {
        auto bytes=pr.proof.bytes();v=verify_m2(c.hc,encode2(hp,c.in),bytes.data(),bytes.size(),&tm);
      } else tm.why="alias prover or sizing failed";
    } else tm.why="alias construction failed";
    S.report("control-cg-alias-design-A",name,v,Verdict::ACCEPT,-1,tm.why.c_str());
#else
    check(false,"control mode requires separately compiled control binary");
#endif
  }
}
