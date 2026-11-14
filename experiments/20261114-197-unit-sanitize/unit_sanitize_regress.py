#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Regression cases for `prover/tests/unit.sh --sanitize` (PREREG amendment 2 of
experiments/20261114-197-unit-sanitize): a sanitizer's report never ends as a pass, whatever the
caller's ASAN_OPTIONS, UBSAN_OPTIONS or LSAN_OPTIONS; the compiler probe removes only what it made;
without --sanitize the script behaves as main's.

usage: python3 -B unit_sanitize_regress.py REPO PRIVATE RECEIPT.json [--dry] [--debug-throwaway=DIR]

REPO is the checkout's top. PRIVATE is a folder that does not exist yet, below a directory that only
this account can change (the script makes it with mode 700). RECEIPT.json must not exist. Exit 0
only if each of the 58 cases has its required outcome; 1 otherwise; 2 for a usage error.
--dry prints the cases and builds, runs and writes nothing.
--debug-throwaway=DIR replaces every committed control and test source by the throwaway programs
tw_shift.cpp, tw_uaf.cpp, tw_selfrestart.cpp and tw_clean.cpp in DIR, for trying the script itself
before a registered run; the receipt then says so and may not lie inside REPO.
It places main's unit.sh at prover/tests/unit_main198.sh while group E runs and removes it again.
Pin it to your own cores with taskset. No GPU, no model, no proof.
"""
import datetime, hashlib, json, os, pathlib, resource, shutil, subprocess, sys

words = [a for a in sys.argv[1:] if not a.startswith('--')]
flags = [a for a in sys.argv[1:] if a.startswith('--')]
if len(words) != 3:
    print(__doc__)
    sys.exit(2)
C = pathlib.Path(words[0]).resolve()
B = pathlib.Path(words[1]).resolve()
RECEIPT = pathlib.Path(words[2]).resolve()
DRY = '--dry' in flags
THROW = next((pathlib.Path(f.split('=', 1)[1]).resolve() for f in flags if f.startswith('--debug-throwaway=')), None)
MAIN = 'cdde96296e658fe803711dbb1b4699a225cc544a'  # main's unit.sh, byte-identical to the base commit's
X = C / 'experiments/20261114-197-unit-sanitize'
SAN_VARS = ('ASAN_OPTIONS', 'UBSAN_OPTIONS', 'LSAN_OPTIONS')
RUNNERS_BOUNDS = 'hard_rss_limit_mb=2048:max_allocation_size_mb=2048'  # ubsan197_run.py, ubsan197_run2.py
if THROW:
    SRC = {'SO': THROW / 'tw_shift.cpp', 'HR': THROW / 'tw_uaf.cpp', 'S0': THROW / 'tw_selfrestart.cpp'}
    SIGN = {'SO': 'runtime error: shift exponent', 'HR': 'ERROR: AddressSanitizer: heap-use-after-free', 'S0': 'runtime error: shift exponent'}
    USAGE_SRC, PASS_SRC, PASS_ARG = str(THROW / 'tw_clean.cpp'), str(THROW / 'tw_clean.cpp'), 'x'
    if C in RECEIPT.parents:
        print('unit_sanitize_regress.py: a --debug-throwaway receipt may not lie inside the checkout')
        sys.exit(2)
else:
    SRC = {'SO': X / 'controls/control_signed_overflow.cpp', 'HR': X / 'controls/control_heap_read_v2.cpp',
           'S0': X / 'controls/control_report_status0.cpp'}
    SIGN = {'SO': 'runtime error: signed integer overflow', 'HR': 'ERROR: AddressSanitizer: heap-buffer-overflow',
            'S0': 'runtime error: signed integer overflow'}
    USAGE_SRC, PASS_SRC = 'tests/parameter_file_tables_test.cpp', 'tests/parameter_file_one_bits_test.cpp'
    PASS_ARG = 'tests/configurations/pinned_no_proof_of_work/policy.txt'

A_SETTINGS = [('no sanitizer variable', {}), ('ASAN_OPTIONS = the runners\' memory bounds', {'ASAN_OPTIONS': RUNNERS_BOUNDS}),
              ('ASAN_OPTIONS=max_allocation_size_mb=2048', {'ASAN_OPTIONS': 'max_allocation_size_mb=2048'}),
              ('ASAN_OPTIONS set and empty', {'ASAN_OPTIONS': ''})]
E_ASAN, E_UBSAN, SUPP, OPTS = str(B / 'elsewhere-asan'), str(B / 'elsewhere-ubsan'), str(B / 'supp.txt'), str(B / 'opts.txt')
B_SETTINGS = [('UBSAN_OPTIONS', 'exitcode=0'), ('ASAN_OPTIONS', 'exitcode=0'), ('LSAN_OPTIONS', 'exitcode=0'),
              ('ASAN_OPTIONS', 'log_path=' + E_ASAN), ('UBSAN_OPTIONS', 'log_path=' + E_UBSAN),
              ('ASAN_OPTIONS', 'halt_on_error=0'), ('UBSAN_OPTIONS', 'halt_on_error=0'),
              ('UBSAN_OPTIONS', 'suppressions=' + SUPP), ('ASAN_OPTIONS', 'suppressions=' + SUPP),
              ('ASAN_OPTIONS', 'hard_rss_limit_mb=2048:exitcode=0'), ('ASAN_OPTIONS', 'hard_rss_limit_mb=2048 exitcode=0'),
              ('ASAN_OPTIONS', 'hard_rss_limit_mb=2048,exitcode=0'), ('ASAN_OPTIONS', 'hard_rss_limit_mb=2048\nexitcode=0'),
              ('ASAN_OPTIONS', 'include=' + OPTS), ('UBSAN_OPTIONS', 'hard_rss_limit_mb=2048'), ('ASAN_OPTIONS', 'abort_on_error=1')]
D1_SENTINELS = ['sanitize_probe', 'sanitize_probe.XXXXXX', 'probe', 'sanitize_settings.cpp', SRC['SO'].stem, SRC['SO'].stem + '.log',
                SRC['SO'].stem + '.build.log']
D3_SENTINELS = ['sanitize_probe', 'sanitize_probe.XXXXXX', 'probe']
E_NAMES = ['no argument', 'a bad action', 'a missing source', 'run with nothing built', '/ as output directory', 'a path ending in ..',
           '--field 3', 'a bad explain-sigill name', 'a parent that others can write', 'an output folder that its group can write',
           'an output folder that is a symbolic link', 'both on the passing test with its argument', 'both on the signed-overflow control']
assert len(B_SETTINGS) == 16 and len(E_NAMES) == 13
if DRY:
    print('DRY: nothing built, run or written')
    print('A (8):', [(w, s[0]) for w in ('SO', 'HR') for s in A_SETTINGS])
    print('B (33):', [(w, k + '=' + v) for w in ('SO', 'HR') for k, v in B_SETTINGS] + [('SO both', 'UBSAN_OPTIONS=exitcode=0')])
    print('C (1 + 1 for information): the status-0 report control, sanitized; and built without --sanitize')
    print('D (3): failing compiler build, failing compiler both, working compiler build; sentinels', D1_SENTINELS, D3_SENTINELS)
    print('E (13):', E_NAMES)
    print('sources', {k: str(v) for k, v in SRC.items()}, 'exist', all(v.exists() for v in SRC.values()))
    print('PRIVATE free', not B.exists(), 'RECEIPT free', not RECEIPT.exists())
    sys.exit(0)
if RECEIPT.exists():
    print('unit_sanitize_regress.py: the receipt exists already; it is not overwritten')
    sys.exit(2)
B.mkdir(mode=0o700)
US = ['bash', 'prover/tests/unit.sh']


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def clean(s):
    s = s.replace(str(B), '<PRIVATE>').replace(str(C), '<REPO>')
    return s.replace(str(THROW), '<THROWAWAY>') if THROW else s


def lim_release():
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (115, 120))


def lim_sanitized_run():  # the address sanitizer cannot run under an address-space cap
    resource.setrlimit(resource.RLIMIT_CPU, (115, 120))


def call(cmd, env_set=None, sanitized_run=False, path_first=None):
    env = {k: v for k, v in os.environ.items() if k not in SAN_VARS}
    env.update(env_set or {})
    if path_first:
        env['PATH'] = str(path_first) + ':' + env['PATH']
    p = subprocess.run([str(x) for x in cmd], cwd=C, text=True, capture_output=True, env=env,
                       preexec_fn=lim_sanitized_run if sanitized_run else lim_release, timeout=150)
    return {'command': clean(' '.join(str(x) for x in cmd)), 'env_set': {k: clean(v) for k, v in (env_set or {}).items()},
            'exit': p.returncode, 'stdout': clean(p.stdout), 'stderr': clean(p.stderr)}


def passes(r):
    return any(l.endswith(': passes') for l in r['stdout'].splitlines())


def listing(d):
    return {p.name: (sha(p) if p.is_file() and not p.is_symlink() else 'not a plain file') for p in sorted(d.iterdir())} if d.is_dir() else None


def elsewhere():
    return sorted(p.name for p in B.glob('elsewhere-*'))


cases, information = [], []


def record(group, name, r, required, ok, **more):
    r.update(group=group, case=name, required=required, ok=bool(ok), **more)
    cases.append(r)
    print('%s %-3s %s | exit %d' % ('ok  ' if ok else 'NOT ', group, name.replace('\n', '\\n'), r['exit']), flush=True)


receipt = {'unit_sh_sha256': sha(C / 'prover/tests/unit.sh'),
           'head': subprocess.run(['git', '-C', str(C), 'rev-parse', 'HEAD'], text=True, capture_output=True).stdout.strip(),
           'utc_start': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'debug_throwaway': bool(THROW),
           'gxx': subprocess.run(['g++', '--version'], text=True, capture_output=True).stdout.splitlines()[0], 'builds': {}}
pathlib.Path(SUPP).write_text('signed-integer-overflow:*\ninterceptor_via_fun:*\n')
pathlib.Path(OPTS).write_text('exitcode=0\n')
controls = B / 'controls'
for k in ('SO', 'HR', 'S0'):
    receipt['builds'][k] = call([*US, '--sanitize', 'build', SRC[k], controls])
    receipt['builds'][k]['source'] = clean(str(SRC[k]))
san = controls / 'sanitized'

# ---- A: accepted settings. A report fails the run; the runners' memory bounds are accepted.
for which in ('SO', 'HR'):
    for label, env in A_SETTINGS:
        r = call([*US, '--sanitize', 'run', SRC[which], controls], env_set=env, sanitized_run=True)
        log = san / (SRC[which].stem + '.log')
        text = log.read_text(errors='replace') if log.exists() else ''
        record('A', which + ': ' + label, r, 'exit 1, a line with "status 97", the control\'s text in the log, no passes line',
               r['exit'] == 1 and 'status 97' in r['stdout'] and SIGN[which] in text and not passes(r),
               log=clean(text), report_in_log=SIGN[which] in text, printed_passes=passes(r))

# ---- B: hostile settings. Refused with exit 2 before the program starts.
REQ_B = 'exit 2, the standard error stream begins "unit.sh: --sanitize: <variable>: ", the log (or the folder) unchanged, no passes line, no elsewhere-* file'
for which in ('SO', 'HR'):
    for var, value in B_SETTINGS:
        log = san / (SRC[which].stem + '.log')
        before = log.read_bytes()
        r = call([*US, '--sanitize', 'run', SRC[which], controls], env_set={var: value}, sanitized_run=True)
        same = log.read_bytes() == before
        record('B', '%s: %s=%s' % (which, var, clean(value)), r, REQ_B,
               r['exit'] == 2 and r['stderr'].startswith('unit.sh: --sanitize: ' + var + ': ') and same and not passes(r) and not elsewhere(),
               log_unchanged=same, printed_passes=passes(r), elsewhere_files=elsewhere())
before = listing(san)
r = call([*US, '--sanitize', 'both', SRC['SO'], controls], env_set={'UBSAN_OPTIONS': 'exitcode=0'}, sanitized_run=True)
same = listing(san) == before
record('B', 'SO with both: UBSAN_OPTIONS=exitcode=0', r, REQ_B,
       r['exit'] == 2 and r['stderr'].startswith('unit.sh: --sanitize: UBSAN_OPTIONS: ') and same and not passes(r) and not elsewhere(),
       folder_unchanged=same, printed_passes=passes(r), elsewhere_files=elsewhere())

# ---- C: a report in a process that ends with status 0.
r = call([*US, '--sanitize', 'run', SRC['S0'], controls], sanitized_run=True)
log = san / (SRC['S0'].stem + '.log')
text = log.read_text(errors='replace') if log.exists() else ''
record('C', 'S0: the status-0 report control, sanitized', r, 'exit 1, no passes line, the overflow text in the log',
       r['exit'] == 1 and not passes(r) and SIGN['S0'] in text, log=clean(text), report_in_log=SIGN['S0'] in text, printed_passes=passes(r))
rel_b = call([*US, 'build', SRC['S0'], B / 'c-release'])
rel_r = call([*US, 'run', SRC['S0'], B / 'c-release'])
rel_log = B / 'c-release' / (SRC['S0'].stem + '.log')
rel_text = rel_log.read_text(errors='replace') if rel_log.exists() else ''
information.append({'case': 'S0 built and run without --sanitize (information only; expected exit 0, passes, no sanitizer text)',
                    'build': rel_b, 'run': rel_r, 'log': clean(rel_text),
                    'sanitizer_text': 'runtime error:' in rel_text or 'Sanitizer' in rel_text, 'printed_passes': passes(rel_r)})

# ---- D: the compiler probe.
wrap = B / 'wrap'
wrap.mkdir(mode=0o700)
(wrap / 'g++').write_text('#!/bin/bash\nfor a in "$@"; do case $a in -fsanitize*) exit 1 ;; esac; done\nexec ' + shutil.which('g++') + ' "$@"\n')
(wrap / 'g++').chmod(0o700)


def probe_case(name, act, sentinels, failing, required, made):
    out = B / ('probe-' + name)
    out.mkdir(mode=0o700)
    (out / 'sanitized').mkdir(mode=0o700)
    for s in sentinels:
        (out / 'sanitized' / s).write_text('sentinel ' + s + ': made by the caller before unit.sh\n')
    before = listing(out / 'sanitized')
    r = call([*US, '--sanitize', act, SRC['SO'], out], path_first=wrap if failing else None)
    after = listing(out / 'sanitized')
    kept = all(after.get(s) == before[s] for s in sentinels)
    added = sorted(set(after) - set(before))
    if failing:
        ok = r['exit'] == 77 and r['stdout'].startswith('not run: ') and kept and after == before
    else:
        ok = r['exit'] == 0 and r['stdout'].strip().endswith(': built') and kept and added == sorted(made) and set(before) <= set(after)
    record('D', name, r, required, ok, sentinels=sentinels, sentinels_kept_with_same_bytes=kept, names_added=added,
           listing_equal=after == before)


probe_case('failing-compiler-build', 'build', D1_SENTINELS, True,
           'exit 77, a line starting "not run: ", every sentinel present with the same bytes, the listing equal to the one before', [])
probe_case('failing-compiler-both', 'both', D1_SENTINELS, True,
           'exit 77, a line starting "not run: ", every sentinel present with the same bytes, the listing equal to the one before', [])
probe_case('working-compiler-build', 'build', D3_SENTINELS, False,
           'exit 0, built, the three sentinels present with the same bytes, the listing = before + program, build log, sanitize_settings.cpp',
           [SRC['SO'].stem, SRC['SO'].stem + '.build.log', 'sanitize_settings.cpp'])

# ---- E: without --sanitize, main's unit.sh and this one give the same exit status.
main_script = C / 'prover/tests/unit_main198.sh'
main_bytes = subprocess.run(['git', '-C', str(C), 'show', MAIN + ':prover/tests/unit.sh'], capture_output=True, check=True).stdout
receipt['main_unit_sh'] = {'commit': MAIN, 'sha256': hashlib.sha256(main_bytes).hexdigest()}
main_script.write_bytes(main_bytes)
try:
    def e_args(arm, i):
        d = B / ('e-%s-%02d' % (arm, i))
        if i == 9:
            (B / ('openw-' + arm)).mkdir(mode=0o700)
            (B / ('openw-' + arm)).chmod(0o777)
            d = B / ('openw-' + arm) / 'x'
        if i == 10:
            d.mkdir(mode=0o700)
            d.chmod(0o770)
        if i == 11:
            (B / ('target-' + arm)).mkdir(mode=0o700)
            os.symlink(B / ('target-' + arm), d)
        return d, {1: [], 2: ['x', USAGE_SRC, d], 3: ['build', 'tests/nope.cpp', d], 4: ['run', USAGE_SRC, d], 5: ['build', USAGE_SRC, '/'],
                   6: ['build', USAGE_SRC, str(B) + '/..'], 7: ['--field', '3', 'build', USAGE_SRC, d], 8: ['explain-sigill', 'a/b'],
                   9: ['build', USAGE_SRC, d], 10: ['build', USAGE_SRC, d], 11: ['build', USAGE_SRC, d],
                   12: ['both', PASS_SRC, d, PASS_ARG], 13: ['both', SRC['SO'], d]}[i]

    for i, name in enumerate(E_NAMES, 1):
        row = {}
        for arm, script in (('main', main_script), ('fixed', C / 'prover/tests/unit.sh')):
            d, a = e_args(arm, i)
            row[arm] = call(['bash', script, *a])
            for k in ('stdout', 'stderr', 'command'):
                row[arm][k] = row[arm][k].replace(clean(str(d)), '<OUT>').replace('unit_main198.sh', 'unit.sh').replace('-' + arm, '-<ARM>')
        r = {'command': row['fixed']['command'], 'env_set': {}, 'exit': row['fixed']['exit'], 'stdout': row['fixed']['stdout'],
             'stderr': row['fixed']['stderr'], 'main': row['main']}
        record('E', name, r, 'the same exit status from main\'s unit.sh and from this one', row['main']['exit'] == row['fixed']['exit'],
               main_exit=row['main']['exit'], stdout_equal=row['main']['stdout'] == row['fixed']['stdout'],
               stderr_equal=row['main']['stderr'] == row['fixed']['stderr'])
finally:
    main_script.unlink()

by_group = {g: {'cases': sum(c['group'] == g for c in cases), 'as_required': sum(c['group'] == g and c['ok'] for c in cases)} for g in 'ABCDE'}
receipt.update(cases=cases, information=information, utc_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               summary={'required_cases': len(cases), 'as_required': sum(c['ok'] for c in cases), 'by_group': by_group,
                        'not_as_required': [c['group'] + ' ' + c['case'] for c in cases if not c['ok']],
                        'e_stdout_equal': sum(c.get('stdout_equal', False) for c in cases if c['group'] == 'E'),
                        'e_stderr_equal': sum(c.get('stderr_equal', False) for c in cases if c['group'] == 'E'),
                        'elsewhere_files_at_end': elsewhere(),
                        'pass': len(cases) == 58 and all(c['ok'] for c in cases)})
RECEIPT.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt['summary'], indent=1))
sys.exit(0 if receipt['summary']['pass'] else 1)
