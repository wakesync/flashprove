#!/usr/bin/env python3
"""Issue #94 follow-ups of PR #67. CPU only.

  run.py build [--ubsan]     compile work/follow[-ubsan].bin; with --receipt write runs/build[-ubsan].json
  run.py debug               seeds 101..103 (disjoint from the registered suite), work/ only
  run.py suite [--ubsan]     registered seeds 1..5; refuses to overwrite an existing receipt
  run.py digests             configuration digests + per-table SHA-256 vs the manifests
  run.py accounting          per-round accounting receipts, every profile at F12/14/16
  run.py summary             counts per case from the receipts

Every run record written here carries started_utc / finished_utc (issue #94 item 3).
"""
import datetime
import hashlib
import json
import pathlib
import platform
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REL = HERE.relative_to(ROOT)
EXP = ROOT / 'experiments/20261111-94-op-followups'
RUNS = EXP / 'runs'
WORK = HERE / 'work'
OPS_DIR = ROOT / 'research/operators/qwen_ops'
SEEDS = [1, 2, 3, 4, 5]
DEBUG_SEEDS = [101, 102, 103]
OPS = ('nonlinear', 'conv', 'l2', 'rms', 'rotary')


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def sh(args, check=True):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if check and p.returncode:
        raise SystemExit(f'{args}: rc={p.returncode}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}')
    return p


def exe(ubsan=False):
    return WORK / ('follow-ubsan.bin' if ubsan else 'follow.bin')


def fresh(path):
    if path.exists():
        raise SystemExit(f'refusing to overwrite {path}')
    return path


def build(ubsan, receipt):
    WORK.mkdir(exist_ok=True)
    started = now()
    cmd = ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1',
           '-I', 'blocks', f'{REL}/follow.cpp', '-o', str(exe(ubsan).relative_to(ROOT))]
    if ubsan:
        cmd += ['-fsanitize=undefined', '-fno-sanitize-recover=undefined']
    sh(cmd)
    r = dict(started_utc=started, finished_utc=now(),
             source_commit=sh(['git', 'rev-parse', 'HEAD']).stdout.strip(),
             dirty_tracked=bool(sh(['git', 'diff', '--name-only', 'HEAD']).stdout.strip()),
             compiler=sh(['g++', '--version']).stdout.splitlines()[0], python=platform.python_version(), command=cmd,
             follow_cpp_sha256=hashlib.sha256((HERE / 'follow.cpp').read_bytes()).hexdigest(),
             qwen_ops_proof_cpp_sha256=hashlib.sha256((OPS_DIR / 'proof.cpp').read_bytes()).hexdigest(),
             binary_sha256=hashlib.sha256(exe(ubsan).read_bytes()).hexdigest())
    if receipt:
        RUNS.mkdir(parents=True, exist_ok=True)
        fresh(RUNS / f'build{"-ubsan" if ubsan else ""}.json').write_text(json.dumps(r, indent=2) + '\n')
    print(json.dumps(r))


def run_seed(seed, ubsan):
    started = now()
    p = sh([str(exe(ubsan)), 'suite', str(seed)], check=False)
    finished = now()
    if p.returncode != 0:
        raise SystemExit(f'seed {seed}: harness error rc={p.returncode}: {p.stderr[-3000:]}')
    rows = []
    for line in p.stdout.splitlines():
        r = json.loads(line)
        r.update(ubsan=ubsan, stderr_bytes=len(p.stderr))
        rows.append(r)
    return dict(mode='run', seed=seed, ubsan=ubsan, started_utc=started, finished_utc=finished,
                stderr_bytes=len(p.stderr), cases=len(rows)), rows


def suite(seeds, ubsan, out):
    lines = []
    for s in seeds:
        head, rows = run_seed(s, ubsan)
        lines.append(head)
        lines.extend(rows)
        bad = [r['case'] + '/' + r['profile'] for r in rows if not r['as_expected']]
        print(json.dumps(dict(seed=s, cases=len(rows), unexpected=bad, started_utc=head['started_utc'],
                              finished_utc=head['finished_utc'])), flush=True)
    out.write_text(''.join(json.dumps(x) + '\n' for x in lines))


def manifest_hashes():
    m = json.loads((OPS_DIR / 'tables/manifest.json').read_text())
    r = json.loads((OPS_DIR / 'tables/rotary-manifest.json').read_text())
    h = {f"{t['name']}-f{t['F']}": t['sha256'] for t in m['tables']}
    h.update({f"rotary-f{t['F']}": t['sha256'] for t in r['tables']})
    return (hashlib.sha256((OPS_DIR / 'tables/manifest.json').read_bytes()).hexdigest(),
            hashlib.sha256((OPS_DIR / 'tables/rotary-manifest.json').read_bytes()).hexdigest(), h)


