# Threat model: who attacks a proof of execution, and what the proof does about it

Part of #6, tracking #53. Base commit `ce4ceef0`. Research only. Every number is labelled
**measured** (run in this repo, with the PR or file that holds it), **cited** (from a paper or an
external README) or **inferred** (reasoned here, not run).

**About PR #50 and PR #51.** Figures quoted from them are from **open, unmerged PRs** (each had a
CHANGES REQUESTED review; fixes were pushed and are not yet re-reviewed) and are **unreplicated**.
Checked here against #50 at `b645f670` and #51 at `0c93d0ea`. They are **honest-prover outcomes
only**: every reply outside the limits was refused by the honest `cp_prove`, so `cp_verify` never
judged an out-of-limits proof. A count like "0 of 57 accepted under exact match" describes the
honest prover's refusals, not a verifier stopping a cheating prover. That exact match closes a
channel is **by design** (and the premise of the Lean theorem, `docs/protocol.md:53`), not measured.

## The one sentence

FlashProve proves a relation: "the committed integer weights, under the committed configuration,
run on this token window, give these checked tokens (exact match) or tokens within these limits
(clipped gap)" (`docs/protocol.md:25-55`). It says nothing about whether those weights are safe,
whose they are, or what they were trained to do. **A valid proof of a backdoored model is a valid
proof of a malicious answer.** Execution integrity and weight safety are separate properties, and
only the first is in scope of the cryptography.

The repo already states the provenance half of this: "Acceptance does not tell you: Whose weights
they are, or whether the model is any good" (`docs/protocol.md:63`), and "The ID does not say whose
weights the table contains. That an ID belongs to a model of some name is its publisher's claim,
outside the protocol" (`blocks/frame/heads.h:88-89`). This document extends that to adversaries who
exploit the gap deliberately.

## What is bound, and what is not (read from the code)

| Input | Bound by the commitment ID or proof? | Evidence |
|---|---|---|
| Integer weights (anchor table root, shape, OOD seeds and answers) | Yes, by design; no binding theorem for the released programs | `blocks/frame/heads.h:78-99` (`published_id`); `docs/limits.md:169-174` (binding of weights to the ID "has not been shown" for the programs, row LIM-2) |
| `policy.txt`, `KL.bin`, `layout.txt` (shape, scales, acceptance policy) | Yes, byte for byte | `blocks/frame/heads.h:66-76` (`configuration_digest`); measured 5/5 rejection per mutation incl. a comment-only control, `experiments/20261103-fiat-shamir-binding/RESULTS.md` (PR #41) |
| Request tokens (prompt + reply + padding) and range r:e | Yes, in the transcript before the first challenge | same RESULTS.md, prompt/reply/range rows, 5/5 first-challenge change (measured) |
| Next token `y` | Yes, but only at the output-head segment (deferred) | same RESULTS.md, next-token row: first challenge unchanged 5/5, rejected later (measured) |
| Tokenizer, chat template, end-token ids | **No** | `docs/architecture.md:223`; `docs/operators-duties.md:682-685` (row R33) |
| System prompt / any server-added tokens | **Only as tokens.** The proof binds whatever IDs are in the window; it does not say who chose them | `docs/operators-duties.md:681-683`; `integrations/ask_and_check.py:10-12` (with `--chat` the server chooses prompt IDs, best exit 24, never 0) |
| Sampling (temperature, seed, top-p) | **No.** "Sampling is not checked under any policy, because a request carries no random seed" | `docs/protocol.md:43` |
| Client identity, time, freshness | **No** | `docs/limits.md:351-367` |
| The verifier binary and built-in constants | **No**; a manual format version stands in | `research/security/fiat-shamir-attacks.md:20-21,53` |
| Upstream checkpoint (e.g. a Hugging Face revision or publisher signature) | **No.** Nothing in the ID ties the integer weights to any upstream artifact | `blocks/frame/heads.h:88-89`; inferred from `published_id` inputs |

## Actors

Columns: **wants** / **FlashProve stops** / **FlashProve does not stop** / **CommitLLM** (from its
public README, cited, `github.com/lambdaclass/CommitLLM`, fetched 2026-11-04) / **evidence**.

### A1. Malicious provider (the party running inference)

- **Wants:** serve a cheaper model, a modified model, or a chosen answer while claiming the
  advertised one.
- **FlashProve stops:** under exact match and a commitment ID the client got out of band, a reply
  that is not the committed integer model's top choice at a checked position (by design; no theorem
  about `cp_verify` itself, `docs/limits.md:162-164`). From open, unmerged PR #50 (H100, synthetic,
  unreplicated, honest-prover path): under exact match the honest prover refused all 57 changed
  steered replies, so none got a proof. That is the policy at the prover; that `cp_verify` would also
  reject a forged one is by design, not measured.
