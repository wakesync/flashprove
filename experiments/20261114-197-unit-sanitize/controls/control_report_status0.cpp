// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

// Control for prover/tests/unit.sh --sanitize (experiments/20261114-197-unit-sanitize, amendment 2):
// a sanitizer report in a process that ends with status 0. The program starts itself once more with
// UBSAN_OPTIONS=exitcode=0 in its own environment, as a caller's setting would be if it got past
// unit.sh's check of the caller's variables, and there overflows a signed int. Built with
// --sanitize, the report ("runtime error: signed integer overflow") goes to the standard error
// stream and the process that unit.sh started ends with status 0: unit.sh must still count the run
// as failed, from the report in the log. Built without sanitizers it returns 0 and prints nothing.
#include <climits>
#include <cstdlib>
#include <unistd.h>
int main(int, char **argv) {
  if (!getenv("CONTROL_REPORT_STATUS0_SECOND")) {
    setenv("CONTROL_REPORT_STATUS0_SECOND", "1", 1);
    setenv("UBSAN_OPTIONS", "exitcode=0", 1);
    execv("/proc/self/exe", argv);
    return 3; // it could not start itself
  }
  volatile int big = INT_MAX;
  volatile int one = 1;
  volatile int sink = big + one;
  (void)sink;
  return 0;
}
