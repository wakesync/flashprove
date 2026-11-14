// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

// Negative control for prover/tests/unit.sh --sanitize (experiments/20261114-197-unit-sanitize):
// a signed int overflow, which C++ leaves undefined. `volatile` hides the values from the compiler.
// Built with --sanitize it must be reported ("runtime error: signed integer overflow", status 97).
#include <climits>
int main() {
  volatile int big = INT_MAX;
  int one = 1;
  int sum = big + one;
  return sum > 0 ? 1 : 0;
}
