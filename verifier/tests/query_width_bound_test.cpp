// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

// Terms: docs/glossary.md.

// Tests queryWidthWithinBound() (verifier/src/vf_widths_and_bounds.h) by itself: the bound on the
// query width dq = H * dh that layout() in cp_verify.cpp asks under the name "shape-heads".
// It includes that header alone and runs no other line of the verifier, so it shows nothing about
// where layout() calls the function; planning calls show that (the experiment
// experiments/20261114-195-dq-ne-d-admission, cases T7b).
//
// build and run, from verifier/src:
//   g++ -std=c++17 -O2 -DDIGEST_WORDS=8 -I . ../tests/query_width_bound_test.cpp -o <program> && <program>
// with the sanitizers: add -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all
// status 0 and a last line "query_width_bound_test: ok (..)": all as expected; 1: not.
#include "vf_widths_and_bounds.h"
#include <cstdio>

static int checks = 0, failures = 0;
static void expect(bool held, u64 H, u64 dh, const char *what) {
  checks++;
  if (held) return;
  failures++;
  printf("NOT AS EXPECTED: H = %llu, dh = %llu: %s\n", (unsigned long long)H, (unsigned long long)dh, what);
}

int main() {
  static_assert(QUERY_WIDTH_MOST == 1048576, "the bound is 2^20, the bound on d");
  // At the bound and below: admitted.
  const u64 in[][2] = {{1, 1ull << 20}, {32, 32768}, {63, 128}, {24, 256}, {1, 2}, {4, 128}};
  for (auto &c : in) expect(queryWidthWithinBound(c[0], c[1]), c[0], c[1], "at most 2^20, and not admitted");
  // Above the bound: refused. The last three products do not fit 64 bits or come close; a product
  // formed in 64 bits would wrap to a small number at (2^32, 2^32) and at (2^63, 2).
  const u64 out[][2] = {{33, 32768},        {3, 1ull << 19},    {1, 1ull << 21},        {63, 1ull << 31},
                        {~0u, ~0u},         {1ull << 32, 1ull << 32}, {1ull << 63, 2},  {~0ull, ~0ull},
                        {(1ull << 20) + 1, 1}, {1, (1ull << 20) + 1}};
  for (auto &c : out) expect(!queryWidthWithinBound(c[0], c[1]), c[0], c[1], "above 2^20, and admitted");
  // Every H that "shape-heads" can pass on (1 to 64) with every power of two dh from 2 to 2^31:
  // the function agrees with a form that multiplies nothing, H <= floor(2^20 / dh).
  u64 admitted = 0;
  for (u64 H = 1; H <= 64; H++)
    for (int k = 1; k <= 31; k++) {
      const u64 dh = 1ull << k;
      const bool other = H <= (1ull << 20) / dh;
      expect(queryWidthWithinBound(H, dh) == other, H, dh, "differs from H <= floor(2^20 / dh)");
      admitted += queryWidthWithinBound(H, dh);
    }
  // With H >= 1 an admitted pair has dh <= 2^20, so log2(dh) is at most 20.
  for (int k = 21; k <= 63; k++) expect(!queryWidthWithinBound(1, 1ull << k), 1, 1ull << k, "dh above 2^20 admitted with H = 1");
  if (failures) return printf("query_width_bound_test: FAILED (%d of %d checks)\n", failures, checks), 1;
  printf("query_width_bound_test: ok (%d checks; %llu of 1984 pairs (H, dh) with H in 1..64 and dh = 2^1..2^31 admitted)\n", checks,
         (unsigned long long)admitted);
  return 0;
}
