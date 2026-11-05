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

- 2026-11-04, first committed in `3bfec225` at 23:27:29Z (that commit wrote "2026-11-05" by mistake;
  corrected in the next commit). After results and after the independent review of PR #59 (head
  078d7429). Correction of times only. The registration line says "2026-11-04 22:25"; the
  registration commit `7930e5b0` is dated 2026-11-04 22:16:43Z. The amendment above says "2026-11-04
  23:20 UTC"; the commit that contains it, `078d7429`, is dated 2026-11-04 22:31:55Z. Both written
  times were wrong; the commit times are the record. The registration line is left as written.

- 2026-11-04, amendment 2, first committed in `3bfec225` at 23:27:29Z (same date slip, same fix),
  before the re-run; after results and after the independent review of PR #59 (head 078d7429). The
  review found three gaps. Code and tests changed, so every number is re-measured at the new code
  commit and the old `numbers.json` stays in git history at `078d7429`.
  1. `ed25519.verify` accepted a small-order public key: with the identity as key, R = [r]B, S = r
     verified for any message. It now refuses any public key A or commitment R with [8]A or [8]R
     the identity (the 8 small-order points). Verification stays cofactorless.
  2. The trusted re-sign arm counted schema refusals of nonsense values as "bound". The runner
     now reports which of its refusals the schema alone causes, and adds a coordinated arm:
     schema-valid alternates (commitment.kind hiding to public-weights with a made-up seed digest;
     a full made-up huggingface upstream with made-up committed files; committed files under the
     synthetic upstream; decode policy and serving alternates), each re-signed by the trusted key,
     without and with the flag that checks it. No threshold, like the first amendment arm.
  3. `--end-tokens` and `--recipe` were opt-in: leaving either out skipped its check.
     `--end-tokens` is now required, and the caller must pass `--recipe FILE` or an explicit
     `--no-recipe` (which leaves the recipe digest the signer's word). The runner adds omission
     rows (no threshold).
  The registered threshold, the 137 registered tampers and n = 10 are unchanged. Two registered
  file substitutions ("end tokens differ", "recipe") used to refuse only because the harness
  passed those flags; they now run with flags the tool requires.

- 2026-11-05 00:23 UTC, amendment 3, before the re-run; after results and after the second
  independent review of PR #59 (head 94966765). Wording, tests and three hardening fixes. The
  registered threshold, the 137 registered tampers and n = 10 are unchanged.
  1. `commitment.kind` was listed as the signer's word "unless --public-weights-seed is passed".
     That was wrong: the flag rehashes a seed file against `conversion.public_weights_seed_sha256`
     and nothing compares that with what the commitment is. The review re-signed the hiding example
     as `public-weights` with the digest of a seed file the signer also ships, passed the flag with
     that file, and got ACCEPTED (`cp_verify` YES). The amendment 2 alternate used a made-up digest
     that did not match the caller's file, so it showed that a mismatched digest is refused, not
     that the kind is checked. `commitment.kind` moves to the always-signer's-word set: 11 always
     (the 10 one-field fields plus `commitment.kind`) and 3 unless a flag
     (`conversion.public_weights_seed_sha256`, `upstream.*`, `conversion.committed_files`). The
     total stays 14 of 37. The coordinated arm adds a matching-seed alternate whose expected result
     with the flag is ACCEPTED, so the test pins the signer's-word status; only rederivation checks
     the kind.
  2. Hardening, each with a test and a runner row (no threshold): a value meaning "none" now has one
     encoding (`{"none": true}`; `{"none": 1}` and `{"none": 1.0}` used to compare equal to it); a
     rehashed directory with any symlink in it is refused (a symlinked subdirectory was not walked,
     so an extra tokenizer file in it was accepted); a trusted-signed manifest nested too deeply to
     parse is refused instead of raising an uncaught `RecursionError`.
  Code and tests changed, so every number is re-measured at the new code commit; the previous
  `numbers.json` stays in git history at `94966765`.
