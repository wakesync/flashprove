# PREREG: 20261111-36-keyfile-tensor-binding
Issue: #36. Lane: keybind36. Date (UTC): 2026-11-11. Base commit: cf4b213f1fe4d1c0073e0e1266281eee7e92b79b.

## Hypothesis
On the existing CPU product toy proof profile, adding per-tensor multilinear evaluation claims on the same committed oracle to a versioned research key file will accept honest tables and reject complete proofs for substituted tables under a verifier-held manifest and conversion ID.

## Metric
Acceptance counts per named case; serialized key-file bytes; verification elapsed milliseconds (including expected evaluation recomputation). Record baseline and bound profile timings, median, sample SD, minimum and maximum, with no speedup claim. Count extension-field responses and linear claims for 1,199 source tensors and distinguish the Qwen design's 722 effective blocks. Inspect existing local caches without downloading weights; recompute Qwen source-byte manifest roots only if complete weights for both pins (37561816 and 739e3c5b) are already present. A cache miss is reported, not replaced by hashing old receipts.

## Acceptance threshold
All honest controls accept and all five named negatives reject: one tensor swapped, two tensors swapped, tensor order permuted, other-checkpoint manifest root, conversion-ID mismatch. In the first three cases the malicious prover must emit a complete proof for a valid product table, keeping the verifier's statement fixed, and the rejection must arise in the native proof checks, not an outside hash of the witness. Other-checkpoint and conversion mismatch also get complete-proof checks against the alternate verifier statement. Every negative has a paired honest control. At least 5 timing repetitions per arm, here 10, with all raw data committed. No security-level or Qwen-proof acceptance criterion is asserted.

## Kill criterion
Hard stop 2026-11-12T01:00:00Z, including queue waits. Each gated suite has a maximum elapsed budget of 20 minutes after slot grant. CPU only, no downloads, no GPU or spend. If native same-oracle claims cannot be implemented or honest proofs fail, report FAIL or KILLED and the exact gap rather than substituting hash-only checks. Stop writing if free disk is below 3 GB.

## Runs
10 repetitions per baseline and bound/attack arm, deterministic seeds 1..10. Alternate baseline/bound ordering by repetition. No timing warmup exclusion; report every run. Registered tensor fixture: length 16, three named rows a, b, c with a*b=c, field-native integer identity conversion. The toy profile is blocks/toy/product.h, with native commitment, PSC and IOPP; this is not cp_verify's production key.bin format. Debugging is permitted only on length 8 and seeds 101..103, never the registered fixture before the registered run. Commit code before the suite. Separate malformed-file tests may use the debug fixture. Test keys and witnesses are public and deterministic, no hiding claim.

## Prior art
- zkLLM (https://arxiv.org/abs/2404.16109) proves tensor operations with commitments and lookup arguments; this lane does not reproduce a full LLM proof.
- EZKL (https://docs.ezkl.xyz/) supports model/parameter visibility and commitments; binding model parameters is established practice, not novel here.
- Modulus Labs / zkML weight-commitment work (https://www.modulus.xyz/) motivates verifier-fixed model weights; no claim that this small adapter improves its protocols.
- Safetensors (https://github.com/huggingface/safetensors) gives tensor names, dtype, shape and byte offsets. Per-tensor content hashes differ from serialized shard hashes.
- OpenSSF model signing (https://github.com/sigstore/model-transparency) authenticates model artifacts and provenance, not an arithmetic table inside a proof.
- This repository's #87 builds checkpoint hash manifests and specifies DESIGN 2.0/2.2; #100 builds rule/config conversion IDs but no integer-table proof binding. Existing research/operators/public_binding already appends public-coordinate linear claims to the product oracle. The new bounded integration is per-tensor root-after-commitment evaluations and same-oracle native linear claims in a versioned toy key file, not a new commitment scheme. Production cp_verify/key.bin integration, Qwen placement/conversion and Fiat-Shamir/grinding analysis remain outside this bounded toy milestone.

## Amendments
