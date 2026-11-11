#!/usr/bin/env python3
"""Test of run.py's replay mode with the clock set after the registered hard stop (PREREG Amendments, 2026-11-11).

  python3 experiments/20261111-7-cpu-phase-cost/test_replay.py <bin_dir> <fixture_dir> <scratch_dir> <receipt.json>

<bin_dir> from build.py, <fixture_dir> from `fixtures.py registered`. <scratch_dir> must not exist; it gets two
output dirs. The runner is imported and its datetime.now() is replaced by the real time plus one day, so the
registered cutoff 2026-11-11T06:30Z is in the past. Checks:
  1. `registered` logs slot_granted + stopped before cold rep 0 and runs no child process (unchanged behaviour).
  2. `replay --reps 1 --budget-min 15` runs the registered suite's first repetition of every cell: 8 child processes
     (A cold, B cold, A amortized, B amortized; prover + verifier each), all exit 0, every proof accepted, event done.
  3. `replay` refuses an output dir under this directory's runs/.
The receipt holds counts, exits, process walls and events only (paths relative). Replay numbers are a smoke test,
not a replication and not part of the registered result. Real children run: use the host's heavy-job gate.
"""
import datetime, importlib.util, json, pathlib, sys
exp = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('cost7_runner', exp / 'run.py')
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
_real = datetime.datetime
SHIFT = datetime.timedelta(days=1)
class AfterCutoff(_real):
    @classmethod
    def now(cls, tz=None):
        t = _real.now(tz) + SHIFT
        return cls(t.year, t.month, t.day, t.hour, t.minute, t.second, t.microsecond, tzinfo=t.tzinfo)
R.datetime.datetime = AfterCutoff
assert R.past_hard_stop(), 'clock shift did not move past the registered cutoff'

bins, fx, scratch, receipt = (pathlib.Path(a).resolve() for a in sys.argv[1:5])
scratch.mkdir(parents=False, exist_ok=False)
def run(argv):
    sys.argv = [str(exp / 'run.py'), *map(str, argv)]
    try: return R.main() or 0   # replay returns its exit status since PREREG Amendments item 3
    except SystemExit as e: return e.code
def load(d): return [json.loads(l) for l in (d / 'runs.jsonl').read_text().splitlines()]
res = {'clock': 'run.py datetime.now() = real UTC + 1 day (registered cutoff in the past)', 'registered_hard_stop': R.HARD_STOP,
       'real_utc_start': _real.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'checks': {}}

# 1. registered mode: unchanged, stops before any child
reg = scratch / 'registered'
code = run(['registered', bins, fx, reg]); recs = load(reg)
procs = [r for r in recs if r.get('role') in ('prover', 'verifier')]
ok1 = code == 0 and [r.get('event') for r in recs] == ['slot_granted', 'stopped'] and recs[-1]['before'] == 'cold rep 0' and not procs
res['checks']['registered_stops_after_cutoff'] = dict(ok=ok1, events=[{k: r[k] for k in ('event', 'before') if k in r} for r in recs], child_processes=len(procs))

# 2. replay mode: runs real children after the cutoff
rep = scratch / 'replay'
code = run(['replay', bins, fx, rep, '--reps', '1', '--budget-min', '15']); recs = load(rep)
procs = [r for r in recs if r.get('role') in ('prover', 'verifier')]
rejects = [l for r in procs for l in r['lines'] if 'reject' in l or 'refused' in l]
cells = sorted({(r['cell'], r['role']) for r in procs})
ok2 = (code in (0, None) and recs[0].get('event') == 'replay_started' and recs[-1].get('event') == 'done'
       and len(procs) == 8 and all(r['exit'] == 0 for r in procs) and not rejects
       and len(cells) == 8 and not any(r.get('event') == 'stopped' for r in recs))
res['checks']['replay_runs_children_after_cutoff'] = dict(
    ok=ok2, head={k: recs[0][k] for k in ('event', 'mode', 'budget_s', 'reps', 'hard_stop', 'registered_hard_stop_not_applied', 'cores')},
    last_event=recs[-1].get('event'), elapsed_s=recs[-1].get('elapsed_s'), child_processes=len(procs), rejects=len(rejects),
    children=[dict(cell=r['cell'], rep=r['rep'], role=r['role'], exit=r['exit'], process_wall_s=r['process_wall_s'],
                   ru_maxrss_kb=r['ru_maxrss_kb']) for r in procs])

# 3. replay refuses the registered runs/ directory
code = run(['replay', bins, fx, exp / 'runs' / 'replay-should-not-exist', '--reps', '1'])
ok3 = isinstance(code, str) and 'refusing' in code and not (exp / 'runs' / 'replay-should-not-exist').exists()
res['checks']['replay_refuses_runs_dir'] = dict(ok=ok3, message=code)

res['all_ok'] = ok1 and ok2 and ok3
res['note'] = 'Smoke test of the replay path only: 1 repetition per cell, not a replication, not part of the registered result.'
receipt.write_text(json.dumps(res, indent=1) + '\n')
print(json.dumps({k: v['ok'] for k, v in res['checks'].items()}), 'all_ok', res['all_ok'])
sys.exit(0 if res['all_ok'] else 1)
