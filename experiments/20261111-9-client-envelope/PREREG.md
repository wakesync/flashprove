# PREREG: 20261111-9-client-envelope
Issue: #9. Lane: envelope9. Date (UTC): 2026-11-11T22:40Z. Base commit: cf4b213f1fe4d1c0073e0e1266281eee7e92b79b.

## Hypothesis
A versioned canonical client envelope (spec in `research/envelope/SPEC.md`) checked by a software-only client verifier (`research/envelope/client_verify.py`, Python standard library plus the shipped `cp_verify`) releases every registered accept vector below and rejects every registered reject vector below at the check named for it, before any reply bytes are released and without advancing the client's session state, in every one of 5 runs.

## Metric
For each vector and run: the client's exit code, its last line (`RELEASE` or `REJECT: <check>`), the three separate verdict lines it prints (`signature: ...`, `tee: ...`, `proof: ...`), whether a release file was written, and whether the client state file changed. Wall time of the whole client call (`time.perf_counter`, includes the `cp_verify` subprocess when it is reached), per vector: median, SD, min, max over the 5 runs. Written by `experiments/20261111-9-client-envelope/run_suite.py` to `runs/`.

A reject vector counts as "rejected by the intended check" only if: exit code 1, last line `REJECT: <registered check>`, no release file, client state file byte-identical to before the call. An accept vector counts only if exit code 0, last line `RELEASE`, the release file holds exactly the reply bytes, the state advanced by one, and the line `tee: MOCK` (or `tee: none`) is printed, never a TEE pass.

### Proof payload
The two stored examples on main, unchanged: `examples/accepted-proof` (exact match, ID 79a5a2bc...) and `examples/accepted-proof-clipped-gap` (clipped gap, ID 8df71434..., policy `clipped-gap,9244130,323343,1,16,8`). Altered proof files are derived at run time by a transform named in the committed vector (truncate, flip), never stored. Envelopes, signatures and client contexts are committed under `research/envelope/vectors/`. Signing key: a fixed published TEST key (seed in the generator), ed25519 via `tools/manifest/ed25519.py`; it authenticates nothing outside the tests. A second TEST key plays an outside attacker.

### Vectors (expected outcome and intended check fixed now)
Accept:
- A1 honest exact example, fresh session, seq 1.
- A2 honest clipped-gap example, client pins the clipped-gap policy and limits.
- A3 two concurrent outstanding requests in one session (A1's and A2's), responses arrive in reverse order (A2 first, A1 second); each released to its own slot.
- A4 provider label (display-only field) set to an arbitrary model name; released, and the release record says provenance comes from the client pin, the label is not provenance.
- A5 **expected accept, confirmed gap**: the exact example's unchanged proof re-wrapped by the provider under a new nonce and new seq, re-signed. Released. The proof relation does not bind the nonce (G-05); freshness rests on the provider signature and the client's state, not on the proof.

Reject (intended check in brackets):
- Substitution: SUB1 clipped-gap proof in the exact envelope, digest updated, re-signed by the provider [proof]; SUB2 envelope commitment ID other than the client pin [commitment-pin]; SUB3 the whole clipped-gap package (files, ID, policy) answering an exact request [commitment-pin]; SUB4 reply token changed (y 199 to 200), digest updated, re-signed [proof]; SUB5 configuration digests of the other example [config-pin]; SUB6 provenance reference naming a manifest digest other than the client pin [provenance-pin]; SUB7 tokenizer digest other than the client pin [version-pin].
- Signature: SIG1 nonce edited after signing [signature]; SIG2 signed by the attacker key [signature].
- Duplicate field: DUP1 duplicate key inside `request`, signed over the raw bytes [canonical]; DUP2 duplicate top-level key [canonical].
- Unknown field: UNK1 unknown top-level field, re-signed [schema]; UNK2 unknown field inside `coverage` [schema].
- Non-canonical: NC1 same content, other key order and whitespace, signed [canonical].
- Downgrade: DWN1 version `flashprove-envelope-v0` [version]; DWN2 envelope says clipped-gap where the client pins exact [policy-pin]; DWN3 proof bits 96 where the client pins 128 [policy-pin]; DWN4 attestation kind claims a hardware TEE [attestation]; DWN5 signature algorithm `none` [schema].
- Cross-request replay: RPL1 envelope for outstanding request A delivered for outstanding request B [nonce]; RPL2 the A1 envelope delivered again after its release [nonce-consumed]; RPL3 current nonce, but request digest of another request [request-digest].
- Truncation: TRN1 envelope bytes cut by 10 bytes [canonical]; TRN2 covered range narrower than requested (e 63 of 64), re-signed [coverage]; TRN3 proof file cut by one byte, envelope digest honest [proof-digest]; TRN4 proof cut by one byte, digest updated, re-signed [proof].
- State rollback: STA1 seq equal to the last released seq [state]; STA2 `prev` digest not the last released envelope's [state].
- Wrong end token: END1 finish `end` but the reply token is not in the client's end-token set [end-token]; END2 envelope end token differs from the reply file [end-token].
- Concurrency/interleaving: CON1 two outstanding, envelope carries A's nonce and B's request digest [request-digest]; CON2 two responses race with the same seq, the first released, the second [state].
- Expired: EXP1 now after `expires_at` [expired]; EXP2 `issued_at` beyond the allowed clock skew in the future [expired]; EXP3 lifetime longer than the client maximum [expired].

