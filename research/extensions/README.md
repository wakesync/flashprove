# Extension foundation v1 (research)

This small stdlib-only adapter admits **one pinned synthetic Maverick integer profile**,
upstream's stored accepted example. Not a model loader or generic plugin framework.
Neither GLM-5.3-Flash nor DeepSeek-V4.1-Flash is supported. Even real Maverick checkpoints
and other upstream shapes are not admitted by this first adapter.

Upstream Anthropic FlashProve source: `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`.
LICENSE, NOTICE and upstream code remain unchanged. New code uses Apache-2.0.

## Run

Repository root, non-root, Python 3.10+ and upstream verifier prerequisites:

```sh
verifier/build.sh
python3 research/extensions/harness.py research/extensions/baseline-v1.json
python3 research/extensions/harness.py research/extensions/baseline-v1.json --baseline
python3 -m unittest discover -s research/extensions -v
```

Manifest validation alone is explicitly **NOT a proof**. `--baseline` invokes unchanged
`integrations/check_proof.py` in Python isolated mode, which runs built `cp_verify`.
No weights downloaded, GPU used or new proof generated. It checks range 60:64, next token
199, exact-match policy and the fixture's published ID. The fixture is the only exception
to obtaining a trusted ID independently. `--end-token none` makes no complete-reply or
text/tokenizer claim. Raw upstream output and limitations are preserved. A zero exit
alone is not accepted without the upstream verified machine outcome.

## Adapter boundary

`load` rejects duplicate keys; `validate` requires exact versioned profile equality,
including keys, types, arithmetic, shape, policy, state and operators. Unknown fields,
versions, architectures, tokenizers and configs fail closed. Hard-coded config hashes
are reviewer-owned trust anchors, not provider declarations. `verify` snapshots hashed
config bytes and delegates parsing, commitment/proof and client-coverage checks to the
existing integration. Requests/responses are local files. No network fetch, dynamic
import, shell command or manifest-selected executable. The optional Python API verifier
argument is for trusted callers only. API callers must apply the upstream documented
exit AND machine-outcome conditions, not merely inspect subprocess.returncode.
For coverage ending before T=64, API `next_token` must be `None`: the `.y` file
contains a mandatory zero sentinel, not a generated after-request token. Passing a
numeric expectation here is rejected rather than silently ignored. Coverage reaching
T requires an integer vocabulary token, which is compared against the response.

Manifest identifier: SHA256(domain || canonical JSON), sorted keys, compact separators.
Domain: `flashprove-extension-manifest/v1` followed by NUL. This is an **application
metadata identifier only**, NOT an authenticated checkpoint/tokenizer commitment or
Fiat-Shamir challenge. It is NOT added to the upstream proof. The H821 transcript is
unchanged. Binding to the admitted relation comes from pinned config bytes, commitment
ID and unchanged verifier, not architecture labels. No external recurrent/KV state is
admitted. Trusted local checkout, Python, binary and filesystem are assumed; this is not
a hostile-local-user sandbox. Resource limits for hostile oversized files are not added.

## Source-checked capability matrix

These are source observations, not new cryptographic coverage:

| Operation | Admitted semantics | Source |
|---|---|---|
| Matmul/embedding/residual | exact integer with upstream range conditions | docs/model.md sections 1,3,9 |
| Quantization | fixed KL.bin powers of two; floor((a+2^(k-1))/2^k), ties up | docs/model.md sections 1,3 |
| Norm | integer isqrt RMS; gains folded into weights | docs/model.md sections 4,11 |
| Attention | causal GQA, fixed softmax and rotary lookup tables | docs/model.md section 5 |
| Router | top-1 first-index argmax after clamp; sigmoid scale on INPUT | model.py `_route` |
| FFN | alternating dense/MoE, shared plus selected expert, SiLU LUT | model.py `_feed_forward` |
| Output | exact greedy choices on client-declared covered positions | integrations/check_proof.py |
| Top-k, KDA, mHC, sparse gather, Engram, vision | rejected | no constraints added |
| External state | rejected | no prefix/state binding implemented |

