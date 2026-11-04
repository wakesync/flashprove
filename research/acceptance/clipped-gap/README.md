# Clipped-gap acceptance policy: which attacked replies its limits reject (small synthetic model, scored)

Pre-registration, code, amendments and environment: [experiments/20261103-6-clipped-gap-rejection/](../../../experiments/20261103-6-clipped-gap-rejection/)
(`PREREG.md` was committed before any code, in its own commit). Issue #6. CPU only, no GPU rented.

**Weak point attacked.** [guide/known-limits.md](../../../guide/known-limits.md) says that no run shows the
clipped-gap policy's own limits rejecting anything at a verifier, and the project recommends no limits.

**What this does and does not close.** Read this first.

- Every acceptance rate in the tables is a **score** from the integer-model package
  (`integrations/vllm/integer_model`, the rule of `examples/try_limits.py` `meets()`), in Python, on a CPU.
  It is not a proof and not a `cp_verify` verdict.
- No proof was made in this study. The prover needs an H100; the lane was CPU only. So **the weak point
  stands as written**: this study, too, shows no `cp_verify` rejection that is due to the policy's limits.
  The honest `cp_prove` refuses a request whose checked tokens break the limits (`E_BOUNDS` in
  `prover/head/forward.cuh`, `k_head_budget`: the honest prover's error word, not the verifier's), so an
  out-of-limits reply gets no proof from it; seeing the verifier reject on the limits needs a prover that
  goes past that check (a cheating test build), which this repository does not ship.
- What `cp_verify` was asked, on the stored example `examples/accepted-proof-clipped-gap`, is in
  "cp_verify spot checks" below, labeled by what each NO shows.
- Synthetic weights, one small configuration (`prover/examples/target_small_f2_gap`, V = 512, T = 64,
  8 layers), random prompt ids. **No limits are recommended for any real model.** A fitted threshold is a
  function of the weights (row H2.2 of docs/limits-all-rows.tsv).

## Setup

