#!/usr/bin/env python3
"""Run make_pins.py --stdout twice as separate processes and compare both outputs with the committed pin
file, byte for byte (issue #203, PREREG threshold F). Writes runs/pin-repro.json.

Usage (from the top of the tree): repro_pins.py      exit 0 iff both runs equal the committed file
"""
import hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PIN = ROOT / "experiments/20261112-149-leaf-v2/runs/registered-pins.json"


def main():
    outs = [subprocess.run([sys.executable, str(HERE / "make_pins.py"), "--stdout"], capture_output=True,
                           cwd=str(ROOT), check=True).stdout for _ in range(2)]
    committed = PIN.read_bytes()
    d = dict(note="make_pins.py --stdout run twice, compared byte for byte with the committed pin; deterministic file reads",
             committed_sha256=hashlib.sha256(committed).hexdigest(), committed_bytes=len(committed),
             run_sha256=[hashlib.sha256(o).hexdigest() for o in outs],
             runs_equal_each_other=outs[0] == outs[1], runs_equal_committed=all(o == committed for o in outs))
    (HERE / "runs/pin-repro.json").write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")
    print(json.dumps(d, sort_keys=True))
    return 0 if d["runs_equal_each_other"] and d["runs_equal_committed"] else 1


if __name__ == "__main__":
    sys.exit(main())
