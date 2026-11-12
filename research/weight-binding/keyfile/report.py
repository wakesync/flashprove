#!/usr/bin/env python3
"""Render this lane's documentation and append its ledger row from immutable receipts."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
REL='experiments/20261111-36-keyfile-tensor-binding'
E=ROOT/REL
PRIMARY='c16632cffc2d7213d37a1e12617d8e123e6ec570'
SUPPLEMENT='147ed8178074148afd3c80ef830cdedbb341862c'
s=json.loads((E/'runs/summary.json').read_text());counts=json.loads((E/'counted.json').read_text())
lines=['# RESULTS: 20261111-36-keyfile-tensor-binding', '',
       '**PASS against the selected small-key registration. Measured, unreplicated.**', '',
       'A complete CPU key proof now binds each of four named row tensors to a verifier-held checkpoint and conversion manifest. The three complete substituted-table proofs are rejected by the native linear-claim check, not an outside hash of the witness. This is the existing small-key research fixture, not production cp_verify, a Qwen proof, or a soundness result.', '',
       'The initial product-toy registration was replaced following a duplicate-session collision; the dated PREREG amendment discloses the entire sequence. The result is against that explicitly selected small-key plan, not an assertion that the original product-toy experiment ran.', '',
       '## Provenance and threshold', '',
       '- Initial PREREG-only commit: `82fae6f`. Duplicate-session rewrite: `12c4f3e`. Reconciliation/selection amendment: `7e42379`, before small-key adapter implementation.',
       '- Implementation: `ba7fa76`; registered run code/CI commit: `d230a025019c59becc9adf073a7981b841a79b9c`. Release raw evidence committed in `'+PRIMARY+'`.',
       '- Ten seeds, 1001..1010; no warmup or outlier exclusions. Gate granted at the UTC timestamp in `runs/ENV.json`, on cores 10-12 of a shared, loaded AMD EPYC-Rome CPU host. CPU only, no download or spend.',
       '- Threshold: all honest controls accept; each of five named negatives refuses in all ten runs. All five thresholds met. Every negative attempted and failed the native proof check.',
       '- `runs/seed-*/results.json` holds every timing/verdict; the adjacent `.key` files retain complete honest and malicious keys. `runs/summary.json` holds full-precision aggregate statistics.',
       '- `replay.json`: all 150 saved-file decisions reproduce in fresh verifier processes. This is same-lane replay, not independent replication.',
       '- Honest controls paired with the three swaps reuse the seed\'s original bound key. They are repeated verifications, not additional independently generated honest proofs.', '',
       '## Named negatives and mechanism', '',
       '| arm | accepts / trials | rejection mechanism |', '|---|---:|---|']
negative=['one-tensor-swapped','two-tensors-swapped','tensor-order-permuted','manifest-root-other-checkpoint','conversion-id-mismatch']
for name in negative:
    a=s['arms'][name];lines.append(f"| {name} | {a['accepted']} / {a['verify_ms']['n']} | {a['stages'][0]}: {a['reasons'][0]} |")
lines += ['',
          'For the first three arms the prover commits an in-range substituted matrix, binds the ORIGINAL held manifest, and uses truthful evaluations of its substituted matrix as its own pending targets. This lets it emit a complete WF/BATT/LIN key. The verifier independently derives the original expected targets and fails at `BASE: the masked message in the proof does not satisfy the linear claim`. The counterpart unbound legacy keys accept. One tensor replacement changes one element of row 0, the two-tensor case additionally changes an element of row 2, and permutation exchanges whole rows 0 and 1 under unchanged named addresses.', '',
          'The checkpoint and conversion negatives replay an honest key under another self-consistent trusted statement. They fail inside the one-time native proof (range-chain opening), before the wrapper compares untrusted header IDs. Honest alternate-checkpoint and alternate-conversion keys accept. This is transcript binding, distinct from the false-evaluation mechanism of the first three arms.', '',
          '## Cost and every timing arm', '',
          'Units below are milliseconds for complete in-memory verification, including manifest consistency hashing and expected-MLE recomputation. File I/O, compilation, proving and caller-side fixture/world construction are not timed. The native KeyUnder copy/validation inside verification is included. SD is sample SD. All arms have n=10.', '',
          '| arm | accepts | median ms | SD ms | min ms | max ms | key bytes (constant) |', '|---|---:|---:|---:|---:|---:|---:|']
for name,a in s['arms'].items():
    t=a['verify_ms'];lines.append(f"| {name} | {a['accepted']}/10 | {t['median']:.6f} | {t['sd']:.6f} | {t['min']:.6f} | {t['max']:.6f} | {a['key_bytes']['median']:.0f} |")
lines += ['',
          'The bound key is 63,944 bytes, versus 63,872 bytes for the legacy key in this fixture: exactly the 72-byte extension envelope. Each size has SD=0 and min=max at that value across all ten seeds. The native key portion remains 63,872 bytes here: BATT still emits the same sized sumcheck after batching six rather than two pending claims. This is not a claim that arbitrary tensor counts have constant proof size.', '',
          'Bound honest verification: median 1.402216 ms, SD 0.263356 ms, range 1.260837..1.991122 ms. Legacy: median 1.338692 ms, SD 0.275164 ms, range 1.120664..1.903108 ms. The ranges overlap. No speedup, statistically resolved overhead, or large-model timing claim is made.', '',
          '## Counted scaling, not Qwen measurements', '',
          'Source: `counted.json`, reproducible with `research/weight-binding/keyfile/count.py`. Shapes come from merged #68 receipts; the effective-block count reuses merged #100. Nothing below is a new Qwen proof or integer conversion.', '',
          '- All 1,199 source-tensor hashes occupy 38,368 bytes before names/shapes; their Merkle tree has 1,198 internal hashes and one 32-byte held checkpoint ID.',
          '- A hypothetical one-effective-block-per-source extension would add 1,199 linear claims and hold 28,776 bytes of evaluation targets internally. Its flat-padding evaluation would have 39,699,843,584 entries, 39,699,842,385 fold multiplications, 21,084 extension-field point coordinates and 63,252 first-attempt SHA-256 point hashes. This is NOT the real Qwen conversion inventory.',
          '- The actual text design instead has 722 effective blocks: 26,895,337,984 integers, 38,414,602,240 padded entries, 38,414,601,518 fold multiplications, 14,110 point coordinates, 42,330 first-attempt point hashes, 722 claims and 17,328 internal target bytes. Folded norms have no separate effective block; visual/MTP are outside that design.',
          '- This adapter recomputes targets, so response serialization is zero bytes; the two root IDs and version/tag occupy a fixed 72-byte envelope. That is NOT an estimate of the full Qwen key size. Full native proof size, plan feasibility, table-side work and verification runtime require implementation and resizing, and remain uncounted/unmeasured. Point-hash counts omit rare rejection retries.', '',
          '## Descriptive Qwen dry run', '',
          '**NOT DONE.** `cache-probe.json` records a read-only search of local project and standard cache directories, plus two absent legacy/model directories. No safetensors files were present in those searched locations for stock pin `37561816` or huihui pin `739e3c5b`. Neither per-tensor root was recomputed from local weights. No weights were downloaded and old #68/#87 hash receipts were not relabelled a fresh rehash.', '',
          '## Supplementary checks', '',
          '- `runs/manifest-cross-check.json`: independent Python hashlib / merged wb_manifest computation agrees with the C++ checkpoint ID for every registered seed.',
          '- `debug-ubsan/`: separate seed 9001, different tensor values and names; all fifteen arms pass with undefined-behavior sanitizer enabled. It additionally checks direct-sum versus folded MLE, row address coefficients, SHA-256 empty known answer, wrong version, truncation, trailing bytes, stale held IDs, noncanonical name order, a false header ID and corrupted native bytes. This is supplemental debugging, not another registered timing sample or independent replication.',
          '- CI workflow rebuilds, runs the separate debug fixture, runs all ten seeds, and replays saved keys. The wrapper never returns a production TestedTable.', '',
          '## Deviations and limits', '',
          '1. Duplicate-session preregistration collision: two sessions addressed the same clone. The duplicate changed the PREREG to the small-key fixture and then stopped. The active session first attempted the originally registered product-toy debug fixture (length 8, seed 101); three attempts refused their plan before producing a proof. The discarded uncommitted product sources were moved out of the repository. Amendment `7e42379` openly selects the stronger small-key fixture before its implementation. No registered-suite fixture was run before its code commit, and no thresholds or observed results were silently changed. History is preserved.',
          '2. The complete raw key files are retained, including the complete dishonest proofs. A later runner-only change records sanitizer flags correctly; it does not change the registered release protocol or its immutable receipts.',
          '3. This is a native small-key research format and verifier, not a production cp_verify extension. The fixture uses test-only hand plans; no error-accounting, hiding, Fiat-Shamir/grinding or soundness theorem is established. No Qwen proof exists here and nothing demonstrates abliteration detection under proof.',
          '4. Only four length-four public tensors with signed identity conversion and fixed row placement are implemented. Arbitrary tensor layouts, hidden-weight signed evaluations, Qwen conversion/placement, request/reply linkage and layers 17..51 remain outside the result.',
          '5. Independent adversarial review and replication remain required. The bounded negative suite does not exhaust malicious strategies.', '',
          '## Reproduce', '',
          'Exact build, suite, replay, sanitizer, count and single-file verification commands are in [the code README](../../../research/weight-binding/keyfile/README.md). Use fresh output paths; never overwrite committed receipts.', '']
with (E/'RESULTS.md').open('x') as f:f.write('\n'.join(lines))
metrics=[]
common=dict(hardware='cpu-epyc-rome-kvm-16',date='2026-11-11',commit=PRIMARY,source=REL+'/runs/summary.json')
for arm,a in s['arms'].items():
    metrics.append(dict(common,name=arm+'_accepted',stat='count',value=a['accepted'],total=10,unit='count',n=10,spread=None,note='Native verification attempted in all ten runs; expected accepts='+str(a['expected_accept'])+'. Paired original honest controls reuse keys.'))
    for field,unit in [('verify_ms','s'),('key_bytes','B'),('native_key_bytes','B')]:
        t=a[field];scale=0.001 if field=='verify_ms' else 1
        metrics.append(dict(common,name=arm+'_'+('verify_s' if field=='verify_ms' else field),stat='median',value=t['median']*scale,unit=unit,n=t['n'],spread={k:t[k]*scale for k in ['sd','min','max']},note='Measured, unreplicated; shared loaded CPU; timing ranges overlap, no speedup or resolved overhead claim. Ledger seconds = raw verify_ms / 1000.'))
for section,values in counts.items():
    if not isinstance(values,dict):continue
    for name,value in values.items():
        if not isinstance(value,int):continue
        metrics.append(dict(hardware='cpu-epyc-rome-kvm-16',date='2026-11-11',commit=PRIMARY,source=REL+'/counted.json',name='counted_'+section+'_'+name,stat='single',value=value,unit='B' if 'bytes' in name else 'count',n=1,spread=None,note='COUNTED only from shapes/code; no variance, no Qwen proof-size or runtime estimate.'))
metrics.append(dict(common,name='saved_key_replay_pass',source=REL+'/replay.json',stat='count',value=150,total=150,unit='count',n=150,spread=None,note='Same-lane fresh-process replay, not independent replication.'))
metrics.append(dict(common,name='separate_ubsan_debug_pass',commit=SUPPLEMENT,source=REL+'/debug-ubsan/summary.json',stat='count',value=15,total=15,unit='count',n=1,spread=None,note='Fifteen arms at separate seed9001 plus parser/layout/MLE assertions; supplemental debugging, not registered timing runs.'))
entry=dict(id='keyfile-tensor-binding-36',title='Per-tensor checkpoint binding inside the native CPU small-key proof',status='measured',status_note='research-only four-row small-key fixture; no production cp_verify or Qwen proof',replication='unreplicated',pr=121,
           summary='PASS against the selected small-key registration: each of five named negatives rejected 10/10, including complete one/two/order substitutions rejected by the native LIN proximity linear-claim check; all paired honest controls accept. Bound key 63,944 B versus legacy 63,872 B; verify medians 1.402216 ms and 1.338692 ms with overlapping ranges. Qwen costs counted only; local-weight root dry run not done.',
           conditions='4x4 matrix; four signed-I64 identity-converted row tensors in [-2,1]; native WF/BATT/LIN key chains with fixture hand plans and deterministic coins1001..1010; cores10-12 shared loaded CPU. Prereg duplicate-session collision disclosed before small-key code. No soundness level, hiding, Qwen proof or abliteration-detection claim.',
           evidence=[REL+'/RESULTS.md','research/weight-binding/keyfile/README.md'],metrics=metrics)
ledger=ROOT/'research/results.yaml';old=ledger.read_text();assert '  - id: '+entry['id'] not in old
block='\n  - id: '+entry.pop('id')+'\n'
for k,v in entry.items():
    if k=='metrics':
        block+='    metrics:\n'+''.join('      - '+json.dumps(m,separators=(', ', ': '))+'\n' for m in v)
    else:block+='    '+k+': '+json.dumps(v)+'\n'
ledger.write_text(old+block)
print('Wrote RESULTS.md and appended ledger row with',len(metrics),'metrics; immutable raw receipts untouched')