35 reject vectors, 5 accept vectors (A3 counts as one vector with two releases).

## Acceptance threshold
PASS: every accept vector released, every reject vector rejected by the intended check with no release and no state change, in all 5 runs. Any reject vector released in any run is a FAIL and a named finding (not retried). A reject at another check than registered is "rejected, other check", not a PASS for that vector. A5 accepting is the registered expectation and is reported as a confirmed gap, not a success. Descriptive: finite vectors on two synthetic fixtures do not establish soundness, freshness or privacy.

## Kill criterion
Lane hard stop 2026-11-12T01:00Z wall clock, queueing in `fp-heavy.sh` included. Registered run budget: 30 minutes elapsed from the moment `fp-heavy.sh` grants the slot (logged by `run_suite.py`); whatever finished is then published as partial and the rest KILLED. If `cp_verify` does not build, every vector that reaches the proof check is KILLED. CPU only, no GPU, no spend, no downloads, no TEE hardware.

## Runs
5 runs of the whole vector set, vectors in fixed order in odd runs and reversed in even runs. Deterministic inputs (fixed keys, fixed nonces, fixed client clock in each context): verdicts are expected identical across runs; the runs measure repeatability of the decision and the client wall time. `cp_verify -j 1`, all runs pinned with `taskset -c 13-15` under `fp-heavy.sh`. Shared loaded host: times are diagnostic only. No run excluded.
Debug before the registered run: only with `run_suite.py --debug`, which uses a separate vector set (`debug-*`, other nonces, other session ids) and a stub verifier that prints a canned `result-v1` line, so `cp_verify` is never called on a registered vector before the registered run. Outside the suite, `cp_verify` is called once directly on each unaltered example to read the format of its `result-v1` line; that is not a run of the suite.

## Prior art
- **IETF RATS architecture (RFC 9334)** separates Attester, Verifier and Relying Party, and evidence from attestation results; **EAT (RFC 9711)** defines claims including `eat_nonce` for freshness and profiles for which claims a relying party requires. Our three verdicts follow that split: the TEE verdict is evidence appraisal, which this milestone does not do (MOCK).
- **COSE (RFC 9052)** and deterministic CBOR (RFC 8949 section 4.2) give canonical signed structures; JSON here follows the repo's existing manifest form (sorted keys, compact) with a byte-equality re-encoding check, close to JCS (RFC 8785) for ASCII.
- **in-toto / SLSA provenance** bind an artifact digest to a subject and builder identity under a signature; they make the point that a signed statement authenticates the signer's claim, not its truth.
- **TLS 1.3 (RFC 8446) and Noise** defend downgrade by binding the negotiated version into the transcript and by a signed/MACed handshake hash; DWN* vectors test the client-side analogue (pinned minimum version and policy, refuse anything weaker).
- **NVIDIA H100 confidential computing** attestation: a nonce-bound GPU report verified against a certificate chain and RIM measurements, with a separate CPU TEE (TDX/SEV-SNP) report. **Phala / Atoma / Nillion** style signed inference receipts bind a response to an enclave key. Neither proves the computation; both rest on hardware/TCB trust.
- In this repository: `tools/manifest` (PR #59, signed manifest, canonical JSON, unknown keys refused), `integrations/check_proof.py` (client comparison of ID, range, end token), the substitution suite (PR #108, G-04, G-05), the coverage inventory (PR #97), the closed PR #2 adapter (provisional).
- What is new here: one versioned envelope that names, field by field, whether the proof relation, a verifier recomputation, the client's own state, the signature, or nothing binds it; a client that fails closed before release on any of them with a named check; and committed reject vectors for replay, rollback, interleaving, downgrade, truncation and expiry around a real `cp_verify` proof.

## Amendments
(empty at registration)

### 2026-11-11T23:14Z, after the client and generator code, before the registered run

Only the debug mode (`run_suite.py --debug`: `debug` label vectors, STUB verifier, in a temporary directory) has run. `cp_verify` was called once directly on each unaltered example to read its `result-v1` line, as Runs allows. No registered vector has been given to the client.

1. **A6 added (accept).** The issue asks that mock attestation stay visibly MOCK. A6 is A1 with `attestation.kind = MOCK`; it must release and its `tee:` line must start `MOCK (not evidence`. 41 vectors: 6 accept (A5 still the expected-accept gap), 35 reject. The reject list and every expected check are unchanged.
2. **Fixture details fixed by the code, not by the registration.** The clipped-gap example's reply ends in token 0 at max_tokens, so its pinned end set is {511} and its envelope says `finish = length`. SUB4 (y changed to 200) is signed with `finish = length` so that the end-token check passes and the proof check decides, as registered. NC1 is the honest body with the signature first and one-space indentation (other key order and whitespace). The tokenizer, chat-template and provenance digests are TEST digests of labels (the example model is synthetic and has no tokenizer).
3. **Paths.** As registered: spec `research/envelope/SPEC.md`, client `research/envelope/client_verify.py`, vectors `research/envelope/vectors/`, runner `run_suite.py`. Added: `envelope.py` (shared encoding), `make_vectors.py`, `stub_cp_verify.py` (debug only), `test_envelope.py` (unit tests: parser, byte-for-byte vector regeneration, debug suite).