- **Does not stop:** (a) committing to a bad model in the first place, the "worst case: the
  provider commits to a small model that gives the answer it wants" (`docs/limits.md:190-191`);
  (b) choosing the system prompt and template tokens, which the proof then faithfully binds;
  (c) under clipped gap, steering within the allowance: 5 of 54 changed steered replies proved and
  accepted `WITHIN LIMITS` (open PR #50, honest prover, unreplicated), one-swap-then-continue 15/16 and 13/16 (open PR #51, honest
  prover, unreplicated);
  (d) truncation, which verifies as a shorter reply (`docs/protocol.md:66`); (e) giving different
  clients different IDs, unless the ID is published in one shared place (`docs/limits.md:183-186`);
  (f) a client that takes the ID from the server.
- **CommitLLM:** binds a deployment manifest, prompt hash and sampling manifest (temperature, top-k,
  top-p, seed) into the receipt and checks decode exactly, including sampled decode via captured
  logits (cited). It does not verify arbitrary-position attention, and its README reports a
  "consistent fake-a" forgery passing 10/10 in its own toy harness (cited). Its key is built "from
  the public checkpoint", so a malicious provider cannot swap weights without a different key, but
  the checkpoint itself is still trusted.
- **Net:** FlashProve is strong against "swap the model at serve time" and weak against "chose a
  bad model, bad template or loose policy up front".

### A2. Malicious model publisher / supply chain

- **Wants:** get a backdoored checkpoint served under a trusted name.
- **FlashProve stops:** nothing about the backdoor. Once the provider commits to the poisoned
  weights, every proof is valid.
- **Does not stop:** everything. The commitment ID is computed from whatever integer weights the
  provider fed `cp_commit`. There is no field for an upstream hash, signature or lineage.
  Concrete case in our own repo: the Maverick example commits to **a third party's 4-bit GGUF
  conversion** (`unsloth/Llama-4-Maverick-17B-128E-Instruct-GGUF` at revision `41032e54...`,
  `examples/maverick/run.sh:73-75`, `examples/maverick/README.md:29-30`), pinned by SHA-256
  (`examples/maverick/weights.sha256`). The pin proves "these are the bytes we downloaded", not
  "these bytes are an honest quantization of Meta's weights". That is precisely the surface of the
  GGUF quantization attack (Egashira et al., ICML 2025, arXiv 2505.23786, cited; see SLEEPER.md).
- **CommitLLM:** same gap. "The verifier builds a key from the public checkpoint" (cited): it
  inherits whatever is in the checkpoint.
- **Mitigation lives outside the proof:** signed provenance from the original publisher to the exact
  integer artifact (RANKED-MITIGATIONS.md, M1 and M3).

### A3. Malicious fine-tuner / LoRA distributor

- **Wants:** publish an adapter or fine-tune that is helpful on benchmarks and harmful on a trigger.
- **FlashProve stops:** an adapter swap at serve time, if the client holds the base model's ID: a
  merged LoRA changes the weights and so the anchor and the ID (inferred from `published_id`
  inputs; #46 measured three different artifact fingerprints for three weight variants, but those
  are SHA-256 fingerprints, not commitment IDs, because CPU cannot run `cp_commit`).
