// Searches proximity-test stage parameters for a product table of 2^L columns, using ONLY the
// unchanged planner (coordinate_size_plan from research/operators/public_binding). Prints one line
// per L: L bytes log_n mask_log_n stages k h log_n mask_log_n ... . Plan-only: proves nothing.
//   plan_search TARGET WORK L_FROM L_TO
#include <cstdio>
#include <cstdlib>
#include "engine/engine_cpu.h"
#include "../operators/public_binding/product.h"
using namespace blk;
static std::vector<StageChoice> family(unsigned L,unsigned k,unsigned h,unsigned rho,unsigned base,unsigned first_mask){
  std::vector<StageChoice> st;int ell=(int)L;bool first=true;
  do{ell-=(int)k;unsigned ln=(unsigned)ell+rho;st.push_back({k,h,ln,first?std::min(ln,first_mask):ln});first=false;}while(ell>(int)(base+k));
  st.push_back({0,0,(unsigned)ell+rho,(unsigned)ell+rho});return st;
}
int main(int argc,char**argv){
  if(argc!=5)return 2;
  Setting set=setting_goldilocks();set.hash_block_bytes=HASH_BLOCK_BYTES;
  set.target=(unsigned)atoi(argv[1]);set.set_work(ErrorKind::QUERY,Scope::REQUEST,(unsigned)atoi(argv[2]));
  for(unsigned L=(unsigned)atoi(argv[3]);L<=(unsigned)atoi(argv[4]);++L){
    const u64 rows=u64(4)<<L; // >= linear claims of any generated slice at this width (checked by the runner)
    u64 best=~u64(0);std::string d="none";
    for(unsigned r1:{2u,3u})for(unsigned m1:{9u,10u,11u})for(unsigned k:{2u,3u,4u})for(unsigned h=1;h<=k&&h<=3;++h)
    for(unsigned rho:{1u,2u,3u})for(unsigned base:{3u,6u})for(unsigned mf:{11u,13u,40u}){
      if(L<base+k+1||m1>L+r1)continue;auto st=family(L,k,h,rho,base,mf);
      auto run=coordinate_size_plan(set,L,L+r1,m1,st,rows);if(!run.plan->holds())continue;
      const u64 b=run.plan->size_of(0).bytes;if(b>=best)continue;best=b;
      d=std::to_string(L+r1)+" "+std::to_string(m1)+" "+std::to_string(st.size());
      for(auto &s:st)d+=" "+std::to_string(s.k)+" "+std::to_string(s.h)+" "+std::to_string(s.log_n)+" "+std::to_string(s.mask_log_n);
    }
    std::printf("%u %llu %s\n",L,(unsigned long long)(best==~u64(0)?0:best),d.c_str());std::fflush(stdout);
  }
}
