#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Reproduction of the two review findings on PR #198 with the harness as it was at e11ec537
(PREREG amendment 2, "Reproduction of the finding at the old harness, before the code").

usage: python3 -B review_cases_oldhead.py REPO PRIVATE_BUILD

It refuses to run unless prover/tests/unit.sh has the SHA-256 it had at e11ec537, and refuses to
overwrite its output directory, experiments/20261114-197-unit-sanitize/runs-oldhead-review/. It
builds the two committed negative controls and a private copy of controls/control_report_status0.cpp
through `unit.sh --sanitize build` and runs them with a caller's sanitizer variable set; then the
compiler-probe case with a g++ wrapper that fails on -fsanitize. It runs no registered fixture and
no positive control. Pin it to your own cores with taskset.
"""
import hashlib, json, os, pathlib, resource, shutil, subprocess, sys, time, datetime

C = pathlib.Path(sys.argv[1]).resolve()
B = pathlib.Path(sys.argv[2]).resolve()
X = C / 'experiments/20261114-197-unit-sanitize'
OUT = X / 'runs-oldhead-review'
OLD_UNIT_SH = 'a228d3bdee58e2c7e00a7974473df218064960ed1b49b2063866d892a0879706'
US = ['bash', 'prover/tests/unit.sh']
SAN_VARS = ('ASAN_OPTIONS', 'UBSAN_OPTIONS', 'LSAN_OPTIONS')


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def clean(s):
    return s.replace(str(B), '<PRIVATE_BUILD>').replace(str(C), '<REPO>')


def lim_build():
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (115, 120))


def lim_run():  # the address sanitizer cannot run under an address-space cap
    resource.setrlimit(resource.RLIMIT_CPU, (115, 120))


def call(cmd, env_set=None, sanitized_run=False, path_first=None):
    env = {k: v for k, v in os.environ.items() if k not in SAN_VARS}
    env.update(env_set or {})
    if path_first:
        env['PATH'] = str(path_first) + ':' + env['PATH']
    p = subprocess.run([str(x) for x in cmd], cwd=C, text=True, capture_output=True, env=env,
                       preexec_fn=lim_run if sanitized_run else lim_build, timeout=150)
    return {'command': clean(' '.join(str(x) for x in cmd)), 'env_set': {k: clean(v) for k, v in (env_set or {}).items()},
            'exit': p.returncode, 'stdout': clean(p.stdout), 'stderr': clean(p.stderr)}


if sha(C / 'prover/tests/unit.sh') != OLD_UNIT_SH:
    raise SystemExit('prover/tests/unit.sh is not the e11ec537 file: this script reproduces the findings at the old harness only')
OUT.mkdir()
controls = B / 'controls'
ctl = X / 'controls'
copy = B / 'copy'
copy.mkdir(mode=0o700)
shutil.copyfile(ctl / 'control_report_status0.cpp', copy / 'control_report_status0.cpp')
sources = {'SO': ctl / 'control_signed_overflow.cpp', 'HR': ctl / 'control_heap_read_v2.cpp', 'S0': copy / 'control_report_status0.cpp'}
signs = {'SO': 'runtime error: signed integer overflow', 'HR': 'ERROR: AddressSanitizer: heap-buffer-overflow',
         'S0': 'runtime error: signed integer overflow'}
rows = {'unit_sh_sha256': sha(C / 'prover/tests/unit.sh'), 'head': subprocess.run(['git', '-C', str(C), 'rev-parse', 'HEAD'], text=True, capture_output=True).stdout.strip(),
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'builds': {}, 'cases': []}
for k, src in sources.items():
    rows['builds'][k] = call([*US, '--sanitize', 'build', src, controls])


def run_case(name, which, env_set, expected):
    src = sources[which]
    log = controls / 'sanitized' / (src.stem + '.log')
    r = call([*US, '--sanitize', 'run', src, controls], env_set=env_set, sanitized_run=True)
    text = log.read_text(errors='replace') if log.exists() else ''
    r.update(case=name, control=src.name, log=clean(text), report_in_log=signs[which] in text,
             printed_passes=r['stdout'].strip().endswith(': passes'), expected=expected,
             elsewhere_files=sorted(p.name for p in B.glob('elsewhere-*')))
    r['false_pass'] = r['exit'] == 0 and r['printed_passes']
    rows['cases'].append(r)
    print(name, 'exit', r['exit'], 'passes' if r['printed_passes'] else 'no-passes', 'report in log', r['report_in_log'],
          'elsewhere', r['elsewhere_files'], flush=True)


run_case('reviewer-1a UBSAN_OPTIONS=exitcode=0 on the signed-overflow control', 'SO', {'UBSAN_OPTIONS': 'exitcode=0'},
         'exit 0 and passes, with the report in the log (both reviews)')
run_case('reviewer-1b ASAN_OPTIONS=exitcode=0 on the heap-read v2 control', 'HR', {'ASAN_OPTIONS': 'exitcode=0'},
         'exit 0 and passes, with the report in the log (both reviews)')
run_case('extra LSAN_OPTIONS=exitcode=0 on the signed-overflow control', 'SO', {'LSAN_OPTIONS': 'exitcode=0'}, 'recorded whatever it gives')
run_case('extra LSAN_OPTIONS=exitcode=0 on the heap-read v2 control', 'HR', {'LSAN_OPTIONS': 'exitcode=0'}, 'recorded whatever it gives')
run_case('extra ASAN_OPTIONS=log_path elsewhere on the heap-read v2 control', 'HR', {'ASAN_OPTIONS': 'log_path=' + str(B / 'elsewhere-asan')},
         'recorded whatever it gives')
run_case('extra the status-0 report control (private copy), no caller variable', 'S0', {}, 'recorded whatever it gives')

# The compiler probe: a pre-existing own folder with a caller's file at the probe's name.
wrap = B / 'wrap'
wrap.mkdir(mode=0o700)
(wrap / 'g++').write_text('#!/bin/bash\nfor a in "$@"; do case $a in -fsanitize*) exit 1 ;; esac; done\nexec ' + shutil.which('g++') + ' "$@"\n')
(wrap / 'g++').chmod(0o700)
out = B / 'preexisting-probe'
out.mkdir(mode=0o700)
(out / 'sanitized').mkdir(mode=0o700)
sentinel = out / 'sanitized/sanitize_probe'
sentinel.write_text('sentinel: created by the caller before unit.sh\n')
before = sha(sentinel)
r = call([*US, '--sanitize', 'build', sources['SO'], out], path_first=wrap)
r.update(case='reviewer-2 failing compiler, pre-existing <out>/sanitized/sanitize_probe', sentinel_sha256_before=before,
         sentinel_exists_after=sentinel.exists(), sentinel_sha256_after=sha(sentinel) if sentinel.exists() else None,
         wrapper='<PRIVATE_BUILD>/wrap/g++: exits 1 if an argument starts with -fsanitize, else runs the real g++',
         expected='exit 77 and the sentinel gone (astra review)')
r['sentinel_deleted'] = not r['sentinel_exists_after']
rows['cases'].append(r)
print(r['case'], 'exit', r['exit'], 'sentinel deleted', r['sentinel_deleted'], flush=True)
rows['summary'] = {
    'false_passes': [c['case'] for c in rows['cases'] if c.get('false_pass')],
    'reviewer_1a_reproduced': rows['cases'][0]['false_pass'] and rows['cases'][0]['report_in_log'],
    'reviewer_1b_reproduced': rows['cases'][1]['false_pass'] and rows['cases'][1]['report_in_log'],
    'reviewer_2_reproduced': r['exit'] == 77 and r['sentinel_deleted'],
}
(OUT / 'review-cases.json').write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps(rows['summary'], indent=1))
