#!/usr/bin/env python3
"""Move the qwen-q1-deep-fidelity block in research/results.yaml from before glm-kda-model-scale to before
qwen-norm-scaling-layer0, so it does not sit next to the row main added after qwen-norm-scaling-layer0 (PR 87),
which made fp_merge_main.py abort on a textual conflict. Content of the block is unchanged."""
from pathlib import Path
Y = Path(__file__).resolve().parents[2] / "research" / "results.yaml"
t = Y.read_text()
start = t.index("  - id: qwen-q1-deep-fidelity\n")
end = t.index("  - id: glm-kda-model-scale\n")
block = t[start:end]
t = t[:start] + t[end:]
anchor = "  - id: qwen-norm-scaling-layer0\n"
assert t.count(anchor) == 1
t = t.replace(anchor, block + anchor)
Y.write_text(t)
print("moved", block.count("\n"), "lines")
