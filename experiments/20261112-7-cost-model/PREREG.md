# PREREG: Q3 cost model for a Qwen3.8-27B proof, from merged numbers only (desk, Part of #7)

Registered 2026-11-12, before the model script or any table was written. Desk lane: no proof run,
no GPU, no provider call, no new measurement. CPU use is limited to running a standard-library
Python script over files already on main.

## Question

From numbers on main only: what does a proof of Qwen3.8-27B cost per 1,000 tokens on one GPU?
Proof time (GPU-seconds), GPU memory (largest resident segment), and USD, and each as a multiple
of plain inference. Where a figure cannot be computed from main, name the measurement that is
missing. Use the result to say which use case is viable on cost: U1 substitution check (every
token proved), U2 sampled audit (a fraction f of windows proved), U3 proof alongside a TEE.

This supersedes nothing. It extends `research/cost/Q3-COST-QWEN-1110.md` (PR #85, merged), which
used only PR #70's extrapolation, with the merged results that landed after it: the built M2
DeltaNet head (#73), the CPU phase split (#106), the joint-boundary handoff counts (#98), the SB
unique-floor counts (#114), the key-file binding counts (#121), the larger-memory GPU rows and
prices (#44), and the fidelity and operator rows (#68, #67, #115).

## Method

1. A script, `research/cost/q3_cost_model_1112.py`, reads its inputs from files on main:
   `research/results.yaml` (each value looked up by result id and metric name, so the ledger's
   commit and source travel with it), `experiments/20261109-32-qwen-m3-design/runs/model-r3.json`
   (the counted Qwen volumes and PR #70's three time rates and memory rates), and
   `experiments/20261109-32-qwen-deltanet-lookup-build/runs/counts-vs-model.json` (the built M2
   head's laid columns). Prices and upstream multiples that exist only as prose are parsed from
   the named file and line, and fail loudly if the text has changed.
2. Every input carries one label: **measured** (a run on main), **counted** (an exact size from a
   model or a builder on main), **extrapolated** (a count times a rate from another statement or
   model), **assumed** (a number chosen, not derived), **unmerged** (open PR #123 only, never used
   in a headline), **not established**.
3. The model is a product of factors, each with a low and a high value taken from main:
   - committed entries per window token (packed plan of record, unbuilt; or the volume of the only
     DeltaNet lowering built at the real head shape, #73),
   - GPU-seconds per committed entry (PR #70's central and high fits to upstream; PR #70's
     small-example rate; and #73's measured-versus-estimated time ratio, applied only to the two
     fitted rates, as a stated transfer from CPU),
   - USD per GPU-hour (invoices and quotes on main, plus PR #70's assumed 3.00),
   - bytes per entry for the largest segment (23 central, 16 low, 46 high, 220 own rate),
   - window length T (64, 256, 1,024), which sets the per-token share of fixed passes and the
     memory of the largest segment.
   The output is a table of ranges, not points. A case whose largest segment does not fit one
   H200 under the 127 GB rule of PR #70 is flagged and, for the headline, replaced by the largest
   window that does fit.
4. The multiple of plain inference = proved GPU-seconds per token x plain tokens per GPU-second,
   same card, same token kind. If no plain Qwen3.8-27B rate is on main, the multiple is reported as
   not established, and the formula is evaluated only at stated assumed plain rates, labelled so.
5. U2 is f times the U1 variable cost plus fixed costs (commit, start-up). U3 is the U1 or U2 cost
   plus a TEE serving overhead.
6. A "not established" section lists each gap with the factor by which closing it could move the
   USD per 1,000 tokens, computed by the script as (high / low) of that factor alone with all
   others held at their central value; the list is ranked by that factor.

## What would count as an answer

No threshold: this is a desk model. The deliverable is the script, its printed table, the ranked
gap list, and a per-use-case viability statement. A negative answer (the cost cannot be bounded
from main to better than some factor) is a valid result and is reported as such.

## Fixed beforehand

- No number from an unmerged branch enters a headline. PR #123 is cited only as "unmerged, PR
  #123", in the gap list.
- Two lanes agreeing on a number is one calculation; the script says what each number means.
- Counted is not built; built on CPU is not GPU. CPU research-harness rates are reported for
  context and are never used as GPU rates.
- No results.yaml row is added: nothing here is measured.
