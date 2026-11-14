#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

# Terms: docs/glossary.md.

"""Negative test of parameter_walk.py's part widths: a file that cp_verify refuses BEFORE the test
"shape-heads" must not count as having reached and passed it.

The test copies a configuration (default prover/tests/configurations/pinned_no_proof_of_work) into a
temporary folder that it creates and removes, and changes only the line eps1_lo to 0. cp_verify
refuses that file "NO: policy-norm" (cp_verify.cpp:517-519), before "shape-heads" (:525-526), and so
every width copy, which changes only H, dh or d. The test checks the seed's refusal, then runs
parameter_walk.py on the copy (--walk-only --steps 0 --wide 8 --jobs 2) and passes only if the walk
ends with status 1, made at least one file with H * dh != d, and counted none of them. It never
changes a committed configuration. It shows nothing about a plan or a proof.

usage: parameter_walk_width_count_test.py <cp_verify> [--config <folder>]
Exit status 0: as described. 1: not. 2: bad arguments.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
top = os.path.dirname(os.path.dirname(here))


def main():
    a = sys.argv[1:]
    config = os.path.join(top, "prover/tests/configurations/pinned_no_proof_of_work")
    if len(a) == 3 and a[1] == "--config":
        config = os.path.abspath(a[2])
        a = a[:1]
    if len(a) != 1 or not os.access(a[0], os.X_OK):
        print(__doc__.split("\n\n")[-2])
        return 2
    program = os.path.abspath(a[0])
    tmp = tempfile.mkdtemp(prefix="width-count-")
    try:
        kit = os.path.join(tmp, "eps1-lo-0")
        os.mkdir(kit)
        pol = open(os.path.join(config, "policy.txt")).read()
        pol, n = re.subn(r"(?m)^eps1_lo 1$", "eps1_lo 0", pol)
        if n != 1:
            print("parameter_walk_width_count_test.py: the configuration has no line 'eps1_lo 1'")
            return 1
        open(os.path.join(kit, "policy.txt"), "w").write(pol)
        for f in ("KL.bin", "layout.txt"):
            shutil.copyfile(os.path.join(config, f), os.path.join(kit, f))
        s = subprocess.run([program, "-plan", "arrays", kit, "128"], capture_output=True, text=True)
        seed = (s.stdout.strip().splitlines() or [""])[-1]
        if s.returncode != 1 or seed != "NO: policy-norm":
            print("parameter_walk_width_count_test.py: the changed seed ended %d '%s', not 1 'NO: policy-norm'" % (s.returncode, seed))
            return 1
        w = subprocess.run([sys.executable, "-B", os.path.join(here, "parameter_walk.py"), program, os.path.join(tmp, "walk"), kit,
                            "--walk-only", "--steps", "0", "--wide", "8", "--jobs", "2"], capture_output=True, text=True)
        sys.stdout.write(w.stdout + w.stderr)
        m = re.search(r"(?m)^parameter_walk\.py: query width: (\d+) files with H \* dh != d, (\d+) reached and passed shape-heads", w.stdout)
        made, counted = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
        ok = w.returncode == 1 and made > 0 and counted == 0
        print("parameter_walk_width_count_test.py: seed refused policy-norm (before shape-heads); walk status %d, %d files with H * dh != d, %d counted: %s"
              % (w.returncode, made, counted, "as expected" if ok else "NOT as expected"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    sys.exit(main())
