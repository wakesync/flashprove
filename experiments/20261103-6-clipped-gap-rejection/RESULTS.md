# RESULTS: 20261103-6-clipped-gap-rejection

Numbers vs the pre-registered thresholds (PREREG.md). Full write-up and table:
[research/acceptance/clipped-gap/README.md](../../research/acceptance/clipped-gap/README.md).
Refs #38 (tracking issue; its real-`cp_verify` per-class deliverable stays open, PREREG amendment 3).

**Every number here: measured, unreplicated (scored, not proved).** The independent reviewer's rerun was on
the same CPU model and OS image: a reproduction, not independent replication. Cells are median, sample SD
over the 5 seeds, (min-max), in %, from `numbers.json`. Results ledger: deferred, since
`research/results.yaml`, `scripts/update-results.py` and `scripts/check-claims.py` do not exist in the
repository yet (main at 78d0c031); no claim is recorded.

| clause | threshold | result | verdict |
|---|---|---|---|
| 1 | some grid point: median acceptance 0 % in every gross class, median FRR <= 5 % | 12 points by median, 7 at every seed (all cap = 0); e.g. `C=p99.9 theta=p100 cap=0`: FRR 5, SD 2.1 (0-5), shipped C/theta with cap 0: FRR 2, SD 1.6 (0-3) | **PASS** |
| 2 | no grid point: median `fp2nd-1` acceptance 0 % at median FRR <= 5 % | lowest such `fp2nd-1` acceptance 5, SD 1.6 (3-6) (`p99.5/p95/1`); `int2nd-1` 6, SD 0.7 (5-6) | **holds** |

All swap classes use random positions, so their rates are lower bounds for a provider that picks the
position; `int2nd-1` is the integer model's second choice at a random position, not the cheapest
deviation (PREREG amendment 3). Clause 1 says nothing about an adaptive 1-token substitution. The
reviewer's exploratory, unreplicated best-position probe (n = 16, seed 2026, not in the committed files)
found a passing single swap for 13/16 replies even under `p99.9/p100/0`: an open lead, not a result.
analyze.py leaves `theta == C with cap > 0` points out of clause 1; no verdict depends on it.

Kill criteria: (a) not hit: the stored reply's four non-first-choice costs reproduced exactly (446,700,
438,154, 56,748, 470,490). (b) not applicable as stated: the seed-2026 fit in float32 gave C 5,178,975 /
theta 203,143 / cap 1 against the shipped bf16-fitted 9,244,130 / 323,343 / 1; the shipped README
records that dtype and machine move the fit (another bf16 machine gave C 6,654,538), and amendment 1
explains the dtype. (c) not hit: about 35 min of scoring wall time (5 seeds in parallel).

Not proved, not verified: all rates are scores. No cp_verify rejection due to the limits was observed
(no proof for an attacked reply can be made on CPU); see the README's spot-check section.

Exploratory (amendment 2, after results; measured, unreplicated): one swap at a random position then
greedy continuation passes the shipped and the fit_limits.py limits 91-95 % (median) of the time
(cap = 1; SDs 2.0-7.6, README table).

cp_verify spot set: 19 of 21 classes (rand-2 and rand-8 not built), a deviation recorded in PREREG
amendment 3.

## Reproduce (CPU, about 40 min on 16 vCPU)

From the repository's top, Python 3.13 venv with torch 2.9.1, transformers 4.57.6, safetensors, numpy:

```sh
D=$(mktemp -d) && export PYTHONPATH=$PWD/integrations/vllm/integer_model
(cd integrations/vllm/integer_model && python -m integer_model_vllm.example small_float_pair --directory "$D/pair" --repository "$OLDPWD" --quiet)
E=experiments/20261103-6-clipped-gap-rejection
for s in 2026 2027 2028 2029 2030; do python $E/score_seed.py "$D/pair" $s "$D/seed$s.json" --threads 3 --dtype float32 & done; wait
for s in 2026 2027 2028 2029 2030; do python $E/score_redecode.py "$D/pair" "$D/seed$s.json" "$D/redecode$s.json" & done; wait
verifier/build.sh
python $E/spot_replies.py "$D/pair" "$PWD" "$D/spot_replies.json"
python3 $E/cp_verify_spot.py "$PWD" "$D/cp_verify_spot.json" "$D/spot_replies.json"
python3 $E/analyze.py "$D/numbers.json" "$D"/seed20*.json --spot "$D/cp_verify_spot.json" --explore "$D"/redecode20*.json
python3 $E/table.py "$D/numbers.json"
```

Seed files from a float32 run should match `research/acceptance/clipped-gap/raw/` on another x86 CPU;
that was not checked (no second machine in this lane; the reviewer's byte-identical rerun used the same
CPU model and OS image). Independent replication is needed before any
number here is used as a headline (STANDARDS.md #5).
