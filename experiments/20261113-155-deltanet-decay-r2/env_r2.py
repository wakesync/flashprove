#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus runs/progress.log.jsonl, runs/provenance.json, runs/determinism.json and
runs/eval/eval-meta.json. usage: env_r2.py"""
import json, platform
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; R = HERE / "runs"
prog = [json.loads(l) for l in (R / "progress.log.jsonl").read_text().splitlines()]
meta = json.loads((R / "eval" / "eval-meta.json").read_text())
env = {
    "experiment": "20261113-155-deltanet-decay-r2",
    "kind": "integer emulation of four registered decay table designs (U1..U4) vs the float64 decay, on the DeltaNet decay inputs PR #146 recorded from the abliterated Qwen3.8-27B; CPU only, no proof, no forward run in this experiment",
    "commits": {
        "base": "17d216d4f81d3e5ecc6011a2fa2c698b8993bf55 (main)",
        "prereg": "ef9bac0769b089673a72a2e012db4cec447ff64d (first commit, alone)",
        "arm_code": "4c25604e419d7592c84b26213f0a62cae96ec1e9 (decay_r2.py, summarise_r2.py, provenance.py, test_r2.py)",
        "code_at_registered_run": prog[0]["code_commit"],
        "registered_run_files": "0a4b6fc52be3b0c19932836ebfc23a68dd72cb2c",
        "amendments_and_posthoc_code": "fa595731d5d4536b7affb070994c8764c8840635 (PREREG Amendments A1 to A3, posthoc.py, determinism.py; committed before the post hoc computations were run)",
        "reused_unchanged": "experiments/20261112-136-deltanet-decay/{decay_tables.py, suite.py} and its committed runs/eval/{cells.csv.gz, domain.json.gz, summary.json} (PR #146); research/operators/qwen_ops/tables.py and tables/softplus-f12.i64le (PR #67); experiments/20261111-8-qwen-e2e-agreement/prompts-e2e.json (PR #124, read by suite.py)",
        "progress": prog,
    },
    "input": {
        "what": "PR #146's recorded ar arrays (48 files, one per DeltaNet layer: ar per prompt (T, 48), A = exp(A_log), dt_bias), from that lane's scratch output; not committed by PR #146 and not committed here",
        "recorded_by": "PR #146 record.py at 513ab974b603003e9a613cac99e37773d7b9b189, 2026-11-12T21:20Z to 21:44Z",
        "sha256_list": "PREREG.md 'Runs' (recorded before use)", "input_list_sha256": meta["input_list_sha256"],
        "provenance_check": json.loads((R / "provenance.json").read_text()),
        "checkpoints_of_the_recording": {"stock": "Qwen/Qwen3.8-27B@37561816e66b5b9153b1b64c10968c18c1e6f4a0 (embedding, layers 0..16)",
                                         "abliterated": "huihui-ai/Huihui-Qwen3.8-27B-abliterated@739e3c5b89849f6c238ce1e5b70008612ae42cdd (layers 17..63)",
                                         "note": "no weight was fetched by this experiment"},
    },
    "tables": {"sha256_int64_le": meta["tables_sha256"], "G": meta["G"], "softplus_wide": meta["softplus_wide"], "u4": meta["u4"],
               "generator": "research/operators/qwen_ops/tables.py expq / logq / nearest (integer, no floating point) for every table of U1..U3, all 2^20 fine rows included; U4's per-head rows are float64 (numpy exp, logaddexp, rint) by registration"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__, "blas": "not used by the evaluation (elementwise numpy only)", "flags": "none"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and loaded", "cores_used": "taskset -c 0-5, single process (6 processes only for generating the fine exp table)",
                 "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none", "provider": "KVM virtual machine (provider not recorded here)",
                 "heavy_gate": "not used: the registered evaluation took 13.6 s wall and 151 MiB peak RSS (runs/progress.log.jsonl), and record.py was not rerun"},
    "seeds": ["registered run: none (deterministic integer table emulation and float64 reference)", "test_r2.py synthetic heads: numpy default_rng(155)"],
    "repeats": "one deterministic evaluation, run twice; per-cell outputs equal (runs/determinism.json). Spread is reported over tokens, prompts and (layer, head, prompt) cells",
    "determinism": json.loads((R / "determinism.json").read_text()),
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
