// Copyright 2026 wakesync
// SPDX-License-Identifier: Apache-2.0
// A word append must match a byte append at every offset, including split blocks.
#include "hash/hash.h"
#include <cstdio>
#include <cstdlib>
#include <csignal>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>
using namespace blk;

static unsigned checks = 0;
static void check(bool ok) { ++checks; if (!ok) std::abort(); }
static void byte_word(Hasher &h, u64 w) {
  u8 b[8];
  for (unsigned j = 0; j < 8; ++j) b[j] = u8(w >> (8*j));
  h.push(b, 8);
}
static bool refuses_finished(bool prefix) {
  const pid_t child = fork();
  if (child < 0) return false;
  if (child == 0) {
    const rlimit no_core{0, 0}; setrlimit(RLIMIT_CORE, &no_core);
    close(STDERR_FILENO);
    Hasher h(Domain::STATEMENT, 0);
    h.push_u64(1);
    if (prefix) (void)h.before_nonce(); else (void)h.finish();
    h.push_u64(2);
    _exit(0);
  }
  int status = 0;
  if (waitpid(child, &status, 0) != child) return false;
  return WIFSIGNALED(status) && WTERMSIG(status) == SIGABRT;
}
int main() {
  std::vector<u8> prefix(257), suffix(129);
  for (size_t j = 0; j < prefix.size(); ++j) prefix[j] = u8(j*83+17);
  for (size_t j = 0; j < suffix.size(); ++j) suffix[j] = u8(j*37+29);
  for (size_t n = 0; n <= 256; ++n)
    for (unsigned count = 1; count <= 34; ++count)
      for (size_t tail : {size_t(0), size_t(1), size_t(127), size_t(128), size_t(129)}) {
        Hasher a(Domain::STATEMENT, 7), b(Domain::STATEMENT, 7);
        a.push(prefix.data(), n); b.push(prefix.data(), n);
        for (unsigned j = 0; j < count; ++j) {
          const u64 w = 0xfedcba9876543210ULL ^ (u64(j)*0x9e3779b97f4a7c15ULL);
          a.push_u64(w); byte_word(b, w);
          check(a.bytes() == b.bytes());
        }
        a.push(suffix.data(), tail); b.push(suffix.data(), tail);
        check(a.finish() == b.finish());
      }
  Digest start{}; start.w[0] = 42;
  for (unsigned n = 0; n < 64; ++n) {
    Hasher a(Domain::CHAIN_QUERY, 3, start), b(Domain::CHAIN_QUERY, 3, start);
    for (unsigned i = 0; i < n; ++i) { a.push_u64(i); byte_word(b, i); }
    a.push_u64(0x1234); byte_word(b, 0x1234);
    const auto x = a.before_nonce(), y = b.before_nonce();
    check(x.fill == y.fill && x.steps == y.steps);
    for (unsigned j = 0; j < HashFn::CVW; ++j) check(x.cv[j] == y.cv[j]);
    for (unsigned j = 0; j < HashFn::BLKW; ++j) check(x.block[j] == y.block[j]);
  }
  check(refuses_finished(false)); check(refuses_finished(true));
  std::printf("ok %u word-feed checks\n", checks);
}
