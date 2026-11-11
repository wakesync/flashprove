#!/usr/bin/env python3
"""Runner of experiments/20261111-7-cpu-phase-cost (see PREREG.md). Run from the repository root.

  run.py registered <bin_dir> <fixture_dir> <out_dir>   the registered suite (run inside fp-heavy.sh)
  run.py debug      <bin_dir> <fixture_dir> <out_dir>   debug fixtures only (A seeds 900..902, B D=16 seed 99)
  run.py replay     <bin_dir> <fixture_dir> <out_dir> [--budget-min M] [--reps N]
                    REPLAY (added 2026-11-11, PREREG Amendments): the registered suite in the registered order,
                    with no wall-clock hard stop, a budget of M minutes (default 45) from its own start and the
                    first N repetitions per cell (default 10). Never part of the registered result; refuses to
                    write under this directory's runs/.
                    Exit status (PREREG Amendments item 3): 0 and final event `done` only if every requested cell
                    ran, every child exited 0 and no child printed a reject/refused line; 2 and final event
                    `stopped` (reason budget) if the budget fired first; 1 and final event `failed` if the suite
                    ran to the end with a failed or rejecting child. The final event carries the counts.

`registered` keeps the registered hard stop (2026-11-11T06:30Z): after it, that mode runs nothing.

Every child process is pinned with taskset to CORES and timed with time.monotonic(); peak RSS is the
child's ru_maxrss from os.wait4 (kernel high-water mark, one value per process, not sampled).
One JSON line per process is appended to <out_dir>/runs.jsonl as soon as it ends, with the child's
own phase lines, exit code, stderr tail, load average and UTC start/end. The output dir must not exist.
"""
import datetime, json, os, pathlib, selectors, sys, time
CORES = os.environ.get('COST7_CORES', '6-11')
BUDGET_S = 45 * 60          # registered: 45 min elapsed from slot grant
HARD_STOP = '2026-11-11T06:30:00Z'
A_BATCHES = 10
B_PER_PROC = 4

def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
def past_hard_stop(): return datetime.datetime.now(datetime.timezone.utc) >= datetime.datetime.fromisoformat(HARD_STOP.replace('Z', '+00:00'))

def run_child(argv, log, meta):
    """fork + exec taskset, read both pipes, reap with os.wait4 to get the child's own rusage."""
    start_utc = utc(); t = time.monotonic()
    r, w = os.pipe(); re_, we = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.dup2(w, 1); os.dup2(we, 2); os.close(r); os.close(re_)
        os.execvp('taskset', ['taskset', '-c', CORES, *map(str, argv)])
    os.close(w); os.close(we)
    sel = selectors.DefaultSelector(); bufs = {r: b'', re_: b''}
    sel.register(r, selectors.EVENT_READ); sel.register(re_, selectors.EVENT_READ)
    while sel.get_map():
        for key, _ in sel.select():
            chunk = os.read(key.fd, 65536)
            if not chunk: sel.unregister(key.fd); os.close(key.fd)
            else: bufs[key.fd] += chunk
    _, status, ru = os.wait4(pid, 0)
    wall = time.monotonic() - t
    code = os.waitstatus_to_exitcode(status)
    lines = []
    for l in bufs[r].decode(errors='replace').splitlines():
        if l.startswith('{'):
            try: lines.append(json.loads(l))
            except json.JSONDecodeError: lines.append({'unparsed': l})
    rec = dict(meta, argv=[str(a) for a in argv], cores=CORES, start_utc=start_utc, end_utc=utc(), exit=code,
               process_wall_s=round(wall, 6), ru_maxrss_kb=ru.ru_maxrss, ru_utime_s=ru.ru_utime, ru_stime_s=ru.ru_stime,
               loadavg=os.getloadavg(), lines=lines, stderr_tail=bufs[re_].decode(errors='replace')[-3000:])
    with open(log, 'a') as f: f.write(json.dumps(rec) + '\n')
    print(json.dumps({k: rec[k] for k in ('cell', 'rep', 'role', 'exit', 'process_wall_s', 'ru_maxrss_kb')}), flush=True)
    return rec

