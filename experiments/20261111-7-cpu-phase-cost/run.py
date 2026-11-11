#!/usr/bin/env python3
"""Runner of experiments/20261111-7-cpu-phase-cost (see PREREG.md). Run from the repository root.

  run.py registered <bin_dir> <fixture_dir> <out_dir>   the registered suite (run inside fp-heavy.sh)
  run.py debug      <bin_dir> <fixture_dir> <out_dir>   debug fixtures only (A seeds 900..902, B D=16 seed 99)

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

def main():
    mode, bins, fx, out = sys.argv[1], *map(lambda x: pathlib.Path(x).resolve(), sys.argv[2:5])
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
    for i in range(10):
        if over(): return stop(f'cold rep {i}')
        a_pair(bins, out, 'A-cold', i, i, 1, log)
        if over(): return stop(f'B cold rep {i}')
        b_pair(bins, 'phase_b', out, 'B-cold', i, [fx / f'stage1-seed{i + 1}.bin'], log)
    for i in range(10):
        if over(): return stop(f'amortized rep {i}')
        a_pair(bins, out, 'A-amort', i, i, A_BATCHES, log)
        if over(): return stop(f'B amortized rep {i}')
        seeds = [((i + j) % 10) + 1 for j in range(B_PER_PROC)]
        b_pair(bins, 'phase_b', out, 'B-amort', i, [fx / f'stage1-seed{s}.bin' for s in seeds], log)
    with open(log, 'a') as f: f.write(json.dumps(dict(event='done', utc=utc(), elapsed_s=round(time.monotonic() - granted, 1))) + '\n')

if __name__ == '__main__':
    main()