def digests(out):
    started = now()
    p = sh([str(exe()), 'digests'])
    man, rman, h = manifest_hashes()
    rows = [json.loads(l) for l in p.stdout.splitlines()]
    checks = []
    for r in rows:
        for name, sha in r['tables'].items():
            checks.append(dict(op=r['op'], F=r['F'], table=name, compiled_sha256=sha, manifest_sha256=h[name], equal=sha == h[name]))
        r['v1_ne_v2'] = r['v1'] != r['v2']
        r['claims_match_manifest_files'] = r['manifest_claim'] == man and r['rotary_manifest_claim'] == rman
    v2s = [r['v2'] for r in rows]
    summary = dict(mode='digests', started_utc=started, finished_utc=now(), profiles=len(rows),
                   manifest_sha256=man, rotary_manifest_sha256=rman,
                   tables_checked=len(checks), tables_equal=sum(c['equal'] for c in checks),
                   v1_ne_v2=sum(r['v1_ne_v2'] for r in rows), v2_distinct=len(set(v2s)),
                   claims_match=all(r['claims_match_manifest_files'] for r in rows))
    out.write_text(''.join(json.dumps(x) + '\n' for x in [summary] + rows + checks))
    print(json.dumps(summary))


def accounting(outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    allrows = []
    for op in OPS:
        for f in (12, 14, 16):
            seed = 7
            started = now()
            cmd = [str(exe().relative_to(ROOT)), 'accounting', op, str(f), str(seed)]
            p = sh(cmd)
            finished = now()
            js, text = p.stdout.split('--- print_accounting ---\n')
            rows = [json.loads(l) for l in js.splitlines()]
            acct = rows[-1]
            acct.update(started_utc=started, finished_utc=finished, command=' '.join(cmd))
            path = fresh(outdir / f'{op}-f{f}.txt')
            path.write_text(f'# command: {" ".join(cmd)}\n# started_utc: {started}\n# finished_utc: {finished}\n'
                            f'# source: {REL}/follow.cpp, plan of research/operators/qwen_ops/proof.cpp run_for() (v1 and v2 share it)\n'
                            + js + '--- print_accounting (blocks/numbers/accounting.h) ---\n' + text)
            allrows.append(acct)
    fresh(outdir / 'summary.json').write_text(json.dumps(allrows, indent=2) + '\n')
    for a in allrows:
        print(a['op'], a['F'], a['rounds'], round(a['diagnostic_sum_bits_with_work'], 8), round(a['weakest_without_work_bits'], 8))


def summary(paths):
    counts = {}
    runs = []
    for path in paths:
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r['mode'] == 'run':
                runs.append(r)
                continue
            k = (r['case'], r['profile'], r['kind'], r['expected'], r['ubsan'])
            c = counts.setdefault(k, dict(case=r['case'], profile=r['profile'], kind=r['kind'], expected=r['expected'],
                                          ubsan=r['ubsan'], runs=0, accepted=0, as_expected=0, complete=0))
            c['runs'] += 1
            c['accepted'] += r['accepted']
            c['as_expected'] += r['as_expected']
            c['complete'] += r['complete_proof']
    rows = sorted(counts.values(), key=lambda c: (c['ubsan'], c['kind'], c['case'], c['profile']))
    tot = {}
    for c in rows:
        t = tot.setdefault((c['kind'], c['ubsan']), dict(kind=c['kind'], ubsan=c['ubsan'], cases=0, decisions=0, as_expected=0, accepted=0))
        t['cases'] += 1
        t['decisions'] += c['runs']
        t['as_expected'] += c['as_expected']
        t['accepted'] += c['accepted']
    return dict(runs=runs, totals=list(tot.values()), cases=rows,
                all_as_expected=all(c['as_expected'] == c['runs'] for c in rows),
                timestamps_present=all(r.get('started_utc', '').endswith('Z') and r.get('finished_utc', '').endswith('Z') for r in runs))


if __name__ == '__main__':
    a = sys.argv[1:]
    ubsan = '--ubsan' in a
    if not a:
        raise SystemExit(__doc__)
    if a[0] == 'build':
        build(ubsan, '--receipt' in a)
    elif a[0] == 'debug':
        WORK.mkdir(exist_ok=True)
        out = WORK / f'debug{"-ubsan" if ubsan else ""}.jsonl'
        suite(DEBUG_SEEDS, ubsan, out)
        print(json.dumps(summary([out])['totals']))
    elif a[0] == 'suite':
        RUNS.mkdir(parents=True, exist_ok=True)
        suite(SEEDS, ubsan, fresh(RUNS / f'suite{"-ubsan" if ubsan else ""}.jsonl'))
    elif a[0] == 'digests':
        RUNS.mkdir(parents=True, exist_ok=True)
        digests(fresh(RUNS / 'digests.jsonl'))
    elif a[0] == 'accounting':
        accounting(EXP / 'receipts/accounting')
    elif a[0] == 'summary':
        paths = [p for p in (RUNS / 'suite.jsonl', RUNS / 'suite-ubsan.jsonl') if p.exists()]
        s = summary(paths)
        fresh(RUNS / 'summary.json').write_text(json.dumps(s, indent=2) + '\n')
        print(json.dumps(dict(totals=s['totals'], all_as_expected=s['all_as_expected'], timestamps_present=s['timestamps_present'])))
    else:
        raise SystemExit(__doc__)
