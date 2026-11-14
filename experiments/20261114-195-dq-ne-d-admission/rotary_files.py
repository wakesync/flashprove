#!/usr/bin/env python3
"""Rotary-table witness files of experiment 20261114-195-dq-ne-d-admission (PREREG, Amendment 4, item 2).

usage: rotary_files.py make <repo> <new folder> <name> ..
       rotary_files.py run <cp_verify> <base|patched> <files folder> <output folder> <name> ..
       rotary_files.py names

make: writes <new folder>/<name>/policy.txt and KL.bin from the small kit
prover/tests/configurations/pinned_no_proof_of_work. The recipe (two layers in one group, no expert
layers, no table digest lines, six call lines) follows a reviewer's script for PR 199; the numbers
of each file are in FILES below. The file has no table digest, so none is compared: a call that gets
past the rotary table goes on to the attention sub-proof's tests.
run: one call `cp_verify -plan arrays <folder> 128` per name, under `prlimit --as=4294967296` and
`timeout 120`, with /usr/bin/time for the peak resident memory. Writes one JSON object per call.
It makes planning calls only: no proof is read or made.
"""
import importlib.util
import json
import pathlib
import re
import struct
import subprocess
import sys

COMMON = {"L": 2, "ll": 1, "nmin": 24, "lidb": 28, "NE": 0, "fe": 0, "hr": 0, "hq": 0, "hv": 0,
          "wb_gs": 0, "wb_us": 0, "wb_gr": 0, "wb_ur": 0, "wb_dnr": 0, "wb_r": 0}
CALLS = ("call R16a R16 G U UT N1 N1H N2 N2H O D\ncall R16b R16 V\ncall R16c R16 QK\ncall R8 R8 GH UH OH DH ROW\n"
         "call FC FC CN1 CN2 CQK CV\ncall FL FL F\n")
FILES = {
    # registered (Amendment 4): T dh = 2^27, 2^28 words with d = 8; 2^25, 2^26 words at equal width
    "P27": {"d": 8, "H": 1, "G": 1, "dh": 131072, "lt": 10, "la": 12},
    "P28": {"d": 8, "H": 1, "G": 1, "dh": 262144, "lt": 10, "la": 12},
    "B25": {"d": 16384, "H": 1, "G": 1, "dh": 16384, "lt": 11, "la": 12, "table#6": 20},
    "B26": {"d": 16384, "H": 1, "G": 1, "dh": 16384, "lt": 12, "la": 13, "table#6": 20},
    # debug shape, not registered: used only to see that this script runs
    "debug-dh64": {"d": 8, "H": 1, "G": 1, "dh": 64, "lt": 6, "la": 8},
}


def kits(repo):
    spec = importlib.util.spec_from_file_location("kits", pathlib.Path(repo, "experiments/20261114-195-dq-ne-d-admission/kits.py"))
    k = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(k)
    return k


def put(text, key, value):
    text, n = re.subn(r"(?m)^%s \d+$" % re.escape(key), "%s %d" % (key, value), text)
    if n != 1:
        sys.exit("rotary_files.py: the kit has %d lines '%s'" % (n, key))
    return text


def make(repo, out, names):
    k = kits(repo)
    small = pathlib.Path(repo, "prover/tests/configurations/pinned_no_proof_of_work")
    for name in names:
        text = (small / "policy.txt").read_text()
        for key, value in {**COMMON, **FILES[name]}.items():
            if key == "table#6":
                text, n = re.subn(r"(?m)^(table \d+ \d+ \d+ \d+ \d+) \d+$", r"\1 %d" % value, text)
                if n != 1:
                    sys.exit("rotary_files.py: no line table of six numbers")
                continue
            text = put(text, key, value)
        text, n = re.subn(r"(?m)^t(?:silu|sig|rope|exp)\d+ \d+\n", "", text)
        assert n == 32, n
        text, n = re.subn(r"(?m)^(?:rcl|gcl) \d+\n", "", text)
        assert n == 2, n
        text, n = re.subn(r"(?m)^call .*\n", "", text)
        assert n == 8, n
        assert text.count("callA KR KR RM RD") == 1
        text = text.replace("callA KR KR RM RD", CALLS + "callA KR KR RM RD")
        for key, value in k.iota(text).items():
            text = put(text, key, value)
        folder = pathlib.Path(out, name)
        folder.mkdir(parents=True)
        (folder / "policy.txt").write_text(text)
        # KL.bin: two layer records of 13 words; the shifts kq, kk, kv (words 0, 1, 2) set to 16.
        words = list(struct.unpack("<26I", (small / "KL.bin").read_bytes()[: 2 * 13 * 4]))
        for layer in range(2):
            for i in (0, 1, 2):
                words[13 * layer + i] = 16
        (folder / "KL.bin").write_bytes(struct.pack("<26I", *words))
        v = FILES[name]
        print("made %s: d %d, H %d, G %d, dh %d, lt %d: T dh = 2^%d u32 words (%d bytes)"
              % (name, v["d"], v["H"], v["G"], v["dh"], v["lt"], v["lt"] + v["dh"].bit_length() - 1, 4 * (1 << v["lt"]) * v["dh"]))
    return 0


def run(binary, which, files, out, names):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = out / ("%s.%s.json" % (name, which))
        if target.exists():
            sys.exit("rotary_files.py: %s exists already: nothing was run" % target.name)
        cmd = ["prlimit", "--as=4294967296", "timeout", "120", "/usr/bin/time", "-f", "peak_kib=%M seconds=%e", binary, "-plan", "arrays", str(pathlib.Path(files, name)), "128"]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
        lines = p.stdout.splitlines()
        m = re.search(r"peak_kib=(\d+) seconds=([0-9.]+)", p.stderr)
        v = FILES[name]
        rec = {"file": name, "binary": which, "d": v["d"], "H": v["H"], "G": v["G"], "dh": v["dh"], "lt": v["lt"],
               "table_u32_words_log2": v["lt"] + v["dh"].bit_length() - 1, "table_bytes": 4 * (1 << v["lt"]) * v["dh"],
               "command": "prlimit --as=4294967296 timeout 120 /usr/bin/time -f 'peak_kib=%M seconds=%e' <cp_verify> -plan arrays <files>/" + name + " 128",
               "status": p.returncode, "last_line": lines[-1][:200] if lines else "", "stdout_lines": len(lines),
               "peak_kib": int(m.group(1)) if m else None, "seconds": float(m.group(2)) if m else None,
               "stderr_tail": [l[:200] for l in p.stderr.splitlines() if not l.startswith("peak_kib=")][-3:]}
        target.write_text(json.dumps(rec, indent=1) + "\n")
        print("%-10s %-7s status %s | %s | peak %s KiB | %s s" % (name, which, rec["status"], rec["last_line"], rec["peak_kib"], rec["seconds"]), flush=True)
    return 0


def main():
    a = sys.argv[1:]
    if a[:1] == ["names"]:
        print(" ".join(FILES))
        return 0
    if a[:1] == ["make"] and len(a) >= 4 and all(n in FILES for n in a[3:]):
        return make(a[1], a[2], a[3:])
    if a[:1] == ["run"] and len(a) >= 6 and a[2] in ("base", "patched") and all(n in FILES for n in a[5:]):
        return run(a[1], a[2], a[3], a[4], a[5:])
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
