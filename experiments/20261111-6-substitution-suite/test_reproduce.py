#!/usr/bin/env python3
"""Regression test for suite.py's reproduction mode (PREREG amendment 5). Not a run of the suite.

The clock is set past the registered stop (2026-11-11T06:40Z) for every part:
  (a) registered mode, setup and generation stubbed: still stops before any case and returns
      normally (the registered behaviour, unchanged);
  (b) --reproduce on a small real slice (C-CFG3, C-RPL2, H-PFX1, one repetition, the real
      verifier binaries): every selected case gives a row and the exit status is 0;
  (c) --reproduce whose budget is used up before the first case: exit 3 (incomplete);
  (d) --reproduce into a directory under runs/: refused, nothing written.
Needs bin/cp_verify (verifier/build.sh), bin/subst6/handoff.bin and bin/subst6/handoff_fp94.bin
(build_variants.py; the handoff generation also makes the FP94 proof).
Writes the receipt runs/replay-check.json (refuses to overwrite) and scratch under the directory
given by --scratch (default bin/subst6/replay-check, ignored by git).

Usage: python3 experiments/20261111-6-substitution-suite/test_reproduce.py [--scratch DIR]
"""
import argparse, datetime, hashlib, importlib.util, json, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REAL_DT = datetime.datetime
LATER = (2026, 11, 12, 0, 0)
BINS = ['bin/cp_verify', 'bin/subst6/handoff.bin', 'bin/subst6/handoff_fp94.bin']


class Later(REAL_DT):
    @classmethod
    def now(cls, tz=None):
        return cls(*LATER, tzinfo=datetime.timezone.utc)


def load(tag):
    spec = importlib.util.spec_from_file_location('suite_' + tag, HERE / 'suite.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--scratch', default=str(ROOT / 'bin/subst6/replay-check'))
    args = a.parse_args()
    receipt = HERE / 'runs/replay-check.json'
    if receipt.exists():
        raise SystemExit('refusing to overwrite ' + str(receipt.relative_to(ROOT)))
    scratch = pathlib.Path(args.scratch).resolve()
    if scratch.exists():
        raise SystemExit('scratch directory exists: ' + str(scratch))
    scratch.mkdir(parents=True)
    for b in BINS:
        if not (ROOT / b).is_file():
            raise SystemExit('missing ' + b + ': build it first (see the module docstring)')
    datetime.datetime = Later
    doc = dict(note='regression test of the reproduction mode, not a run of the suite and not evidence for the result',
               simulated_utc=Later.now(datetime.timezone.utc).isoformat(),
               started_utc=REAL_DT.now(datetime.timezone.utc).isoformat(),
               binaries={b: sha(ROOT / b) for b in BINS},
               suite_sha256=sha(HERE / 'suite.py'), parts={})

    # (a) registered mode after the stop: stubs only, no checker may run.
    s = load('a')
    s.WORK = scratch / 'a-work'
    s.c_cases = lambda dry=False: [{'case': 'C-RPL2'}]
    s.h_cases = lambda seed, rep, debug=False: ([], {'stub_generation': True})

    def no_run(cmd):
        raise AssertionError('registered mode ran a checker after its stop')
    s.run = no_run
    out = scratch / 'a-registered.jsonl'
    sys.argv = ['suite.py', '--out', str(out)]
    ret = s.main()
    summ = json.loads(out.with_suffix('.summary.json').read_text())
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    pa = dict(returned=ret, partial=summ['partial'], cases=summ['cases'],
              case_rows=sum('case' in r for r in rows))
    pa['ok'] = ret is None and summ['partial'] is True and summ['cases'] == {} and pa['case_rows'] == 0
    doc['parts']['a_registered_after_stop_unchanged'] = pa

    # (b) reproduce, real slice.
    s = load('b')
    d = scratch / 'b-reproduce'
    sel = ['C-CFG3', 'C-RPL2', 'H-PFX1']
    sys.argv = ['suite.py', '--reproduce', str(d), '--budget-min', '20', '--reps', '1', '--cases', ','.join(sel)]
    t = time.monotonic()
    code = s.main()
    summ = json.loads((d / 'reproduce.summary.json').read_text())
    rows = [json.loads(l) for l in (d / 'reproduce.jsonl').read_text().splitlines()]
    crow = [r for r in rows if 'case' in r]
    pb = dict(exit=code, seconds=round(time.monotonic() - t, 1), rows=len(crow), planned=summ['planned'],
              complete=summ['complete'], mode=summ['mode'],
              cases={r['case']: dict(control_accepts=r['control_accepts'], attack_last=r['attack']['last'],
                                     intended=r['intended'], passed=r['pass']) for r in crow})
    pb['ok'] = (code == 0 and summ['complete'] and sorted(pb['cases']) == sorted(sel)
                and all(v['passed'] for v in pb['cases'].values()) and all(r.get('mode') == 'reproduce' for r in crow))
    doc['parts']['b_reproduce_slice_runs_cases'] = pb

    # (c) reproduce with its budget used up before the first case.
    s = load('c')

    def slow_cases(dry=False):
        time.sleep(0.2)
        return [{'case': 'C-RPL2', 'cmd': [], 'control': [], 'expected': 'accept', 'kind': 'not_enforced', 'reason': None}]
    s.c_cases = slow_cases
    s.run = no_run
    d = scratch / 'c-reproduce'
    sys.argv = ['suite.py', '--reproduce', str(d), '--budget-min', '0.001', '--reps', '1', '--cases', 'C-RPL2']
    code = s.main()
    summ = json.loads((d / 'reproduce.summary.json').read_text())
    pc = dict(exit=code, rows=summ['rows'], complete=summ['complete'], partial=summ['partial'])
    pc['ok'] = code == 3 and summ['rows'] == 0 and not summ['complete']
    doc['parts']['c_reproduce_budget_used_exits_3'] = pc

    # (d) reproduce into runs/: refused before anything is written.
    s = load('d')
    target = HERE / 'runs' / 'replay-check-should-not-exist'
    sys.argv = ['suite.py', '--reproduce', str(target), '--budget-min', '1']
    try:
        s.main()
        refused = False
        msg = ''
    except SystemExit as e:
        refused = True
        msg = str(e)
    pd = dict(refused=refused, message=msg, created=target.exists())
    pd['ok'] = refused and not target.exists()
    doc['parts']['d_reproduce_refuses_runs_dir'] = pd

    datetime.datetime = REAL_DT
    doc['finished_utc'] = REAL_DT.now(datetime.timezone.utc).isoformat()
    doc['all_ok'] = all(p['ok'] for p in doc['parts'].values())
    text = json.dumps(doc, indent=2).replace(str(ROOT), '<repo>') + '\n'
    with receipt.open('x') as f:
        f.write(text)
    print(json.dumps({k: v['ok'] for k, v in doc['parts'].items()} | {'all_ok': doc['all_ok']}))
    return 0 if doc['all_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