`model.py` means `integrations/vllm/integer_model/integer_model/model.py`.
`docs/model.md` and `lean/IntegerModel/Model.lean` remain specification references.
Activation clamp [-2047,2047] does not apply to every intermediate; upstream specifies
those. No replacement numerical oracle or rounding kernel is introduced here.

Lean's final theorems have full-size, exact-match and other assumptions. They do NOT
prove this Python adapter, C++ binary, small fixture or a new model. See
`lean/THEOREM.md`, `lean/LIMITS.md`, `integrations/LIMITS.md`. Integer agreement does not
show floating-point equivalence, checkpoint provenance, weight privacy or production
security. Upstream supports clipped-gap, but this adapter intentionally rejects it.

## Extension checklist (gates, not a manifest edit)

1. Pin artifact revisions, tokenizer/chat encoding hashes, licenses and trusted
   checkpoint-to-integer-commitment provenance. Reject missing/unexpected tensors.
2. Specify the entire integer graph: rounding, saturation, bounds, tables, tie breaks,
   quantization conversion, initialization and committed state transitions. Pin an
   executable oracle; test prefill/decode and adversarial boundaries.
3. Implement witnesses, constraints and composition for every new operator. Reference
   tests alone are not proof coverage. Require honest proofs and malicious-witness
   rejection, not just bit-flip parser tests.
4. Bind architecture/version/config, policy, input/output and state in the actual proof
   protocol. Changed semantics need new transcript domains, not a renamed JSON field.
5. Extend Lean relation/correspondence and named final theorems. Run axiom/independent
   checks; recompute security, masking and capacity accounting at actual shapes.
6. Only then add a reviewed adapter/profile with positive, cross-family replay,
   wrong-policy/state/coverage and malformed-input tests. Record exact source,
   dependencies/environment, commands, seed, time, exit, logs and artifact hashes.
   Independent tiny end-to-end reproduction precedes large checkpoints or scale-up.

## TEE boundary (design only)

A future signed receipt must bind fresh client nonce/request digest, manifest digest,
model/tokenizer commitments, arithmetic/proof policy, input/output commitments,
coverage/state endpoints, code measurement, ephemeral key and proof digest. Trust chain,
measurement allowlist, signature, freshness/replay and key binding are separate from
proof verification. Acceptance needs BOTH when TEE policy is requested. This version
rejects every TEE policy other than not-implemented: attestation cannot bypass a missing
proof. No attestation verifier or software receipt signature is implemented. A software
hash is not hardware attestation. Attestation does not extend the proof relation or
establish physical accelerator coverage, privacy or floating-point equivalence.

## Recorded CPU evidence

`python3 research/extensions/record.py` completed with exit 0. It rebuilds the verifier
and creates a fresh `evidence/` directory (refuses to overwrite an existing run).
`evidence/results.json` records commands, environment, source base, seeds, elapsed time,
exits and artifact SHA256 hashes; numbered logs preserve full output with local path
prefixes sanitized only.

- Build: exit 0, 83.899 seconds, final `THE VERIFIER IS BUILT: <REPO>/bin/cp_verify`.
- Tests: exit 0, 5.544 seconds, 8 tests plus negative subcases, final `OK`.
- Baseline: exit 0, 2.286 seconds, upstream `outcome=verified`, exact match,
  r=60 e=64, tokens 61..63 plus next token 199. Full final line in `evidence/2.log`.
- Corrupted proof, wrong client coverage and wrong next token each exit 1.
- Commitment ID: `79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183`.
- 49 commitment-assumed rounds; proof of work up to 32 bits in 38 rounds;
  upstream least-round figures 128.00 with work, 96.23 without, NOT security levels.

Build emitted the upstream warning that another account may be able to change a
checkout ancestor. No permissions changed or safeguard bypassed. This is a shared-host
research reproduction, not a secured build attestation. Timings are single observations,
not benchmarks. Stored proofs are supplied upstream, not produced by this harness.
