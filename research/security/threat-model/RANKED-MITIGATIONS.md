# Ranked mitigations

Ranked by (risk closed) / (cost). Costs are **inferred** engineering estimates, not measured.
Type: **code** (this repo's programs), **protocol** (what the ID / proof / envelope binds), or
**out of scope** (policy, provenance, process the protocol cannot enforce).

## M1. Pin the commitment to a signed, public checkpoint hash (provenance manifest)

- **What:** publish, next to each commitment ID, a manifest signed by the party that vouches for the
  model: upstream publisher + repo + revision, SHA-256 of every weight file actually committed,
  conversion tool + version (GGUF quantizer, `weight_sums`, `scales/` commit), `policy.txt`/`KL.bin`/
  `layout.txt` digests, the `-public-weights` 32-byte file if public, and the resulting ID. For public
  weights, anyone can recompute the ID from the manifest (`prover/common/public_weights.h:6-13`), so a
  signature on the manifest becomes a signature on the ID. Binding the manifest digest into the
  configuration itself is **not available today and untested**: the configuration files are hashed
  byte for byte, but the parameter-file syntax says the frame lines take "No blank line, comment or carriage return"
  (`verifier/docs/parameter-file.md:39`), and PR #41's comment control (appended to `layout.txt`)
  ended `NO: model-statement`. That shows the bytes are bound, not that a comment-bearing file is
  usable. Binding it in would need a parser or format change.
- **Closes:** A2 (supply chain swap after vetting), A3 (adapter swap), A6 (MITM on the ID) as far as
  the signature key is trusted; gives sleeper defenses (vetting, scanning) a fixed object to vet.
- **Does not close:** a backdoor in the vetted checkpoint itself; a malicious signer.
- **Cost:** low. Manifest format + a `tools/` script to recompute and compare; signing with an
  existing scheme (Sigstore / minisign / SSH signatures). About 1-2 days for the detached manifest.
  An in-configuration binding would be extra and is not costed.
- **Type:** protocol (manifest) + small code (tool). Fits under #9's envelope work.

## M2. Bind tokenizer, chat template, system prompt and end tokens into the manifest and the client check

- **What:** the manifest of M1 also carries hashes of the tokenizer files, the chat template, any
  fixed system prompt, and `generation_config.json` end tokens. The example client rebuilds the
  window from its own message + the hashed template, and refuses (does not just downgrade to exit
  24) if the server's `prompt_token_ids` differ. Today the client already compares
  (`integrations/ask_and_check.py:355`); this gives it an authenticated template to compare against.
- **Closes:** C4, the provider-chosen system prompt as a trigger channel; truncation via end-token
  substitution; tokenizer swap.
- **Cost:** low to medium. 2-3 days in `integrations/`.
- **Type:** protocol (manifest fields) + code (client). Overlaps #9 ("tokenizer/template/config/
  operator versions" in the envelope).

## M3. Vet and attest the exact integer artifact, with reproducible conversion

- **What:** treat the committed object (integer weights + `KL.bin` + `policy.txt`) as the unit of
  vetting. Require the conversion from a publisher-signed fp16 checkpoint to the committed integers
  to be reproducible by a third party (pinned quantizer, pinned calibration set, deterministic
  `scales/`), so a vetter can regenerate it and get the same ID. Run behavioral evals and any
  backdoor scans on the **integer model** (the CPU integer-model package already evaluates it,
  `experiments/20261103-model-identity/RESULTS.md`), not on the fp16 parent.
- **Closes:** quantization-activated backdoors (Egashira et al. 2024, 2025, cited) introduced by a
  third-party quantizer; makes A2 visible. Does not close a backdoor that is already in the fp16
  model.
- **Cost:** medium to high. Deterministic scale fitting and an independent conversion run per model;
  integer-model eval runs on CPU are slow at full size. 1-2 weeks for one model.
- **Type:** out of scope for the proof (process + provenance), with code support in `scales/`.

## M4. Exact decode check instead of clipped gap for anything safety-relevant

- **What:** for high-assurance use, accept only exact match (`C=theta=256`, `cap=0`). Use integer
  serving so served replies are the integer model's greedy choices (`docs/architecture.md:141-146`).
  Treat `WITHIN LIMITS` as "close to the model", never "the model's answer".
- **Closes (by design, not measured):** the clipped-gap steering channel and the sleeper stack
  (CODE-CHECKS C5). The evidence for the channel is unreplicated and on the honest-prover path:
  one-swap acceptance 15/16 and 13/16 under shipped limits (PR #51, open, approved, unmerged) and
  5/54 steered (PR #50, merged, main `a6c5a8e6`). Under exact match the honest prover refused all 57 changed steered replies in
  #50, so `cp_verify` never judged an out-of-limits proof; that exact match also stops a cheating
  prover is the design and the premise of the Lean soundness theorem, which covers exact match only
  (`docs/protocol.md:53`).
- **Does not close:** a strong backdoor, which is the top choice anyway; sampling (exact match is
  greedy only).
- **Cost:** medium. No protocol change (policy already exists). Cost is operational: integer
  serving is slower than fp serving and diverges from fp16 at about 6.81 % of positions
  (`docs/limits.md:2760-2765`, reported there from an outside Python implementation of the integer model, `docs/limits.md:2783-2789`). A middle ground short of exact match has to tighten
  **both** limits, because they carry different acceptances (CODE-CHECKS C5): `cap=0` would remove
  #51's cap-carried swaps (all 13 accepted random-token swaps, 3 of 15 float-second-choice), but not
  #50's 5 steered acceptances, which have `above-clip=0` and pass on the theta mean bound alone, nor
  the 12 of 15 #51 swaps that stay under C. Those need a lower theta (and a lower C, since theta's room
  grows with reply length). Not tested; where such a point sits between "no free branch" and false
  rejections of honest replies is unknown.
- **Type:** policy choice (client side) + documentation. Holds up: yes, the evidence supports it.

## M5. Reproducible verifier build and a client-held manifest of what to accept

- **What:** publish a reproducible-build digest for `cp_verify` (and the Lean `verify` export),
  and a client config that fixes: expected ID (from M1), expected policy, expected template (M2),
  and the verifier digest. Reject any check that was not run by that binary.
- **Closes:** A5 (colluding or lazy verification service), the FS lane's "verifier binary not
  identified by the transcript" (`research/security/fiat-shamir-attacks.md:20-21`).
- **Cost:** medium. Reproducible C++ builds need pinned toolchains; the repo already pins nvcc for
  the prover (`prover/build.sh:9`). 3-5 days.
- **Type:** code + process.

## Considered and not ranked

- **Backdoor scanning inside the protocol.** Out of scope and cannot be complete: Goldwasser et al.
  2022 (arXiv 2204.06974) construct backdoors undetectable under standard assumptions (cited).
  Scanners belong in M3's vetting step as one signal, never as a protocol guarantee.
- **Behavioral canaries.** Cheap and worth running per commitment (fixed prompts with known answers,
  including date-shifted and trigger-style variants), proved under exact match, results published
  with the ID. Weak against sleepers by design: Hubinger et al. 2024 show the behavior survives safety
  evals (cited). Useful as a tripwire for M3, not a defense.
- **Activation probes** (Anthropic 2024, "Simple probes can catch sleeper agents"): need hidden
  states, which FlashProve hides on purpose (weight and activation hiding). Could be done by the
  provider on its own model as part of M3; not a client-side check.
- **Training attestation** (proof or TEE attestation of the training run): closes data poisoning in
  principle; research-grade, orders of magnitude costlier than inference proofs. Out of scope.
- **TEE attestation of the prover host** (A7): separate verdict, tracked in #9.

## Proposed claims (none added to research/results.yaml or loop/claims.json)

1. (read) "The commitment ID binds the integer weights and configuration, not any upstream
   checkpoint; a valid proof of a backdoored model verifies." Evidence: `blocks/frame/heads.h:78-99`,
   this directory.
2. (from merged PR #50 and open, approved, unmerged PR #51, both unreplicated, honest-prover outcomes) "Under the shipped
   clipped-gap limits, a rank-2 harmful branch can be proved with one swap." Second half (by design /
   inferred, not measured): "under exact match it cannot."
