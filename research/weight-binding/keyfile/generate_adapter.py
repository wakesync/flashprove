#!/usr/bin/env python3
"""Generate the research-only key adapter from main's key orchestration.

No native WF/BATT/LIN algorithm or rejection check is removed. Only a separate
chain label, bound manifest input and four pending claims are added. Generated
source is committed so review does not depend on running this generator.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[3]
s=(root/'blocks/frame/check_key.h').read_text()
a=s.index('[[nodiscard]] inline bool make_key_under(')
b=s.index('/* Reads header | root',a)
make=s[a:b].replace('make_key_under(', 'tensor_make_native(')
make=make.replace('const KeyUnder &under, IndexHolder &table,', 'const KeyUnder &under, const TensorManifest &manifest, const TensorWords *dishonest, IndexHolder &table,')
make=make.replace('Binder b(LABEL_ONE_TIME_CHAIN, plans.one_time);','Binder b(TENSOR_KEY_LABEL, plans.one_time);')
make=make.replace('const KeyPublic x = bind_one_time_chain(b, fixed, name);','const KeyPublic x = bind_one_time_chain(b, fixed, name);\n  const auto held = b.statement("checkpoint and conversion manifests v1", manifest);')
old='LinFirst first = member_first_prove(P, x.lin, masks, left.pending.take(), products);'
assert old in make
make=make.replace(old,'auto pending = left.pending.take();\n  tensor_append(pending, fixed, name, ch.get(held), dishonest);\n  LinFirst first = member_first_prove(P, x.lin, masks, std::move(pending), products);')
a=s.index('[[nodiscard]] inline bool check_key_under(')
b=s.index('// ---- what a program calls:',a)
check=s[a:b].replace('check_key_under(', 'tensor_check_native(')
check=check.replace('const KeyUnder &under, Reader &file, TestedTable &key,', 'const KeyUnder &under, const TensorManifest &manifest, Reader &file, IndexKey &key,')
# Never mint a production TestedTable from a research-only protocol.
check=check.replace('key = TestedTable(std::move(read), plans.shared->set, key_public_bytes(fixed));','key = std::move(read); // research result only, NOT a production TestedTable')
check=check.replace('Binder first_b(LABEL_ONE_TIME_CHAIN, plans.one_time);','Binder first_b(TENSOR_KEY_LABEL, plans.one_time);')
check=check.replace('const KeyPublic x = bind_one_time_chain(first_b, fixed, name);','const KeyPublic x = bind_one_time_chain(first_b, fixed, name);\n  const auto held = first_b.statement("checkpoint and conversion manifests v1", manifest);')
old='if (!member_first_verify(first_V, x.lin, ids[0], left.pending.take(), first))'
assert old in check
check=check.replace(old,'auto pending = left.pending.take();\n  tensor_append(pending, fixed, name, first_ch.get(held), nullptr);\n  if (!member_first_verify(first_V, x.lin, ids[0], std::move(pending), first))')
(root/'research/weight-binding/keyfile/key_adapter.h').write_text('// Copyright 2026 Anthropic PBC\n// SPDX-License-Identifier: Apache-2.0\n// Generated derivative of blocks/frame/check_key.h by generate_adapter.py.\n// Research-only; no production format or security claim.\n#pragma once\n#include "manifest.h"\nnamespace blk {\n'+make+check+'} // namespace blk\n')
