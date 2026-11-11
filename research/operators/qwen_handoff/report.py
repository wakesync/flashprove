#!/usr/bin/env python3
"""Render the local evidence report; optionally append exactly one ledger entry.
Never changes raw runs. --commit is the ancestor containing the immutable evidence.
"""
import argparse
import json
import pathlib
import statistics
import subprocess

ROOT=pathlib.Path(__file__).resolve().parents[3]
EXP=ROOT/'experiments/20261110-93-handoff'
SOURCE='experiments/20261110-93-handoff/runs/'

def stats(xs):
    return dict(n=len(xs),median=statistics.median(xs),sd=statistics.stdev(xs) if len(xs)>1 else 0,min=min(xs),max=max(xs))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pr',type=int);ap.add_argument('--commit');args=ap.parse_args()
    summary=json.loads((EXP/'runs/summary.json').read_text())
    counts=json.loads((EXP/'runs/counts.json').read_text())['rows']
    rows=[json.loads(l) for l in (EXP/'runs/suite.jsonl').read_text().splitlines()]
    cases=list(summary['case_acceptance'])
    violations={name:stats([r['proof']['violated_relations'] for r in rows if r['case']==name]) for name in cases if name!='statement_replay_other_layer'}
    text=f'''# Results: two-chunk joint handoff

**{summary['verdict']} against the bounded PREREG, measured and unreplicated.** This is a joint proof for two fixed-size chunks, not a separately resumable/private-root handoff protocol. Issue #93 remains broader than this milestone.

## Plain-language result

The first chunk's final state and the second chunk's starting state are linked by constraints inside one proof, rather than by Python comparing public boundary hashes. The proof also enforces the history shift register from verifier-pinned pre-conv inputs. The standalone verifier reads only its own statement file and a proof. It does not read the prover's manifest or witness files.

The initial root still has a **public opening checked by SHA-256 outside the proof**. Synthetic model/weights identifiers are bound labels, not proof of checkpoint execution. There is no convolution, projection, real-weight fidelity, privacy or production-security claim.

## Registered outcomes

- H1: {summary['honest_accepted']}/5 honest windows accepted, five independent synthetic seeds, D8/F12, two chunks of two tokens.
- H2: 65 complete-hostile proofs and five unchanged-proof statement replays were tested. {summary['hostile_rejected']}/{summary['hostile_cases']} rejected by the proof verifier. All complete-hostile proofs preserve every product gate and emit the full protocol; the reported affine violations are diagnostics, not a verifier precheck.
- H3: the independent counting script matched core/aligned columns, affine relations and range cells of every honest built relation.
- No runs excluded. No timing or speedup hypothesis. Outcomes below are Boolean observations, not estimates of cryptographic soundness.

Raw evidence: `runs/suite.jsonl`, `runs/summary.json`, `runs/counts.json`; environment and source revision: `ENV.json`; binary/source hashes: `runs/build.json`. Deterministic proof and statement hashes are in every raw row. Proofs and witness files are reproducible under ignored `work/`, not committed as large binary artifacts.

| Case | Acceptances / n | Acceptance median; SD; min..max | Violated relations median; SD; min..max |
|---|---:|---|---|
'''
    for name in cases:
        v=summary['case_acceptance'][name]
        accepted=sum(r['verify']['accept'] for r in rows if r['case']==name)
        q=violations.get(name)
        vs=f"{q['median']:g}; {q['sd']:.6g}; {q['min']}..{q['max']}" if q else 'not applicable: transcript replay'
        text+=f"| `{name}` | {accepted}/{v['n']} | {v['median']:g}; {v['sd']:.6g}; {v['min']}..{v['max']} | {vs} |\n"
    text+='''
## Structure, not a performance study

All built structural observations below have n=5 (one per honest seed). These are this lowering's product columns and affine relations, not model-wide values or device memory. Three product field rows live behind each column. The aligned-column count still excludes the larger oracle padding, lookup planes, masks and proximity machinery.

| Quantity per window | Median | SD | Min | Max |
|---|---:|---:|---:|---:|
'''
    for name,v in summary['structure'].items():
        text+=f"| {name} | {v['median']} | {v['sd']:.6g} | {v['min']} | {v['max']} |\n"
    text+='''
The exact formula at T=2C is:

- Extra descriptor/history/input columns and relations: `E = 150 + 36D + 3TD`.
- Core columns: `T((F+5)D^2 + (4F+5)D) + E`.
- Affine relations: `T((2F+9)D^2 + (8F+7)D) + E`.
- Range cells: `T(D^2 + 3D)`.
- The core relation includes D^2 inter-chunk state equalities. The removal of the second initial pin and addition of the equality cancel in the formula. Both chunks' final public state pins are removed. History uses 27D equalities and 9D initial public pins.

`count.py` inventories these independently and the registered runner compares the built fields. The following larger shapes are **counted, not built/proved**; D128 is outside the executable's admitted verifier domain. These are not fit estimates.

| D | C | Core columns/token | Affine relations/token | Evidence kind |
|---:|---:|---:|---:|---|
'''
    for c in counts:
        kind='counted and checked against built relation' if c['D']==8 else 'counted-not-built'
        text+=f"| {c['D']} | {c['C']} | {c['core_columns_per_token']} | {c['relations_per_token']} | {kind} |\n"
    text+='''
## What the negatives do and do not establish

Mixed F12/F13 supplies second-chunk reference states computed with F13 while the verifier derives an F12 relation. Replaced token inputs are actually changed and the suffix recomputed. Initial/intermediate-state changes re-prove the altered recurrence. Two-sided history shifts change both copies of the handoff, and still violate the input-to-history relation. Other layer/request/model/weights proposals change descriptor cells while keeping the verifier statement fixed.

The split/drop/truncation/prefix cases use the two fixed circuit slots: proposed counts/ranges/lengths differ, with identity padding for absent computation. Their rejection is in-proof, but they are **not a variable-size chain of independently accepted chunk proofs**. A private implementation may internally split an otherwise identical computation and then provide the correct fixed-slot witness; that does not change the proved statement. The experiment does not claim to detect that invisible scheduling.

The replay case changes the verifier's layer and retains the honest proof. It tests transcript/statement binding separately from the complete-hostile affine-relation cases.

## Deviations and debugging

Append-only PREREG A1 makes the fixed-slot encoding explicit. A2 records the tiny-head RNG sample-pad collision found only on disjoint debug seed909/D4/C1, before the registered run. Sizing now reserves sample-pad space without dropping any check. `runs/build-debug-1.json` preserves the failed debug binary's hashes; `runs/build.json` is the successful registered binary. Missing local OpenSSL development headers were avoided with a small SHA-256 implementation for the public opening, independently checked against Python hashlib in statement generation. No registered threshold or seed changed; no registered run file was edited.

## Remaining work

- A kept-oracle/segment-frame construction for independently resumable chunks and an authenticated continuation root.
- Hidden initial-state commitment opening, if that is required by the application; the public opening here does not provide it.
- Actual weight/projection commitments and upstream input provenance. Synthetic identifiers alone do not prove model identity.
- The convolution and its connection to post-conv recurrence inputs; only history shift-register provenance is proved here.
- Higher security settings, non-deterministic prover coins, independent replication and hostile-witness review.
- Model-scale counting including all operators, and hardware measurement only in an authorized later lane. No device-fit claim is made here.

Reproduction commands and detailed trust boundary are in `research/operators/qwen_handoff/README.md`.
'''
    (EXP/'RESULTS.md').write_text(text)
    if args.pr is None:return
    if not args.commit:raise ValueError('--commit required with --pr')
    path=ROOT/'research/results.yaml';old=path.read_text()
    if '  - id: qwen-joint-handoff\n' in old:raise ValueError('ledger entry already exists; no overwrite')
    receipt_date=subprocess.check_output(['git','show','-s','--format=%cI',args.commit],cwd=ROOT,text=True).strip().split('T')[0]
    metrics=[]
    def metric(name,value,unit,n,spread,source,note,stat='median',total=None):
        d=dict(name=name,series='qwen-joint-handoff',stat=stat,value=value,unit=unit,n=n,spread=spread,
               hardware='cpu-epyc-rome-kvm-16',date=receipt_date,commit=args.commit,source=SOURCE+source,note=note)
        if total is not None:d['total']=total
        metrics.append(d)
    common='Measured, unreplicated, joint two-slot proof only; D8/F12/C2, research target10/work6, deterministic coins; no timing or privacy claim.'
    for name,v in summary['case_acceptance'].items():
        metric(name+'_acceptance',v['median'],'fraction',v['n'],{k:v[k] for k in ['sd','min','max']},'summary.json',common)
    for name,v in summary['structure'].items():
        metric(name,v['median'],'B' if name=='proof_bytes' else 'count',v['n'],{k:v[k] for k in ['sd','min','max']},'summary.json',common+' Structural description, not a performance comparison.')
    for name,v in violations.items():
        metric(name+'_violated_relations',v['median'],'count',v['n'],{k:v[k] for k in ['sd','min','max']},'suite.jsonl',common+' Diagnostic only; acceptance is decided by the full proof verifier.')
    metric('honest_accepted',summary['honest_accepted'],'count',5,None,'summary.json',common+' Boolean totals, per-seed spread given in honest_acceptance.',stat='count',total=5)
    metric('hostile_rejected',summary['hostile_rejected'],'count',5,None,'summary.json',common+' Includes 65 complete-hostile and 5 transcript replay tests; per-case seed spread above.',stat='count',total=summary['hostile_cases'])
    for c in counts:
        for field in ['core_columns_per_token','relations_per_token']:
            metric(f"counted_D{c['D']}_C{c['C']}_{field}",c[field],'count',1,None,'counts.json',
                   'Exact formula, no variance; counted-not-built except D8/C2 checked against five built relations. Not bytes, not a model-wide or hardware fit estimate.',stat='single')
    entry='\n  - id: qwen-joint-handoff\n'
    fields=dict(title='Two-chunk DeltaNet joint-boundary proof',status='measured' if summary['verdict']=='PASS' else 'negative',
                replication='unreplicated',pr=args.pr,
                summary='5/5 honest accepted; 65/65 complete-hostile and 5/5 statement-replay cases rejected inside the joint proof. Boundary state/history are linked in-proof; the initial SHA root has a public opening checked outside. Not separately resumable chunks.',
                conditions='Five synthetic seeds, one head, D8/F12, two fixed slots of C2 tokens, shared CPU. Split/drop/length proposals use fixed-slot encodings. Model/weights IDs are synthetic labels; no weight, conv, privacy, production-security or hardware-fit claim.',
                evidence=['experiments/20261110-93-handoff/RESULTS.md','research/operators/qwen_handoff/README.md'])
    for k,v in fields.items():entry+=f'    {k}: '+json.dumps(v)+'\n'
    entry+='    metrics:\n'
    for m in metrics:entry+='      - '+json.dumps(m)+'\n'
    path.write_text(old+entry)
    print(f'Added qwen-joint-handoff: {len(metrics)} metrics, PR {args.pr}, receipt commit {args.commit}')

if __name__=='__main__':main()
