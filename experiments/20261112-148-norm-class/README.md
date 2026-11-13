# 20261112-148-norm-class: Qwen pre-norm outputs against the public class 2,047

Issue #148. Registration: [PREREG.md](PREREG.md). Outcome: [RESULTS.md](RESULTS.md).

**Outcome in one line: partial.** The registered run stopped itself on its free-disk floor after layer 51 of 63. The baseline covers 52 layers and the arms 27 layers. No arm has a registered verdict. See RESULTS.md for what the layers done show and for what is not established.

## What this is
A CPU measurement harness. It builds no proof and changes no relation or verifier.

The M3 design gives the public normed input of every Qwen statement the class |x| <= 2,047 at scale 2^12. PR #138 found the MLP input over that class on about a tenth of entries. This experiment asks which of three candidate fixes keeps every pre-norm output in a class the statement can admit, and what each costs in one layer's output error against float64:

- **C**: clamp to 2,047 at 2^12 (what upstream's norm does).
- **S**: a smaller scale 2^k, with k fixed by a rule on the baseline maximum.
- **W**: keep 2^12 and widen the class.

It runs open loop: every arm starts each layer from the float64 reference stream, so one layer's error never feeds the next.

## What it does not cover
- No logits, no token agreement, no compounding of error across layers.
- No proof, no soundness claim. The arms are numerical lowerings.
- The DeltaNet heads, attention, q/k norms, in_proj and out_proj stay float64. Only the two pre-norm outputs and the MLP are integer.
- It does not choose the design arithmetic.

## Files
| file | what |
|---|---|
| `norm_class.py` | the harness: baseline class counters for both pre-norm outputs, arms C, S (k = 3, 4, 5), W, per-layer error metrics. Imports PR #138 `mlp_e2e.py`, PR #124 `e2e.py` and PR #88 `q1_forward.py` unchanged |
| `run_norm.sh` | the registered run wrapper: logs the slot grant, enforces the 80 minute budget and the 00:05Z hard stop, refuses to start under 10 GB of free memory or 21 GB of free disk |
| `ledger_w.py` | counts arm W's cost from `research/operators/qwen_m3/bounds.py` (imported unchanged). Counted on class edges. It reads no activation |
| `runs/ledger-w.json` | output of `ledger_w.py` |
| `run_all.sh`, `decide_set.py` | PREREG A-1: the fixture debug and the registered run as one queued job, and the layer-set rule (timing only) |
| `summarise.py` | applies the registered rules to `runs/baseline.jsonl` and `runs/arms.jsonl`; writes `runs/summary.json` and `runs/summary.md` |
| `make_results.py`, `results_tail.md` | write RESULTS.md from `runs/summary.json`, `runs/ledger-w.json`, `runs/progress.log` and the fixed prose |
| `add_results_row.py` | writes this experiment's `research/results.yaml` entry from `runs/summary.json` and `runs/ledger-w.json` |
| `check_manifests.py`, `env.py`, `scrub_time_path.py` | weight manifest comparison with PR #124 and PR #68; ENV.json; placeholder for the scratch path in `runs/run.time` |
| `runs/baseline.jsonl`, `runs/arms.jsonl` | the registered run's raw rows (52 baseline layers, 27 arm layers) |
| `runs/debug/synthetic.json` | debug: synthetic checks of the new code |
| `runs/debug/fixture-partial-1/` | debug: the interrupted fixture run (fixture tokens only, stock layers 0 to 2). Not results |

## What was added to reused code
Nothing in the reused files is edited. New in `norm_class.py`: `quant` (the three quantisers), `qstats` and `base_stats` (class counters and the bit-length histogram), `with_norm` (hands a precomputed norm output to the unchanged `q1_forward` mixer functions), `mlp_arm` (PR #138 `mlp_int`'s formulas with the input given and the gate / up shift s = e + k - 12), the open-loop layer driver and the run loop.

## Commands
Run from the repository root. `<scratch>` is any directory outside the repository.

```
# counted ledger for arm W (seconds, no network)
python3 experiments/20261112-148-norm-class/ledger_w.py experiments/20261112-148-norm-class/runs/ledger-w.json

# synthetic debug checks (seconds, no network)
python3 experiments/20261112-148-norm-class/norm_class.py synth experiments/20261112-148-norm-class/runs/debug/synthetic.json

# fixture debug: "The capital of Italy is" through stock layers 0 to 3 (fetches 4 layers of weights into memory)
python3 experiments/20261112-148-norm-class/norm_class.py fixture <scratch>/fixture <scratch>/fixture.json

# the registered run (peak 8.3 GB of memory measured, streams one layer of weights at a time, writes no weights to disk)
# layer set: full = arms on all 64 layers, r33 = arms on the reduced set (what was run here)
bash experiments/20261112-148-norm-class/run_norm.sh <scratch>/run r33

# summary, manifest check and write-up from the committed raw rows (seconds, no network)
python3 experiments/20261112-148-norm-class/summarise.py
python3 experiments/20261112-148-norm-class/check_manifests.py
python3 experiments/20261112-148-norm-class/make_results.py experiments/20261112-148-norm-class/results_tail.md
```

The run fetches the public weights by HTTP range request and needs no token. It stops itself under 21 GB of free disk; that floor is this lane's, on its shared host.
