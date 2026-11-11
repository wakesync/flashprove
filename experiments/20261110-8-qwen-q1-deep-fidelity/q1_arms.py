#!/usr/bin/env python3
"""Run arms-q1.json on one target through scaled_head.run (PR #74, unchanged), with the target layer's out_proj in
place of layer 0's for the descriptive residual measure (set in scaled_head._WO before the worker pool forks).
Head inputs come from q1_forward.py's prep files (NS_PREP = <prep dir>, ckpt label e.g. stock-L16).
Usage: q1_arms.py <prep_dir> <label> <Wo.npy> <out.jsonl> <fref_scratch> <deadline HHMM UTC>"""
import os, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "20261110-8-qwen-norm-scaling"))
sys.path.insert(0, str(HERE.parent / "20261109-8-qwen-real-weights"))

def main():
    prep, label, wo, out, fref, dl = sys.argv[1:7]
    os.environ["NS_PREP"] = prep
    import scaled_head as SH
    SH._WO[label] = np.load(wo)
    SH.run(None, label, str(HERE / "arms-q1.json"), out, 6, None, fref, None, dl, False)

if __name__ == "__main__": main()
