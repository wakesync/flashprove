# Qwen3.8-27B M3: counting model and cost model (research only, no proof)

Nothing in this directory proves anything. It holds three small Python programs that count how big
the M3 statement would be and extrapolate what it might cost. Design, PREREG and verdicts:
`experiments/20261109-32-qwen-m3-design/` (DESIGN.md, RESULTS.md). Status page: `docs/qwen-port.md`.

## What M3 would prove, in plain words

A provider commits once to the integer weights of Qwen3.8-27B. For a reply it then proves that the
reply's tokens are what that committed model computes, layer by layer, without showing the weights
or any intermediate value. The verifier holds a 32-byte commitment ID, the tokens and the proof.

- **Proved (by design, not built):** every matrix product against the committed weights; the
  causal convolution, SiLU, the q/k norm and the gates of each Gated DeltaNet head; the recurrence
  from one committed state to the next; the gated norm; the MLPs, attention layers and output head.
- **What the verifier recomputes:** only things that depend on public data: the commitment ID from
  the public files, the class of each public word, relation coefficients that are constants of the
  format, and the no-overflow check of DESIGN.md section 6.
- **Not covered:** how close the integer model is to the real floating-point model (known to be
  poor at the precision counted here, see below), vision and MTP, sampling, and whether the
  committed weights are the checkpoint the provider advertises.

## Files

| file | what it does | output |
|---|---|---|
| `planner_proxy.py` | runs the upstream planner (`cp_verify -plan arrays`) on proxy shapes for Qwen's dense family and sums its arrays | `runs/planner-proxy.json`, `runs/planner-*.arrays.txt` |
| `count_m3.py` | counts the M3 statements on the research harness (imports `../qwen_deltanet_m2/count_model.py`), counts the packed form of the full model, and extrapolates VRAM, time and proof size | `runs/model.json` |
| `bounds.py` | recomputes the worst magnitude of every relation from the bound that is enforced on each factor; fails if one reaches 2^63 | `runs/bounds.json` |

## Reproduce every number

From the repository root. Python 3 standard library only. The first step needs g++ 13 and about two
minutes; the rest take seconds. No GPU.

```
V=$(mktemp -d)      # a private directory; verifier/build.sh refuses one that others can write
bash verifier/build.sh - "$V"
R=experiments/20261109-32-qwen-m3-design/runs
python3 research/operators/qwen_m3/planner_proxy.py --cp-verify "$V/cp_verify" --out $R
python3 research/operators/qwen_m3/count_m3.py --planner $R/planner-proxy.json --json $R/model.json
python3 research/operators/qwen_m3/bounds.py --json $R/bounds.json
```

`count_m3.py` prints the five verdicts (H1 to H5). `runs/model.json` holds every number in
RESULTS.md: `harness` (H1, H2, H3, the MLP and layer statements), `H4`, `packed` (per case and
window), `m3b`, `sensitivity_open_norm_scaling`, `vram_calibration_descriptive`, `H5`.
`runs/model-first-run.json` is the first run, kept because one design choice was changed after it
(RESULTS.md, "Deviations").

## How to read the numbers

- **Counted** numbers (columns, cells, keys, relations, committed entries) are exact outputs of a
  model. The recurrence part reproduces the measured M1 and M1b statements. The M3 additions have no
  builder to check them against.
- Fields named `terms_PROVISIONAL` are not to be used: a review of #66 found the norm's term counts
  in the imported model inexact.
- Everything under a key with `extrapolated` or `EXTRAPOLATED` in its name is a count multiplied by
  a rate from another model's runs (upstream's published Llama 4 Maverick figures on one H100, not
  reproduced by this fork). The assumptions are listed in RESULTS.md H5.3.
- All counts are at F = 12 with the M2 norm lowering. On real layer-0 weights that arithmetic keeps
  its ranges but misses the fidelity threshold (PR #68, draft). The scaling is an open parameter;
  `sensitivity_open_norm_scaling` says how much the sizes move.

## Limits

No proof, no verifier, no hostile suite: there is nothing here to attack. The packed DeltaNet
count describes a GPU sub-proof that does not exist. A proxy configuration is not a Qwen
configuration: it has Maverick's attention shape and no DeltaNet.
