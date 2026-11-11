# PREREG: 20261111-6-substitution-suite
Issue: #6. Lane: subst6. Date (UTC): 2026-11-11T04:27Z. Base commit: 8d5793374ece39954b48b8a86f54e6bde1d193e5.

## Hypothesis
On the stored small CPU-checkable fixtures (`examples/accepted-proof`, `examples/accepted-proof-clipped-gap`, checked by `bin/cp_verify`, `integrations/check_proof.py` and `tools/manifest/manifest.py`) and on the research two-chunk handoff prototype (`research/operators/qwen_handoff`, the one CPU-provable relation on main with a state input), every listed substitution, transcript-domain change, replay under another request, malformed proof and state-prefix substitution is rejected in every run by the check named for it below, while the unaltered control is accepted in every run; the cases listed as "expected accept" are accepted, which confirms an already-registered open gap and is not a rejection.

## Metric
For each case and run: exit code, last line (cp_verify: `YES` / `WITHIN LIMITS:` / `NO: <name>`; check_proof: `check_proof: verified|rejected`; manifest: `manifest: ACCEPTED|REFUSED: <field>`; handoff: the verify JSON `accept` and `why`, or the `FAIL: <reason>` line of the statement reader), the line that names the check, and which kind of check it is: **application validation** (a comparison on public values outside the proof: ID, policy, range, end token, manifest digest, statement parsing/root opening) or **proof constraint** (the proof's own transcript/sub-proof checks: `proof-refused`, `key-refused`, `entry-refused`, handoff `chunk_verify` false). Input SHA-256s recorded. Written by `experiments/20261111-6-substitution-suite/suite.py` to `runs/`.

A case counts as "rejected by the intended check" only if exit code is the expected nonzero one, the last line is the expected one, the named reason line or field is present, and the case's control is accepted in the same repetition.

### Cases (C = cp_verify fixtures, H = handoff prototype). Expected outcome and intended check fixed now.

Config substitution
- C-CFG1 exact example files with the clipped-gap example's `config/` (policy.txt, KL.bin; layout.txt is identical), `-id` exact ID. Expect `NO: model-statement` (validation, ID recomputed from config).
- C-CFG2 exact example's req/y/proof under the clipped-gap example's complete config + ivk and its own ID and `-policy` (the commitment's own public files, another commitment's proof). Expected class: proof constraint (any of `NO: proof-refused`, `NO: key-refused`, `NO: entry-refused`); the exact name is recorded. A `NO:` of another name is "rejected, other check".
- C-CFG3 one config byte changed (policy.txt trailing comment), derived ID of the changed config passed. Expect `NO: key-refused` (proof constraint; PR #41 saw the same).
- H-CFG1 honest handoff proof of statement A verified under statement B with another model identifier. Expect `accept=false` (proof constraint: descriptor pins and transcript-bound statement).
- H-CFG2 same, other weights identifier. Expect `accept=false`.

Request substitution and replay under a different request
- C-REQ1 exact example with the clipped-gap example's request and y (a complete honest request of another proof). Expect `NO: proof-refused` (or `statement-range` / `token-range` if a form check fires first; recorded as validation then).
- C-REQ2 prompt token 5 changed by +1. Expect `NO: proof-refused`.
- C-REQ3 two prompt tokens (3 and 4) swapped (same multiset). Expect `NO: proof-refused`.
- C-REQ4 r moved 60 to 59 (a wider coverage claim). Expect `NO: proof-refused`.
- C-REQ5 exact example's config/ivk/req/y with the clipped-gap example's proof (a valid proof, another statement), exact ID. Expect a proof-constraint `NO:`.
- C-RPL1 replay of the exact example's unaltered proof with a request built for another reply: reply token 62 changed. Expect `NO: proof-refused`.
- C-RPL2 replay of the unaltered proof with the unaltered request, a second time in the same run. **Expected accept** (no freshness or client binding; inventory IS-16, gap G-05). Recorded as a confirmed gap, not a rejection.
- H-REQ1 honest proof of statement A under statement B with request + 1. Expect `accept=false`.
- H-REQ2 statement B with one public output word + 1. Expect `accept=false`.
- H-REQ3 statement B with one pre-conv input word + 1. Expect `accept=false`.
- H-RPL1 honest proof of seed s presented under the honest statement of seed s+1 (another complete honest run, same shape). Expect `accept=false`.

Tokenizer-policy substitution
- C-TOK1 manifest verify (tools/manifest, signed test fixture) with a tokenizer directory whose tokenizer.json differs by one byte. Expect `manifest: REFUSED: serving.tokenizer.files...` (validation).
- C-TOK2 manifest verify with another chat template. Expect `REFUSED: serving.chat_template...`.
- C-TOK3 manifest verify with `--end-tokens 1` against a manifest that says none. Expect `REFUSED: serving.end_tokens...`.
- C-TOK4 check_proof.py on the exact example with `--end-token 5` (a policy whose end token is not the reply's last token 199). Expect `check_proof: rejected` "not one of your end tokens".
- C-TOK5 bare cp_verify on the exact example: the call takes no tokenizer at all. **Expected accept** (IS-13, G-04). Confirmed gap.
- C-TOK6 manifest verify with a tokenizer directory that matches the manifest but a different manifest signer key (attacker re-signs a manifest naming another tokenizer). Expect `REFUSED` at the signature (validation).

Transcript-domain change
- C-DOM1 cp_verify built with `LABEL_FIRST_CHAIN` changed (0x46524d01 to 0x46524d11; overlay copy of blocks/frame/heads.h, production sources untouched) on the unaltered exact example. Expect `NO: proof-refused` (proof constraint).
- C-DOM2 cp_verify built with `LABEL_ONE_TIME_CHAIN` changed (0x46524d02 to 0x46524d12). Expect `NO: key-refused`.
- H-DOM1 handoff proof made by a prover whose transcript domain is `FP94` instead of `FP93` (overlay copy of handoff.cpp, otherwise honest), verified by the unchanged verifier. Expect `accept=false`. A complete proof under a foreign domain.
- H-DOM2 unchanged honest proof verified by the `FP94` build. Expect `accept=false`.

Malformed proof
- C-MAL1 proof truncated by its last byte; C-MAL2 truncated to half; C-MAL3 truncated to 16 bytes; C-MAL4 empty file; C-MAL5 one byte appended; C-MAL6 4096 zero bytes appended; C-MAL7 bit flip in byte 0 (header); C-MAL8 bit flip in the middle byte; C-MAL9 bit flip in the last byte. Expect a `NO:` from the proof-file reader (validation: `cp-proof-length`, `header-magic`, ...) or `proof-refused` (proof constraint); exact name recorded, any `NO:` counts if the control accepts and the name is one of those two classes.
- H-MAL1 handoff proof truncated by one byte; H-MAL2 one byte appended; H-MAL3 bit flip in the middle byte; H-MAL4 empty. Expect `accept=false` or a `FAIL:` refusal, never accept.

State-prefix substitution
- C-PFX1 prompt prefix (tokens 0..r, the cp_verify "state" the reply depends on) with token 0 replaced. Expect `NO: proof-refused`. (C-REQ2/3 change other prefix tokens.)
- H-PFX1 honest proof for initial state S0, statement with another initial state S0' (one cell + 1) and its correctly recomputed root. Expect `accept=false` (proof constraint: initial words pinned in the proof).
- H-PFX2 statement with S0' but the root of S0 (inconsistent public opening). Expect `FAIL: verifier initial root opening` (validation, before any proof check).
- H-PFX3 honest proof for history H0, statement with H0' (one word + 1) and recomputed root. Expect `accept=false`.
- H-PFX4 complete hostile proof: statement says S0', prover writes a witness for S0 (honest recurrences from S0, descriptor true) with `hostile` mode (locally true linear targets), verified under S0'. Expect `accept=false`.
- H-PFX5 complete hostile proof: the second chunk starts from the first chunk's end state + 1 in one cell (the intermediate, uncommitted state substituted), recurrences honest from there, hostile mode. Expect `accept=false`.

Controls: C-CTL exact example unaltered (`YES`), C-CTLG clipped-gap unaltered with its `-policy` (`WITHIN LIMITS:`), C-CTLM manifest honest (`ACCEPTED`), C-CTLP check_proof honest (`verified`), H-CTL honest handoff proof under its own statement (`accept=true`), and the two domain builds on proofs of their own domain where one exists (H-DOM build proving and verifying FP94 with itself: accept).

## Acceptance threshold
Fixed now. PASS: every control accepts in every run, every case listed with an expected rejection is rejected by the intended check (or, where a class is given, by a check of that class) in every run, and every "expected accept" case is accepted in every run. Any listed hostile case accepted in any run is a FAIL for that case and is reported as a finding (registered as a named negative and added to the inventory's open gaps), not retried. A case rejected by a different check than registered is reported as "rejected, other check" (not a PASS for that case), with the check named.
This is descriptive: finite tests on fixed synthetic fixtures do not establish soundness.

## Kill criterion
Hard stop for the lane 2026-11-11T06:40Z wall clock, queueing in fp-heavy.sh included. Registered run budget: 30 minutes elapsed from the moment fp-heavy.sh grants the slot (logged by suite.py); whatever finished is then published as partial. If a verifier build fails or the handoff build fails, the affected cases are KILLED with the reason. CPU only, no GPU, no spend, no downloads.

## Runs
- 5 repetitions per case and control. Order alternates per repetition (odd: control then case; even: case then control). cp_verify `-j 1`. All runs pinned with taskset to cores 6-11 under fp-heavy.sh. Shared, loaded host: times are diagnostic only. No run excluded.
- Handoff: D = 8, C = 2 (the prototype's registered shape), five seeds 201..205, one per repetition (seeds differ from the #93 suite's 101..105). Honest and hostile proofs are generated inside the registered run.
- Builds (`verifier/build.sh`, the two domain-variant cp_verify builds, the handoff release build and its FP94 variant) happen before the run and are not runs of the suite; their digests go in ENV.json.
- Debug: cp_verify, check_proof and manifest cases only with `suite.py --dry-run` (builds altered inputs and command lines, hashes inputs, calls no checker). Handoff code is debugged on seed 909 at D = 4, C = 1, a shape and seed the registered run does not use.

## Prior art
- **EZKL**: the proved statement is the circuit plus visibility settings; public inputs/outputs are instance columns, so substituting one is a Halo2 instance mismatch (proof constraint), while model/settings identity rests on the verifying key the host trusts (application validation). Malformed-proof handling is the Halo2 deserializer.
- **zkLLM** (Sun, Li, Zhang, CCS 2024): binds the model by commitments and the prompt/output as public values; no published substitution suite separating host checks from proof checks.
- **Jolt**: the program and its I/O are bound into the transcript via the preprocessing/commitment; Jolt's audit history includes Fiat-Shamir transcript-omission bugs (public inputs not absorbed), the class C-REQ*/H-REQ* test for.
- **Expander / Polyhedra**: GKR with the circuit and public input absorbed into the transcript; the "weak Fiat-Shamir" literature shows why this matters.
- **Weak Fiat-Shamir**: Bernhard, Pereira, Warinschi (ASIACRYPT 2012) "How not to prove yourself"; Dao, Miller, Wright, Grubbs (IEEE S&P 2023) "Weak Fiat-Shamir attacks on modern proof systems" (Frozen Heart class: public statement not hashed before the first challenge). Khovratovich, Rothblum, Soukhanov (ePrint 2025/118) and the 2026/1838 attack analysed in `research/security/fiat-shamir-attacks.md` (PR #41).
- In this repository: PR #41 (fixed-ID mutations of the exact example, first-challenge trace), `examples/rejected-proofs/` (bit flips and cut bytes of honest proofs), PR #97 N1 to N3 (honest proofs of another statement against application checks), #93 handoff suite (13 hostile witnesses at the prover side, one layer replay).
- What is new here: cross-fixture substitution of complete honest proofs and requests, prefix-permutation and coverage-widening requests, transcript-domain changes on both the shipped verifier (label-changed builds) and a CPU prover (a complete proof under a foreign domain), verifier-side statement substitution and inconsistent-opening cases on the handoff's state input, and an explicit validation-versus-proof-constraint label per case.

## Amendments
(empty at registration)
