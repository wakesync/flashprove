// SPDX-License-Identifier: Apache-2.0
#include "head.h"
#include <climits>
int main() {
  unsigned long long count=0;
  auto test=[&](i64 n) {i64 r=isqrt64(n);check(r>=0 && (__int128)r*r<=n && (__int128)(r+1)*(r+1)>n,"integer sqrt postcondition");count++;};
  test(0);test(1);test(LLONG_MAX);
  // Squares and neighbours across the entire admitted host domain, including its upper edge.
  for(i64 r: {0LL,1LL,2LL,4096LL,8192LL,16777215LL,94906265LL,3037000498LL,3037000499LL}) {
    const i64 square=r*r;test(square);if(square)test(square-1);if(square<LLONG_MAX)test(square+1);
  }
  for(i64 r=0;r<=100000;r++) {test(r*r);if(r)test(r*r-1);test(r*r+1);}
  u64 seed=73;for(int k=0;k<100000;k++) {seed=seed*6364136223846793005ULL+1;test(i64(seed>>1));}
  std::printf("{\"test\":\"pure-integer-isqrt\",\"cases\":%llu,\"pass\":true,\"long_double_bytes\":%zu}\n",count,sizeof(long double));
}
