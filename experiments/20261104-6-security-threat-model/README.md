# Security threat model: threat actors and sleeper LLMs

Part of #6, tracking #53. Research only: no experiment code, no GPU, nothing added to
`research/results.yaml`. Base commit `ce4ceef0`.

Core point: FlashProve proves "the committed integer weights ran on this window and gave these
checked tokens." A proof of correct execution of a backdoored model is a perfect proof of a
malicious answer. Integrity of execution is not safety of weights.

- `THREAT-MODEL.md`: what is and is not bound; seven actors; FlashProve vs CommitLLM.
- `SLEEPER.md`: backdoor classes mapped to commitment / proof / extra layer; why
  quantization-triggered backdoors matter for an integer-model prover; clipped-gap stacking.
- `CODE-CHECKS.md`: C1-C7 against this repo with file:line evidence.
- `RANKED-MITIGATIONS.md`: top five with cost and type, plus rejected options.

Labels: every number is marked measured (with the PR or file), cited (paper / external README) or
inferred. No new measurements were made in this lane; the optional CPU experiment was judged not
decisive (SLEEPER.md, last section) and not registered or run.