def files_bytes(d):
    return {p.name: p.stat().st_size for p in sorted(pathlib.Path(d).iterdir()) if p.is_file()}

def a_pair(bins, out, cell, rep, seed, batches, log):
    d = out / 'artifacts' / f'{cell}-{rep}'; d.mkdir(parents=True)
    pr = run_child([bins / 'phase_a', 'prove', d, seed, batches], log, dict(profile='A', cell=cell, rep=rep, role='prover', seed=seed, batches=batches))
    done = next((l.get('batches') for l in pr['lines'] if l.get('summary') == 'prove'), 0) or 0
    vr = run_child([bins / 'phase_a', 'verify', d, done], log, dict(profile='A', cell=cell, rep=rep, role='verifier', seed=seed, batches=done))
    with open(log, 'a') as f: f.write(json.dumps(dict(profile='A', cell=cell, rep=rep, role='files', bytes=files_bytes(d))) + '\n')
    return pr, vr

def b_pair(bins, binname, out, cell, rep, fixtures, log):
    d = out / 'artifacts' / f'{cell}-{rep}'; d.mkdir(parents=True)
    pr = run_child([bins / binname, 'prove', d, *fixtures], log, dict(profile='B', cell=cell, rep=rep, role='prover', fixtures=[pathlib.Path(x).name for x in fixtures]))
    n = len(fixtures) if pr['exit'] == 0 else 0
    vr = run_child([bins / binname, 'verify', d, n], log, dict(profile='B', cell=cell, rep=rep, role='verifier', count=n))
    with open(log, 'a') as f: f.write(json.dumps(dict(profile='B', cell=cell, rep=rep, role='files', bytes=files_bytes(d))) + '\n')
    return pr, vr

REPLAY_USAGE = 'usage: run.py replay <bin_dir> <fixture_dir> <out_dir> [--budget-min M] [--reps N]'

def replay_args(rest):
    """--budget-min M (finite, > 0 also after conversion to seconds) and --reps N (integer 1..10) for replay mode."""
    budget_min, reps, i = 45.0, 10, 0
    while i < len(rest):
        if rest[i] not in ('--budget-min', '--reps'): sys.exit(f'replay: unknown argument {rest[i]!r}\n{REPLAY_USAGE}')
        if i + 1 >= len(rest): sys.exit(f'replay: {rest[i]} needs a value\n{REPLAY_USAGE}')
        flag, val = rest[i], rest[i + 1]; i += 2
        try:
            if flag == '--budget-min': budget_min = float(val)
            else: reps = int(val)
        except ValueError:
            sys.exit(f'replay: {flag} got {val!r}, not a {"number" if flag == "--budget-min" else "whole number"}\n{REPLAY_USAGE}')
    budget_s = budget_min * 60
    if not (0 < budget_s < float('inf')): sys.exit('replay: --budget-min must be finite and > 0 (also in seconds)')
    if not (1 <= reps <= 10): sys.exit('replay: --reps must be 1..10')
    return budget_s, reps

