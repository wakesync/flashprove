#!/usr/bin/env python3
"""CPU test of RUNBOOK.md step 5's result fetch: the fetch must be over before the restore cut-off,
or not be started at all. No GPU, no network, no provider command, no credential.

The test does not test a copy of the fetch logic. It reads the two fetch commands out of a runbook
(default: RUNBOOK.md next to this file): the `tinfoil http get` block and the proxy `curl`
alternative. In each it keeps the runbook's own text up to the point where the fetch program starts
(the clock reads, the guard, `timeout`, or the helper call, with the runbook's own arguments) and
puts an inert local program in place of the fetch. It then runs these shims in bash:

  one_to_zero        mocked clock: 1 s left at the first read, 0 at the second
  at_cutoff          mocked clock: 0 s left at every read
  past_cutoff        mocked clock: 30 s past the cut-off (extra case)
  insufficient_grace real clock: 4 s left, less than the kill grace; the fetch ignores TERM
  term_ignoring      real clock: 20 s left; the fetch ignores TERM and would run 40 s
  normal_fetch       real clock: 60 s left; the fetch takes 1 s (sanity: a fetch still runs)

and checks: with too little time left the fetch is not started; when it is started it is over
(including a KILL after the grace) no later than the cut-off by the wall clock; a fetch with time
enough runs to the end. A static check requires both fetch commands to go through
fetch_bounded.sh. Without --runbook it also checks the helper's own argument handling and exit
statuses.

  python3 fetch_bounded_test.py                       # this package's RUNBOOK.md and helper
  python3 fetch_bounded_test.py --runbook OLD.md      # e.g. RUNBOOK.md of an earlier commit

Prints PASS/FAIL per check and "N of M checks passed"; exit 0 only if all pass.
"""
import argparse
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
HELPER = HERE / 'fetch_bounded.sh'
FIXED_CUT = 2000000000          # mocked-clock cut-off, epoch seconds
FIXED_CUT_ISO = '2033-05-18T03:33:20Z'

results = []


def check(name, ok, detail=''):
    results.append(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + ((': ' + detail) if detail else ''), flush=True)


def iso(epoch):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(epoch))


def extract(runbook_text):
    """Returns (setup_lines, block_prefix, proxy_prefix) from the runbook's step 5."""
    step5 = runbook_text.split('## 5.', 1)[1].split('## 6.', 1)[0]
    blocks = re.findall(r'```sh\n(.*?)```', step5, re.S)
    block = next(b for b in blocks if 'results.tar.gz --enclave' in b)
    lines = block.splitlines()
    i = next(k for k, ln in enumerate(lines) if 'tinfoil http get' in ln)
    prefix_line = lines[i - 1].rstrip()
    if prefix_line.endswith('\\'):
        prefix_line = prefix_line[:-1].rstrip()
    setup = [ln for ln in lines[:i - 1] if ln.strip() and not ln.startswith('CUTOFF=')]
    spans = re.findall(r'`([^`]*127\.0\.0\.1:3301/results\.tar\.gz[^`]*)`', step5)
    proxy = spans[0] if spans else ''
    proxy_prefix = proxy[:proxy.index('curl')].rstrip() if 'curl' in proxy else ''
    return setup, prefix_line, proxy_prefix


INERT = '''import signal, sys, time
mode, seconds, marker = sys.argv[1], float(sys.argv[2]), sys.argv[3]
if mode == 'ignore-term':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
open(marker, 'a').write('started\\n')
time.sleep(seconds)
open(marker, 'a').write('finished\\n')
'''

MOCK_DATE = '''#!/usr/bin/env python3
# Mocked `date` for the test: `date -u +%s` returns the next value of the sequence file (the last one
# repeats); every other form (`-d <cutoff>`, formats) is passed to the real date.
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
if '-d' not in args and '+%s' in args:
    seq = open(os.path.join(here, 'seq')).read().split()
    n = int(open(os.path.join(here, 'n')).read()) if os.path.exists(os.path.join(here, 'n')) else 0
    open(os.path.join(here, 'n'), 'w').write(str(n + 1))
    print(seq[min(n, len(seq) - 1)])
    sys.exit(0)
os.execv('/usr/bin/date', ['date'] + args)
'''


