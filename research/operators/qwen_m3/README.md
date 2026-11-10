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
  format or public shifts, and the no-overflow check of DESIGN.md section 6. Each value it derives
  is checked against its class before use (DESIGN 6.3).
- **Not covered:** how close the integer model is to the real floating-point model (on layer 0,
  10 prompts, the precision counted here missed the accuracy threshold, PR #68; deeper layers
  unmeasured), vision and MTP, sampling, and whether the committed weights are the checkpoint the
  provider advertises. The counts cover the request's trace only, not the weight table or the
  matmuls' rounds.

**Revision r2 (2026-11-10)**, after two reviews of PR #70: `count_m3.py` and `bounds.py` were
corrected (exact remainder classes at public shifts, the q scale, the weight-cell class and tie,
arm A split at 256 terms, retained gains, the MLP down projection rounded, exact ledger sums).
Their outputs are `runs/model-r2.json` and `runs/bounds-r2.json`. `runs/model.json` and
`runs/bounds.json` are the r1 outputs and are kept unchanged; the r1 code is at commit `be3da765`.
The change list is DESIGN.md section 12.

**Revision r3 (2026-11-10)**, after the round-2 re-reviews: dt_bias has its own class
[-2^17, 2^17) (r2's [-4,096, 4,095] at 2^F refused every honest head); `bounds.py` adds a
completeness check of every weight-cell class against PR #68's layer-0 values
(`experiments/20261109-8-qwen-real-weights/runs/weight-stats.json`); `count_m3.py` counts the M3a-1
fallback and writes `H5.how_to_read`. Outputs `runs/model-r3.json` and `runs/bounds-r3.json`; the
r2 files are kept unchanged and the r2 code is at commit `82a4601e`. Change list: DESIGN.md
section 13.

## Files

| file | what it does | output |
|---|---|---|
| `planner_proxy.py` | runs the upstream planner (`cp_verify -plan arrays`) on proxy shapes for Qwen's dense family and sums its arrays | `runs/planner-proxy.json`, `runs/planner-*.arrays.txt` |
| `count_m3.py` | counts the M3 statements on the research harness (imports `../qwen_deltanet_m2/count_model.py`), counts the packed form of the full model, and extrapolates VRAM, time and proof size | `runs/model-r3.json` (r2: `runs/model-r2.json`, r1: `runs/model.json`) |
| `bounds.py` | sums \|term\| over every term of every relation with each factor at the edge of its enforced class, exactly; fails if one reaches 2^63, if a control row does not wrap, if the r1 floor counterexample is not refused, or (r3) if an honest layer-0 weight is outside its class | `runs/bounds-r3.json` (r2: `runs/bounds-r2.json`, r1: `runs/bounds.json`) |

## Reproduce every number

From the repository root. Python 3 standard library only. The first step needs g++ 13 and about two
minutes; the rest take seconds. No GPU.

```
V=$(mktemp -d)      # a private directory; verifier/build.sh refuses one that others can write
bash verifier/build.sh - "$V"
R=experiments/20261109-32-qwen-m3-design/runs
python3 research/operators/qwen_m3/planner_proxy.py --cp-verify "$V/cp_verify" --out $R
python3 research/operators/qwen_m3/count_m3.py --planner $R/planner-proxy.json --json $R/model-r3.json
python3 research/operators/qwen_m3/bounds.py --json $R/bounds-r3.json
```

`bounds.py` reads `experiments/20261109-8-qwen-real-weights/runs/weight-stats.json` by a path
relative to the repository root (option `--weight-stats`), so run it from the root.
To check the r3 outputs without the planner step (the count reads the committed
`planner-proxy.json`), run the last two lines into a scratch directory and compare with `cmp`.
The planner step rewrites `runs/planner-*`; its outputs are unchanged since r1. The r2 files come
from the code at `82a4601e` (`git show 82a4601e:<path>` for each of the two scripts and
`../qwen_deltanet_m2/count_model.py`).

`count_m3.py` prints the five verdicts (H1 to H5), then `H5_r2_plain_answer`. `runs/model-r3.json` holds every number in
RESULTS.md: `harness` (H1, H2, H3, the MLP and layer statements), `H4`, `packed` (per case and
window), `m3b`, `sensitivity_open_norm_scaling`, `vram_calibration_descriptive`, `H5`, and
`H5_r2` (the registered verdicts kept, the own-rate case, segment counts against cp_verify's cap,
the low-rank status), and (r3) `harness.m3a1_fallback`.
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
- All counts are at F = 12 with the M2 norm lowering. On real layer-0 weights (10 prompts) that
  arithmetic keeps its ranges but missed the fidelity threshold (PR #68). F and the lowering are
  open parameters; `sensitivity_open_norm_scaling` says how much the sizes move.
- Every low-rank figure (`low_rank_*`) is **not established**: it depends on a construction that is
  not specified or proved (DESIGN 7.3). The plan of record is the per-token cases.
- `fits_log22` now also requires every relation to have at most 256 terms (the harness's cap).
- **The `H5` field and the `H5` block that `count_m3.py` prints are not a fit answer.** Its strings
  ("fits, also on the high estimate", `pass_: true`, `registered_expectation_held: true`) are the
  registered decision rule applied at the registered rates. They include segmentations chosen after
  the first run was seen (post hoc) and the low-rank case, which is not established. This holds for
  the same strings in `runs/model-r2.json` and `runs/model.json`, which are not edited. The answer
  is in `H5_r2.plain_answer`: **unknown**. From r3 the file also carries this note as
  `H5.how_to_read`, and the script prints the plain answer after H5.

## Limits

No proof, no verifier, no hostile suite: there is no executable M3 verifier to attack. The design's
equations and the bound ledger can be attacked on paper, as both reviews did. The packed DeltaNet
count describes a GPU sub-proof that does not exist. A proxy configuration is not a Qwen
configuration: it has Maverick's attention shape and no DeltaNet.
