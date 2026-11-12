# Results: hidden-root window handoff (issue #93)

**PASS against the pre-registered H1-H4, measured and unreplicated.** This is a construction plus tests on the D8/F12/C2 synthetic research prototype. It is not a soundness level, not zero-knowledge, and says nothing about real weights.

## Plain-language result

In merged #98 the two chunks shared one proof, and the starting state was tied to a SHA-256 root whose full opening (the state itself) was given to the verifier and checked outside the proof. Here every window is its own proof. Inside that proof, the prover opens a field-native hash commitment of the window's starting state, history and a private salt, runs the recurrence from those exact cells, and recomputes the commitment of its final state, history and salt. The verifier gives each window only its own public statement, the commitment it got from the previous window (or the verifier-held initial root for window 0) and the commitment the prover claims as output. No boundary state is ever handed to the verifier. A chain of 3 windows is accepted only if every window verifies and the count matches the verifier's statement.

## Binding chosen, and why

- **Choice:** a Poseidon-shaped sponge over Goldilocks (width 12, rate 8, capacity 4, x^7 S-box, 8 full + 22 partial rounds, Cauchy MDS, SHA-256 counter constants). Capacity is initialised from a SHA-256 of the public context (F, D, C, N, request, layer, policy, boundary index, model and weights labels), computed by the verifier natively. The intent is context separation: assuming the sponge is binding (collision resistant) and the proof system is sound, both unproven here (no hash-security level, no soundness level), a commitment for boundary b of layer l under F12 could not be opened as boundary b' or layer l' or F13. The suite only shows that the registered cases of that kind (`other_window_commitment`, `other_layer_state`, `mixed_F_chain`, the chain splices) were rejected, not that no such opening exists.
- **Why:** SHA-256 inside this product/affine proof needs bit decomposition of every 32-bit word; an x^7 sponge is 4 product columns per S-box with all linear layers folded into affine relation terms.
- **Not established:** these sponge parameters are not the vetted Plonky2 instance and have had no cryptanalysis. They are a research stand-in. The suite checks an independent Python implementation (`fixtures.py`) against the in-circuit one on every honest window (15/15 agree).

## Registered outcomes (seeds 201-205, D8, F12, C2 tokens per window, N=3 windows)

Raw: `runs/suite.jsonl` (every row), `runs/summary.json`, `runs/counts.json`, `runs/build.json`, `ENV.json`. Slot granted 2026-11-11T23:26:22Z, suite finished 23:30:53Z (budget 40 min).

Acceptance is per instance by the standalone window verifier (separate process) or the chain verifier. "Violated" is a diagnostic: relations of the verifier's canonical relation that the hostile table breaks; rejection is decided by the full proof verifier, not by this count.

| Case | Accepted / instances | Violated relations median; SD; min..max | Rejected by |
|---|---:|---|---|
| honest_window (w0, w1, w2) | 15/15 | 0; 0; 0..0 | paired honest control |
| honest_window_hostile_path | 15/15 | 0; 0; 0..0 | paired control: honest witness through the hostile prover path |
| honest_layer4_window | 5/5 | 0; 0; 0..0 | paired control: layer-4 window 1 under its own statement |
| honest_chain (3 windows) | 5/5 | n/a | paired honest control |
| tampered_boundary_state | 0/5 | 4; 0.447; 4..5 | proof verifier |
| tampered_boundary_history | 0/5 | 4; 0; 4..4 | proof verifier |
| tampered_output_commitment | 0/5 | 1; 0; 1..1 | proof verifier |
| state_from_other_window | 0/5 | 20; 0.894; 18..20 | proof verifier |
| other_window_commitment | 0/5 | 20; 0.894; 18..20 | proof verifier |
| other_layer_state | 0/5 | 8; 0; 8..8 | proof verifier |
| mixed_F_chain (F13 window under F12) | 0/5 | 175; 0.837; 174..176 | proof verifier |
| replayed_earlier_window_witness | 0/5 | 652; 0; 652..652 | proof verifier |
| truncated_chain_relabel (descriptor N=2) | 0/5 | 8; 0; 8..8 | proof verifier |
| replayed_earlier_window (chain, w1 proof in slot 2) | 0/5 | n/a | proof verifier at slot 2 |
| dropped_middle_window (chain, w0, w2) | 0/5 | n/a | proof verifier at slot 1, and verifier-held N |
| spliced_other_layer_proof (chain, layer-4 proof in slot 1) | 0/5 | n/a | proof verifier at slot 1 |
| truncated_chain (chain, w0, w1 of 3) | 0/5 | n/a | **chain-statement check outside the arithmetic** (verifier-held N=3); both supplied windows verify |

