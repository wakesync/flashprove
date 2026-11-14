// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

// Negative control for prover/tests/unit.sh --sanitize (experiments/20261114-197-unit-sanitize):
// a read one element past the end of a heap array. `volatile` hides the index from the compiler.
// Built with --sanitize it must be reported ("ERROR: AddressSanitizer: heap-buffer-overflow",
// status 97).
int main() {
  volatile unsigned long n = 8;
  int *a = new int[n];
  for (unsigned long i = 0; i < n; i++) a[i] = 0;
  volatile unsigned long past = n;
  const int v = a[past];
  delete[] a;
  return v == 12345;
}
