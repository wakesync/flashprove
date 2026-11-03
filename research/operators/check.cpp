// Research constraint evaluator, not a proof verifier.
// Uses upstream Goldilocks arithmetic without modifying upstream sources.
#include "field/field.h"
#include <iostream>
#include <vector>
int main() {
  using namespace blk;
  size_t n, m, pubs;
  if (!(std::cin >> n >> m >> pubs) || n < 1 || n > 100000 || m > 100000 || pubs > n) return 2;
  std::vector<F> w(n);
  for (auto &x : w) if (!(std::cin >> x.v) || x.v >= P) return 2;
  bool ok = w[0] == F::one();
  for (size_t j=0; j<pubs; ++j) {
    size_t i; u64 v;
    if (!(std::cin >> i >> v) || i>=n || v>=P) return 2;
    ok &= w[i].v == v;
  }
  for (size_t j=0; j<m; ++j) {
    F a[3];
    for (auto &v : a) {
      size_t count;
      if (!(std::cin >> count) || count > n) return 2;
      v=F::zero();
      for (size_t t=0; t<count; ++t) {
        size_t i; u64 coeff;
        if (!(std::cin >> i >> coeff) || i>=n || coeff>=P) return 2;
        v += w[i]*F{coeff};
      }
    }
    ok &= a[0]*a[1] == a[2];
  }
  std::string tail;
  if (std::cin >> tail) return 2;
  std::cout << (ok ? "CONSTRAINTS SATISFIED (not a cryptographic proof)" : "CONSTRAINTS REJECTED") << '\n';
  return ok ? 0 : 1;
}
