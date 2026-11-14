#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Run 3 runner (the confirmation run with the fixed harness) for
experiments/20261114-197-unit-sanitize (issue #197, part of #182), under PREREG amendment 2. A copy
of ubsan197_run2.py (run 2, kept unchanged) with these changes only:
- outputs go to runs-3/ and runs-ubsan-20261114-3/;
- the default-build identity compares against main's unit.sh (commit MAIN below; byte-identical to
  the base commit's, which the receipt records) instead of the base commit's;
- after the harness controls it runs the 58 regression cases of amendment 2
  (unit_sanitize_regress.py, receipt runs-3/regression-cases.json); if any case does not have its
  required outcome, the harness change is not established and the UBSan arms are not run;
- it stops at once on a positive control that fails or shows sanitizer text;
- for each reader call it also compares the exit status with the release receipt's for the same
  case and arm, and counts a call whose status differs or is not 0, 1 or 2 as a failure, whatever
  category was printed;
- budget 20 minutes from its own slot grant, hard stop 2026-11-14T06:40:00Z, cores 0-1; the
  caller's ASAN_OPTIONS, UBSAN_OPTIONS and LSAN_OPTIONS are removed from every child's environment
  before the runner's own ASAN_OPTIONS memory bounds are set.

usage: python3 -B ubsan197_run3.py REPO PRIVATE_BUILD [--dry]

REPO is the checkout's top; PRIVATE_BUILD a directory made with `mktemp -d` (only this account can
change it). --dry prints the plan and writes nothing. Without --dry it writes two new directories,
refusing to overwrite either: experiments/20261114-197-unit-sanitize/runs-3/ (harness controls,
regression cases, default-build identity, fixture identity, positive controls) and
experiments/20261113-182-reader-parity/runs-ubsan-20261114-3/ (the #182 UBSan arms). It makes no
proof, builds no .cu, uses no GPU and edits no committed file. See PREREG.md for the registration.
"""
import datetime, hashlib, json, os, pathlib, platform, re, resource, shutil, statistics, struct, subprocess, sys, time

C = pathlib.Path(sys.argv[1]).resolve()
B = pathlib.Path(sys.argv[2]).resolve()
DRY = '--dry' in sys.argv[3:]
X = C / 'experiments/20261114-197-unit-sanitize'
E = C / 'experiments/20261113-182-reader-parity'
R1 = X / 'runs-3'
R2 = E / 'runs-ubsan-20261114-3'
SUP = E / 'runs/supplementary-matrix'
BASE = 'bf447d2725acbb185f21cd2397edde46c38f095c'  # this experiment's base commit
MAIN = 'cdde96296e658fe803711dbb1b4699a225cc544a'  # main when amendment 2 was registered
READER_BASE = '59bff9a4608e0cc720d58d7c30823a8838fa43e4'  # #182's baseline header
HARD_STOP = datetime.datetime.fromisoformat('2026-11-14T06:40:00+00:00').timestamp()
BUDGET = 1200  # seconds from the slot grant (this script runs inside fp-heavy.sh)
CORES = '0,1'
CORE_SET = {0, 1}
SAN_VARS = ('ASAN_OPTIONS', 'UBSAN_OPTIONS', 'LSAN_OPTIONS')
TESTS = ['parameter_file_tables_test', 'parameter_file_one_bits_test', 'parameter_file_one_place_test']
POLICY_ARG = 'tests/configurations/pinned_no_proof_of_work/policy.txt'
RUN_ASAN = 'hard_rss_limit_mb=2048:max_allocation_size_mb=2048'
SAN_SIGNS = ('runtime error:', 'AddressSanitizer', 'LeakSanitizer')

start = time.time()
stop = min(start + BUDGET, HARD_STOP)


def utc(t=None):
    return datetime.datetime.fromtimestamp(t if t else time.time(), datetime.timezone.utc).isoformat()


def clean(s):
    return s.replace(str(B), '<PRIVATE_BUILD>').replace(str(C), '<REPO>')


def cap_as():
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (115, 120))
    os.sched_setaffinity(0, CORE_SET)


def cap_cpu_only():  # sanitized runs: the address sanitizer cannot run under an address-space cap
    resource.setrlimit(resource.RLIMIT_CPU, (115, 120))
    os.sched_setaffinity(0, CORE_SET)


def run(cmd, sanitized_run=False, env_extra=None, xtrace=False):
    if time.time() >= stop:
        raise SystemExit('KILLED: registered run budget or hard stop reached')
    env = {k: v for k, v in os.environ.items() if k not in SAN_VARS}
    if sanitized_run:
        env['ASAN_OPTIONS'] = RUN_ASAN
    if env_extra:
        env.update(env_extra)
    cmd = [str(x) for x in cmd]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=C, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                       preexec_fn=cap_cpu_only if sanitized_run else cap_as, timeout=min(150, max(1, stop - time.time())))
    r = {'command': clean(' '.join(cmd)), 'exit': p.returncode, 'stdout': clean(p.stdout), 'stderr': clean(p.stderr),
         'seconds': round(time.time() - t0, 3), 'limits': 'RLIMIT_CPU 115/120, cores 0-1' + (
             ', ASAN_OPTIONS=' + RUN_ASAN + ', no address-space cap' if sanitized_run else ', RLIMIT_AS 4 GiB')}
    if env_extra:
        r['env_extra'] = {k: ('<PRIVATE_BUILD>/wrap:<caller PATH>' if k == 'PATH' else clean(v)) for k, v in env_extra.items()}
    return r


def save(p, x):
    p.write_text(json.dumps(x, indent=2) + '\n')


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def log_has(path, sign):
    path = pathlib.Path(path)
    return path.exists() and sign in path.read_text(errors='replace')


def sanitizer_seen(text):
    return any(s in text for s in SAN_SIGNS)


plan = [
    '1 fixture identity: regenerate with reader182b_supplement.py fixture code into PRIVATE_BUILD/regen, compare hashes',
    '2 default-build identity: main unit.sh (git show %s) as prover/tests/unit_base197.sh vs patched, bash -x, 3 tests' % MAIN[:12],
    '2b python3 -B tests/folder_look_copies_test.py',
    '3 harness controls: --sanitize build/run of the two controls; release build/run (info); .cu refusal; g++ wrapper 77',
    '3b regression cases: unit_sanitize_regress.py REPO PRIVATE_BUILD/regress runs-3/regression-cases.json (58 required cases)',
    '4 baseline sources from %s header; --sanitize build of 3 tests per arm' % READER_BASE[:12],
    '5 positive controls: --sanitize run one_bits/one_place per arm with ' + POLICY_ARG,
    '6 UBSan arms: 5 repetitions x 33 committed supplementary fixtures x 2 arms, alternating order',
]
if DRY:
    print('DRY: no file written, nothing built or run')
    print('REPO', C, 'PRIVATE_BUILD', B, 'outputs', R1, R2)
    for line in plan:
        print(' ', line)
    for p in [SUP / 'fixture-hashes.json', SUP / 'expectations.json', E / 'reader182b_supplement.py', C / 'prover/tests/unit.sh',
              X / 'unit_sanitize_regress.py', X / 'controls/control_report_status0.cpp']:
        print('exists' if p.exists() else 'MISSING', p)
    print('outputs free:', not R1.exists(), not R2.exists())
    sys.exit(0)

R1.mkdir()
R2.mkdir()
progress = []


def note(s):
    line = utc() + ' ' + s
    progress.append(line)
    print(line, flush=True)
    (R1 / 'progress.txt').write_text('\n'.join(progress) + '\n')


note('slot granted, runner start; budget %d s, stop %s' % (BUDGET, utc(stop)))
env_capture = {
    'start_utc': utc(start), 'stop_utc': utc(stop), 'head': subprocess.run(['git', '-C', str(C), 'rev-parse', 'HEAD'], text=True, capture_output=True).stdout.strip(),
    'gxx': subprocess.run(['g++', '--version'], text=True, capture_output=True).stdout.splitlines()[0],
    'python': platform.python_version(), 'kernel': platform.release(), 'machine': platform.machine(),
    'cpu': next((l.split(':', 1)[1].strip() for l in open('/proc/cpuinfo') if l.startswith('model name')), ''),
    'cores_used': CORES, 'nproc': os.cpu_count(), 'unit_sh_sha256': sha(C / 'prover/tests/unit.sh'),
    'parameter_file_h_sha256': sha(C / 'prover/common/parameter_file.h'),
    'callers_sanitizer_variables_removed': sorted(k for k in SAN_VARS if k in os.environ),
    'unit_sanitize_regress_py_sha256': sha(X / 'unit_sanitize_regress.py'),
}
save(R1 / 'env-capture.json', env_capture)

# ---- 1. Fixture identity: reader182b_supplement.py's fixture code, copied unchanged, minus the
# two verifier-made files (dense-base/arrays.txt and the dense layout.txt files).
def put(t, k, v):
    t, n = re.subn(r'^' + k + r' .*$', k + ' ' + str(v), t, flags=re.M)
    assert n == 1, (k, n)
    return t


def nodigest(t):
    return re.sub(r'^t(?:silu|sig|rope|exp)\d+ .*\n', '', t, flags=re.M)


def malformed(t, kind):
    lines = t.splitlines(True)
    ids = [i for i, l in enumerate(lines) if re.match(r't(?:silu|sig|rope|exp)\d+ ', l)]
    assert len(ids) == 32
    if kind == 'partial': del lines[ids[-1]]
    if kind == 'reordered': lines[ids[4]], lines[ids[5]] = lines[ids[5]], lines[ids[4]]
    if kind == 'duplicate': lines[ids[5]] = lines[ids[4]]
    if kind == 'invalid': lines[ids[5]] = 'tsilu5 4294967296\n'
    return ''.join(lines)


kit = C / 'prover/tests/configurations/pinned_no_proof_of_work'
old = C / 'experiments/20261113-156-dense-table-digests/runs/served/dense-files'
dense = (old / 'routed-experts.dense-with-digests.policy.txt').read_text()
expert = (kit / 'policy.txt').read_text()
cases = {}


def add(name, t, b, a, v):
    cases[name] = {'bytes': t, 'before': b, 'after': a, 'verifier': v}


ok = 'ok'
add('dense-valid', dense, 'policy-tables', ok, 'met')
add('dense-no-digests', nodigest(dense), ok, ok, 'not-met:table-digests')
for kind in ['partial', 'reordered', 'duplicate', 'invalid']:
    tag = 'parse:policy-line-form' if kind == 'invalid' else 'parse:policy-tables'
    add('dense-' + kind, malformed(dense, kind), tag, tag, 'policy-tables')
    add('experts-' + kind, malformed(expert, kind), tag, tag, 'policy-tables')
for i in range(8): add('dense-sigmoid-' + str(i), put(dense, 'tsig' + str(i), 1), 'policy-tables', 'policy-tables', 'policy-tables')
for prefix, which in [('tsilu', 'silu'), ('trope', 'rope'), ('texp', 'exp')]:
    val = int(re.search('^' + prefix + '7 (\\d+)$', dense, re.M).group(1)) ^ 1
    add('dense-changed-' + which, put(dense, prefix + '7', val), 'policy-tables', ok, 'table-digest-' + which)
for k in ['rcl', 'gcl']:
    t = dense.replace('xl 5\n', k + ' 1\nxl 5\n')
    add('dense-' + k, t, 'policy-' + k, 'policy-' + k, 'policy-' + k)
    t = put(expert, k, 0)
    add('experts-' + k + '-zero', t, 'policy-' + k, 'policy-' + k, 'policy-' + k)
for k, v, tag in [('hr', 1, 'header-absent-class'), ('wb_r', 13, 'header-absent-kind')]:
    add('dense-' + tag, put(dense, k, v), 'policy-tables' if k == 'wb_r' else tag, tag, tag)
add('experts-valid', expert, ok, ok, 'met')
add('experts-no-digests', nodigest(expert), ok, ok, 'not-met:table-digests')
for prefix, which in [('tsilu', 'silu'), ('tsig', 'sigmoid'), ('trope', 'rope'), ('texp', 'exp')]:
    val = int(re.search('^' + prefix + '7 (\\d+)$', expert, re.M).group(1)) ^ 1
    add('experts-changed-' + which, put(expert, prefix + '7', val), ok, ok, 'table-digest-' + which)
F = B / 'regen/fixtures'
F.mkdir(parents=True)
D = F / 'dense-base'
D.mkdir()
(D / 'policy.txt').write_text(nodigest(dense))
L = int(re.search(r'^L (\d+)$', dense, re.M).group(1))
(D / 'KL.bin').write_bytes((kit / 'KL.bin').read_bytes()[:4 * 13 * L])
lt = int(re.search(r'^lt (\d+)$', dense, re.M).group(1))
n = 1 << lt
(F / 'request.bin').write_bytes(struct.pack('<' + 'I' * (n + 2), *([7] * n + [n - 1, n])))
(F / 'reply.bin').write_bytes(struct.pack('<I', 5))
for name, c in sorted(cases.items()):
    d = F / name
    d.mkdir()
    (d / 'policy.txt').write_text(c.pop('bytes'))
    files = ['KL.bin'] if name.startswith('dense-') else ['KL.bin', 'layout.txt']  # dense layout.txt: verifier-made
    src = D if name.startswith('dense-') else kit
    for f in files: (d / f).write_bytes((src / f).read_bytes())
committed = json.loads((SUP / 'fixture-hashes.json').read_text())
regen = {str(p.relative_to(F.parent)): sha(p) for p in F.rglob('*') if p.is_file()}
compared = {k: {'regenerated': v, 'committed': committed.get(k), 'equal': committed.get(k) == v} for k, v in sorted(regen.items())}
not_regen = sorted(set(committed) - set(regen))
expect_committed = json.loads((SUP / 'expectations.json').read_text())
fixture_identity = {'compared': len(compared), 'equal': sum(v['equal'] for v in compared.values()),
                    'not_regenerated_committed_files': not_regen,
                    'not_regenerated_reason': 'made by cp_verify -plan arrays and pack_layout.py; the reader does not read them',
                    'expectations_equal_committed': cases == expect_committed, 'files': compared}
save(R1 / 'fixture-identity.json', fixture_identity)
note('fixture identity: %d compared, %d equal, %d committed not regenerated, expectations equal: %s' % (
    fixture_identity['compared'], fixture_identity['equal'], len(not_regen), fixture_identity['expectations_equal_committed']))
fixtures_ok = fixture_identity['equal'] == fixture_identity['compared'] and fixture_identity['expectations_equal_committed']

# ---- 2. Default-build identity.
base_script = C / 'prover/tests/unit_base197.sh'
base_text = subprocess.run(['git', '-C', str(C), 'show', MAIN + ':prover/tests/unit.sh'], capture_output=True, check=True).stdout
base_commit_text = subprocess.run(['git', '-C', str(C), 'show', BASE + ':prover/tests/unit.sh'], capture_output=True, check=True).stdout
base_script.write_bytes(base_text)
identity = {'base_unit_sh_sha256': hashlib.sha256(base_text).hexdigest(), 'patched_unit_sh_sha256': sha(C / 'prover/tests/unit.sh'),
            'base_is': 'main ' + MAIN, 'main_unit_sh_equals_base_commit_unit_sh': base_text == base_commit_text,
            'base_commit': BASE, 'tests': {}}


def gxx_lines(trace, out):
    lines = [l for l in trace.splitlines() if re.match(r'^\++ g\+\+ ', l)]
    # unit.sh resolves the output directory without links (open_above), so match by its last part too
    return [re.sub(r'\S*/' + re.escape(out.name) + r'(?=/)', '<OUT>', l).replace(str(B), '<PRIVATE_BUILD>').replace(str(C), '<REPO>') for l in lines]


try:
    for test in TESTS:
        row = {}
        for arm, script in [('base', base_script), ('patched', C / 'prover/tests/unit.sh')]:
            out = B / ('identity-' + arm)
            r = run(['bash', '-x', script, 'build', 'tests/' + test + '.cpp', out])
            row[arm] = {'exit': r['exit'], 'stdout': r['stdout'], 'binary_sha256': sha(out / test) if (out / test).exists() else None,
                        'gxx': gxx_lines(r['stderr'], out), 'command': r['command'], 'seconds': r['seconds']}
        row['binary_identical'] = row['base']['binary_sha256'] is not None and row['base']['binary_sha256'] == row['patched']['binary_sha256']
        row['gxx_identical'] = row['base']['gxx'] == row['patched']['gxx'] and len(row['base']['gxx']) == 1
        if not row['binary_identical']:
            out = B / 'identity-base-again'
            r = run(['bash', '-x', base_script, 'build', 'tests/' + test + '.cpp', out])
            row['base_again_sha256'] = sha(out / test) if (out / test).exists() else None
            row['base_reproducible'] = row['base_again_sha256'] == row['base']['binary_sha256']
        identity['tests'][test] = row
        note('identity %s: binaries identical %s, g++ lines identical %s' % (test, row['binary_identical'], row['gxx_identical']))
finally:
    base_script.unlink()
r = run([sys.executable, '-B', 'tests/folder_look_copies_test.py'])
identity['folder_look_copies_test'] = {'exit': r['exit'], 'tail': r['stdout'].splitlines()[-3:] + r['stderr'].splitlines()[-3:]}
identity['pass'] = all(t['binary_identical'] or (t['gxx_identical'] and not t.get('base_reproducible', True)) for t in identity['tests'].values()) and r['exit'] == 0
save(R1 / 'default-build-identity.json', identity)
note('default-build identity pass: %s (folder_look_copies_test exit %d)' % (identity['pass'], r['exit']))

# ---- 3. Harness controls.
controls = {}
ctl_dir = 'experiments/20261114-197-unit-sanitize/controls/'
for name, sign in [('control_signed_overflow', 'runtime error: signed integer overflow'), ('control_heap_read_v2', 'ERROR: AddressSanitizer: heap-buffer-overflow')]:
    out = B / 'controls'
    src = C / (ctl_dir + name + '.cpp')
    b = run(['bash', 'prover/tests/unit.sh', '--sanitize', 'build', src, out])
    r = run(['bash', 'prover/tests/unit.sh', '--sanitize', 'run', src, out], sanitized_run=True)
    log = out / 'sanitized' / (name + '.log')
    rel_b = run(['bash', 'prover/tests/unit.sh', 'build', src, B / 'controls-release'])
    rel_r = run(['bash', 'prover/tests/unit.sh', 'run', src, B / 'controls-release'])
    rel_log = B / 'controls-release' / (name + '.log')
    controls[name] = {'sign': sign, 'sanitized_build': b, 'sanitized_run': r, 'sanitized_log': clean(log.read_text(errors='replace')) if log.exists() else None,
                      'reported': r['exit'] == 1 and log_has(log, sign),
                      'release_info': {'build': rel_b, 'run': rel_r, 'log': clean(rel_log.read_text(errors='replace')) if rel_log.exists() else None,
                                       'sanitizer_text': log_has(rel_log, 'Sanitizer') or log_has(rel_log, 'runtime error:')}}
    note('%s: sanitized build exit %d, run exit %d, reported %s; release run exit %d (info)' % (name, b['exit'], r['exit'], controls[name]['reported'], rel_r['exit']))
r = run(['bash', 'prover/tests/unit.sh', '--sanitize', 'build', 'tests/base_kernels_test.cu', B / 'controls-cu'])
controls['cu_refused'] = {'run': r, 'pass': r['exit'] == 2 and not (B / 'controls-cu').exists()}
note('.cu with --sanitize: exit %d, output directory made: %s' % (r['exit'], (B / 'controls-cu').exists()))
wrap = B / 'wrap'
wrap.mkdir(mode=0o700)
real_gxx = shutil.which('g++')
(wrap / 'g++').write_text('#!/bin/bash\nfor a in "$@"; do case $a in -fsanitize*) exit 1 ;; esac; done\nexec ' + real_gxx + ' "$@"\n')
(wrap / 'g++').chmod(0o700)
r = run(['bash', 'prover/tests/unit.sh', '--sanitize', 'build', C / (ctl_dir + 'control_signed_overflow.cpp'), B / 'controls-wrap'],
        env_extra={'PATH': str(wrap) + ':' + os.environ['PATH']})
controls['not_run_77'] = {'run': r, 'wrapper': '<PRIVATE_BUILD>/wrap/g++: exits 1 if an argument starts with -fsanitize, else runs ' + real_gxx,
                          'binary_made': (B / 'controls-wrap/sanitized/control_signed_overflow').exists(),
                          'pass': r['exit'] == 77 and r['stdout'].startswith('not run: ') and not (B / 'controls-wrap/sanitized/control_signed_overflow').exists()}
note('g++ without sanitizers: exit %d, %s' % (r['exit'], r['stdout'].strip()[:80]))
controls['pass'] = all(controls[k]['reported'] for k in ['control_signed_overflow', 'control_heap_read_v2']) and controls['cu_refused']['pass'] and controls['not_run_77']['pass']
save(R1 / 'harness-controls.json', controls)
note('harness controls pass: %s' % controls['pass'])
# ---- 3b. The regression cases of amendment 2 (their own script, their own limits per child).
if time.time() >= stop:
    raise SystemExit('KILLED: registered run budget or hard stop reached')
reg_receipt = R1 / 'regression-cases.json'
reg_cmd = [sys.executable, '-B', str(X / 'unit_sanitize_regress.py'), str(C), str(B / 'regress'), str(reg_receipt)]
reg_env = {k: v for k, v in os.environ.items() if k not in SAN_VARS}
t0 = time.time()
reg = subprocess.run(reg_cmd, cwd=C, text=True, capture_output=True, env=reg_env, preexec_fn=lambda: os.sched_setaffinity(0, CORE_SET),
                     timeout=max(1, stop - time.time()))
reg_summary = json.loads(reg_receipt.read_text())['summary'] if reg_receipt.exists() else None
regression = {'command': clean(' '.join(reg_cmd)), 'exit': reg.returncode, 'seconds': round(time.time() - t0, 1), 'stdout': clean(reg.stdout),
              'stderr': clean(reg.stderr), 'summary': reg_summary,
              'pass': reg.returncode == 0 and bool(reg_summary) and reg_summary['pass'] and reg_summary['required_cases'] == 58}
save(R1 / 'regression-run.json', regression)
note('regression cases: exit %d, %s of %s as required, pass %s' % (
    reg.returncode, reg_summary and reg_summary['as_required'], reg_summary and reg_summary['required_cases'], regression['pass']))
if not (controls['pass'] and identity['pass'] and regression['pass']):
    note('KILL: harness change not established (controls %s, identity %s, regression cases %s); UBSan arms not run' % (
        controls['pass'], identity['pass'], regression['pass']))
    save(R2 / 'summary.json', {'status': 'NOT RUN', 'reason': 'harness change failed its registered checks', 'controls_pass': controls['pass'],
                               'identity_pass': identity['pass'], 'regression_cases_pass': regression['pass']})
    sys.exit(1)
if not fixtures_ok:
    note('KILL: regenerated fixtures differ from the committed hashes; UBSan arms not run')
    save(R2 / 'summary.json', {'status': 'NOT RUN', 'reason': 'fixture identity failed'})
    sys.exit(1)

# ---- 4. Baseline sources and sanitized builds.
bl = B / 'baseline'
bl.mkdir()
(bl / 'parameter_file_baseline.h').write_bytes(subprocess.run(['git', '-C', str(C), 'show', READER_BASE + ':prover/common/parameter_file.h'], capture_output=True, check=True).stdout)
for test in TESTS:
    text = (C / 'prover/tests' / (test + '.cpp')).read_text()
    assert text.count('#include "common/parameter_file.h"') == 1
    (bl / (test + '.cpp')).write_text(text.replace('#include "common/parameter_file.h"', '#include "parameter_file_baseline.h"'))
c182 = json.loads((E / 'runs/continuation-build/hashes.json').read_text())
baseline_hashes = {f: {'sha256': sha(bl / f), 'equals_182': sha(bl / f) == c182.get('<PRIVATE_BUILD>/baseline/' + f)} for f in sorted(os.listdir(bl))}
builds = {'baseline_sources': baseline_hashes, 'builds': []}
for arm in ['before', 'after']:
    for test in TESTS:
        src = bl / (test + '.cpp') if arm == 'before' else 'tests/' + test + '.cpp'
        r = run(['bash', 'prover/tests/unit.sh', '--sanitize', 'build', src, B / arm])
        binp = B / arm / 'sanitized' / test
        r.update(arm=arm, test=test, binary_sha256=sha(binp) if binp.exists() else None,
                 build_log=clean((B / arm / 'sanitized' / (test + '.build.log')).read_text(errors='replace')) if (B / arm / 'sanitized' / (test + '.build.log')).exists() else None)
        builds['builds'].append(r)
        note('sanitized build %s %s: exit %d, %.1f s' % (arm, test, r['exit'], r['seconds']))
builds['settings_source'] = clean((B / 'after/sanitized/sanitize_settings.cpp').read_text())
save(R2 / 'builds.json', builds)
if any(b['exit'] != 0 for b in builds['builds']):
    note('KILL: a sanitized build failed; UBSan arms not run')
    save(R2 / 'summary.json', {'status': 'NOT RUN', 'reason': 'sanitized build failed'})
    sys.exit(1)

# ---- 5. Positive controls.
positive = []
for arm in ['before', 'after']:
    for test in TESTS[1:]:
        src = bl / (test + '.cpp') if arm == 'before' else 'tests/' + test + '.cpp'
        r = run(['bash', 'prover/tests/unit.sh', '--sanitize', 'run', src, B / arm, POLICY_ARG], sanitized_run=True)
        log = B / arm / 'sanitized' / (test + '.log')
        r.update(arm=arm, test=test, test_output=clean(log.read_text(errors='replace')) if log.exists() else '')
        r['sanitizer_text'] = sanitizer_seen(r['test_output'])
        r['pass'] = r['exit'] == 0 and r['stdout'].strip() == test + ': passes' and not r['sanitizer_text']
        positive.append(r)
        note('positive control %s %s: exit %d, pass %s' % (arm, test, r['exit'], r['pass']))
        if not r['pass']:  # stop at once: a failed positive control or sanitizer text in its log
            save(R1 / 'positive-controls.json', positive)
            save(R2 / 'positive-controls.json', positive)
            note('KILL: positive control %s %s did not pass (exit %d, sanitizer text %s); UBSan arms not run' % (arm, test, r['exit'], r['sanitizer_text']))
            save(R2 / 'summary.json', {'status': 'STOPPED: positive control %s %s did not pass' % (arm, test), 'positive_controls_run': len(positive),
                                       'reader_calls': 0})
            sys.exit(1)
save(R1 / 'positive-controls.json', positive)
save(R2 / 'positive-controls.json', positive)

# ---- 6. The UBSan arms.
def reader_tag(p):  # as in reader182b_supplement.py, on standard output
    if p['exit'] == 0: return 'ok'
    m = re.search(r'^parse: (?!ok)([^: ]+)', p['stdout'], re.M)
    if m: return 'parse:' + m.group(1)
    m = re.search(r'^admission: ([^: ]+)', p['stdout'], re.M)
    return m.group(1) if m else 'unknown'


release, release_exit = {}, {}
for name in expect_committed:
    for arm in ['before', 'after']:
        rows = [json.loads((SUP / ('%02d-%s-%s.json' % (rep, name, arm))).read_text()) for rep in range(1, 6)]
        seen = {x['observed'] for x in rows}
        assert len(seen) == 1, (name, arm, seen)
        release[(name, arm)] = seen.pop()
        seen = {x['exit'] for x in rows}
        assert len(seen) == 1, (name, arm, seen)
        release_exit[(name, arm)] = seen.pop()
mismatch_release, mismatch_expect, reports, status_failures = [], [], [], []
stopped = None
fx = SUP / 'fixtures'
for rep in range(1, 6):
    m_rel = m_exp = rep_reports = m_status = 0
    for name in sorted(expect_committed):
        for arm in (['before', 'after'] if rep % 2 else ['after', 'before']):
            p = run([B / arm / 'sanitized/parameter_file_tables_test', fx / name / 'policy.txt'], sanitized_run=True)
            p.update(repetition=rep, case=name, arm=arm, mode='ubsan+asan', release=release[(name, arm)], expected=expect_committed[name][arm])
            p['observed'] = reader_tag(p)
            p['sanitizer_report'] = p['exit'] == 97 or sanitizer_seen(p['stderr']) or sanitizer_seen(p['stdout'])
            p['matches_release'] = p['observed'] == p['release']
            p['matches_expected'] = p['observed'] == p['expected']
            # the status, judged without the printed category: equal to release's, and one of 0, 1, 2
            p['release_exit'] = release_exit[(name, arm)]
            p['status_ok'] = p['exit'] == p['release_exit'] and p['exit'] in (0, 1, 2)
            m_status += not p['status_ok']
            m_rel += not p['matches_release']
            m_exp += not p['matches_expected']
            rep_reports += p['sanitizer_report']
            save(R2 / ('%02d-%s-%s.json' % (rep, name, arm)), p)
            if p['sanitizer_report'] and stopped is None:
                stopped = 'sanitizer report at repetition %d, case %s, arm %s' % (rep, name, arm)
            if stopped: break
        if stopped: break
    mismatch_release.append(m_rel)
    mismatch_expect.append(m_exp)
    reports.append(rep_reports)
    status_failures.append(m_status)
    note('UBSan repetition %d: %d category mismatches vs release, %d vs expectations, %d sanitizer reports, %d status failures' % (
        rep, m_rel, m_exp, rep_reports, m_status))
    if stopped:
        note('KILL: ' + stopped)
        break


def stats(xs):
    return {'per_repetition': xs, 'n': len(xs), 'median': statistics.median(xs), 'population_sd': statistics.pstdev(xs), 'min': min(xs), 'max': max(xs)}


summary = {
    'status': 'STOPPED: ' + stopped if stopped else 'COMPLETE',
    'fixtures': len(expect_committed), 'repetitions_completed': len(reports), 'reader_calls': len(list(R2.glob('0*-*.json'))),
    'category_mismatches_vs_release': stats(mismatch_release), 'category_mismatches_vs_expectations': stats(mismatch_expect),
    'sanitizer_reports': stats(reports), 'status_failures': stats(status_failures),
    'status_rule': 'a call fails if its exit status differs from the release receipt\'s for the same case and arm, or is not 0, 1 or 2',
    'positive_controls': len(positive), 'positive_control_failures': sum(not p['pass'] for p in positive),
    'flags': '-O1 -g -fno-ipa-modref -D_GLIBCXX_ASSERTIONS -fno-omit-frame-pointer -fsanitize=address,undefined -fno-sanitize-recover=all -std=c++17 -pthread -DDIGEST_WORDS=8 -DBLK_FIELD=2 -msha -msse4.1 -mssse3 -I. -I../blocks',
    'run_asan_options': RUN_ASAN, 'elapsed_seconds': round(time.time() - start, 1), 'start_utc': utc(start), 'end_utc': utc(),
}
save(R2 / 'summary.json', summary)
save(R1 / 'summary.json', {'fixture_identity_equal': fixtures_ok, 'default_build_identity_pass': identity['pass'], 'harness_controls_pass': controls['pass'],
                           'regression_cases_pass': regression['pass'], 'regression_cases': reg_summary and reg_summary['required_cases'],
                           'regression_cases_as_required': reg_summary and reg_summary['as_required'],
                           'positive_controls_pass': all(p['pass'] for p in positive), 'ubsan_arms': summary['status'],
                           'ubsan_receipts': 'experiments/20261113-182-reader-parity/runs-ubsan-20261114-3/summary.json'})
note('done: ' + json.dumps({k: summary[k] for k in ['status', 'reader_calls', 'elapsed_seconds']}))