How the chain-level rejections happen: in `replayed_earlier_window`, `dropped_middle_window` and `spliced_other_layer_proof`, the rejected slot holds a genuine, internally consistent proof made for a different statement. Its relations are not violated. It fails because the verifier's Fiat-Shamir transcript header (statement, C_in and C_out of the slot) differs from the one the proof was made under, which in every rejected slot (20 slot rejections across those 15 chain instances; `spliced_other_layer_proof` fails at slots 1 and 2) shows up as the proof-of-work nonce check failing (`why` = "a nonce does not give the proof of work that its round asks for" in `runs/suite.jsonl`). So these are transcript-binding rejections by the proof verifier, under the toy coins (target 10, work 6), not relation violations. The window-level negatives instead fail the linear claim ("the masked message in the proof does not satisfy the linear claim"). `dropped_middle_window` is also caught by the verifier-held N.

All per-seed acceptance fractions have SD 0 (every seed identical). H1 (honest chains), H2 (all named negatives rejected), H3 (paired honest controls accepted) and H4 (counts) hold. Python and C++ commitments agree on all 15 honest windows. None of the verifier's non-proof inputs (statement, C_in, C_out) contains any full state row of S0..S3 (15/15 honest windows scanned); the proof files were scanned too, 0/15 contained a state row, but that is a diagnostic only, not a hiding claim.

## Cost (structure, n=15 honest windows, SD 0 for all counts)

Per window at D8/C2, built and matched by `count.py`:

| Quantity | Value |
|---|---:|
| core columns | 28986 |
| of which hash (2 commitments, 36 permutations) | 25704 |
| of which recurrence (2 tokens, no boundary pins) | 3024 |
| aligned columns | 29184 |
| affine relations | 48696 |
| of which hash | 42704 |
| range cells | 240 |
| proof bytes (median; SD; min..max) | 1805040; 283.1; 1804432..1805680 |

One permutation is 714 product columns (118 S-boxes x 4, plus 22 x 11 materialised partial-round lanes) and 1186 affine relations (118 x 8, plus 242 lane links). Each commitment adds 4 output pins. A boundary of D^2 + 9D + 1 words needs ceil((D^2 + 9D + 2)/8) permutations; each window commits twice.

Counted only, not built or proved (from `runs/counts.json`, formula in `count.py`):

| D | C | core columns/token | relations/token | hash share of columns | evidence kind |
|---:|---:|---:|---:|---:|---|
| 8 | 2 | 14493 | 24348 | 0.887 | built and matched |
| 32 | 2 | 137811 | 233022 | 0.855 | counted-not-built |
| 128 | 2 | 1860843 | 3155718 | 0.841 | counted-not-built |
| 128 | 64 | 334919.3 | 635536.2 | 0.146 | counted-not-built |

Compared with #98's joint proof (1645.5 core columns/token at D8/C2), the hash dominates at small windows. The boundary cost is fixed per window and amortises with the window length; at D128 it is about 15% of columns at C64. These are column/relation counts of this lowering, not bytes, memory, prover time or a device-fit estimate.

Timing, descriptive only (shared loaded host, cores 6-9, n=15 honest windows): prove 2.58 s median (SD 0.245, 2.45..3.43), verify 0.238 s median (SD 0.035, 0.215..0.347). No performance hypothesis was registered and none is claimed.

## What is NOT established

