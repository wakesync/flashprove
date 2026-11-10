#!/usr/bin/env python3
"""Assemble receipts; optionally append the evidence-pinned research ledger entry."""
import argparse
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
EXP=ROOT/'experiments/20261109-35-qwen-operators'
RUNS=EXP/'runs'
OPS=('nonlinear','conv','l2','rms','rotary')
HARDWARE='cpu-epyc-rome-kvm-16'
BASE='4f7a876151c309f0159e88b18c8e286d4e1909c9'
OPUS_REVIEW='https://github.com/wakesync/flashprove/pull/67#issuecomment-6757161440'
ASTRA_REVIEW='https://github.com/wakesync/flashprove/pull/67#issuecomment-6756145013'

# Text blocks added by the review fix of PR #67 (wording and provenance only; no number below is computed here).
BINDING=f'''## What a proof binds (read before the numbers)

The public statement of every proof is only: the operator, F, the rotary position (zero for the other operators) and the claimed output vector. Everything else is a committed witness cell that the prover chooses freely. Nothing outside the proof fixes those cells: they are not tied to any model's weights, to a matmul output, or to an earlier chunk.

| Operator | Public | Committed, chosen freely by the prover | What an accepting proof shows |
|---|---|---|---|
| Nonlinear | operator, F, six outputs | the scalar X in [-8,8), its quotient/remainder, the one-hot selector | there exists an in-domain X whose six pinned table rows are these outputs |
| Convolution | operator, F, four outputs | the four taps (the kernel), the three history words, the four new inputs, remainders | there exist a kernel, a history and inputs in [-S,S) for which the four-tap floor relation gives these outputs |
| L2 / RMS | operator, F, 128 / 256 outputs | the whole input vector, its energy, key, selected coefficient, remainders | there exists an in-range input vector, with mean square in the admitted domain, whose bounded norm gives these outputs |
| Rotary | operator, F, position, 256 outputs | all 256 inputs, remainders (the coefficients are fixed by the public position) | there exist inputs in [-S,S) whose partial rotation at this position gives these outputs |

In words: a proof shows "there exist inputs (and, for the convolution, a kernel and a history) in range for which this relation gives these outputs", and nothing about a particular model's weights or a particular earlier chunk.

For the convolution and the rotary this means **almost any in-range output vector can be proved**. The nonlinear outputs must form one consistent table row and the norm outputs must be a scaled copy of some in-range vector at a table coefficient, so those two are more constrained, but their inputs are equally unbound. The evidence is the opus reviewer's three complete proofs, built with the unmodified prover and accepted by the unchanged verifier ({OPUS_REVIEW}). They are the reviewer's runs, not committed run files of this PR:

- convolution with outputs of the reviewer's choosing, (S, -S+1, 1234, -77), using taps (0,0,0,-S);
- convolution reproducing the seed-3 public outputs with a different kernel (all taps -S) and freshly solved history and inputs;
- rotary at position 517 for a random 256-word target, after moving 3 of the 256 target words by 1 (29 of 32 pairs were reachable exactly before that).

The committed history-substitution control below is the narrowest case of the same fact. Binding the kernel and inputs to committed weights and to the previous chunk is the job of the M3 statement (PR #70, draft) and the state-commitment work (#34), not of this PR.

'''
SECURITY=f'''## Security setting (research only)

"Research target 10 bits" is a **per-round** target that includes 6 bits of proof-of-work on the query rounds: `Plan::holds` accepts a round when its error, times 2^-work, is at most 2^-10. The weakest query rounds are about 4.3 to 4.5 bits before the work factor (astra reviewer, {ASTRA_REVIEW}: 4.30 to 4.49 bits across the five profiles). Added over all rounds of a whole proof, the union bound is about 2^-7.3, roughly 1 in 160 (opus reviewer's calculation, 2^-7.33 over 27 rounds, {OPUS_REVIEW}). The review-fix lane recomputed it from the same plan objects (sum over every plan round of the round's whole error, with draw accounting, times 2^-work, times its count, for the F12 fixture of each profile) and got 2^-7.33 for the convolution (27 rounds) and 2^-7.38 for the other four profiles (31 or 32 rounds), about 1 in 160 to 1 in 167. That computation is reported in the PR thread and is not a committed run file. This is a research setting. The rejection counts below do not show production security.

"Fixed test coins" (`ToyCoins(seed)`) are the prover's own randomness: the salt and the masks. Every verifier challenge is derived from the transcript by hashing (BLAKE2b Fiat-Shamir over the bound configuration, relation list, salt, roots, prior messages and nonces). Fixed coins make runs reproducible and remove hiding; they do not weaken soundness.

'''
PROVENANCE='''**Deviation, registration order (added by the review fix).** The original thresholds were registered before any code (first commit `0f0153f`, which contains only the PREREG). A1 was committed in `50d454f`, before the rotary code that arrives in `c8e2a42`. **A2 was not registered before its code:** A2 and the typed-profile implementation it covers first appear together in `c8e2a42`, before the final measurement commit `5e93627`. The raw run files carry no execution timestamps, so the order of the runs themselves cannot be shown from the repository; only commit order can. The final profiles are therefore "registered thresholds; A2 profile co-committed with its code", not "preregistered final profiles". A2 changed no threshold or input distribution. See the dated note appended to PREREG.md.\n\nA1 registered rotary before its code; A2 added typed transcript profiles, expanded malformed-statement tests, and a final unified rerun before measuring that profile. '''


