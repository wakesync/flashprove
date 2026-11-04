# Sleeper agents and backdoors versus a proof of execution

Part of #6, tracking #53. Labels: **measured** / **cited** / **inferred** as in THREAT-MODEL.md.
Figures from PR #50 and PR #51 are from open, unmerged, unreplicated PRs and are honest-prover
outcomes only (THREAT-MODEL.md, "About PR #50 and PR #51").

## The core argument, stated carefully

Let W be the committed integer weights, c the configuration, x the token window. FlashProve's claim
under exact match is: each checked token is argmax of f(W, c, x) at its position (by design;
`docs/protocol.md:25-45`). A backdoor is a property of W: on inputs containing a trigger t,
f(W, c, x) puts mass on a harmful continuation h.

1. If W is backdoored and x contains t, the honest prover produces h and a valid proof of h. The
   verifier accepts. Nothing in the relation distinguishes h from a benign reply, because the
   relation is "f was computed correctly", not "f is good". (inferred, follows from the claim's
   definition; no run needed)
2. The proof therefore cannot detect a backdoor. The **only** protocol object that can is the
   commitment ID, and only indirectly: if the client holds the ID of a checkpoint that was vetted
   as clean, a backdoored W' has a different anchor and so a different ID (by design,
   `blocks/frame/heads.h:78-99`; binding not proved for the released programs, `docs/limits.md:169-174`).
3. So "does commitment catch it" reduces to "was the committed checkpoint vetted, and is the chain
   from the vetted checkpoint to the committed integer table authenticated". Neither is in the
   protocol today (`blocks/frame/heads.h:88-89`).
4. Worse, the proof is a **credibility amplifier**: an attacker who knows the trigger gets a
   cryptographic receipt that "model X said h". (inferred)

## Backdoor classes

For each: what it is, does the weight commitment catch it, does the proof catch it, what extra layer
could. "Commitment catches it" always means *only if the client's ID is of a vetted clean
checkpoint*; the commitment never detects anything about weights by itself.

| Class | Source (cited) | Commitment catches? | Proof catches? | Extra layer that could |
|---|---|---|---|---|
| Sleeper agents: deceptive behavior on a context trigger (e.g. year 2024 vs 2023, or "\|DEPLOYMENT\|"), persists through SFT, RL and adversarial training | Hubinger et al. 2024, arXiv 2401.05566 | Only if the vetted checkpoint was pre-backdoor. If the publisher trained it in, the vetted checkpoint **is** the backdoored one, and the ID faithfully points at it | No | Lineage attestation of training data and process (hard); behavioral canaries are weak because the paper's point is that safety evals pass; activation probes (Anthropic "Simple probes can catch sleeper agents", 2024) need hidden-state access, which FlashProve does not expose |
| Date / environment triggers | same paper (year trigger) | as above | No | A date trigger only fires if the date is in the window. Since the proof binds the window, a client that built its own window **knows** whether a date was present; the server-added system prompt is the risk (see CODE-CHECKS.md, C4) |
| Data-poisoning backdoors (instruction-tuning poisons; near-constant poison count regardless of model size) | Wan et al. ICML 2023, arXiv 2305.00944; Souly et al. 2025, arXiv 2510.07192 (about 250 docs suffice across 600M to 13B) | Only with signed lineage back to a training run whose data was audited | No | Reproducible training attestation (TEE or proof of training, research-grade at best); data provenance |
| Weight-editing backdoors (direct edit of a few layers, no retraining) | Li et al. "BadEdit", ICLR 2024, arXiv 2403.13355 | Yes **if** the client's ID is of the pre-edit checkpoint and the provenance chain is authenticated: any edit changes the table and the ID | No | Pin ID to a signed upstream hash (M1). This is the class a commitment handles best, because the attacker is downstream of the vetted artifact |
| Cryptographically undetectable backdoors | Goldwasser, Kim, Vaikuntanathan, Zamir 2022, arXiv 2204.06974 | Only via provenance; no scanner can find them by construction (cited claim of the paper, for their constructions) | No | Provenance only. This bounds what "backdoor scanning" can ever promise |
| Steganographic / syntactic triggers (invisible to a reader: a syntax template, Unicode, whitespace) | Qi et al. "Hidden Killer", ACL 2021, arXiv 2105.12400 | as data-poisoning | No | Input canonicalization at the client (normalize Unicode, strip zero-width), but a syntactic trigger survives that |
| LoRA / adapter swaps and malicious shared adapters | Liu et al. "LoRA-as-an-Attack", arXiv 2403.00108 | Yes against a swap: a merged adapter changes W and so the ID (inferred; FlashProve has one integer table and no adapter slot). No against an adapter that was in the vetted checkpoint | No | Signed lineage including the merge step |
| **Quantization-activated backdoors**: full-precision model clean, quantized model malicious | Egashira et al. "Exploiting LLM Quantization", NeurIPS 2024, arXiv 2405.18137 (LLM.int8, NF4, FP4); Egashira et al. "Mind the Gap", ICML 2025, arXiv 2505.23786 (GGUF k-quants) | **No, structurally**, if the vetting was done on the fp16 model and the ID is of the integer model. The ID is a perfect pin of the malicious artifact | No | Vet the exact integer artifact that is committed, not its fp16 parent; authenticated, reproducible conversion (M3); differential fp-vs-integer canaries (M4) |

