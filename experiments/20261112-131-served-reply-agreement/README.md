# Served BF16 replies vs float64 and XS18 / XS20 token picks (abliterated Qwen3.8-27B, CPU, no proof)

Issue #131, part of #8, tracking #32. PREREG: [PREREG.md](PREREG.md) (first commit 989fd6d, alone). Results: [RESULTS.md](RESULTS.md). Builds on PR #124 (`../20261111-8-qwen-e2e-agreement/e2e.py`), PR #88, PR #74 and PR #68 (all on main); their code is imported unchanged.

## What this is, in plain language

PR #124 showed that the integer DeltaNet heads (arms XS18, XS20) pick the same next token as a float64 reference almost everywhere, on fixed prompts. It never looked at text a real serving stack generated. Here, an attested H200 serving deployment (vLLM, BF16) of the same pinned abliterated checkpoint generated short greedy replies to 10 harmless prompts. Each reply is fed back, token by token, through the float64 CPU forward and the XS18 / XS20 paths, and at every reply position we ask: does each path pick the token that was served?

**Nothing here is proved.** No proof is built or verified. The integer arms are numerical lowerings, not sound proof-ready relations.

- **What is lowered:** only the DeltaNet head computation (conv, SiLU, q/k L2 norms, gates, delta-rule recurrence, gated RMS norm) in all 48 DeltaNet layers, as PR #124.
- **What stays float64:** in_proj, out_proj, the 16 full-attention layers, every MLP, every RMSNorm, the final norm and lm_head.
- **Served side:** the model identity (repository, revision, dtype, engine image) is as reported by the deployment's configuration; it is not independently hashed. The route returns text, `finish_reason` and `usage` counts, no token ids and no logprobs.
- **Token ids:** rebuilt from text with the pinned tokenizer and chat template (thinking disabled, see PREREG "Template probe"). A prompt counts only if the rebuilt prompt and reply counts equal the served counts. Equal counts are necessary, not sufficient.
- **Two registered bins, kept apart:** a miss where float64 itself disagrees with the served token is counted in the bin the PREREG names "serving precision". A miss where float64 agrees with the served token and XS18 / XS20 does not is counted as "lowering". The first name is descriptive, not a causal attribution: the bin holds every served-vs-float64 mismatch whatever its cause (BF16 arithmetic, engine kernels or batching, a weights or configuration difference, or an error in the rebuilt token ids cannot be told apart through this route). Result: four shared served-vs-reference mismatches, consistent with a serving-precision difference but not causally attributed; zero additional XS18/XS20 top-1 mismatches relative to REF on these inputs.
- **What a verifier would recompute:** not applicable, there is no proof.
- **Not covered:** stock checkpoint; sampled (non-greedy) replies; replies over 64 tokens; integer in_proj / out_proj / attention / MLP / lm_head; harmful prompts; whether abliteration changes behaviour.

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration and amendments |
| `prompts-served.json` | the 10 frozen user messages |
| `served_route.py` | sends the bounded batch to the serving route (endpoint, key, model from the environment, never logged); keeps only the attestation `verified` flag, reply text, finish_reason, usage and wall time |
| `rebuild_ids.py` | rebuilds prompt and reply token ids, applies the registered inclusion rule -> `runs/served-ids.json` |
| `served_e2e.py` | the CPU forward: imports PR #124's `e2e.py` and runs its abl leg on the served sequences with paths REF, XS18, XS20 (+ REF#2, XS18#2 on q01, q02) -> `runs/forward.json`; `fixture` = timing/debug on the template-probe sequence (not a suite prompt) |
| `run_served.sh` | the registered run under its hard stop (through the big-memory lock and `fp-heavy.sh`) |
| `summarise_served.py` | the bars, the three-way per-prompt table, every disagreement with REF's top-2 margin -> `runs/summary.json`, `runs/summary.md`. Since the review fix it refuses to write a summary unless the determinism record is complete: exactly layers 0 to 63, exactly the four registered duplicate keys per layer, boolean values (PREREG Amendment A-1). Optional argument: a runs directory, so it can be run on a copy |
| `test_summarise_served.py` | checks that guard on temporary copies of the committed run files: the unchanged copy gives a byte-identical summary, 9 incomplete or malformed records are refused, a complete record with a false equality gives "NOT DETERMINISTIC" -> `runs/summariser-guard-check.json` |
| `check_manifests.py` | sha256 of every fetched tensor vs PR #124's committed manifests -> `runs/manifest-check.json` |
| `time_summary.py`, `env.py`, `add_results_row.py` | run-time fields, `ENV.json`, the `research/results.yaml` row |

Changes relative to PR #124's code (made in `served_e2e.py`, `e2e.py` itself is unchanged): `PATH_ORDER` set to REF, XS18, XS20, REF#2, XS18#2 (no BF16H); only the abl leg (no stock leg); input sequences from `runs/served-ids.json` instead of `prompts-e2e.json`; no p01 " Tokyo" sanity check (the registered sanity check is float64 vs served >= 80%); output `runs/forward.json`.

## Reproduce

The CPU part, from this directory, with a scratch directory `$X` outside the repo, cores 0 to 5, Python 3.12, numpy 2.4.3, network access to huggingface.co:

```
python3 rebuild_ids.py <dir with pinned tokenizer.json + chat_template.jinja> runs/replies.jsonl prompts-served.json runs/served-ids.json   # needs jinja2 + tokenizers 0.23.3
fp-heavy.sh bash run_served.sh $X        # about 40 min on 6 cores of a shared VM; resumes from $X/ckpt.npz
python3 summarise_served.py
python3 check_manifests.py
python3 test_summarise_served.py         # seconds, CPU only, works on temporary copies; exit 0 = guard behaves as stated
```

The served replies (`runs/replies.jsonl`) cannot be regenerated without access to a serving deployment; `served_route.py collect prompts-served.json <out>` with `BRIDGE_URL`, `BRIDGE_KEY_FILE`, `BRIDGE_MODEL` set is how they were collected. `run_served.sh` has a registered wall-clock stop; edit its cap to rerun at another time.