STATUS_NOTE='research only; kernel/taps, history and all inputs are prover-chosen (no external identity), so almost any in-range conv or rotary output is provable'
SUMMARY=('Local tuple relations only. Public: operator, F, rotary position, outputs. The convolution kernel (taps), its history and every input '
         'are chosen freely by the prover, so a proof shows only that some in-range inputs give these outputs, not a particular model\'s weights '
         'or earlier chunk; binding is for the M3 statement (PR #70) and #34. No model support or production-security claim.')
CONDITIONS=('CPU-only synthetic inputs; research target 10 bits is per round incl. 6 bits proof-of-work, a whole proof is weaker '
            '(reviewer union bound in RESULTS), not production security; thresholds registered before code, A2 profile co-committed with its code '
            '(no run timestamps); explicit negative history control')


def read(name):return json.loads((RUNS/name).read_text())
def lines(name):return [json.loads(x) for x in (RUNS/name).read_text().splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fmt(x):return f'{x:.9g}'
def stats_text(s):return f"{fmt(s['median'])} [{fmt(s['min'])}, {fmt(s['max'])}], SD {fmt(s['sd'])}"


def collect():
    result={}
    for op in OPS:
        result[op]=dict(summary=read(f'{op}-summary.json'),fidelity=read(f'{op}-fidelity.json'))
        for suffix in ('','-ubsan'):
            hs=[x for x in lines(f'{op}-hostile{suffix}.jsonl') if x['mode']=='hostile']
            result[op]['hostile'+suffix]=dict(total=len(hs),rejected=sum(x['rejected'] for x in hs),
                                              complete=sum(x['complete_proof'] for x in hs))
        for f in (14,16):
            result[op][f'smoke{f}']=lines(f'{op}-f{f}-smoke.jsonl')[0]
    return result


def report(data):
    build=read('build.json');san=read('build-ubsan.json')
    assert build['proof_cpp_sha256']==san['proof_cpp_sha256']==sha(HERE/'proof.cpp')
    cpu=next(x.split(':',1)[1].strip() for x in pathlib.Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name'))
    mem=next(int(x.split()[1]) for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:'))
    env=dict(commits=dict(base=BASE,prereg=subprocess.check_output(['git','rev-parse','0f0153f'],cwd=ROOT,text=True).strip(),
                          implementation=build['source_commit'],sanitizer= san['source_commit']),
             toolchain=dict(python=sys.version.split()[0],compiler=build['compiler'],platform=platform.system(),kernel=platform.release()),
             hardware=dict(key=HARDWARE,cpu=cpu,logical_cpus=os.cpu_count(),memory_kib=mem,
                           affinity='0-5',shared_loaded_host=True,exclusive_core=False,heavy_gate=True,gpu=False),
             seeds=list(range(1,11)),fidelity_seeds=dict(nonlinear=35,other_vectors=list(range(1,11))),
             security=dict(target_bits=10,field='Goldilocks',test_coins='deterministic seed per run',privacy_claim=False),
             release_build=build,sanitizer_build=san,
             hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and 'work' not in p.parts and '__pycache__' not in p.parts})
    (EXP/'ENV.json').write_text(json.dumps(env,indent=2)+'\n')
    text='# RESULTS: bounded Qwen operator relations\n\n'
    text+='Five scoped operator profiles now have real product-oracle proofs, not just witness checks.\n'
    text+='Their nonlinear and rotary tables are deterministic integer artifacts, with no runtime float evaluation.\n'
    text+='All final honest batches and sampled local-relation attacks meet their registered criteria.\n'
    text+='Only the operator, F, the rotary position and the outputs are public. The prover chooses every input, and for the convolution also the kernel (taps) and the history.\n'
    text+='So a proof says nothing about a particular model\'s weights or a particular earlier chunk, and for the convolution and the rotary almost any in-range output vector can be proved.\n'
    text+='Issue #35 therefore remains PARTIAL: this is research operator machinery, not a Qwen model proof.\n\n'
    text+=BINDING
    text+=SECURITY
    text+='## Verdict and final proof measurements\n\n'
    text+='CPU-only, shared AMD EPYC-Rome KVM host, affinity 0-5, all proof batches through the shared heavy-job gate. Research target 10 bits. Each performance row is n=10, F=12, seeds1..10; no warmup excluded. Times are seconds, proof sizes bytes. Brackets are min/max; SD is sample SD. Verifier time includes witness-free circuit construction and sizing. Prove time excludes circuit lowering, sizing and witness-table assembly, so it is not end-to-end prover latency. No speedup comparison or model-scale extrapolation.\n\n'
    text+='| Profile | Honest | Local hostile rejected (complete proofs) | Prove median [range], SD | Verify median [range], SD | Bytes median [range], SD | Columns / relations |\n|---|---|---|---|---|---|---|\n'
    for op,d in data.items():
        s=d['summary'];h=d['hostile']
        text+=f"| {op} | {s['accepted']}/10 | {h['rejected']}/{h['total']} ({h['complete']}) | {stats_text(s['prove_s'])} | {stats_text(s['verify_s'])} | {stats_text(s['proof_bytes'])} | {int(s['columns']['median'])} / {int(s['relations']['median'])} |\n"
    text+='\n- **Nonlinear PASS, bounded relation:** one proof jointly covers six functions on one committed scalar, not six independent input positions. General learned decay parameters and downstream gate multiplication are absent.\n'
    text+='- **Convolution local PASS; kernel, history and input identity absent (PARTIAL/FAIL for #35):** four tokens of one depthwise channel use the same canonical three-word history and four taps, but taps, history and inputs are all chosen by the prover. The explicit history substitution control accepts the replacement, 1/1, against the SAME public outputs. Both its original and modified tuple proofs are valid. This committed control shows only the narrowest case (history changed, taps fixed); the reviewer\'s accepted constructions (see "What a proof binds") show that a different kernel, or outputs of the prover\'s own choosing, are accepted too. This is a negative result for external kernel, history and input identity, not a failure of the stated existential relation or a hostile rejection.\n'
    text+='- **Norm PASS under registered bounded semantics:** D128 L2 and D256 RMS, unit gain, no epsilon, no extra query scaling. **These are NOT the M2 design\'s integer-square-root (isqrt/epsilon) norm (#66)** and not full Qwen norms.\n'
    text+='- **Rotary PASS under A1:** public position, first64of256, rotate-half, theta10^7, context1024. No private/multimodal position or YaRN.\n\n'
    text+='## Fidelity against float reference\n\n'
    text+='Absolute real-valued errors on the same dequantized integer inputs. Input quantization error versus a separately sampled float tensor is NOT included. Nonlinear n=8197 per row: 4096 random, every4096grid point, five boundaries/zero points. Conv n=40 outputs from10chunks. L2/RMS n=1280/2560 correlated components from10heads. Rotary n=640 rotated coordinates from10positions/vectors; 1920 other coordinates per F are exactly unchanged, excluded from error quantiles. These are synthetic distributions, not real-weight fidelity.\n\n'
    text+='Limits of this section: these are synthetic, quantized-input measurements, not model fidelity. The convolution threshold (<=2^-F) cannot fail, and the rotary threshold (<=2*2^-F) nearly cannot, because rounding down keeps the error under 2^-F per floor by construction; those two rows check the implementation, not a fidelity margin. The norm fidelity inputs are 10 uniform [-1,1) vectors per F, whose mean square sits near 1/3, so they mostly sample one region of the admitted interval, not its boundaries or real activation distributions.\n\n'
    text+='| Function | F | n | Median | p95 | Max | SD | Threshold | Verdict |\n|---|---|---|---|---|---|---|---|---|\n'
    for d in data.values():
        for r in d['fidelity']:
            s=r['error'];text+=f"| {r['op']} | {r['F']} | {s['n']} | {fmt(s['median'])} | {fmt(s['p95'])} | {fmt(s['max'])} | {fmt(s['sd'])} | {fmt(r['threshold'])} | {'PASS' if r['passed'] else 'FAIL'} |\n"
    text+='\nHigher F does not eliminate the fixed input-grid error. SiLU worst maximum is grid-limited, not a claim of convergence with F.\n\n'
    text+='## Hostile scope, smoke checks and sanitizer\n\n'
    text+='All operators sample sign changes, out-of-domain operand, quotient+1 with compensating invalid remainder, changed output, changed scale/type, malformed output count, i64 extreme public outputs, flipped proof byte, truncation and trailing data. Nonlinear/norm add wrong table row; norm adds out-of-domain mean-square; conv adds wrong history reuse; rotary adds wrong pair, changed unrotated coordinate and position attacks. Complete malicious proofs preserve all multiplication equations and replace affine targets ONLY inside the malicious prover; the unchanged verifier derives its own targets. This is sampled coverage, not exhaustive soundness. The committed hostile proofs are rejected by an equation check with a large margin (the plan\'s ZERO round, about 186 bits in the opus reviewer\'s plan dump), not by a low-probability query round. They show that each constraint exists and is wired to the right cell. They do not show that the protocol reaches its 10-bit target: no grinding attack against the weakest query rounds was attempted, by this lane or by either reviewer.\n\n'
    for op,d in data.items():
        h=d['hostile-ubsan'];text+=f"- {op}: UBSan local hostile {h['rejected']}/{h['total']} rejected, one honest accepted, zero sanitizer reports; F14 and F16 smoke {'PASS' if d['smoke14']['accept'] and d['smoke16']['accept'] else 'FAIL'} (n=1 each, not performance estimates).\n"
    text+='\nThe history substitution control is also repeated under UBSan and again accepts the alternative consistent history. Its status is intentionally separate from local-relation rejection totals.\n\n'
    cross=read('crosscheck.json')
    text+=f"Independent Python integer lowering matches all {cross['matched']}/{cross['cases']} actual C++ fixture cases ({cross['output_words']} output words), all five operators, F12/14/16, seeds1..10. C++ reads compiled headers while Python reads binary tables. This checks implementation agreement separately from float fidelity.\n\n"
    text+='## Table format, exact identity and regeneration\n\n'
    for manifest in ('manifest.json','rotary-manifest.json'):
        m=json.loads((HERE/'tables'/manifest).read_text())
        text+=f"- `{m['format']}`, manifest SHA-256 `{sha(HERE/'tables'/manifest)}`.\n"
    text+='\nNonlinear: 24 headerless i64LE files,4096rows each, F12/14/16; x=(i-2048)/256 for six nonlinear functions; mean-square=(i+256)/1024 for rsqrt/l2-128. Rotary: three headerless i64LE files,65536words each, flattened[1024position][32pair][cos,sin]. Nearest-even of deterministic Q256 integer approximation; reciprocal-root rounding is exact by integer midpoint comparison. The artifact generator is not a theorem of correctly rounded real exp/log/trig. Both manifest families and generated headers are regenerated bit for bit.\n\n'
    text+='| File | SHA-256 |\n|---|---|\n'
    for manifest in ('manifest.json','rotary-manifest.json'):
        for t in json.loads((HERE/'tables'/manifest).read_text())['tables']:
            text+=f"| {t['file']} | `{t['sha256']}` |\n"
    text+='\n## Deviations and what remains missing from #35\n\n'
    text+=PROVENANCE
    text+='Development batches are preserved under runs/milestones, not pooled with final timings. The conservative O4096 selector backend, restricted norm domain and fixed decay examples were registered before code (`0f0153f`), not post hoc error-budget changes. No failed sample or warmup was removed.\n\n'
    text+='External commitment identity is the principal gap: no matmul provenance, checkpoint-bound taps/constants or prior-chunk history root. Binding the kernel and inputs to committed weights and to the previous chunk is the job of the M3 statement (PR #70, draft) and the state-commitment work (#34), not of this PR. Conv is only one channel/four tokens. Norm lacks learned gains, epsilon, nearzero support and DeltaNet q extra scaling. No sigmoid-times-mixer gate composition, learned A_log/dt_bias, hybrid layer planner, main-prover/CUDA integration, production security/hiding, Lean extension or real-weight fidelity. Upstream no-expert/dq!=d/head256 admission limits are untouched; exact locations and required work are in research/operators/qwen_ops/LIMITS-AND-ROTARY.md. Rotary beyond the public-position text-only1024 profile remains absent.\n\n'
    text+='## Reproduction and evidence provenance\n\nSee research/operators/qwen_ops/README.md and each gadget README. Run record.py final and record.py ubsan-all through the host heavy-job gate with taskset-c0-5; run check_tables.py, check_rotary_tables.py, crosscheck.py and fidelity.py for each operator. Run report.py after all receipts exist. All commands require only g++, Python standard library and the repository; no weights, GPU or paid API.\n\n'
    text+=f"Release proof implementation commit `{build['source_commit']}`, sanitizer commit `{san['source_commit']}`; identical proof.cpp SHA-256 `{build['proof_cpp_sha256']}`. ENV.json pins toolchain, source hashes and compiled artifacts as of the receipt; its hashes of README files and report.py describe the receipt commit and were intentionally not regenerated by the later wording-only review fix (proof.cpp, tables and runs are unchanged). Raw lines and distribution summaries are in runs/. research/results.yaml links to the receipt commit, not a future squash commit. Independent replication and review are still required.\n"
    (EXP/'RESULTS.md').write_text(text)
    (RUNS/'aggregate.json').write_text(json.dumps(data,indent=2)+'\n')


def ledger(data,commit):
    metrics=[]
    def add(name,value,unit,n,stat,source,spread=None,**kw):
        metrics.append(dict(name=name,value=value,unit=unit,n=n,stat=stat,spread=spread,
                            hardware=HARDWARE,date='2026-11-10',commit=commit,
                            source=str((RUNS/source).relative_to(ROOT)),**kw))
    for op,d in data.items():
        for name,unit in [('prove_s','s'),('verify_s','s'),('proof_bytes','B'),('columns','count'),('relations','count')]:
            s=d['summary'][name]
            add(f'{op}_{name}',s['median'],unit,s['n'],'median',f'{op}-summary.json',
                {k:s[k] for k in ('sd','min','max')},note='F12 synthetic research tuple; shared loaded CPU; no model-scale claim')
        add(f'{op}_honest_accept',d['summary']['accepted'],'count',10,'count',f'{op}-summary.json',total=10)
        for suffix in ('','-ubsan'):
            h=d['hostile'+suffix]
            add(f'{op}_hostile{suffix}_reject',h['rejected'],'count',h['total'],'count',f'{op}-hostile{suffix}.jsonl',total=h['total'],note='Sampled local-relation attacks; external history substitution control excluded and separately reported')
            add(f'{op}_complete_malicious{suffix}',h['complete'],'count',h['total'],'count',f'{op}-hostile{suffix}.jsonl',total=h['total'])
        for r in d['fidelity']:
            s=r['error']
            for key,stat in [('median','median'),('p95','single'),('max','max')]:
                add(f'{r["op"]}_f{r["F"]}_error_{key}',s[key],'abs_diff',s['n'],stat,f'{op}-fidelity.json',
                    {k:s[k] for k in ('sd','min','max')},note='Component/point observations; norm/rotary components share 10 vectors; quantized-input reference, not BF16 or learned-weight fidelity')
            if op=='rotary':add(f'rotary_f{r["F"]}_unchanged',r['unchanged'],'count',1920,'count',f'{op}-fidelity.json',total=1920)
        for f in (14,16):
            s=d[f'smoke{f}']
            add(f'{op}_f{f}_smoke_accept',int(s['accept']),'count',1,'count',f'{op}-f{f}-smoke.jsonl',total=1)
            for name,unit in [('prove_s','s'),('verify_s','s'),('proof_bytes','B'),('columns','count'),('relations','count')]:
                add(f'{op}_f{f}_smoke_{name}',s[name],unit,1,'single',f'{op}-f{f}-smoke.jsonl',note='Single smoke run; not a performance estimate')
    add('external_history_replacement_accepted',1,'count',1,'count','conv-history-control.jsonl',total=1,note='NEGATIVE scope result: different consistent history verifies against same public outputs; external history identity absent')
    add('integer_table_regenerations',2,'count',2,'count','table-checks.json',total=2)
    add('rotary_table_regenerations',2,'count',2,'count','rotary-table-checks.json',total=2)
    cross=read('crosscheck.json')
    add('cpp_python_fixture_matches',cross['matched'],'count',cross['cases'],'count','crosscheck.json',total=cross['cases'])
    add('cpp_python_output_words',cross['output_words'],'count',cross['output_words'],'count','crosscheck.json',total=cross['output_words'])
    entry=dict(id='qwen-bounded-operators-1109',title='Bounded Qwen operator relations and pinned integer tables',
               status='measured',status_note=STATUS_NOTE,replication='unreplicated',pr=67,
               summary=SUMMARY,
               conditions=CONDITIONS,
               evidence=[str((EXP/'RESULTS.md').relative_to(ROOT)),'research/operators/qwen_ops/README.md'],metrics=metrics)
    path=ROOT/'research/results.yaml';text=path.read_text();assert 'id: qwen-bounded-operators-1109' not in text
    text+='\n  - id: '+entry.pop('id')+'\n'
    for key,value in entry.items():
        if key=='metrics':
            text+='    metrics:\n'+''.join('      - '+json.dumps(m,separators=(',',':'))+'\n' for m in value)
        else:text+='    '+key+': '+json.dumps(value)+'\n'
    path.write_text(text)
    print(json.dumps(dict(ledger_metrics=len(metrics),receipt_commit=commit)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ledger-commit');a=p.parse_args()
    data=collect()
    if a.ledger_commit:ledger(data,a.ledger_commit)
    else:report(data)
