// SPDX-License-Identifier: Apache-2.0
// Research-only: the prover of the two-lookup run (two_lookup.h), honest and hostile.
// The honest prover calls the library's lkp_prove() for the remainder lookup. Hostile provers use
// research copies, on the PROVER side only: a copy of rng_prove() that can wrap a combination or
// move a digit (as M1b's rng_prove_research) and that writes the remainder lookup's multiplicities
// into the multiplicity message; and a copy of LKP's prover side whose sumchecks do not stop when a
// claim is false (the library's psc_prove() ends the process there), so that a complete proof of a
// false lookup can be written and given to the unchanged verifier.
#pragma once
#include <functional>
#include "engine/engine_cpu.h"
#include "toy/toy_coins.h"
#include "two_lookup.h"
namespace blk {

// psc_prove() (blocks/iop/psc.h) without its self-check "the round polynomial sums to the running
// claim". With true claims it sends the same bytes.
template <class K, class Ch>
PscOutput<K> psc_prove_forgiving(Ch &ch, SumClaim<K> &&claim, const Summand<K> &S, SumcheckProver<K> &inner, std::vector<MaskSlot> &&fresh, const MaskValues<K> &masks) {
  const std::vector<Weight<K>> vars = psc_vars(claim, S);
  const size_t entries = hp_entries(vars);
  BLK_REQUIRE(fresh.size() == entries + S.shown, "psc: wrong number of fresh mask entries");
  const size_t k = claim.vars.size();
  std::vector<K> w(entries), c(S.shown);
  for (size_t i = 0; i < entries; ++i) w[i] = masks(fresh[i].oracle(), fresh[i].index());
  for (size_t j = 0; j < c.size(); ++j) c[j] = masks(fresh[entries + j].oracle(), fresh[entries + j].index());
  K sigma = K::zero();
  for (const MaskTerm<K> &m : claim.masks) sigma = sigma + m.coeff * masks(m.slot.oracle(), m.slot.index());
  HidingPolynomial<K> U(vars, w);
  K mu = U.sum();
  ch.send_hiding_sum(mu);
  const K eps = ch.close_epsilon(R_PSC_EPSILON);
  K running = mu + eps * claim.target;
  K psis = K::one();
  std::vector<K> challenges, ends;
  for (size_t j = 0; j < vars.size(); ++j) {
    std::vector<K> s;
    if (j < k) {
      s = inner.round();
    } else {
      ends = inner.end_values();
      const std::vector<K> u(ends.begin() + S.shown, ends.end());
      std::vector<K> values, y(S.shown);
      for (unsigned n = 0; n <= S.degree; ++n) {
        for (unsigned i = 0; i < S.shown; ++i) y[i] = ends[i] + c[i] * small_int<K>(n);
        values.push_back(S.at_values(challenges, y, u));
      }
      s = poly_from_values_at_0_1_2(std::move(values));
    }
    std::vector<K> q = U.round();
    for (size_t t = 0; t < s.size() && t < q.size(); ++t) q[t] = q[t] + eps * s[t];
    for (size_t t = 0; t < vars[j].psi.size(); ++t) q[t] = q[t] + eps * sigma * psis * vars[j].psi[t];
    // (no self-check here: the claim may be false)
    for (size_t t = 0; t < q.size(); ++t)
      if (t != vars[j].fixed) ch.send(q[t]);
    auto draw = ch.close_algebraic(j < k ? R_PSC_ROUND : R_PSC_Y);
    challenges.push_back(j < k ? draw.draw() : draw.draw_nonzero());
    const K &g = challenges.back();
    running = poly_at(q, g);
    U.bind(g);
    psis = psis * poly_at(vars[j].psi, g);
    if (j < k) inner.bind(g);
  }
  std::vector<K> end_values(S.shown);
  for (unsigned i = 0; i < S.shown; ++i) end_values[i] = ends[i] + challenges.back() * c[i];
  for (const K &v : end_values) ch.send(v);
  if (S.shown) ch.close_empty(R_PSC_VALUES);
  return psc_rows(std::move(claim), S, vars, std::move(fresh), eps, challenges, running, end_values);
}
// LkpProverSide (blocks/iop/lkp.h) with the forgiving sumcheck, and with the trees built under
// another alpha than the one the channel drew if `alpha_override` is set (the alpha-replay attack).
struct RemResearchSide {
  ProverContext &P;
  MaskLedger &ledger, &key_ledger;
  LkpProver &heavy;
  const E *alpha_override;
  std::vector<E> power, plane, root, rest;
  E a = E::one();
  ProverRounds &ch() { return P.ch; }
  Statement &statement() { return P.st; }
  void tie_factor(const E &factor) { a = factor; }
  void note(const char *, const E &) {}
  MaskValues<E> values() {
    ProverContext *p = &P;
    return [p](u32 oracle, u32 index) { return p->behind[oracle].mask.entry(index); };
  }
  void begin(const E &theta, const E &alpha) {
    heavy.begin(theta, alpha_override ? *alpha_override : alpha);
    plane = heavy.plane_roots();
    power = plane;
    for (size_t j = plane.size() - 1; j-- > 0;) power[j] = power[j + 1] * power[j + 1] * plane[j];
    root = rest = heavy.key_roots();
    for (size_t i = root.size() - 1; i-- > 0;) rest[i] = root[i] * rest[i + 1];
  }
  bool tie(SumClaim<E> &&claim, const Summand<E> &S, size_t j, PscOutput<E> &out) {
    std::vector<std::vector<E>> maps;
    if (j == 0) maps.push_back({rest[0]});
    maps.push_back({power[j + 1]}), maps.push_back({plane[j]});
    SumcheckCpu<E> inner(S, claim.vars, std::move(maps));
    std::vector<MaskSlot> fresh = ledger.take(psc_masks(claim, S));
    out = psc_prove_forgiving<E>(P.ch, std::move(claim), S, inner, std::move(fresh), values());
    return true;
  }
  bool split(SumClaim<E> &&claim, const Summand<E> &S, size_t i, PscOutput<E> &out) {
    SumcheckCpu<E> inner(S, claim.vars, {{root[i]}, {rest[i + 1]}});
    std::vector<MaskSlot> fresh = ledger.take(psc_masks(claim, S));
    out = psc_prove_forgiving<E>(P.ch, std::move(claim), S, inner, std::move(fresh), values());
    return true;
  }
  bool psc(SumClaim<E> &&claim, const Summand<E> &S, LkpStep step, unsigned part, unsigned level, const std::vector<unsigned> &order, bool last_of_keys, PscOutput<E> &out) {
    const std::unique_ptr<SumcheckProver<E>> inner = heavy.sumcheck(step, part, level, S, claim.vars, order);
    std::vector<MaskSlot> fresh = lkp_fresh(ledger, key_ledger, psc_masks(claim, S), last_of_keys);
    out = psc_prove_forgiving<E>(P.ch, std::move(claim), S, *inner, std::move(fresh), values());
    return true;
  }
};

// Multiplicities of keys in the range table {0 .. 2^d - 1}, in LkpCpu's layout. A key outside the
// table is not counted; returns false if there is one.
inline bool rem_count(const LkpPublic &L, const std::vector<E> &keys, std::vector<E> &bits, u64 *uncounted = nullptr) {
  std::vector<u64> count(size_t(1) << L.d, 0);
  bool all = true;
  for (const E &k : keys) {
    if (k.c[1].v == 0 && k.c[2].v == 0 && k.c[0].v < (u64(1) << L.d)) count[k.c[0].v]++;
    else { all = false; if (uncounted) ++*uncounted; }
  }
  bits.assign(count.size() << L.mu, E::zero());
  for (size_t t = 0; t < count.size(); t++)
    for (size_t j = 0; j < size_t(1) << L.mu; j++)
      if ((count[t] >> j) & 1) bits[j + (t << L.mu)] = E::one();
  return all;
}

// rng_prove() (blocks/iop/rng.h) as M1b's rng_prove_research (mode 0 honest, 1 wrap a combination
// that leaves its window, 2 move one low digit), and `extra` writes further entries into the
// multiplicity message before it is sent (the remainder lookup's planes).
inline bool two_rng_prove(ProverContext &P, const Public<RngShape> &fixed, const RngWeights &phi, const std::vector<std::vector<i64>> &cells, GroupId group, RngOutput &out,
                          int mode, u64 *wrapped, const std::function<void(Table &)> &extra, const Writer &proof, size_t *lookup_begin, size_t *lookup_end) {
  const RngShape &S = P.ch.get(fixed);
  rng_shape_check(P.st, S), rng_weights_check(S, phi);
  const Public<LkpPublic> look = fixed.derive(rng_lookup);
  const LkpPublic &L = P.ch.get(look);
  out.phi = phi;
  out.theta = rng_theta(P.ch, S);
  const u64 N = S.combinations, DC = S.digit_columns;
  const i64 D = i64(1) << (S.digit_bits[0] + S.digit_bits[1] - 1);
  Table digits(S.digits.shape.main_deg, S.digits.shape.main_rows, P.st.codes().base[S.digits.shape.code].ell);
  std::vector<E> keys(L.all_keys(), E::zero());
  u64 column = 0, cell_row = 0; bool bumped = false;
  for (size_t mu = 0; mu < S.matrices.size(); mu++) {
    const RngMatrix &m = S.matrices[mu];
    for (u64 i = 0; i < m.rows; i++)
      for (u64 u = 0; u < N; u++) {
        __int128 wide = 0;  // hostile cells may be any field element (read as signed 64-bit)
        for (u64 c = 0; c < m.columns; c++) wide += (__int128)cells[mu][i * m.columns + c] * out.theta[(column + c) * N + u];
        if (wide < -D || wide >= D) {
          if (mode != 1) return false;
          wide = ((wide + D) % (2 * D) + 2 * D) % (2 * D) - D;
          if (wrapped) ++*wrapped;
        }
        const i64 psi = (i64)wide;
        const i64 shifted = psi + D;
        i64 lo = shifted & ((i64(1) << S.digit_bits[0]) - 1), hi = (shifted - lo) >> S.digit_bits[0];
        if (mode == 2 && !bumped) { lo = lo + 1 < (i64(1) << S.digit_bits[0]) ? lo + 1 : lo - 1; bumped = true; }
        laid_set(digits, S.digits_laid, u, cell_row + i, E::from(from_i64(lo)));
        laid_set(digits, S.digits_laid, u, DC + cell_row + i, E::from(from_i64(hi)));
        keys[0 + 2 * (cell_row + i + DC * u)] = E::from(from_i64(lo)), keys[1 + 2 * (cell_row + i + DC * u)] = E::from(from_i64(hi));
      }
    column += m.columns, cell_row += m.rows;
  }
  std::vector<E> bits;
  BLK_REQUIRE(lkp_count(L, keys, bits), "RNG research copy: a digit outside its range");
  Table planes(S.multiplicities.shape.main_deg, S.multiplicities.shape.main_rows, P.st.codes().base[S.multiplicities.shape.code].ell);
  for (const std::pair<unsigned, unsigned> &block : lkp_live_blocks(L.planes()))
    for (u64 t = 0; t < u64(1) << L.d; t++)
      for (u64 j = 0; j < u64(1) << block.second; j++) planes.set(0, ((u64)block.first << L.d) + j + (t << block.second), bits[block.first + j + (t << L.mu)]);
  if (extra) extra(planes);
  std::vector<OracleDraft> drafts(2);
  drafts[0].shape = S.digits.shape, drafts[0].leaf_class = S.digits.leaf_class, drafts[0].main = P.engine.put(digits);
  drafts[1].shape = S.multiplicities.shape, drafts[1].leaf_class = S.multiplicities.leaf_class, drafts[1].main = P.engine.put(planes);
  for (OracleDraft &d : drafts) if (d.shape.mask_rows) d.mask = Send::fresh_mask(P.st.codes(), d.shape, P.coins);
  const std::vector<OracleId> ids = send_prove(P, std::move(drafts));
  BLK_REQUIRE(ids[0] == S.digits_in && ids[1] == S.digits_in + 1, "RNG research copy: message numbers");
  out.digits = ids[0];
  P.st.join(group, ids[0]), P.st.join(group, ids[1]);
  out.row_owed = true, out.channel = &P.ch;
  LkpCpu heavy(L, std::move(keys), std::move(bits));
  LkpOutput left;
  if (lookup_begin) *lookup_begin = proof.size();
  lkp_prove(P, look, heavy, rng_planes_at(P.st, S, L), S.masks_from, group, left);
  if (lookup_end) *lookup_end = proof.size();
  out.shift = left.theta, out.alpha = left.alpha, out.rows = std::move(left.rows);
  Row on_keys = rng_key_row(P.st, S, left.keys.take());
  out.rows.push_back(on_keys);
  P.st.add_row(group, std::move(on_keys));
  return true;
}

// What a hostile prover does differently. on = false: the honest prover (library lkp_prove).
struct Hostile {
  bool on = false;            // linear rows get their true local values as targets (as M1b); research sumchecks in the remainder lookup
  int rng_mode = 0;           // two_rng_prove mode
  bool alpha_replay = false;  // the remainder lookup's trees are built with the DIGIT lookup's alpha
  bool swap_rows01 = false;   // the prover's copy of the table has rows 0 and 1 exchanged
  u64 planes_shift = 0;       // the remainder multiplicities are written (and read by the prover) at planes_first + this
  std::function<void(std::vector<E> &)> keys_edit;  // the prover's own view of its keys (not the committed cells)
  // The committed multiplicities; plane j of row t at j + (t << mu). uncounted: how many keys are in no row of the table.
  std::function<void(const LkpPublic &, std::vector<E> &, u64 uncounted)> bits_edit;
};
struct Proved {
  Writer proof;
  size_t digit_begin = 0, digit_end = 0, rem_begin = 0, rem_end = 0;  // byte ranges of the two lookups' transcripts
  u64 wrapped = 0, uncounted = 0;  // RNG combinations wrapped; remainder keys in no row of the table
  bool keys_in_table = true;
};
inline E two_eval(const WideRelation &a, const Table &t) { E x = E::zero(); for (const auto &z : a.terms) x += E::from(z.coefficient) * t.at(z.row, z.column); return x; }
// cells: the RNG cells read from row a of the table (a field element above p/2 reads as negative).
inline std::vector<std::vector<i64>> two_range_cells(const RngShape &R, const Table &t) {
  std::vector<std::vector<i64>> cells;
  for (const RngMatrix &m : R.matrices) {
    std::vector<i64> c(m.rows * m.columns);
    const u64 base = m.laid[0].first_place;
    for (u64 i = 0; i < m.rows; i++) for (u64 col = 0; col < m.columns; col++) {
      const u64 v = t.at(0, base + col * m.rows + i).c[0].v;
      c[i * m.columns + col] = v > P / 2 ? -(i64)(P - v) : (i64)v;
    }
    cells.push_back(std::move(c));
  }
  return cells;
}
inline bool two_prove(const TwoRun &run, const Table &t, const Hostile &h, Proved &out) {
  EngineCpu engine; ToyCoins coins(100); Writer &proof = out.proof; Binder b(TWO_LABEL, run.product.plan); const TwoPublic in = two_bind(b, run);
  ProverRounds ch(b, random_digest(coins), proof, [&](const ChainPrefix &p, unsigned bits) { return engine.search_nonce(p, bits); });
  ProverContext pr(in.product.codes, ch, engine, coins); FoldMask mask;
  const GroupId g = toy_prove_preamble(pr, in.product, t, mask); const OracleId abc = pr.st.group(g).members[0];
  for (const auto &a : ch.get(in.relations)) { Row row = wide_row(abc, a); if (h.on) row.target = two_eval(a, t); pr.st.add_row(g, std::move(row)); }
  const RngShape &R = ch.get(in.range); const LkpPublic &L2 = ch.get(in.rem);
  const std::vector<u64> &places = ch.get(in.key_places);
  std::vector<E> keys; keys.reserve(L2.all_keys());
  for (size_t p = 0; p < L2.parts.size(); p++) for (u64 i = 0; i < u64(1) << L2.parts[p]; i++) keys.push_back(t.at(0, places[p] + i));
  if (h.keys_edit) h.keys_edit(keys);
  std::vector<E> bits; out.uncounted = 0; out.keys_in_table = rem_count(L2, keys, bits, &out.uncounted);
  if (!h.on && !out.keys_in_table) return false;  // an honest prover has no key outside the table
  if (h.bits_edit) h.bits_edit(L2, bits, out.uncounted);
  const u64 first = ch.get(in.planes_first) + h.planes_shift;
  const auto fill = [&](Table &planes) {
    for (const std::pair<unsigned, unsigned> &block : lkp_live_blocks(L2.planes()))
      for (u64 r = 0; r < u64(1) << L2.d; r++)
        for (u64 j = 0; j < u64(1) << block.second; j++) planes.set(0, first + ((u64)block.first << L2.d) + j + (r << block.second), bits[block.first + j + (r << L2.mu)]);
  };
  RngOutput rout; out.wrapped = 0;
  if (!two_rng_prove(pr, in.range, ch.get(in.weights), two_range_cells(R, t), g, rout, h.rng_mode, &out.wrapped, fill, proof, &out.digit_begin, &out.digit_end)) return false;
  LkpPublic Lh = L2;
  if (h.swap_rows01) { std::vector<E> rows(size_t(1) << L2.d); for (size_t i = 0; i < rows.size(); i++) rows[i] = E::from(from_u64(i < 2 ? 1 - i : i)); Lh.tables[0].rows = rows; }
  LkpCpu heavy(Lh, std::move(keys), std::move(bits));
  LkpOutput left;
  const LkpPlanesAt planes_at = rem_planes_at(pr.st, R.digits_in + 1, L2, first);
  out.rem_begin = proof.size();
  if (!h.on) {
    lkp_prove(pr, in.rem, heavy, planes_at, R.masks_from, g, left);
  } else {
    lkp_mask_messages_check(pr.st, R.masks_from, NONE_ID);
    const E replay = rout.alpha;
    RemResearchSide side{pr, pr.st.masks(R.masks_from), pr.st.masks(R.masks_from), heavy, h.alpha_replay ? &replay : nullptr, {}, {}, {}, {}};
    lkp_run(side, L2, planes_at, g, left);
  }
  out.rem_end = proof.size();
  rem_key_rows(pr.st, g, abc, L2, places, left);
  E x; pr.st.add_row(g, rng_row(pr, in.range, rout, x));
  iopp_prove(pr, g, in.product.stages, in.product.choice, std::move(mask)); ch.finish(); pr.st.require_all_tested();
  return true;
}
}  // namespace blk
