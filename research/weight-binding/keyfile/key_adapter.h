// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0
// Generated derivative of blocks/frame/check_key.h by generate_adapter.py.
// Research-only; no production format or security claim.
#pragma once
#include "manifest.h"
namespace blk {
[[nodiscard]] inline bool tensor_make_native(const KeyUnder &under, const TensorManifest &manifest, const TensorWords *dishonest, IndexHolder &table, WfHeavy &ranges, MemberHeavy &products,
                                         Engine &engine, Coins &coins, const NonceSearch &search, Writer &file) {
  const KeyPlans &plans = under.plans;
  const KeyFixed &fixed = under.fixed;
  const char *fault = key_fault(fixed);
  BLK_REQUIRE(!fault, fault ? fault : "");  // an internal check: `configure` rejects such files
  BLK_REQUIRE(file.bytes().empty(), "make_key: the file comes empty");
  const IndexName name{table.commitment(), table.record()};
  std::unique_ptr<LinBegun> begun;
  if (!lin_begin(table, fixed.lin, begun)) return false;

  Writer &out = file;  // in place, so that a `file` set to `keep_list` records each item's kind
  write_head(out, TAG_KEY);
  BLK_REQUIRE(name.commitment.size() == DIGEST_BYTES, "make_key: what a table's keeper gives as its commitment is a root");
  Digest root;
  digest_from_bytes(name.commitment.data(), root);
  out.put(root);
  for (const E &y : name.record.y) out.put(y);

  Binder b(TENSOR_KEY_LABEL, plans.one_time);
  const KeyPublic x = bind_one_time_chain(b, fixed, name);
  const auto held = b.statement("checkpoint and conversion manifests v1", manifest);
  ProverRounds ch(b, random_digest(coins), out, search);
  ProverContext P(x.lin.codes, ch, engine, coins);
  std::vector<OracleDraft> drafts(1);
  drafts[0].shape = ch.get(x.index_masks).shape, drafts[0].leaf_class = ch.get(x.index_masks).leaf_class;
  drafts[0].mask = Send::fresh_mask(P.st.codes(), drafts[0].shape, coins), drafts[0].mask_draw = coins.last_draw();
  const OracleId masks = send_prove(P, std::move(drafts))[0];
  // Self-check after sending: a key file stays public; its masks cover sums linear in the weights.
  BLK_REQUIRE_NAMED(not_as_drawn(P, masks) == 0, "own-test-index-mask", "internal error (own-test-index-mask): values of the key file's index-mask message are not the random values that were drawn for it. The program or the machine has a fault; nothing of this run may be used");
  WfOutput left;
  if (!wf_prove(P, x.ranges, x.lin, masks, ranges, left)) return file.clear(), false;
  auto pending = left.pending.take();
  tensor_append(pending, fixed, name, ch.get(held), dishonest);
  LinFirst first = member_first_prove(P, x.lin, masks, std::move(pending), products);
  Sealed seal;
  BLK_REQUIRE(ch.seal(R_SEAL, seal), "a prover's channel does not refuse");
  ch.finish_inside_a_file();  // every chain's end is run, earlier chains first

  LinBinding binding(fixed.binding, ch.configuration(), coins);
  binding.put(0, seal.digest());
  const LinBindingRoot binding_root = binding.root();
  binding.write_path(out, 0);

  Binder shared_b(LIN_LABEL_SHARED, plans.shared);
  shared_b.configuration(fixed.configuration);
  const LinPublic shared_x = lin_bind_shared(shared_b, fixed.codes, fixed.lin, name, binding_root);
  ProverRounds shared_ch(shared_b, Digest{}, out, search);
  ProverContext shared_P(shared_x.codes, shared_ch, engine, coins);
  LinShared shared;
  lin_shared_prove(shared_P, shared_x, TableTest::ONE_TIME, table, std::move(begun), shared);
  lin_shared_tests_prove(shared_P, shared_x, shared);
  Sealed shared_seal;
  BLK_REQUIRE(shared_ch.seal(R_SEAL, shared_seal), "a prover's channel does not refuse");
  shared_ch.finish_inside_a_file();
  shared_P.st.require_all_tested();

  Binder second_b(LIN_LABEL_SECOND, plans.second);
  second_b.configuration(fixed.configuration);
  lin_bind_second(second_b, seal, shared_seal);
  ProverRounds second_ch(second_b, random_digest(coins), out, search);
  ProverContext P2 = lin_go_on(std::move(P), second_ch);
  const LinSecond second = lin_second_prove(P2, x.lin, first, shared_P, shared);
  lin_second_tests_prove(P2, x.lin, first, second);
  second_ch.finish();
  P2.st.require_all_tested();
  lin_release(shared_P, shared);
  return true;
}

[[nodiscard]] inline bool tensor_check_native(const KeyUnder &under, const TensorManifest &manifest, Reader &file, IndexKey &key, const char *&why, Notes *notes = nullptr, const char **place = nullptr) {
  const KeyPlans &plans = under.plans;
  const KeyFixed &fixed = under.fixed;
  if (place) *place = "before the chains";
  auto no = [&](const VerifierRounds &ch, const char *where) {
    if (place) *place = where;
    return why = ch.why() ? ch.why() : where, false;
  };
  if ((why = key_fault(fixed))) return false;
  for (const Planned *p : {&plans.one_time, &plans.shared, &plans.second})
    if (!(*p)->holds()) return why = does_not_hold(*p, "check_key"), false;  // no key is worth anything under such parameters
  BLK_REQUIRE(Plan::same_setting(plans.one_time->set, plans.shared->set) && Plan::same_setting(plans.shared->set, plans.second->set), "check_key: a key's three chains are planned under one setting");
  IndexKey read;
  if (!read_key_table_unproved(fixed, file, read, why)) return false;
  const IndexName name{read.commitment(), read.rec};

  Binder first_b(TENSOR_KEY_LABEL, plans.one_time);
  const KeyPublic x = bind_one_time_chain(first_b, fixed, name);
  const auto held = first_b.statement("checkpoint and conversion manifests v1", manifest);
  VerifierSession session;  // three chains, one verdict; one record of vertex values per root
  VerifierRounds first_ch(first_b, file, session);
  VerifierContext first_V(x.lin.codes, first_ch);
  first_V.notes = notes;
  std::vector<OracleId> ids;
  if (!send_verify(first_V, std::vector<OracleNotice>{first_ch.get(x.index_masks)}, ids)) return no(first_ch, "one-time chain: the index-mask message");
  WfOutput left;
  if (!wf_verify(first_V, x.ranges, x.lin, ids[0], left)) return no(first_ch, "one-time chain: the ranges");
  LinFirst first;
  auto pending = left.pending.take();
  tensor_append(pending, fixed, name, first_ch.get(held), nullptr);
  if (!member_first_verify(first_V, x.lin, ids[0], std::move(pending), first)) return no(first_ch, "one-time chain: the rows on the table");
  Sealed seal;
  if (!first_ch.seal(R_SEAL, seal) || !first_ch.finish_inside_a_file()) return no(first_ch, "one-time chain: its end");

  LinBindingRoot binding_root;
  if (place) *place = "between the one-time chain and the shared chain";
  if (!lin_binding_root(file, first_ch.get(x.binding), first_ch.configuration(), seal.digest(), binding_root)) return why = "the seal's place", false;

  Binder shared_b(LIN_LABEL_SHARED, plans.shared);
  shared_b.configuration(fixed.configuration);
  const LinPublic shared_x = lin_bind_shared(shared_b, fixed.codes, fixed.lin, name, binding_root);
  VerifierRounds shared_ch(shared_b, file, session);
  VerifierContext shared_V(shared_x.codes, shared_ch);
  shared_V.notes = notes;
  LinShared shared;
  if (!lin_shared_verify(shared_V, shared_x, TableTest::ONE_TIME, read, shared)) return no(shared_ch, "shared chain");
  if (!lin_shared_tests_verify(shared_V, shared_x, shared)) return no(shared_ch, "shared chain: a proximity test");
  Sealed shared_seal;
  if (!shared_ch.seal(R_SEAL, shared_seal) || !shared_ch.finish_inside_a_file()) return no(shared_ch, "shared chain: its end");
  shared_V.st.require_all_tested();

  Binder second_b(LIN_LABEL_SECOND, plans.second);
  second_b.configuration(fixed.configuration);
  lin_bind_second(second_b, seal, shared_seal);
  VerifierRounds second_ch(second_b, file, session);
  VerifierContext V = lin_go_on(std::move(first_V), second_ch);
  V.notes = notes;
  LinSecond second;
  if (!lin_second_verify(V, x.lin, first, shared_V, shared, second)) return no(second_ch, "second chain");
  if (!lin_second_tests_verify(V, x.lin, first, second)) return no(second_ch, "second chain: a proximity test");
  if (!second_ch.finish()) return no(second_ch, "second chain: its end");  // also: no byte is left over
  V.st.require_all_tested();
  if (place) *place = "behind the chains";
  if (!session.accepted()) return why = "a chain of the key has refused", false;  // the verdict: false if a chain rejected, even if a result above was dropped; else ends the process if one is unfinished
  if (place) *place = nullptr;
  key = std::move(read); // research result only, NOT a production TestedTable
  why = nullptr;
  return true;
}

} // namespace blk
