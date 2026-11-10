// SPDX-License-Identifier: Apache-2.0
// Research-only: the two-lookup composition ("arm B" of the Qwen DeltaNet M2 design, PR #66).
// The M1b run (research/operators/qwen_deltanet_lookup/lookup.h: wide affine product oracle + RNG
// with its digit lookup, one proximity-test group) plus a SECOND lookup instance, the remainder
// lookup: unshifted, one function, keys in parts, table {0 .. 2^12 - 1}. Its keys are never sent:
// they are cells of row a of the product oracle itself (message 0), in public aligned key regions.
// Messages on the channel, in order:
//   0  a, b, c         the product oracle; one mask row (PSC's masks and both lookups' masks)
//   1  fold mask
//   2  digits          RNG's digits
//   3  multiplicities  BOTH lookups' planes, in two disjoint fixed place ranges of row 0:
//                      RNG's from place 0, the remainder lookup's from place planes_first
// Rounds, in order: SEND 0/1, ZERO, PSC (a b = c), RNG Theta, SEND 2/3, digit lookup (shift, alpha,
// ...), remainder lookup (its own alpha, ...), RNG's batched row, the proximity test.
// So every message that holds keys or multiplicities of either lookup (0, 2, 3) is sent and sampled
// before the first challenge of either lookup, and the remainder lookup's alpha is drawn from a
// chain value that already depends on the whole digit-lookup transcript.
// The verifier below calls the library's rng_verify() and lkp_verify(), unchanged.
#pragma once
#include "../qwen_deltanet_lookup/lookup.h"
namespace blk {
constexpr u64 TWO_LABEL = 0x46503242ULL;  // own transcript domain ("FP2B")
constexpr unsigned REM_BITS = 12;         // the remainder table {0 .. 2^12 - 1}

// The key regions: part i has 2^part_bits[i] keys at places first_place[i] .. of row a (aligned).
struct KeySpec {
  std::vector<unsigned> part_bits;
  std::vector<u64> first_place;
};
// The remainder lookup's public inputs. No padding: an unused key cell holds 0, a row of the table.
inline LkpPublic rem_lookup(const KeySpec &ks, OracleId abc, OracleId multiplicities) {
  LkpPublic L;
  L.parts = ks.part_bits;
  L.d = REM_BITS;
  u64 keys = 0;
  for (unsigned v : ks.part_bits) keys += u64(1) << v;
  unsigned planes = 2;
  while ((u64(1) << planes) <= keys) planes++;  // the least with keys < 2^planes
  for (unsigned v : ks.part_bits) planes = std::max(planes, v + 1);
  L.mu = std::max(1u, ceil_log2(planes));
  L.live = planes == 1u << L.mu ? 0 : planes;
  L.g = 0, L.shifted = false;
  L.keys = {{0, 0, 0, 0}};
  L.tables = {{0, REM_BITS, 0, {}}};
  L.read_from = {abc, multiplicities};
  return L;
}
// The linear claims that the remainder lookup leaves: its own (tie, parts, key levels, table
// levels, leaves, bits, bits at the point, number of keys) and one key claim for each part.
inline u64 rem_rows(const LkpPublic &L) {
  u64 n = (L.planes() - 1) + (L.parts.size() - 1) + L.d + 4 + L.parts.size();
  for (unsigned v : L.parts) n += v;
  return n;
}
// Where the remainder lookup's multiplicities are: as rng_planes_at() (blocks/iop/rng.h), moved by
// first_place, which is a multiple of 2^(mu + d).
inline LkpPlanesAt rem_planes_at(const Statement &st, OracleId o, const LkpPublic &L, u64 first_place) {
  const unsigned row_bits = st.row_bits(o, Part::MAIN), place_bits = st.table_bits(o, Part::MAIN) - row_bits, mu = L.mu, d = L.d, planes = L.planes();
  BLK_REQUIRE((first_place & ((u64(1) << (mu + d)) - 1)) == 0, "remainder lookup: the planes' first place is not aligned");
  return [o, row_bits, place_bits, mu, d, planes, first_place](Row &row, Tensor v) {
    for (const std::pair<unsigned, unsigned> &block : lkp_live_blocks(planes)) {
      Tensor part = lkp_on_block(v, mu, block);
      const unsigned own = part.vars();
      part.insert_choice(own, place_bits - own, (first_place + ((u64)block.first << d)) >> own);
      part.insert_choice(0, row_bits, 0);
      row.add(o, Part::MAIN, std::move(part));
    }
  };
}
// The claims that the remainder lookup leaves on its keys, as linear claims on row a of the product
// oracle: key i of part p is the entry at place first_place[p] + i of row 0 of message `abc`.
inline void rem_key_rows(Statement &st, GroupId g, OracleId abc, const LkpPublic &L, const std::vector<u64> &first_place, LkpOutput &left) {
  const unsigned row_bits = st.row_bits(abc, Part::MAIN), place_bits = st.table_bits(abc, Part::MAIN) - row_bits;
  BLK_REQUIRE(first_place.size() == L.parts.size() && left.keys.parts() == L.parts.size(), "remainder lookup: not one key region for each part");
  for (size_t p = 0; p < L.parts.size(); p++) {
    LkpKeys k = left.keys.take(p);
    const unsigned v = L.parts[p];
    BLK_REQUIRE(v <= place_bits && (first_place[p] & ((u64(1) << v) - 1)) == 0 && (first_place[p] >> place_bits) == 0, "remainder lookup: a key region is not an aligned block of row a");
    BLK_REQUIRE(k.weights.entries.empty(), "remainder lookup: weights that LKP has not made");
    Row row;
    row.name = "the remainder keys at the point";
    for (const Tensor &w : k.weights.tensors) {
      BLK_REQUIRE(!w.has_dense() && w.vars() == v, "remainder lookup: weights that LKP has not made");
      Tensor t = w;
      t.insert_choice(v, place_bits - v, first_place[p] >> v);
      t.insert_choice(0, row_bits, 0);  // row a
      row.add(abc, Part::MAIN, std::move(t));
    }
    row.target = k.target;
    for (MaskTerm<E> &m : k.masks) row.add_mask(std::move(m));
    left.rows.push_back(row);
    st.add_row(g, std::move(row));
  }
}

struct TwoRun {
  ToyRun product;
  RngShape range;
  LkpPublic rem;
  std::vector<u64> key_places;
  u64 planes_first = 0;
  std::vector<WideRelation> relations;
};
// Whether two_size() would end the process on these inputs (a verifier asks this first and rejects).
inline const char *two_size_fault(const Setting &set, unsigned log_len, const std::vector<WideRelation> &relations, const RegionSpec &rs, const KeySpec &ks) {
  if (relations.empty() || relations.size() > (u64(1) << 23)) return "relation count out of range";
  if (log_len < 18 || log_len > 22) return "length out of range";
  const u64 len = u64(1) << log_len;
  for (const auto &a : relations) {
    if (wide_fault(a)) return "invalid wide relation";
    for (const auto &t : a.terms) if (t.column >= len) return "wide column out of range";
  }
  if (ks.part_bits.empty() || ks.part_bits.size() != ks.first_place.size() || rs.rows.size() != rs.first_place.size() || rs.rows.empty()) return "regions";
  std::vector<std::pair<u64, u64>> blocks;  // (first, size)
  for (size_t i = 0; i < rs.rows.size(); i++) {
    if (rs.rows[i] == 0 || (rs.rows[i] & (rs.rows[i] - 1)) || rs.columns != 16) return "range region";
    blocks.push_back({rs.first_place[i], rs.rows[i] * rs.columns});
  }
  for (size_t i = 0; i < ks.part_bits.size(); i++) {
    if (ks.part_bits[i] < 1 || ks.part_bits[i] > log_len) return "key region";
    blocks.push_back({ks.first_place[i], u64(1) << ks.part_bits[i]});
  }
  for (size_t i = 0; i < blocks.size(); i++) {
    if (blocks[i].first % blocks[i].second || blocks[i].first + blocks[i].second > len) return "a region is not an aligned block of the table";
    for (size_t j = 0; j < i; j++)
      if (blocks[i].first < blocks[j].first + blocks[j].second && blocks[j].first < blocks[i].first + blocks[i].second) return "two regions overlap";
  }
  (void)set;
  return nullptr;
}
inline TwoRun two_size(const Setting &set, unsigned log_len, unsigned log_n, unsigned mask_log_n, const std::vector<StageChoice> &further,
                       std::vector<WideRelation> relations, const RegionSpec &rs, const KeySpec &ks) {
  const char *fault = two_size_fault(set, log_len, relations, rs, ks);
  BLK_REQUIRE(!fault, fault ? fault : "");
  TwoRun run{ToyRun(set), RngShape(), LkpPublic(), ks.first_place, u64(1) << (log_len - 1), std::move(relations)};
  Plan plan(set);
  run.range = lk_rng_shape(set, rng_combinations(plan), rs, log_len);
  const RngShape &R = run.range;
  const LkpPublic L = rng_lookup(R);
  run.rem = rem_lookup(ks, R.masks_from, R.digits_in + 1);
  const LkpPublic &L2 = run.rem;
  fault = lkp_fault(L2);
  BLK_REQUIRE(!fault, fault ? fault : "");
  // The two planes ranges are disjoint, and neither covers the multiplicity message's pad (the last
  // 3 * samples places of its one main row: Send::pad()).
  BLK_REQUIRE(rng_planes_places(L) <= run.planes_first && run.planes_first + rng_planes_places(L2) + 3 * set.samples <= (u64(1) << log_len),
              "two lookups: the multiplicities do not fit their row in two disjoint ranges");
  const u64 rows = toy_rows_batched(set) + run.relations.size() + lk_rng_rows(R) + rem_rows(L2) + 2 * set.samples;
  GroupSize g;
  g.name = "a, b, c, digits, multiplicities";
  g.k = 3, g.h = 0;  // 4 + 2 + 1 main rows in a table of 8; one mask row
  g.main.name = "rows", g.main.log_n = log_n, g.main.ell = u64(1) << log_len;
  const u64 masks = 1 + 2 * u64(log_len) + 2 + 2 + lkp_masks(L) + lkp_masks(L2);
  g.mask.name = "mask row", g.mask.log_n = mask_log_n, g.mask.over_E = true;
  g.mask.ell = pow2_at_least(std::max<u64>(masks + set.samples, 2 * g.k + 1 - g.h));
  u64 t = 0;
  for (int turn = 0; turn < 16; turn++) {
    g.main.r = g.mask.r = tail_for(set, t);
    GroupLoad load; load.cube_bits = stage_cube_bits(g); load.batched_rows = rows;
    g = size_group(set, plan.scope(), g, load);
    if (analysis(set, g).bad()) { plan.refuse("no slack holds the first stage's rounds at the target"); run.product.plan = plan.finish(); return run; }
    const u64 more = plan_positions(plan, analysis(set, g).at.agree, Bound(Real::two_to(-(long)set.target - 30)));
    if (more <= t) break;
    t = more;
  }
  const std::vector<Stage> stages = solve_stages(plan, g, t, further);
  if (plan.refused()) { run.product.plan = plan.finish(); return run; }
  Codes &codes = run.product.shape.codes;
  run.product.stages = iopp_stages(stages, codes);
  if (const char *f = iopp_sized_fault(codes, run.product.stages, stages)) { plan.refuse(f); run.product.plan = plan.finish(); return run; }
  plan_chain_start(plan, "two-lookup run", true);
  toy_plan_preamble(plan, run.product.shape, run.product.stages, {g});
  plan_rng(plan, "range check", R.all_columns());
  const std::vector<OracleNotice> own = {R.digits, R.multiplicities};
  plan_send(plan, "digits", {SampleSize{Send::cube(codes, R.digits.shape).bits, {g}}, SampleSize{Send::cube(codes, R.multiplicities.shape).bits, {g}}},
            (unsigned)tree_sizes(codes, own).size());
  plan_lookup(plan, "range check: digit lookup", LookupSize{L.parts[0], L.d, L.mu, true, L.live});
  plan_lookup(plan, "remainder lookup", LookupSize{0, L2.d, L2.mu, false, L2.live, L2.parts});
  plan_bat_sigma(plan, "range check", R.equations());
  std::vector<TreeSize> trees = tree_sizes(codes, toy_first_message(OracleNotice{run.product.shape.oracle(), 0}, run.product.stages));
  for (const TreeSize &x : tree_sizes(codes, own)) trees.push_back(x);
  plan_iopp(plan, g.name, stages, trees, rows, 0, true);
  std::vector<std::pair<const char *, u64>> words = {{"affine-relations", run.relations.size()}, {"log-length", log_len}, {"log-n", log_n}, {"mask-log-n", mask_log_n},
      {"rng-columns", rs.columns}, {"rng-b0", rs.b0}, {"rng-b1", rs.b1}, {"rng-combinations", R.combinations}, {"rem-bits", REM_BITS}, {"rem-planes-first", run.planes_first}};
  for (size_t mu = 0; mu < rs.rows.size(); mu++) words.push_back({"rng-matrix-rows", rs.rows[mu]}), words.push_back({"rng-matrix-place", rs.first_place[mu]});
  for (size_t p = 0; p < ks.part_bits.size(); p++) words.push_back({"rem-part-bits", ks.part_bits[p]}), words.push_back({"rem-part-place", ks.first_place[p]});
  run.product.shape.text = toy_text("research-wide-affine-product-rng-rem-v1", set, words, further);
  run.product.plan = plan.finish();
  return run;
}
// The first query's items. Each lookup instance's public inputs stand under their own item name.
struct TwoPublic {
  ToyPublic product;
  Public<RngShape> range;
  Public<RngWeights> weights;
  Public<LkpPublic> rem;
  Public<std::vector<u64>> key_places;
  Public<u64> planes_first;
  Public<std::vector<WideRelation>> relations;
};
constexpr const char *ITEM_DIGITS = "range check: digit lookup";
constexpr const char *ITEM_REM = "remainder lookup";
inline TwoPublic two_bind_named(Binder &b, const TwoRun &run, const char *digits_item, const char *rem_item) {
  TwoPublic in;
  in.product = toy_bind_run(b, run.product);
  in.range = b.parameter(digits_item, run.range);
  in.weights = b.parameter("weights of the reads", RngWeights());
  in.rem = b.parameter(rem_item, run.rem);
  in.key_places = b.parameter("remainder lookup: the first places of the key regions in row a", run.key_places);
  in.planes_first = b.parameter("remainder lookup: the first place of its multiplicities", run.planes_first);
  in.relations = b.statement("wide sparse affine product relations v1", run.relations);
  return in;
}
inline TwoPublic two_bind(Binder &b, const TwoRun &run) { return two_bind_named(b, run, ITEM_DIGITS, ITEM_REM); }
// CONTROL ONLY (hostile suite): the two instances' public inputs bound under exchanged item names.
inline TwoPublic two_bind_relabelled(Binder &b, const TwoRun &run) { return two_bind_named(b, run, ITEM_REM, ITEM_DIGITS); }
inline bool two_decide(VerifierRounds &ch, const TwoPublic &in, Notes *notes) {
  VerifierContext vf(in.product.codes, ch); vf.notes = notes;
  GroupId g = 0; FoldMask mask;
  if (!toy_verify_preamble(vf, in.product, g, mask)) return false;
  const OracleId abc = vf.st.group(g).members[0];
  wide_rows(vf.st, g, ch.get(in.relations));
  RngOutput out;
  if (!rng_verify(vf, in.range, ch.get(in.weights), g, out)) return false;
  const RngShape &R = ch.get(in.range);
  const LkpPublic &L2 = ch.get(in.rem);
  BLK_REQUIRE(L2.read_from.size() == 2 && L2.read_from[0] == abc && L2.read_from[1] == R.digits_in + 1 && R.masks_from == abc, "two lookups: the remainder lookup reads other messages than the product oracle and the multiplicities");
  LkpOutput left;
  if (!lkp_verify(vf, in.rem, rem_planes_at(vf.st, R.digits_in + 1, L2, ch.get(in.planes_first)), R.masks_from, g, left)) return false;
  rem_key_rows(vf.st, g, abc, L2, ch.get(in.key_places), left);
  E x; vf.st.add_row(g, rng_row(vf, in.range, out, x));
  if (!iopp_verify(vf, g, in.product.stages, in.product.choice, std::move(mask))) return false;
  vf.st.require_all_tested(); return true;
}
// Library internal. NOT a verifier entry: it takes caller-built relations. The entries are in
// stage1.cpp and m2.cpp; they derive the run from statement words.
inline bool two_verify(const TwoRun &run, const u8 *proof, size_t bytes, const char **why = nullptr, Notes *notes = nullptr) {
  return run_verifier(TWO_LABEL, run.product.plan, run, two_bind, two_decide, proof, bytes, why, notes);
}
}  // namespace blk
