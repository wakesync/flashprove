# Design note: proven abliterated models on vast hosts, compared with amiller/dsmack

Issue #58 (part of #6, #36, #9). Builds on the threat model of PR #54 (merged after this note was written;
`research/security/threat-model/`) and the signed manifest prototype in
`tools/manifest/` (this PR). Design only. No GPU was rented and nothing in this note is a result;
nothing goes into `research/results.yaml`.

Labels used below: **measured** (a receipt in this repository), **cited** (an upstream or external
source, linked), **inferred** (arithmetic or reasoning on those, not run).

The question (Shadow, 2026-11-04): "can we do something like amiller/dsmack with vast nodes running
proven abliterated models and everything is attested?"

Short answer: **partly.** Integrity of *which weights produced the reply* survives on an untrusted
vast host with FlashProve alone, and a signed manifest plus reproducible derivation can make
"which weights" mean "this published base model, abliterated by this published recipe". Prompt
privacy does not survive: a vast host sees every prompt in plaintext, and nothing in FlashProve
changes that. "Everything is attested" in the dsmack sense (hardware-rooted, which program runs,
sealed inputs) is not available on vast today. See section 1.

## 1. What each system gives, and what survives on vast

### 1.1 dsmack (read from its repository, 2026-11-04)

Sources: [README](https://github.com/amiller/dsmack),
[docs/architecture.md](https://github.com/amiller/dsmack/blob/main/docs/architecture.md),
[contracts/DEPLOY.md](https://github.com/amiller/dsmack/blob/main/contracts/DEPLOY.md),
[applications/private-agent-web](https://github.com/amiller/dsmack/blob/main/applications/private-agent-web/README.md),
[applications/relay-broker](https://github.com/amiller/dsmack/blob/main/applications/relay-broker/README.md).

- **Which program is running, hardware-rooted (cited).** Apple App Attest binds each assertion to a
  key that only the enrolled, signed Mac app can use. `CDRegistry` on Base Sepolia approves one
  runner build (CDHash, masked page 0, entitlements) and admits re-signed copies of it;
  `AppleAttestRegistryV1` admits App Attest keys whose CDHash resolves. The runner launches a Linux
  VM with a measured kernel/initramfs and a verity-protected rootfs, then an OCI workload whose
  digest, compose manifest and profile are bound into a launch assertion and a result assertion.
- **What it rests on (cited).** Apple's root of trust, SIP and the hardened runtime ("no process on
  the Mac, root included, can read the runner process"). Physical memory probing and kernel
  exploits are out of its model. **Private inputs are staged as plaintext disk files on the host**
  (architecture.md, "Trust"), so dsmack's Mac layer is integrity + program identity, not
  confidentiality against a determined Mac owner.
- **Model inference is not on the Macs (cited).** In private-agent-web, "model requests and
  responses remain encrypted between the browser and NEAR AI Cloud's model TEE; the broker
  forwards ciphertext and meters usage". The relay broker itself runs in a dstack CVM (Intel TDX),
  and email recovery checks a TDX quote. The prompt privacy in dsmack comes from a **TDX + GPU TEE at
  NEAR**, not from App Attest. (NEAR's own description: TEE-hosted models run inside Intel TDX
  confidential VMs with NVIDIA H200 GPUs in confidential-computing mode,
  <https://near.ai/blog/assume-were-lying-how-to-verify-private-ai>,
  <https://docs.near.ai/cloud/private-inference>; dsmack itself only says "NEAR AI Cloud's model TEE".)
- **Marketplace pieces (cited).** Node enrollment (`enroll.py`, App Attest chain), signed
  heartbeats with ownership links (EIP-712 `MacLink`), Ed25519 byte/time grants, a metering and
  settlement loop on Base Sepolia (`applications/payments`), bounty escrow (`work-escrow/`), and a
  forgery canary contract that pays out on a forged assertion.

### 1.2 FlashProve (this repository)

- **What it proves (cited, `guide/what-is-proved.md`, `docs/limits.md`).** For a request file the
  client builds, the checked tokens are those that the *committed integer model* ranks first
  (exact match) or that pass the clipped-gap limits, under the commitment ID that the client
  names. It needs no hardware trust: an untrusted GPU host produces the proof, any CPU checks it
  (about 1.4 s for the small example, **measured** in
  `experiments/20261104-58-signed-manifest/RESULTS.md`; about 21 s single-thread at full size,
  **cited** `guide/performance.md`). The binding rests on stated assumptions (BLAKE2b as a random
  oracle, the codes theorem taken as given, a not-public paper argument), listed in
  `examples/accepted-proof/README.md`.
- **What it does not give.** Which *program* ran (irrelevant to the proof, by design). Which
  *checkpoint* the ID stands for (the ID is the provider's own commitment unless a manifest pins
  it: threat model M1). What *template, system prompt, tokenizer* wrapped the client's message
  (M2). Prompt confidentiality: the prover must read the prompt to prove the reply.

### 1.3 On an untrusted vast host

Vast hosts are a marketplace of independent machines running "an unprivileged Docker container",
with Docker-level tenant isolation and a "Secure Cloud" tier that adds datacenter agreements and
DPAs (**cited**, <https://vast.ai/compliance>). Our own receipts are two on-demand vast H100 rentals,
one "unverified listing" and one "provider-verified listing" (**measured**, `research/gpu/README.md`,
`research/gpu/replication-1/README.md`).

Confidential computing on vast (**cited**): vast's own article on NVIDIA CC (2024-03-15) ends "some
hosts are experimenting with NVIDIA Confidential Computing. Complete support for this feature is
not yet available"
(<https://vast.ai/article/Absolute-Security-with-NVIDIA-Confidential-Computing>). The compliance page
lists SOC 2, HIPAA on Secure Cloud and Docker isolation, and does not mention confidential
computing or hardware attestation. One comparison page from another GPU provider says the same
(<https://voltagegpu.com/compare/voltagegpu-vs-vast-ai>, a competitor's page, weak source). We found
no vast offer filter, API field or document for H100 CC mode, TDX or SEV-SNP. **Conclusion
(inferred from those sources):** as of 2026-11-04 a vast renter cannot select an attested
CC-on H100 inside a TDX/SEV-SNP CVM, and the host operator has root on the machine that sees the
prompt. H100 CC requires a CPU TEE (TDX or SEV-SNP) on the host
(<https://docs.nvidia.com/confidential-computing/virtual-machines/threat-model>); that is a host
configuration, not something a container tenant can turn on.

| Guarantee | FlashProve alone on vast | Needs a TEE (CC-on H100 in TDX/SNP CVM) | dsmack today |
|---|---|---|---|
| Reply came from committed weights W (integrity of the computation) | **yes**, cryptographic, no hardware trust | also yes, under hardware trust | no (no model on the Macs; NEAR TEE attests its own image) |
| W is the published base model + published recipe | **yes with manifest + rederivation** (section 2) | TEE attests image, not weights, unless the image pins a weight hash | n/a |
| Template / system prompt / tokenizer are the published ones | **yes with manifest M2** if the client rebuilds the window itself | yes if the attested image pins them | workload digest pins them, for its workloads |
| Which program ran on the node | no (not needed for the proof) | yes | **yes** (App Attest + CDRegistry) |
| Prompt and reply hidden from the host | **no**, host sees plaintext | **yes**, within the CC threat model | Mac layer: no (plaintext on host disk); model layer: yes (NEAR TEE) |
| Host cannot withhold, delay or selectively refuse | no | no | no |
| Payment only for proved work | **yes**: settle on a verified proof | yes, on attestation | yes, on assertions |
| Safety / no backdoor in W | no | no | no |

So on vast, FlashProve alone gives a *public, hardware-free* integrity guarantee that dsmack does
not have for inference, and none of the confidentiality. A privacy-preserving version needs a TEE
provider (Phala, NEAR AI, Azure CC H100, or a vast host that some day ships CC); then the proof and
the attestation are complementary, as the README already says ("signatures authenticate messages,
TEE evidence authenticates measured execution under hardware trust, and cryptographic proofs
establish a specified relation").

## 2. "Proven abliterated": reproducible derivation

Abliteration (Arditi et al., <https://arxiv.org/abs/2406.11717>) computes a refusal direction r
from mean activations on harmful vs harmless prompt sets at a chosen layer, then orthogonalizes
every matrix that writes to the residual stream (embedding, attention out, MLP down; for an MoE
every expert's down projection) against r: `W' = W - r r^T W`. Given base weights, r and the
recipe, it is deterministic arithmetic.

### 2.1 Derivation pipeline that a third party can rerun

```
base checkpoint (HF repo @ 40-hex revision, file sha256s)          <- manifest.upstream
  + direction r (published tensor, sha256)                          <- conversion.params / committed file
  + abliterate script (sha256, pinned torch/numpy, fp32 math, fixed op order)
  -> abliterated fp16/bf16 safetensors (sha256s)
  + quantize/convert (pinned GGUF quantizer version, no imatrix or a published one)
  -> integer-model weights
  + scales/ fit (pinned calibration set, deterministic) -> policy.txt, KL.bin, layout.txt
  + cp_commit -public-weights <published 32-byte seed>
  -> commitment ID                                                  <- manifest.commitment.id
```

Every arrow is a pinned program on pinned inputs. A manifest (this PR's `tools/manifest/`) records
each input digest and the recipe; the signer signs it; anyone who reruns the chain and gets the same
ID has checked the signer's claim rather than trusted it. Without that rerun, the client can
only rehash what it holds: `upstream.files`, `conversion.committed_files` and the public-weights
seed digest are the signer's word unless it passes `--upstream-dir`, `--committed-dir` and
`--public-weights-seed`; `upstream.repo` and `upstream.revision` (the rehash checks file contents,
not where they came from) and `commitment.kind` are the signer's word even then, because the seed
flag checks a file against the digest, not the kind against the commitment (measured in the
manifest experiment's amendment arms).
Today that rerun is possible only for `-public-weights` commitments (hiding ones mix in a secret
seed, `prover/common/public_weights.h`),
and the last step needs an H100 and about 330 GB of host memory for Maverick (**cited**,
`examples/maverick/figures.txt`: commit 43 minutes, peak 310 GB). The Maverick example already
does the last three arrows for the unmodified base (`examples/maverick/run.sh`, ID
`c7982f8a...71f46` in `expected.txt`); abliteration adds two arrows in front.

Determinism of each arrow is **not tested** in this lane. Known risks (inferred): GPU matmul
nondeterminism (do the projection on CPU in fp32, or in integer arithmetic on the already-quantized
weights, see 2.3); GGUF quantizers differ across llama.cpp versions; importance-matrix
quantization depends on calibration text; `scales/calibrate.py` must be shown to give identical
`KL.bin` on two machines. Threat model M3 costs this at 1 to 2 weeks per model (inferred, #54).

### 2.2 What this proves, and what it does not

Proves (given a matching rederivation and a valid proof):
- the reply was computed by *exactly* the integer model obtained from that base, that direction and
  that recipe, under the stated decode policy;
- nobody swapped in a different fine-tune, an adapter or a "lightly edited" variant after vetting
  (threat model A2, A3);
- the template, system prompt and tokenizer around the message are the manifest's (M2), if the
  client rebuilds the window from its own message.

Does **not** prove:
- **that refusals are gone.** Abliteration is a behavioral intervention; whether it worked is an
  eval claim about the integer model, not a property of the proof. Run the refusal evals on the
  integer model (the CPU integer-model package can), and publish them as evals, not as proofs.
- **that nothing else was inserted.** The direction r is a published tensor: a malicious publisher
  can choose an r that does more than ablate refusal, and the base checkpoint itself can carry a
  sleeper (threat model `research/security/threat-model/SLEEPER.md`, #54). Rederivation shows the recipe was
  followed, not that the recipe is benign. Publishing how r was computed (prompt sets, layer,
  script) lets others recompute r too, which narrows this to "the base and the prompt sets".
- **that quantization did not activate something.** #54 cites quantization-activated backdoors
  (Egashira et al., "Mind the Gap", ICML 2025, arXiv 2505.23786): a full-precision model that behaves well can
  be built to misbehave only after a given quantizer. Abliterating in full precision and then
  quantizing inherits exactly that risk. Mitigation: vet and eval the *integer* artifact (M3), and
  prefer exact match (M4) for anything safety-relevant, because clipped gap lets a provider pick a
  second-ranked token (#51: one swap proved and accepted 15/16 and 13/16 under the shipped
  limits, measured, unreplicated, honest-prover only).
- that the base publisher's weights are what they claim to be about training data or provenance.

### 2.3 A cheaper variant worth testing

Instead of abliterating in bf16 and requantizing, project r out of the **already committed
integer weights** with an exact integer projection (the model-identity lane did this for a
synthetic coordinate direction: `experiments/20261103-model-identity/PREREG.md`, "projection of
coordinate direction e_0 ... exact integer projection"). That removes the quantizer from the
abliterated arrow, so the derivation is base integer artifact (already reproducible for Maverick)
+ r + a short integer script. Cost: it is not the same model as a bf16 abliteration followed by
quantization, and a general (non-coordinate) r needs a rounding rule that must itself be pinned.
Untested at real scale.

## 3. Marketplace shape, mirroring dsmack

```
           Base (L2)                                 off-chain
 +---------------------------+         +------------------------------------+
 | ModelRegistry             |  read   | client / gateway                   |
 |  manifestHash -> {id,     |<--------|  1. pick model, fetch manifest +   |
 |   signer, status}         |         |     signature (IPFS / HTTPS)       |
 |  approve / revoke by      |         |  2. tools/manifest verify (keys    |
 |   curator (multisig)      |         |     from registry, not from node)  |
 +---------------------------+         |  3. build own request window       |
 | NodeRegistry              |         |     from manifest template          |
 |  node key, stake, served  |         |  4. send prompt to node            |
 |   manifestHashes          |         |  5. get reply + proof              |
 +---------------------------+         |  6. cp_verify + manifest verify    |
 | Escrow / Settlement       |<--------|  7. sign "verified" receipt        |
 |  per-request reservation, |  settle +------------------------------------+
 |  release on client-signed |                     ^   | prompt (plaintext)
 |  receipt or verifier      |                     |   v
 |  attestor quorum; slash   |         +------------------------------------+
 |  on a signed bad proof    |         | vast node: cp_commit once, serve,  |
 +---------------------------+         | cp_prove per reply, publish proof  |
                                       +------------------------------------+
```

- **Model registry (mirrors CDRegistry).** Stores approved manifest hashes and their commitment
  IDs, with the signer key. Approval is a curator decision, like `setBuild`; anyone can register a
  rederived manifest that matches an approved recipe, like `registerBuild`. Revocation voids it.
  The contract does not verify proofs.
- **Node enrollment.** Without App Attest there is no hardware identity, so enrollment is a staked
  key plus the list of manifest hashes it serves. It is economic, not attested: the node can lie
  about its hardware but cannot fake proofs.
- **Per request.** The node proves each reply. The client (or a verifier service it trusts, or a
  quorum of them) runs `cp_verify` and `tools/manifest verify` off-chain. Verifying on-chain is out
  of reach: an 18.78 MB proof and about 21 s of CPU per full-size check (**cited**,
  `guide/performance.md`).
- **Settlement on Base.** The client's signed "verified" receipt releases the reservation, as in
  dsmack's payments loop. A node that signs a proof that fails verification can be slashed by
  anyone who posts it to a verifier quorum (an optimistic scheme; the dispute game is not designed
  here). A node that just withholds is not slashable by proof, only by timeout.
- **Forgery canary (mirrors dsmack's Canary).** A pot that pays anyone who presents an accepted
  proof under a registered ID for a reply that the committed integer model does not produce.
  Worth having: it prices the soundness assumptions publicly.

### 3.1 Cost per request

| quantity | value | label |
|---|---|---|
| vast H100 on-demand price, our two rentals | $2.40/h and $2.16/h | measured, `research/gpu/README.md`, `research/gpu/replication-1/README.md` |
| small synthetic example, whole session all in | $1.19 and $0.92 | measured, same files |
| full-size Maverick prefill, 1,024 tokens, batch 24, steady | 9.206 +/- 0.077 s per request on one H100 | cited, `guide/performance.md` (upstream, not reproduced) |
| proving vs stock vLLM prefill, per GPU | 93.0x at the highest load tried (92.2 to 94.1), 71.4x at 24 requests | cited, `guide/performance.md`; calculated upstream, FP8 engine on 8 H100s vs 4-bit integer prover on 1 |
| whole replies, clipped gap, batch 24 | 39.1 +/- 1.0 reply tokens/s on one H100 | cited, same |
| commit once per model | 43 min, 310 GB host peak | cited, `examples/maverick/figures.txt` (other programs, not the released ones) |
| client verify, full size | about 21 s on one thread, up to 3.53 GB | cited, `guide/performance.md` |
| **GPU cost per proved 1,024-token prefill request** | 9.206 s x $2.16 to 2.40/h = **$0.0055 to $0.0061** | inferred |
| **GPU cost per proved 500-token reply** (whole-reply rate) | 500 / 39.1 = 12.8 s = **$0.0077 to $0.0085** | inferred |
| commit per model per node | 43 min = **$1.55 to $1.72** | inferred, and only on hosts with about 330 GB RAM |

Caveats (inferred): these use upstream's best-case steady rates (start-up and commit excluded);
the host must have about 330 GB of RAM for Maverick, which most single-H100 vast offers do not
(our rentals were not checked for that); the 93x compares against an FP8 engine on other hardware,
so "93x the price of unproved inference" is a rough figure, not a measured price ratio on vast,
and if anything low: upstream says its vLLM baseline is not the most those machines can do, which
flatters the prover (`guide/performance.md`, Cost).
Client-side verification at about 21 CPU-seconds per proof is a real cost for a gateway and is
not in the GPU figure. The reply figure is proving only: generating the reply is not in it, and
upstream's stored replies were chosen because scoring expected them to meet the clipped-gap limits
(`guide/performance.md`, Whole replies). That rate is under clipped gap, which `tools/manifest`
`verify` does not accept yet: it calls `cp_verify` without `-policy` and requires `YES`, so an
honest clipped-gap manifest on `examples/accepted-proof-clipped-gap` is refused (`NO: policy`).

### 3.2 Which models are provable today

- **Llama 4 Maverick: yes, end to end** (cited upstream: public 4-bit files, commitment recomputed
  and compared, proof checked; `examples/maverick/`). This is the only real model. It is also the
  only candidate for "proven abliterated" now.
- **Qwen3.8 27B: no.** Feasibility scoped (#28, committed 26.9 B parameters, 7 new operator
  families); DeltaNet head M1 proved one head but FAILED its range bound (#47, merged, negative);
  M1b (#52, open) KILLED as registered. No layer, no block, no model.
- **GLM: no.** KDA slice and model-scale sweep only (#42, open, pre-standards, synthetic). No
  model.
- Everything else: not ported.

## 4. Verdict and smallest demo path

**Verdict.** "Vast nodes running proven abliterated models" is buildable with integrity, not with
privacy. FlashProve on vast gives what dsmack's Mac layer cannot give for inference: a public,
hardware-free check that a reply came from committed weights, and a signed manifest ties those
weights to "base + direction + recipe". It does **not** make anything "attested" in dsmack's
sense, does not hide prompts from the host, does not prove the model is uncensored or clean, and
today only one model (Maverick) works, at about 330 GB of host RAM, with a reproducible
abliteration chain that nobody has run yet. "Everything is attested" needs a TEE host, which vast
does not offer (section 1.3).

**Smallest demo path** (each step is a lane with its own PREREG; costs inferred):

1. **CPU, now (this PR).** Signed manifest + client verify on the stored synthetic example, tamper
   tests. Done here.
2. **CPU, 1 to 2 days.** Abliterate the *synthetic* small model with an integer projection
   (2.3) using a published direction, sign its manifest, show two independent reruns produce
   byte-identical weights and config files. No commitment yet (CPU cannot run `cp_commit`).
3. **One H100, about $1 to $2.** `cp_commit -public-weights` on the abliterated synthetic model on
   two separate rentals: same ID twice, then prove + verify through `tools/manifest`. This is the
   first "proven abliterated" receipt, synthetic. Needs Shadow's GPU approval.
4. **Contracts, Base Sepolia, a few days.** Registry + escrow with client-signed receipts,
   mirroring dsmack's CDRegistry/payments. No proof on-chain.
5. **Maverick abliterated, one large-RAM H100 host, hours and tens of dollars.** Integer
   projection of a published refusal direction on the committed Maverick artifact, rederive,
   commit, prove, plus refusal evals on the integer model published as evals. Only after 2 and 3
   pass.
6. **Privacy, separate track.** Run the same prover inside a CC-on H100 CVM at a TEE provider
   and bind the TEE quote and the proof to the same request. Not on vast.

Proposed claims: none. Every number above is measured elsewhere (linked) or cited; nothing here is
a new result.