def replay_counts(pairs):
    procs = [r for p in pairs for r in p]
    return dict(children=len(procs), nonzero_exits=sum(1 for r in procs if r['exit'] != 0),
                reject_or_refused_lines=sum(1 for r in procs for l in r['lines'] if 'reject' in l or 'refused' in l))

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'replay' and len(sys.argv) < 5: sys.exit(REPLAY_USAGE)
    mode, bins, fx, out = sys.argv[1], *map(lambda x: pathlib.Path(x).resolve(), sys.argv[2:5])
    if mode == 'replay':
        budget_s, reps = replay_args(sys.argv[5:])
        runs_dir = (pathlib.Path(__file__).resolve().parent / 'runs').resolve()
        if out == runs_dir or runs_dir in out.parents:
            sys.exit('replay: refusing to write under the registered runs/ directory; pass a fresh output dir')
        out.mkdir(parents=False, exist_ok=False)
        log = out / 'runs.jsonl'
        granted = time.monotonic()
        head = dict(event='replay_started', utc=utc(), mode='replay', cores=CORES, budget_s=budget_s, reps=reps,
                    hard_stop=None, registered_hard_stop_not_applied=HARD_STOP, loadavg=os.getloadavg(),
                    note='replay: not part of the registered result')
        with open(log, 'a') as f: f.write(json.dumps(head) + '\n')
        print(json.dumps(head), flush=True)
        pairs = []
        stopped = suite(bins, fx, out, log, granted, reps, lambda: time.monotonic() - granted > budget_s, pairs)
        counts = replay_counts(pairs)
        elapsed = round(time.monotonic() - granted, 1)
        if stopped is not None:
            ev, rc = dict(event='stopped', utc=utc(), before=stopped, reason='budget', elapsed_s=elapsed, **counts), 2
        elif counts['nonzero_exits'] or counts['reject_or_refused_lines']:
            ev, rc = dict(event='failed', utc=utc(), elapsed_s=elapsed, **counts), 1
        else:
            ev, rc = dict(event='done', utc=utc(), elapsed_s=elapsed, **counts), 0
        with open(log, 'a') as f: f.write(json.dumps(ev) + '\n')
        print(json.dumps(ev), flush=True)
        return rc
    out.mkdir(parents=False, exist_ok=False)
    log = out / 'runs.jsonl'
    granted = time.monotonic()
    head = dict(event='slot_granted', utc=utc(), mode=mode, cores=CORES, budget_s=BUDGET_S, hard_stop=HARD_STOP, loadavg=os.getloadavg())
    with open(log, 'a') as f: f.write(json.dumps(head) + '\n')
    print(json.dumps(head), flush=True)
    def over():
        return time.monotonic() - granted > BUDGET_S or past_hard_stop()
    def stop(what):
        with open(log, 'a') as f: f.write(json.dumps(dict(event='stopped', utc=utc(), before=what)) + '\n')
        print('STOPPED before', what, flush=True)
    if mode == 'debug':
        for s in (900, 901):
            a_pair(bins, out, 'debug-A-cold', s, s, 1, log)
        a_pair(bins, out, 'debug-A-amort', 902, 902, A_BATCHES, log)
        b_pair(bins, 'phase_b_d16', out, 'debug-B-cold', 99, [fx / 'd16-seed99.bin'], log)
        b_pair(bins, 'phase_b_d16', out, 'debug-B-amort', 99, [fx / 'd16-seed99.bin'] * B_PER_PROC, log)
        return
    assert mode == 'registered'
    return suite(bins, fx, out, log, granted, 10, over)

def suite(bins, fx, out, log, granted, reps, over, pairs=None):
    """The registered suite and order (PREREG Runs). `registered` calls it with reps = 10 and the registered stop
    (pairs None: it logs `stopped`/`done` itself and returns None, unchanged). `replay` passes a list: the pair results
    are collected there, nothing final is logged here, and the return value is the stop point (None if it completed)."""
    def stop(what):
        if pairs is not None: return what
        with open(log, 'a') as f: f.write(json.dumps(dict(event='stopped', utc=utc(), before=what)) + '\n')
        print('STOPPED before', what, flush=True)
    keep = pairs.append if pairs is not None else (lambda p: None)
    for i in range(reps):
        if over(): return stop(f'cold rep {i}')
        keep(a_pair(bins, out, 'A-cold', i, i, 1, log))
        if over(): return stop(f'B cold rep {i}')
        keep(b_pair(bins, 'phase_b', out, 'B-cold', i, [fx / f'stage1-seed{i + 1}.bin'], log))
    for i in range(reps):
        if over(): return stop(f'amortized rep {i}')
        keep(a_pair(bins, out, 'A-amort', i, i, A_BATCHES, log))
        if over(): return stop(f'B amortized rep {i}')
        seeds = [((i + j) % 10) + 1 for j in range(B_PER_PROC)]
        keep(b_pair(bins, 'phase_b', out, 'B-amort', i, [fx / f'stage1-seed{s}.bin' for s in seeds], log))
    if pairs is not None: return None
    with open(log, 'a') as f: f.write(json.dumps(dict(event='done', utc=utc(), elapsed_s=round(time.monotonic() - granted, 1))) + '\n')

if __name__ == '__main__':
    sys.exit(main())   # registered/debug return None (exit 0, unchanged); replay returns its status
