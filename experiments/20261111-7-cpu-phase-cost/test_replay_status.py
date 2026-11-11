#!/usr/bin/env python3
"""Subprocess-level test of run.py's exit status and final event (PREREG Amendments item 3, 2026-11-11).

  python3 experiments/20261111-7-cpu-phase-cost/test_replay_status.py <bin_dir> <fixture_dir> <scratch_dir> <receipt.json>

<bin_dir> from build.py, <fixture_dir> from `fixtures.py registered`. <scratch_dir> must not exist. Every case runs
`python3 run.py ...` as a child process and checks its return code and the events in its runs.jsonl:
  budget_before_any_child   replay --budget-min 1e-12 --reps 1              -> rc 2, final `stopped` reason budget, 0 children
  budget_partial_real       replay --budget-min 0.02 --reps 1 (real bins)   -> rc 2, final `stopped`, partial records kept
  missing_binaries          replay with an empty bin dir                     -> rc 1, final `failed`, no `done`, 8 exits 127
  reject_line               replay with stub binaries that exit 0 but print a reject line -> rc 1, final `failed`
  happy_completion          replay --reps 1 --budget-min 15 (real bins)      -> rc 0, final `done`, 8 children exit 0
  registered_after_cutoff   registered (real clock, after 2026-11-11T06:30Z) -> rc 0, slot_granted + stopped (unchanged)
  option errors             --budget-min 1e308 / inf, --reps 2.5, --reps without value, too few arguments
                            -> nonzero, a one-line message, no Python traceback, no output dir created
The two real-binary cases run real child processes: use the host's heavy-job gate. Replay numbers are not a
replication and not part of the registered result. The receipt holds return codes, events and counts only.
"""
import datetime, json, os, pathlib, stat, subprocess, sys
exp = pathlib.Path(__file__).resolve().parent
root = exp.parents[1]
bins, fx, scratch, receipt = (pathlib.Path(a).resolve() for a in sys.argv[1:5])
scratch.mkdir(parents=False, exist_ok=False)
empty = scratch / 'empty-bins'; empty.mkdir()
stub = scratch / 'stub-bins'; stub.mkdir()
for name in ('phase_a', 'phase_b'):
    p = stub / name
    p.write_text('#!/bin/sh\necho \'{"reject":"proof","batch":0,"why":"stub"}\'\nexit 0\n')
    p.chmod(p.stat().st_mode | stat.S_IXUSR)

def run(args):
    p = subprocess.run([sys.executable, str(exp / 'run.py'), *map(str, args)], capture_output=True, text=True, cwd=str(root), timeout=1800)
    return p
def events(d):
    log = d / 'runs.jsonl'
    if not log.exists(): return None, []
    recs = [json.loads(l) for l in log.read_text().splitlines()]
    return recs, [r for r in recs if r.get('role') in ('prover', 'verifier')]
def summary(p, recs, procs):
    ev = [r['event'] for r in recs if 'event' in r] if recs else []
    last = next((r for r in reversed(recs or []) if 'event' in r), {})
    return dict(rc=p.returncode, events=ev, final={k: last[k] for k in ('event', 'reason', 'before', 'children', 'nonzero_exits', 'reject_or_refused_lines') if k in last},
                child_processes=len(procs), child_exits=[r['exit'] for r in procs])

res = {'real_utc_start': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'cases': {}}
C = res['cases']

o = scratch / 'budget0'; p = run(['replay', empty, fx, o, '--budget-min', '1e-12', '--reps', '1']); recs, procs = events(o)
s = summary(p, recs, procs)
s['ok'] = p.returncode == 2 and s['events'] == ['replay_started', 'stopped'] and s['final'].get('reason') == 'budget' and not procs
C['budget_before_any_child'] = s

