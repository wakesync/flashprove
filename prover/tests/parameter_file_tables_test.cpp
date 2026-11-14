// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

// Host-only parse/admission probe. It deliberately computes no public table digest.
// unit.sh build tests/parameter_file_tables_test.cpp <output>
// <output>/parameter_file_tables_test <policy.txt>
// Exit 0: admitted, 1: parse failure, 2: limit failure, 3: usage/read failure.
// See experiments/20261113-182-reader-parity/README.md for the regression matrix.
#include "common/parameter_file.h"
#include <cstdio>
int main(int argc, char **argv) {
  std::string bytes;
  using namespace parameter_file;
  if (argc != 2 || read_once(argv[1], bytes, PARAMETER_FILE_MOST) != Found::Read) {
    std::puts("input: unreadable or wrong argument count");
    return 3;
  }
  Parameters p;
  const std::string parsed = parse(bytes, p);
  std::printf("parse: %s\n", parsed.empty() ? "ok" : parsed.c_str());
  if (!parsed.empty()) {
    std::puts("admission: not-run");
    return 1;
  }
  const std::string limit = limit_missed(p);
  std::printf("admission: %s\n", limit.empty() ? "ok" : limit.c_str());
  return limit.empty() ? 0 : 2;
}
