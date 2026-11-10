#!/usr/bin/env python3
"""Print the engine-check maxima RESULTS.md quotes, from runs/engine-check.json. Usage: engine_facts.py"""
import json
from pathlib import Path
d = json.load(open(Path(__file__).resolve().parent / "runs" / "engine-check.json"))
print("pass_a", d["pass_a"], "pass_b", d["pass_b"], "prompts", len(d["bit_identical"]), "tokens", sum(v["tokens"] for v in d["bit_identical"].values()),
      "identical", sum(v["identical"] for v in d["bit_identical"].values()))
print("max_rel_y", max(v["max_rel_y"] for v in d["all_exact"].values()), "max_rel_S", max(v["max_rel_S"] for v in d["all_exact"].values()))