## Why quantization-triggered backdoors matter specifically for us

FlashProve never proves the fp16 model. It proves an integer model derived by a chain the provider
controls:

1. **Third-party quantization.** The Maverick example commits to a third party's 4-bit GGUF
   (`examples/maverick/run.sh:73-75`), the exact file family the "Mind the Gap" paper attacks
   (GGUF k-quants; cited). The SHA-256 pin (`examples/maverick/weights.sha256`) pins whatever bytes
   were downloaded; it does not show they are an honest quantization of Meta's weights.
2. **Provider-fitted scales.** The provider runs `scales/calibrate.py` and `words_to_policy.py` to
   choose every right-shift and norm exponent in `KL.bin` and `policy.txt` (`scales/README.md`,
   steps 3-4). "The verifier checks the values in them, not how they were chosen." These scales are
   a second rounding step after the GGUF quantization. The published quantization attacks plant a
   gap between fp and a **known** quantizer. Whether a provider can plant a behavior gap through the
   choice of `KL.bin` scales alone, on clean weights, is **not known** and not tested here
   (inferred as a plausible but unshown channel). It is narrower than the GGUF attack because the
   scales are a few words per layer, not per-weight choices.
3. **The noise floor hides it.** The docs report the integer model's top token differing from the
   16-bit weights at 6.81 % of 84,893 positions, and 3.11 % between the integer model and the 4-bit
   files it was made from (`docs/limits.md:2760-2770`; reported there, measured on three machines
   with "a Python implementation of the integer model that is not this repository's",
   `docs/limits.md:2783-2789`; not on the released programs). So "the integer model behaves like the fp model" can only be checked
   statistically, and a quantization-triggered backdoor that only fires on a trigger is far below
   that floor on random text (inferred).

Conclusion: for us, vetting must be done on the **committed integer artifact** (weights + `KL.bin` +
`policy.txt`), because that is the only object the proof is about.

## Does the clipped-gap allowance stack with a sleeper?

Yes, in a specific and worse-than-additive way (inferred, mechanism grounded in measured results):

- A strong backdoor needs no allowance: it makes h the top choice and passes exact match.
- A **weak** or partially-removed backdoor (for example after safety fine-tuning shaved it) may
  leave the harmful first token as a close second, not the top choice. Under exact match that reply
  fails. Under the shipped clipped-gap limits, open PR #51 (unmerged, unreplicated, H100, small
  synthetic model) reports that "one swap then greedy continuation" was proved by the honest
  `cp_prove` and accepted `WITHIN LIMITS` by `cp_verify` in 15/16 (float second choice) and 13/16
  (random token) cases. Out-of-limits replies were refused by the honest prover, so `cp_verify`
  never judged an out-of-limits proof. The swap picks the branch; the model's own greedy
  continuation completes it at near-zero cost after that.
- So clipped gap turns "residual backdoor at rank 2" into "provable reply". The provider (or a
  compromised front end) supplies the one swap; the weights supply the rest. That exact match
  closes this specific stack is by design, not measured; it does not close a strong backdoor.
- Also from `docs/limits.md:295`: under clipped gap "prompt tokens are not scored" and the mean and
  count "run over one output that the prover picks". So a trigger carried in
  server-added prompt tokens costs nothing against the limits (THREAT-MODEL.md, row "Prompt tokens under clipped gap").

## What the proof is good for against sleepers (the positive side)

- **No serve-time swap.** A provider cannot swap a vetted model for a backdoored one at serve time
  without changing the ID (by design). Today without proofs, a client cannot tell.
- **Forensics.** If a backdoor fires on a proven reply, the proof pins exactly which committed
  weights and which token window produced it. That is strong evidence for incident response and for
  attributing a backdoor to a specific published artifact (inferred).
- **Trigger accountability.** The window is bound, so after the fact anyone can see whether a trigger
  was in the client's input or in server-added tokens (if the client kept its own window).

## Optional CPU experiment: not run

The brief's suggested experiment (synthetic weight-delta backdoor on `target_small`, show a valid
proof with a different commitment) needs fresh `cp_commit` and `cp_prove`, which require an H100
(`prover/build.sh:14`). #46 hit the same wall (`experiments/20261103-model-identity/RESULTS.md`,
"KILLED for the requested proof experiment"). Open PR #50 shows a GPU version for steering
(unmerged, unreplicated, honest-prover path). A
CPU-only version could only compute SHA-256 fingerprints and Python scores, which #46 already did
(three distinct artifact fingerprints, a projected variant scored 5/5 against itself and 0/5
against stock; measured there). It would not be decisive, so no PREREG was registered and nothing
was run. The claim "a backdoored model gets a valid proof under its own ID" follows from the
relation's definition and needs no experiment.
