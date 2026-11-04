# Security threat model: threat actors and sleeper LLMs

Part of #6. Research only, no experiment code, no GPU, no claims added to `research/results.yaml`.

Core question: FlashProve proves "the committed weights ran on this prompt and produced this reply."
A proof of correct execution of a backdoored model is a perfect proof of a malicious answer.
Integrity of execution is not safety of weights. This directory works out what that means for us.

Files (filled in as the lane progresses):
- `THREAT-MODEL.md`: actors, what FlashProve stops, what it does not, evidence with file:line.
- `SLEEPER.md`: sleeper agents and backdoors mapped to commitment / proof / extra layers.
- `CODE-CHECKS.md`: specific checks against this repository.
- `RANKED-MITIGATIONS.md`: top five mitigations with cost and type.

Labels: every number is marked measured, cited or inferred.
