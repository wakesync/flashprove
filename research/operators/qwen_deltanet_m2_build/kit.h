// SPDX-License-Identifier: Apache-2.0
// Research-only: the hostile-suite kit shared by stage1.cpp and m2.cpp. Every "complete" case is a
// whole proof written by a hostile prover (two_lookup_prove.h) on a tampered table whose product
// gates all hold, checked by the UNCHANGED verifier through the stage's entry point.
#pragma once
#include "head.h"

struct Suite {
  int as_expected = 0, total = 0;
  void report(const char *cls, const std::string &what, Verdict got, Verdict want, long long violated = -1, const char *why = "") {
    total++; const bool good = got == want; as_expected += good;
    std::printf("{\"mode\":\"hostile\",\"class\":\"%s\",\"attack\":\"%s\",\"violated_relations\":%lld,\"rejected\":%s,\"stage\":\"%s\",\"expected_stage\":\"%s\",\"as_expected\":%s,\"why\":\"%s\"}\n",
                cls, what.c_str(), violated, got != Verdict::ACCEPT ? "true" : "false", stage_name(got), stage_name(want), good ? "true" : "false", why);
    std::fflush(stdout);
  }
  void summary() { std::printf("{\"mode\":\"hostile-summary\",\"as_expected\":%d,\"total\":%d,\"peak_rss_kb\":%ld}\n", as_expected, total, rss_kb()); std::fflush(stdout); }
};
// Table edits. A gate column keeps a b = c; a range or key cell is [x, 0, 0].
struct Edit {
  const Built &b; Table &t;
  void gate_a(u64 c, i64 d) { const u64 p = b.place(c); const E x = t.at(0, p) + E::from(fi(d)); t.set(0, p, x); t.set(2, p, x * t.at(1, p)); }
  void gate_b(u64 c, i64 d) { const u64 p = b.place(c); const E y = t.at(1, p) + E::from(fi(d)); t.set(1, p, y); t.set(2, p, t.at(0, p) * y); }
  void gate_ab(u64 c, i64 d) { const u64 p = b.place(c); const E x = t.at(0, p) + E::from(fi(d)), y = t.at(1, p) + E::from(fi(d)); t.set(0, p, x); t.set(1, p, y); t.set(2, p, x * y); }
  void cell(u64 c, i64 d) { const u64 p = b.place(c); t.set(0, p, t.at(0, p) + E::from(fi(d))); }
  i64 key(u64 c) const { return (i64)t.at(0, b.place(c)).c[0].v; }
};
// The proof bytes with [a0, a1) and [b0, b1) (adjacent, a1 == b0) exchanged.
static std::vector<u8> exchanged(const std::vector<u8> &p, size_t a0, size_t a1, size_t b1) {
  std::vector<u8> out(p.begin(), p.begin() + a0);
  out.insert(out.end(), p.begin() + a1, p.begin() + b1);
  out.insert(out.end(), p.begin() + a0, p.begin() + a1);
  out.insert(out.end(), p.begin() + b1, p.end());
  return out;
}
// dst segment overwritten by the first bytes of the src segment (lengths kept).
static std::vector<u8> overwritten(const std::vector<u8> &p, size_t dst0, size_t dst1, size_t src0, size_t src1) {
  std::vector<u8> out = p;
  for (size_t i = 0; dst0 + i < dst1; i++) out[dst0 + i] = p[src0 + i % (src1 - src0)];
  return out;
}
