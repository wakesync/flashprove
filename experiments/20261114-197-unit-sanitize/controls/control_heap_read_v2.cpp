// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

// Negative control for prover/tests/unit.sh --sanitize (experiments/20261114-197-unit-sanitize,
// amendment 1): a read one element past the end of a heap array. The pointer itself is volatile,
// so the compiler cannot see which object it points into and the undefined-behaviour sanitizer's
// object-size check does not fire first (it did on control_heap_read.cpp in run 1); the address
// sanitizer must report it ("ERROR: AddressSanitizer: heap-buffer-overflow", status 97).
int main() {
  volatile unsigned long n = 4;
  long *a = new long[n]();
  long *volatile p = a;
  volatile unsigned long past = 4;
  const long v = p[past];
  delete[] a;
  return v == 12345;
}
