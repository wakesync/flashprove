# PREREG: 20261104-58-signed-manifest
Issue: #58 (part of #6, #36, #9). Lane: signed model manifest + vast/abliterated design. Date (UTC): 2026-11-04 22:25. Base commit: eb6e6ea379db87b3bd34c6377414422ed6a236dd.

## Hypothesis
A detached, ed25519-signed manifest checked by a client-side tool next to `cp_verify` refuses every single-field tamper of the manifest, every substitution of a bound file (configuration files, proof's commitment ID, tokenizer, chat template, system prompt, verifier build digest), and every wrong signer key, while accepting the untampered stored example (`examples/accepted-proof/`) with zero false refusals.

## Metric
- Tamper refusal rate: for each manifest field (every leaf of the canonical JSON, enumerated mechanically, not hand-picked) one mutation, re-signed by an attacker key and also left with the original signature; count refusals / mutations. Also: each bound file replaced by a one-byte-changed copy; manifest signed by a different key; signature bit flipped; non-canonical JSON (key reorder, whitespace) with the original signature.
- False refusal count on the untampered example: n runs.
- Verify wall time on CPU (seconds, `time.perf_counter`), informational only.
- `cp_verify` end-to-end: the tool runs the real `cp_verify` binary on the stored proof with the manifest's ID and reports its exit code and `result-v1` line.
- ed25519 implementation correctness: RFC 8032 section 7.1 test vectors 1-3 and, where the `cryptography` package exists, cross-signature agreement on random messages.

## Acceptance threshold
PASS iff: 100% of tampers refused (any single miss = FAIL), 0 false refusals in n=10 untampered verifies, all RFC 8032 vectors match, the untampered path ends with `cp_verify` exit 0 and `YES`. Timing has no threshold.

## Kill criterion
CPU only, no GPU, no paid API, no model download. Time box 3 h wall. If `cp_verify` cannot be built on this CPU host, the end-to-end row is NOT MEASURED and the manifest-only rows still report. If the pure-Python ed25519 fails any RFC vector and cannot be fixed in 30 min, stop and publish the negative.

## Runs
Untampered verify: n=10, same inputs, deterministic (repeat counts a determinism check, not independent trials). Tamper set: one mutation per field, fully enumerated, ordered by JSON path; each mutation run once (deterministic). Random cross-check vs `cryptography`: 64 messages, seed 1104. Nothing excluded.

## Prior art
- Sigstore / cosign and in-toto/SLSA provenance: signed supply-chain attestations binding artifacts to build recipes. This manifest is a tiny special case for one committed model.
- minisign / signify / SSH signatures: detached ed25519 signatures on files.
- Hugging Face repo revisions + file sha256 (LFS oids): the upstream pin this manifest records.
- Tinfoil Modelwrap (https://tinfoil.sh/blog/2026-02-03-proving-model-identity): model identity bound inside a TEE attestation, not a proof.
- amiller/dsmack (https://github.com/amiller/dsmack): approved-code registry + hardware attestation (Apple App Attest), compared in DESIGN-VAST-ABLITERATED.md.
- zkML (EZKL, zkLLM, Jolt, Expander), TEEs (H100 CC, TDX, SEV-SNP; Phala, Atoma, Nillion): adjacent, none is changed here.
- Threat model PR #54, mitigations M1 and M2: this lane implements their detached-manifest form. Binding the manifest into the configuration itself (in-statement) is out of scope (parser change).
What is new: nothing cryptographically; it is the missing glue between a FlashProve commitment ID and an upstream checkpoint + serving template, with tamper tests.

## Amendments

- 2026-11-04 23:20 UTC, after code. Added a third tamper arm not named at registration: each field changed and **re-signed by the trusted signer key itself**. It has no threshold. It sorts fields into those the client can check against its own files or cp_verify's output ("bound") and those that are only the signer's word; the test suite asserts that set exactly, so a new unbound field fails a test. The registered PASS rule (100% of tampers refused) applies to the registered arms only: original signature kept, attacker key, attacker key written into `signer.public_key`, file substitutions, signature bit flips, non-canonical JSON. Reason: a signed manifest cannot stop its own signer from lying about fields nobody can rehash; saying which fields those are is the useful output.