Honest replies: greedy decodes of 32 tokens by the float32 copy of the model (`small_float_pair`) to 16
random prompt ids, 128 prompts per seed; first 64 fit the limits, last 64 are the held-out honest set.
5 prompt seeds (2026 = `try_limits.py`'s own draw, 2027-2030). Decoded in float32, not bfloat16 as the
shipped limits were (PREREG amendment 1: this CPU has no bfloat16 hardware, bf16 was 17x slower).

Attack classes, each built from each held-out honest reply (n = 62-64 per class per seed):

| class | what |
|---|---|
| `fp2nd-k` | k random positions (k = 1, 2, 4, 8, 16) set to the float model's 2nd choice there |
| `int2nd-k` | k positions set to the **integer** model's 2nd choice (an adversary that knows the weights) |
| `rand-k` | k positions set to a random other id |
| `rand-reply` | the whole reply random |
| `other-prompt` | the reply after the next prompt |
| `trunc-half`, `trunc-1` | reply cut to half / last token dropped (control: the policy cannot see truncation) |
| `*-1-redecode` (exploratory) | one position swapped (2nd choice / random), then the float model continues greedily from the new prefix. Added after the pre-registered results were seen (amendment 2); reported apart |

Grid: C in {256, p99, p99.5, p99.9, max of fit-half costs, shipped 9244130}; theta in {256, p50..p100 of
fit-half clipped means, shipped 323343}; cap in {0, 1, 2, 4}. 180 points, refit per seed. All in `numbers.json`.

## Headline table

Acceptance rate in % (median over 5 seeds, min-max in brackets). FRR = false-reject rate on honest
held-out replies = 100 - honest acceptance. Scored, not proved.

| class | exact match `256/256/0` | shipped `9244130/323343/1` | fitted `p99.9/p100/1` (fit_limits.py rule) | fitted, cap 0 `p99.9/p100/0` | tighter `p99.5/p95/1` |
|---|---|---|---|---|---|
| honest (acceptance) | 58 (52-61) | 100 (98-100) | 98 (98-100) | 95 (95-100) | 95 (92-97) |
| fp2nd-1 | 0 (0-2) | 12 (11-17) | 17 (5-25) | 6 (0-11) | 5 (3-6) |
| int2nd-1 | 0 | 12 (9-17) | 12 (6-17) | 6 (0-8) | 6 (5-6) |
| fp2nd-2 | 0 | 0 (0-3) | 0 (0-2) | 0 (0-2) | 0 |
| int2nd-2 | 0 | 0 (0-2) | 0 (0-2) | 0 (0-2) | 0 |
| fp2nd-4 / 8 / 16 | 0 | 0 | 0 | 0 | 0 |
| int2nd-4 / 8 / 16 | 0 | 0 | 0 | 0 | 0 |
| rand-1 | 0 | 5 (5-11) | 6 (5-12) | 0 | 5 (3-9) |
| rand-2 / 4 / 8 / 16 | 0 | 0 | 0 | 0 | 0 |
| rand-reply | 0 | 0 | 0 | 0 | 0 |
| other-prompt | 0 | 0 | 0 | 0 | 0 |
| trunc-half (control) | 75 (72-84) | 100 (98-100) | 98 (97-100) | 98 (97-100) | 94 (89-97) |
| trunc-1 (control) | 59 (52-61) | 100 (98-100) | 98 (98-100) | 95 (95-100) | 95 (94-97) |
| fp2nd-1-redecode (exploratory) | 2 (0-6) | 95 (91-95) | 94 (84-95) | 58 (19-67) | 75 (70-84) |
| rand-1-redecode (exploratory) | 0 | 91 (81-92) | 92 (81-98) | 0 (0-2) | 73 (66-83) |
| **FRR** | **42 (39-48)** | **0 (0-2)** | **2 (0-2)** | **5 (0-5)** | **5 (3-8)** |

Fitted values per seed (C / theta / cap) are in `numbers.json` (`aggregate.<label>.values_per_seed`);
`fit_limits.py`'s rule (C = p99.9 of costs, theta = largest clipped mean, cap = most costs above C) gave
cap = 1 at every seed, C from 1,240,103 to 8,358,715 and theta from 50,304 to 369,248. 33-51 of
2,017-2,048 fitted tokens per seed were not the integer model's first choice.

## Pre-registered verdicts

1. **PASS.** Some grid points accept 0 % of every "gross" class (k >= 4 second-choice swaps, random
   tokens incl. 1 and 2, whole random reply, other prompt) at median FRR <= 5 %. Seven do so at every
   one of the 5 seeds, all with cap = 0, e.g. `C=p99.9 theta=p100 cap=0` at FRR 5 % (0-5) and the shipped
   C and theta with cap = 0 at FRR 2 % (0-3). With cap = 1 (what `fit_limits.py` fits), `rand-1` gets
   through 5-12 % of the time, so cap = 1 points pass only the variant of the clause without rand-1/rand-2.
2. **Holds.** No grid point stops 1-token second-choice swaps at FRR <= 5 %: the lowest median
   acceptance of `fp2nd-1` at FRR <= 5 % is 5 % (`p99.5/p95/1`), of `int2nd-1` 6 %.

Cautious statement, as the brief asks: *on this small synthetic model, scored and not proved, limits
fitted to honest float32 replies with cap = 0 (e.g. C = 99.9th percentile of honest costs, theta = largest
honest clipped mean) rejected every tested reply with 4 or more tokens swapped, every tested reply with 1
or more random tokens, every random reply and every reply after another prompt, at a 0-5 % false-reject
rate on held-out honest replies (5 seeds, 62-64 replies per class per seed). They let through 6 % of
1-token second-choice swaps, 0-2 % of 2-token swaps, and all truncated replies.*

## What the exploratory class adds (not pre-registered)

The pre-registered swap classes leave the rest of the reply as it was, so the tokens after a swap are
scored in a context they were not chosen for, and the drift costs more than the swap. An adversary who
swaps one token and then lets the model continue (`*-1-redecode`) is accepted **91-95 %** of the time
under the shipped limits and under `fit_limits.py`'s fitted limits, both of which have cap = 1: the one
token above C is free (`cp_verify` prints this as `above-clip=1`), and the honest continuation is cheap.
cap = 0 stops the random-token version (0-2 %), not the second-choice one (58 %, 19-67). So most of what
the swap classes measure above is detection of the *inconsistency* after a swap, not of the swap itself.
A provider that controls decoding can change one token per reply under cap = 1 limits and pass.

## cp_verify spot checks (released sources at the base commit, CPU)

`cp_verify_spot.json`. cp_verify built from this tree (`build=ea191b01...`; the fork's #27 changed
verifier sources, so it differs from the examples' printed 93afdaf5...). All calls use the stored proof of
`examples/accepted-proof-clipped-gap`; no proof was made for any attacked reply.

| kind | calls | result | what a NO here shows |
|---|---|---|---|
| control: stored files, shipped policy | 1 | `WITHIN LIMITS` (exit 0) | n/a |
| binding spot check: one attacked reply per class for 19 of the 21 classes (all but rand-2 and rand-8; incl. both exploratory), built from the stored reply.json; the 12 model-built ones scored too, beside the stored proof | 19 | 19 x `NO: proof-refused` (exit 1) | the proof is bound to its own reply. **Not** a rejection by the limits: 2 of these replies (both redecode) meet the shipped limits by score and are still refused, because the proof is for another reply |
| policy-named: stored honest files, `-policy` naming tighter limits or exact match | 4 | 4 x `NO: policy` (exit 1) | the verifier refuses a policy other than the one the commitment ID fixes. **Not** a rejection by the limits either |

So the verifier never got to compare an attacked reply's costs with the limits: that needs a proof for
that reply, which the honest prover refuses to make when the limits are broken.

## Files

- `numbers.json`: per seed and grid point `[accepted, n, no_proof]` per class; aggregate median / SD /
  min / max; verdicts; the cp_verify spot rows. No window failed a range condition (`no_proof` = 0 throughout).
- `cp_verify_spot.json`, `spot_replies.json`: the 24 cp_verify calls and the model-built attacked replies
  of the stored example with their costs.
- `raw/seed*.json.gz`, `raw/redecode*.json.gz`: prompts, honest replies, every attacked reply and its
  per-token costs (logit gap + 2^sh). These are functions of the synthetic weights; with secret weights
  such costs must not be published (score_reply.py's own warning).
- `SHA256SUMS`.

Reproduce: `experiments/20261103-6-clipped-gap-rejection/RESULTS.md` has the commands.
