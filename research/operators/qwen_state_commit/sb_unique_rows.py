#!/usr/bin/env python3
"""SUPPLEMENTARY per-run evidence for experiments/20261111-34-sb-unique-floor (PREREG amendment of
2026-11-11 10:55 UTC). Not the registered run.

Reruns the registered suite with the SAME code (sb_unique.py, sb_unique_lib.py, unchanged from
2e6e4a37) and keeps what sb_unique.main computes but does not save: the per-run rows of run_set,
the first out-of-window floor of each run and of each adversarial case, and the adversarial per-case
rows. It wraps the existing functions and adds no arithmetic of its own, except reading the quotient
of the first out-of-window floor (N >> k, the same Q that sb_unique_lib.alternatives computes).

The aggregate output of sb_unique.main from this rerun goes to a temporary file and is compared with
the committed registered file (every key except elapsed `seconds`); the result of that comparison is
written into the rows file. The registered file is only read.

Usage: sb_unique_rows.py --registered <runs/sb-unique.json> --out <runs/sb-unique-rows.json>
"""
import argparse, datetime, json, os, pathlib, statistics, sys, tempfile
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import sb_unique as S
import sb_unique_lib as U

state = dict(mode=None, chunk=0, run_events=[], adv_events=[], arm=None)
_orig_gen = S.R.gen_tokens
_orig_check = S.check_chunk
_orig_run_set = S.run_set
_orig_adv = S.adversarial
arms_rows = []


def gen_tokens(*a, **kw):
    # run_set calls gen_tokens once per (dist, seed): start a new run
    state['chunk'] = 0
    state['run_events'].append(None)
    return _orig_gen(*a, **kw)


def first_out_of_window(fl, GB):
    for i, (kind, N, k) in enumerate(fl):
        lo, hi = U.window(kind, GB)
        Q = N >> k
        if not (lo <= Q < hi):
            return dict(kind=kind, floor_index_in_chunk=i, k=k, N=N, N_bits=abs(N).bit_length(), Q=Q,
                        window=[lo, hi], excess_over_window=(Q - (hi - 1)) if Q >= hi else (Q - lo))
    return None


def check_chunk(fl, GB, tally, ctrl=None, mut=None):
    ev = first_out_of_window(fl, GB)
    if state['mode'] == 'reg':
        if ev is not None and state['run_events'][-1] is None:
            ev = dict(chunk=state['chunk'], **ev)
            state['run_events'][-1] = ev
        state['chunk'] += 1
    elif state['mode'] == 'adv':
        state['adv_events'].append(ev)
    return _orig_check(fl, GB, tally, ctrl, mut)


def sd_block(rows):
    out = {}
    for k in S.KINDS:
        xs = [r['max_bits'][k] for r in rows]
        out[k] = dict(n=len(xs), median=statistics.median(xs), min=min(xs), max=max(xs),
                      sd_sample=round(statistics.stdev(xs), 4) if len(xs) > 1 else 0.0,
                      sd_population=round(statistics.pstdev(xs), 4))
    return out


def run_set(GB, C, dists, seeds, tally, ctrl, mut, rows):
    state.update(mode='reg', run_events=[], arm=dict(GB=GB, C=C))
    _orig_run_set(GB, C, dists, seeds, tally, ctrl, mut, rows)
    assert len(state['run_events']) == len(rows)
    per_run = [dict(r, first_out_of_window=e) for r, e in zip(rows, state['run_events'])]
    arms_rows.append(dict(GB=GB, C=C, runs=per_run, max_bits_over_runs=sd_block(rows)))
    state['mode'] = None


def adversarial(GB, C, n, rng):
    state.update(mode='adv', adv_events=[])
    tally, rows = _orig_adv(GB, C, n, rng)
    assert len(state['adv_events']) == len(rows)
    a = arms_rows[-1]; assert (a['GB'], a['C']) == (GB, C)
    a['adversarial_cases'] = [dict(r, first_out_of_window=e) for r, e in zip(rows, state['adv_events'])]
    state['mode'] = None
    return tally, rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--registered', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    S.R.gen_tokens = gen_tokens; S.check_chunk = check_chunk; S.run_set = run_set; S.adversarial = adversarial
    start = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    fd, tmp = tempfile.mkstemp(suffix='.json'); os.close(fd)
    try:
        sys.argv = ['sb_unique.py', '--out', tmp]
        S.main()
        agg = json.loads(pathlib.Path(tmp).read_text())
    finally:
        os.unlink(tmp)
    finish = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    reg = json.loads(pathlib.Path(a.registered).read_text())
    reg_s = reg.pop('seconds'); agg_s = agg.pop('seconds')
    equal = reg == agg
    diff_keys = [] if equal else sorted(k for k in set(reg) | set(agg) if reg.get(k) != agg.get(k))
    out = dict(
        label='SUPPLEMENTARY deterministic rerun of the registered suite with the same code, for per-run rows. '
              'Not the registered run (that is runs/sb-unique.json, unchanged). Timestamps below are this rerun\'s own.',
        experiment='20261111-34-sb-unique-floor', code='sb_unique.py and sb_unique_lib.py as in 2e6e4a37, called through sb_unique_rows.py',
        rerun_start_utc=start, rerun_finish_utc=finish, rerun_seconds=agg_s, registered_seconds=reg_s,
        aggregates_equal_registered_except_seconds=equal, differing_top_level_keys=diff_keys,
        note='max_bits_over_runs: per-run maximum numerator bits per floor kind, n = 20 runs (R1..R4 x seeds 1..5); '
             'sd_sample uses n - 1. first_out_of_window: the first floor of the run whose honest quotient Q = N >> k '
             'leaves L\'s window, with its chunk index (chunks of C tokens after the 64-token warm-up) and its quotient; '
             'null when every floor of the run is accepted. Adversarial case rows as computed by sb_unique.adversarial.',
        arms=arms_rows)
    p = pathlib.Path(a.out); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, default=int) + '\n')
    print('wrote', p.name, 'aggregates_equal_registered_except_seconds =', equal, diff_keys)
    if not equal: sys.exit(3)


if __name__ == '__main__':
    main()
