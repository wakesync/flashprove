#!/usr/bin/env python3
"""Check that arms-q1.json's arms that reuse PR #74 configurations equal PR #74's arms-r2.json definitions.
Usage: check_arms.py"""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
a = json.load(open(HERE / "arms-q1.json")); b = json.load(open(HERE.parent / "20261110-8-qwen-norm-scaling" / "arms-r2.json"))
pairs = {"XS18": "X3-r2", "C4P": "C4P-r2", "C4+RU": "C4P-noG-r2", "C4+U": "C4+U-r2", "C4+R": "C4+R-r2", "C4+G": "C4+G-r2"}
ok = True
for k, v in pairs.items():
    eq = a[k]["cfg"] == b[v]["cfg"]; ok &= eq
    print(k, "==", v, eq, "" if eq else sorted(set(a[k]["cfg"].items()) ^ set(b[v]["cfg"].items())))
raise SystemExit(0 if ok else 1)