- No soundness level: research target 10 bits, work 6, deterministic toy coins (inherited). Booleans above are observations, not soundness estimates.
- The sponge is unvetted; collision/binding resistance of these parameters is assumed, not shown.
- Not zero-knowledge. "Hidden" means the verifier is never handed the state; the proof system may leak table values through openings. The private salt is intended to impede a verifier guessing a low-entropy state and checking the guess against the commitment. That is a design intent, not a demonstrated hiding property: no hiding or zero-knowledge guarantee is claimed.
- Window-0 trust: the initial root R0 is verifier-held, produced here by the trusted test harness from the synthetic state. How a real verifier obtains R0 (e.g. from an earlier proof or a published commitment) is out of scope.
- Truncation of a chain is rejected by the verifier-held window count, outside the arithmetic proof. No recursion or aggregation: the chain verifier runs N proof verifiers.
- Model and weights are synthetic labels in the context. No weight binding, projection, convolution or real-checkpoint claim.
- One head, D8/F12, C2, N3, five seeds, unreplicated. D32/D128 are counted, not built. No full five-seed independent replication: the round-1 reviews rebuilt the binary and spot-checked one seed only.
- No sponge security analysis or cryptanalysis of any kind, by the lane or its reviewers.
- Field-element binding, not byte binding. State, history and salt words enter the sponge as Goldilocks field elements (each value reduced mod P = 2^64 - 2^32 + 1). Two integers that differ by a multiple of P are the same word, so they give the same commitment and the same proof. A reviewer showed this on a deliberately crafted history outside the registered fixtures: `Hin[0,0] = -2^63+1` and `-2^63+1+P` gave the same commitment and an identical accepted proof ([astra review](https://github.com/wakesync/flashprove/pull/123#issuecomment-6810544514), descriptive). This is not a sponge collision and does not affect the registered trusted R0 (registered history values are in [-1000, 1000), salts in [0, 2^62)). Binding a history or salt as arbitrary signed 64-bit integers or bytes would need a canonical encoding or range constraints on those words. The incoming state cells are already range cells (|x| < 2^23); the history and salt words are not range-constrained.

## Deviations

PREREG amendment A1 (before the registered run): debug used N=3 (seed 909, D4, C1), S-box relation count is 8 not 7, extra honest layer-4 control, violation totals not per group. No threshold or seed changed. The debug binary and the registered binary are the same build (`binary_sha256` 44ea5702...). No registered run file was edited. After the registered run, `run.py` got one reproduction fix: the lane's wall-clock hard stop now applies only to the registered directory, so a later `--out` rerun is not killed at start. `runs/build.json` therefore pins the pre-fix `run.py` hash; `window.cpp`, `fixtures.py` and `count.py` are unchanged since the run.

**Overlapping lane attempts (provenance disclosure, added after round-1 review).** This lane ran as overlapping model attempts of the same lane on one working clone. The sequence, from the lane's notes and the git history:

1. Before registration, a retry attempt's own PREREG draft was overwritten in the working tree before it was ever committed. The registration is `f7f8cb9` exactly as pushed; nothing else was registered.
2. Code (`24f9594`, 23:24:57Z) and A1 (`07d6462`, 23:25:25Z) were committed and pushed. The registered binary was built from that tree at 23:26:17Z (`runs/build.json`, sha256 `44ea5702e87012341d51353162edfbb5f8a3bfe3abb187ba18624cb046aad4e0`), the suite ran 23:26:22Z to 23:30:53Z, and the receipts were committed in `d69013f` at 23:31:23Z.
3. After that, a second, still-running attempt of the lane worked in the same clone. In the working tree only, never committed or pushed, it rewrote the tracked `window.cpp`, `run.py` and `count.py`, added three untracked helper files (`chain.py`, `hr_hash.py`, `poseidon.h`), and recompiled the git-ignored `work/window.bin` from those edited sources, giving a different binary (sha256 prefix `305eec9b`). The backed-up copies keep their file times: the edited `count.py` is 23:33:20Z and `chain.py` 23:31:03Z (after the suite), while `hr_hash.py` and `poseidon.h` are 23:26:31Z, inside the suite window. Those two are untracked files that the committed `run.py`, `fixtures.py` and `window.cpp` do not import or include (`run.py` imports only `fixtures` and `count`). The suite hashes the binary again when it writes `ENV.json` at its end (23:30:53Z) and recorded 44ea5702, the registered value.
4. Not changed by the second attempt: `fixtures.py`, the shared `qwen_handoff`/`qwen_deltanet`/`qwen_deltanet_lookup` sources, PREREG, every committed file, and every receipt (`runs/suite.jsonl`, `runs/summary.json`, `runs/counts.json`, `runs/build.json`, `ENV.json`). Its edits were backed up outside the repository, the three tracked files were restored to the committed version, the untracked helpers were removed, and the binary was rebuilt from committed sources. That rebuild gave 44ea5702 again. The second attempt then acknowledged and stopped writing.
5. The committed registered evidence is: source at `07d6462` (the commit `ENV.json` records; all eight source hashes in `runs/build.json` match it and `d69013f`), receipts at `d69013f`. From `d69013f` to this head, `runs/` and `ENV.json` are unchanged, and the only source change is the 2-line `run.py` rerun fix above. Every metric in `research/results.yaml` pins `d69013f`.
6. Independent confirmation (reviewer numbers, descriptive, linked): both round-1 reviewers rebuilt the committed source with the recorded flags and got binary sha256 44ea5702e87012341d51353162edfbb5f8a3bfe3abb187ba18624cb046aad4e0 ([opus review](https://github.com/wakesync/flashprove/pull/123#issuecomment-6810412599), [astra review](https://github.com/wakesync/flashprove/pull/123#issuecomment-6810544514)). The astra reviewer's fresh one-seed rerun (seed 201) matched all 21 outcomes and 15/15 recorded proof sha256 hashes bit for bit. That is a spot check, not a replication.

Commit message note: the subject of `24f9594` ends "; PREREG A1", but that commit does not touch `PREREG.md`. A1 is `07d6462` alone. History is left as is (no rewrite).

Reproduction: `research/operators/qwen_hidden_root/README.md`.