def run_shim(td, name, setup, prefix, cutoff_iso, mode, seconds, mock_seq=None):
    """Runs one shim; returns dict(started, finished, exit, end_wall)."""
    d = pathlib.Path(tempfile.mkdtemp(prefix=re.sub(r'[^A-Za-z0-9]+', '-', name) + '-', dir=td))
    marker = d / 'marker'
    inert = d / 'inert.py'
    inert.write_text(INERT)
    shim = d / 'shim.sh'
    cmd = 'python3 ' + str(inert) + ' ' + mode + ' ' + str(seconds) + ' ' + str(marker)
    shim.write_text('CUTOFF=' + cutoff_iso + '\n' + '\n'.join(setup) + '\n' + prefix + ' ' + cmd + '\n')
    env = dict(os.environ)
    if mock_seq is not None:
        mock = d / 'mockbin'
        mock.mkdir()
        (mock / 'date').write_text(MOCK_DATE)
        (mock / 'date').chmod(0o755)
        (mock / 'seq').write_text('\n'.join(str(v) for v in mock_seq) + '\n')
        env['PATH'] = str(mock) + os.pathsep + env['PATH']
    p = subprocess.Popen(['bash', str(shim)], cwd=str(REPO), env=env, start_new_session=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = p.communicate(timeout=70)
    except subprocess.TimeoutExpired:
        out, err = '', 'test timeout'
    end = time.time()
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    p.wait()
    text = marker.read_text() if marker.exists() else ''
    return {'started': 'started' in text, 'finished': 'finished' in text, 'exit': p.returncode,
            'end': end, 'err': err.strip().splitlines()[-1:] if err.strip() else []}


def fmt(r, cut=None):
    s = 'exit %s, started %s, finished %s' % (r['exit'], r['started'], r['finished'])
    if cut is not None:
        s += ', ended %+.1f s from the cut-off' % (r['end'] - cut)
    if r['exit'] not in (0, 121, 124, 137) and r['err']:
        s += ', stderr: ' + r['err'][0][:160]
    return s


def path_cases(td, label, setup, prefix):
    # Deterministic clock cases: the fetch must not start.
    r = run_shim(td, label + '-1to0', setup, prefix, FIXED_CUT_ISO, 'normal', 3, [FIXED_CUT - 1, FIXED_CUT])
    check(label + ': one_to_zero (1 s then 0 s left): fetch not started', not r['started'], fmt(r))
    r = run_shim(td, label + '-at', setup, prefix, FIXED_CUT_ISO, 'normal', 3, [FIXED_CUT])
    check(label + ': at_cutoff (0 s left): fetch not started', not r['started'], fmt(r))
    r = run_shim(td, label + '-past', setup, prefix, FIXED_CUT_ISO, 'normal', 3, [FIXED_CUT + 30])
    check(label + ': past_cutoff (30 s past, extra case): fetch not started', not r['started'], fmt(r))
    # Real-clock cases: the wall clock decides.
    cut = int(time.time()) + 4
    r = run_shim(td, label + '-insuff', setup, prefix, iso(cut), 'ignore-term', 12)
    check(label + ': insufficient_grace (4 s left, TERM ignored): over by the cut-off',
          r['end'] <= cut and not r['finished'], fmt(r, cut))
    cut = int(time.time()) + 20
    r = run_shim(td, label + '-term', setup, prefix, iso(cut), 'ignore-term', 40)
    check(label + ': term_ignoring (20 s left, TERM ignored, 40 s fetch): started and over by the cut-off',
          r['started'] and not r['finished'] and r['end'] <= cut, fmt(r, cut))
    cut = int(time.time()) + 60
    r = run_shim(td, label + '-normal', setup, prefix, iso(cut), 'normal', 1)
    check(label + ': normal_fetch (60 s left, 1 s fetch): runs to the end, exit 0',
          r['finished'] and r['exit'] == 0 and r['end'] <= cut, fmt(r, cut))


def helper_cases(td):
    def run(args, mock_seq=None, timeout=30):
        env = dict(os.environ)
        if mock_seq is not None:
            mock = pathlib.Path(tempfile.mkdtemp(prefix='h-', dir=td)) / 'mockbin'
            mock.mkdir()
            (mock / 'date').write_text(MOCK_DATE)
            (mock / 'date').chmod(0o755)
            (mock / 'seq').write_text('\n'.join(str(v) for v in mock_seq) + '\n')
            env['PATH'] = str(mock) + os.pathsep + env['PATH']
        return subprocess.run(['bash', str(HELPER)] + args, env=env, capture_output=True, text=True,
                              timeout=timeout)
    later = iso(int(time.time()) + 60)
    for bad in ([], [later, '5', '5', 'true'], [later, '0', '5', '--', 'true'], [later, '5', '0', '--', 'true'],
                [later, 'x', '5', '--', 'true'], [later, '5', '-1', '--', 'true'],
                ['not a date', '5', '5', '--', 'true']):
        r = run(bad)
        check('helper: bad arguments %r refused with exit 2' % (bad[:4],), r.returncode == 2, 'exit %d' % r.returncode)
    r = run([later, '5', '5', '--', 'sh', '-c', 'exit 7'])
    check('helper: the command\'s own exit status is passed through', r.returncode == 7, 'exit %d' % r.returncode)
    # Exactly grace + margin + 1 s left: budget 1 s, the smallest that runs; a 3 s command is stopped (124).
    r = run([FIXED_CUT_ISO, '5', '5', '--', 'sleep', '3'], [FIXED_CUT - 11])
    check('helper: grace + margin + 1 s left runs under a 1 s budget (exit 124)', r.returncode == 124,
          'exit %d, %s' % (r.returncode, r.stderr.strip().splitlines()[:1]))
    r = run([FIXED_CUT_ISO, '5', '5', '--', 'true'], [FIXED_CUT - 10])
    check('helper: exactly grace + margin left is refused (exit 121, budget 0 never passed to timeout)',
          r.returncode == 121, 'exit %d' % r.returncode)
    # The helper reads the clock once.
    mockdir = pathlib.Path(tempfile.mkdtemp(prefix='once-', dir=td)) / 'mockbin'
    mockdir.mkdir()
    (mockdir / 'date').write_text(MOCK_DATE)
    (mockdir / 'date').chmod(0o755)
    (mockdir / 'seq').write_text(str(FIXED_CUT - 100) + '\n')
    env = dict(os.environ)
    env['PATH'] = str(mockdir) + os.pathsep + env['PATH']
    subprocess.run(['bash', str(HELPER), FIXED_CUT_ISO, '5', '5', '--', 'true'], env=env, capture_output=True, timeout=30)
    reads = int((mockdir / 'n').read_text()) if (mockdir / 'n').exists() else 0
    check('helper: reads the clock exactly once', reads == 1, '%d reads' % reads)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runbook', default=str(HERE / 'RUNBOOK.md'))
    a = ap.parse_args()
    text = pathlib.Path(a.runbook).read_text()
    setup, prefix, proxy_prefix = extract(text)
    print('runbook: %s' % ('this package' if a.runbook == str(HERE / 'RUNBOOK.md') else 'given file'))
    print('fetch command prefix (tinfoil path): ' + prefix)
    print('fetch command prefix (proxy path):   ' + proxy_prefix)
    check('static: the tinfoil fetch goes through fetch_bounded.sh',
          'fetch_bounded.sh' in '\n'.join(setup + [prefix]) and 'timeout' not in prefix)
    check('static: the proxy fetch goes through fetch_bounded.sh',
          'fetch_bounded.sh' in '\n'.join(setup) and 'timeout' not in proxy_prefix and proxy_prefix != '')
    with tempfile.TemporaryDirectory(prefix='fp-fetch-bounded-') as td:
        path_cases(td, 'tinfoil path', setup, prefix)
        if proxy_prefix:
            path_cases(td, 'proxy path', setup, proxy_prefix)
        else:
            check('proxy path: present in the runbook', False)
        if a.runbook == str(HERE / 'RUNBOOK.md'):
            helper_cases(td)
    print('%d of %d checks passed' % (sum(results), len(results)))
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