o = scratch / 'partial'; p = run(['replay', bins, fx, o, '--budget-min', '0.02', '--reps', '1']); recs, procs = events(o)
s = summary(p, recs, procs)
s['ok'] = (p.returncode == 2 and s['events'][0] == 'replay_started' and s['events'][-1] == 'stopped' and 'done' not in s['events']
           and s['final'].get('reason') == 'budget' and 0 < len(procs) < 8 and s['final'].get('children') == len(procs))
C['budget_partial_real'] = s

o = scratch / 'missing'; p = run(['replay', empty, fx, o, '--budget-min', '5', '--reps', '1']); recs, procs = events(o)
s = summary(p, recs, procs)
s['ok'] = (p.returncode == 1 and s['events'] == ['replay_started', 'failed'] and 'done' not in s['events'] and len(procs) == 8
           and all(e != 0 for e in s['child_exits']) and s['final'].get('nonzero_exits') == 8)
C['missing_binaries'] = s

o = scratch / 'reject'; p = run(['replay', stub, fx, o, '--budget-min', '5', '--reps', '1']); recs, procs = events(o)
s = summary(p, recs, procs)
s['ok'] = (p.returncode == 1 and s['events'] == ['replay_started', 'failed'] and len(procs) == 8 and all(e == 0 for e in s['child_exits'])
           and s['final'].get('nonzero_exits') == 0 and s['final'].get('reject_or_refused_lines', 0) >= 8)
C['reject_line'] = s

o = scratch / 'happy'; p = run(['replay', bins, fx, o, '--budget-min', '15', '--reps', '1']); recs, procs = events(o)
s = summary(p, recs, procs)
rej = [l for r in procs for l in r['lines'] if 'reject' in l or 'refused' in l]
s['ok'] = (p.returncode == 0 and s['events'] == ['replay_started', 'done'] and len(procs) == 8 and all(e == 0 for e in s['child_exits'])
           and not rej and s['final'].get('children') == 8 and s['final'].get('nonzero_exits') == 0)
s['cells'] = sorted({f"{r['cell']}/{r['role']}" for r in procs})
s['process_wall_s'] = [r['process_wall_s'] for r in procs]
C['happy_completion'] = s

o = scratch / 'registered'; p = run(['registered', empty, fx, o]); recs, procs = events(o)
s = summary(p, recs, procs)
s['ok'] = p.returncode == 0 and s['events'] == ['slot_granted', 'stopped'] and recs[-1].get('before') == 'cold rep 0' and not procs and set(recs[-1]) == {'event', 'utc', 'before'}
s['note'] = 'unchanged registered behaviour after the cutoff (exit 0, disclosed in PR #106)'
C['registered_after_cutoff'] = s

for nm, extra in [('budget_1e308', ['--budget-min', '1e308']), ('budget_inf', ['--budget-min', 'inf']), ('reps_float', ['--reps', '2.5']),
                  ('reps_missing_value', ['--reps']), ('budget_word', ['--budget-min', 'ten'])]:
    o = scratch / f'opt-{nm}'; p = run(['replay', empty, fx, o, *extra])
    C[nm] = dict(rc=p.returncode, message=p.stderr.strip().splitlines()[0] if p.stderr.strip() else '', outdir_created=o.exists(),
                 ok=p.returncode != 0 and 'Traceback' not in p.stderr and p.stderr.startswith('replay:') and not o.exists())
p = run(['replay', empty, fx])
C['too_few_arguments'] = dict(rc=p.returncode, message=p.stderr.strip(), ok=p.returncode != 0 and 'Traceback' not in p.stderr and p.stderr.startswith('usage:'))

res['all_ok'] = all(c['ok'] for c in C.values())
res['note'] = 'Exit-status test of the replay path; the real-binary cases are 1 repetition per cell, not a replication, not part of the registered result.'
receipt.write_text(json.dumps(res, indent=1) + '\n')
print(json.dumps({k: v['ok'] for k, v in C.items()}), 'all_ok', res['all_ok'])
sys.exit(0 if res['all_ok'] else 1)