- **Does not stop:** a provider who honestly commits to the merged fine-tune and publishes that ID.
  The proof is then a proof of the fine-tune's behavior, backdoor included.
- **Note:** FlashProve has no adapter mode; weights are one integer table. That is good here: there
  is no unbound "LoRA slot".

### A4. Malicious client

- **Wants:** extract weights, forge a "verified" claim about a reply the model never gave, or burn
  the provider's resources.
- **FlashProve stops:** forging a proof for a reply the model did not give (soundness, by design).
- **Does not stop:** (a) score leakage under clipped gap: "A client that chooses the checked tokens
  can measure the model's hidden scores over many requests. No theorem bounds this, no one has
  measured it, and none of these programs limits requests" (row LIM-23, `docs/limits-all-rows.tsv`);
  (b) replaying someone else's proof as their own, since proofs carry no client or time
  (`docs/limits.md:351-367`); (c) resource exhaustion with hostile files (`docs/limits.md:370`) or
  by consuming leaf-table openings (`docs/limits.md:2630-2643`).
- **Sleeper angle:** a malicious client who knows a trigger can obtain a **verified** harmful
  answer from an honest provider serving a poisoned model, and then publish "cryptographically
  proven that Model X said this". The proof is a credibility amplifier for the attacker
  (inferred). This is the cleanest statement of why integrity is not safety.

### A5. Colluding verifier / verification service

- **Wants:** say `YES` for a provider.
- **FlashProve stops:** nothing if the client delegates. `cp_verify` exit 0 alone is not
  acceptance (`docs/limits.md:237-265`), and the docs require building the verifier yourself
  (`docs/verifying.md:97-98`).
- **Does not stop:** a third-party "verified" badge. The binary is not identified by the transcript
  (`research/security/fiat-shamir-attacks.md:20-21`).
- **Mitigation:** reproducible verifier build with a published digest (M5).

### A6. MITM on weights or commitments

- **Wants:** substitute the commitment ID, the policy lines or the weights a provider downloads.
- **FlashProve stops:** substitution of configuration or ID once the client holds the right ID
  (measured 5/5 per case, PR #41).
- **Does not stop:** substitution before the client learns the ID. Docs say "never take it from
  files that arrive with a proof" (`docs/protocol.md:63`, `docs/verifying.md:36-46`) but there is no
  signed channel; the ID is a bare 64-hex string. On the provider side, the only check on weight
  files is a SHA-256 list that ships next to the download script (`examples/maverick/weights.sha256`),
  so whoever controls the repo or the download path controls both.
- **CommitLLM:** same; key from "the public checkpoint".

### A7. Compromised prover host

- **Wants:** exfiltrate weights or co-batched prompts; serve outputs from another model.
- **FlashProve stops:** serving another model's outputs under the honest ID (the proofs would fail
  against the published ID; `docs/limits.md:2637-2640` notes wrong-directory proofs fail at the
  first `cp_verify` with the right ID).
- **Does not stop:** confidentiality. The secret key directory unmasks weights
  (`docs/architecture.md:238-240`); an attacker with the host has the weights and prompts.
  Hiding evidence is partial (rows LIM-22.x to LIM-29). A compromised host can also re-commit to a
  poisoned model and publish a new ID: "no proof links it to the old one"
  (`docs/verifying.md:44-45`).
- **Mitigation:** TEE attestation is a separate verdict (#9), not a substitute.

## Bottom line per question Shadow asked

- **Threat actors:** FlashProve closes "the provider ran something other than what it committed".
  It does not close "what it committed was bad", "who chose the system prompt", "who chose the
  limits", or "who chose the ID the client trusts".
- **Sleeper LLMs:** entirely outside the proof. The only lever the protocol has is the commitment
  ID, and that lever is only as good as the vetting of the checkpoint the ID points to, plus the
  provenance chain from that checkpoint to the exact integer weights. See SLEEPER.md.
