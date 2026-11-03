# Research program: practical verifiable inference

This is the roadmap for the active [wakesync/flashprove](https://github.com/wakesync/flashprove) research fork, not an upstream commitment or a production-support announcement. The starting artifact is Anthropic's FlashProve v0.16.0 at [`9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`](https://github.com/anthropics/FlashProve/tree/9e2bdd8ff5bf9c62f18263d7dac189b0400b260c). Preserve its license, notices, attribution, operational instructions and theorem boundaries.

Our mission is to investigate whether verifiable inference can become practically useful: reproducible proofs with explicit coverage, measured cost, characterized numerical fidelity and a client that checks the claim it actually requested. Faster proving is useful only if the relation remains correct and the verified output remains useful. A documented no-go result is progress.

## Evidence vocabulary and present status

Snapshot: 2026-11-03. Work in open PRs is not functionality on `main`. Read the [evidence ledger](research-evidence.md) for exact commits and limitations.

- **Reproduced, narrow CPU scope:** independently built C++ verifier, accepted stored synthetic exact/clipped fixtures, 41-call mutation audit, and toy proof-library checks in [PR #3](https://github.com/wakesync/flashprove/pull/3), building on [PR #1](https://github.com/wakesync/flashprove/pull/1). This is neither GPU inference nor a new architecture proof.
- **Provisional integration:** [PR #2](https://github.com/wakesync/flashprove/pull/2) admits only a pinned synthetic profile and fails closed on unsupported models. [PR #4](https://github.com/wakesync/flashprove/pull/4) has focused combined checks, but full CPU closure remains gated. Neither manifest labels nor a fake-Lean launcher test establish a theorem.
- **Provisional operator research:** narrow independent review of public-coordinate and same-oracle cell-equality experiments found no blocking issue within their supported constructor boundary. The source/receipt publication gate remains separate. No complete router, architecture, network parser, formal soundness or hiding claim follows.
- **Planned or unvalidated:** fresh GPU replication, measured fork overhead, real-checkpoint fidelity, longer-context proofs, GLM/DeepSeek support, real TEE attestation and production service. No completed GPU validation receipt was available for this snapshot. Historical infrastructure preparation is not a current provider-state claim.

Do not collapse these categories into a single completion percentage. Each issue closes only on its stated evidence, with remaining skips and failures visible.

## What the upstream numbers actually say

Primary sources below are pinned to the starting commit, not a moving branch:

- [Performance](https://github.com/anthropics/FlashProve/blob/9e2bdd8ff5bf9c62f18263d7dac189b0400b260c/guide/performance.md): 111.23 +/- 0.92 prompt tokens/s at batch 24, one H100 80 GB plus 24 host CPUs, 1,024-token prompts, three runs. It is steady **prefill**, with each proof stating the next token; nothing is generated in that rate. Startup, committing, queueing and serving-side verification are excluded. Batch proof release takes 220.7 to 225.9 seconds after the first batch, before middleware verification.
- The same page reports calculated **71.4x** per-GPU slowdown versus stock vLLM prefill at 24 requests and **93.0x** versus the highest load tried. The engine used the FP8 release on eight H100s; the prover used a third-party 4-bit conversion and integer semantics on one H100. Thus "roughly 70-100x" is a rough description of particular upstream prefill comparisons, not a universal tax, matched end-to-end serving comparison or reproduced fork measurement. The separate 20.1x pass/decode comparison is explicitly not the cost of proving a generated reply.
- [Integer model](https://github.com/anthropics/FlashProve/blob/9e2bdd8ff5bf9c62f18263d7dac189b0400b260c/docs/model.md) and the pinned README specify the full-size Maverick relation with **T=1024**. This is the artifact's context shape, not a fundamental impossibility bound and not evidence of longer-context support.
- The performance page reports **6.81% top-token disagreement** with a 16-bit reference and **zero of 96 stored replies from each of the 16-bit and FP8 stock engines** meeting exact match. These were scored by a Python integer-model implementation on other programs, not proved on the released programs or reproduced here. Do not silently relabel the upstream "16-bit" comparison as a newly validated BF16 benchmark. Future BF16 and FP8 studies must pin their exact references separately. None of this proves that an arbitrary approximate model is unusable or establishes a task-quality score.
- The upstream performance page says the historical raw run records are not in the repository. Several baseline scripts, replies and fitted limits are also unavailable. We can repeat measurement kinds with new disclosed inputs, not claim exact reproduction of historical records.

## Threat model and claim classes

Assume the provider and transport may be malicious: substitute weights/configuration, omit tokens or operators, forge intermediate states, replay a valid proof on another request, choose weak policies, exploit parser/resource failures or selectively withhold responses. The client must hold a trusted commitment/configuration policy, construct its own request and check its intended coverage and terminal condition. A provider-generated commitment does not by itself authenticate a publisher checkpoint or tokenizer. Availability, truthful answers, model safety and training provenance are not proved by inference correctness.

The cryptographic claim relies on the protocol's stated hash/random-oracle assumptions and exact relation. The client runtime/verifier, trusted configuration/provenance source and any code translating bytes into a statement remain part of the trust boundary. Parser rejection, application admission, cryptographic rejection and formal proof are distinct evidence classes.

- **Full requested exact-match coverage:** all requested output positions satisfy the committed integer model's deterministic greedy relation, with the required prefix/state linkage and end policy. "Full" describes this declared relation and output scope, not floating-point equivalence or every possible service property.
- **Selective coverage:** only the declared checked subset is established. It says nothing deterministically about unchecked positions/operators. A randomized audit needs a separately stated adversary model and statistical detection bound; it cannot inherit full-proof assurance for unchecked work.
- **Clipped-gap:** `WITHIN LIMITS` asserts the chosen cost policy, not exact generation and not correct sampling. Exit code zero alone is insufficient. A client requesting exact match must not silently accept clipped-gap or selective evidence.
- **Signatures:** authenticate a message under a key, not correctness of inference.
- **TEE attestation:** authenticates a measured environment/key under hardware, endorsement, TCB and freshness assumptions. It does not create missing proof constraints, establish checkpoint provenance or automatically cover a GPU.
- **Cryptographic proofs:** establish the specified relation under their assumptions, not hardware identity. Composition requires independent verification of both proof and attestation when both are requested. Confidentiality, zero knowledge, accelerator protection and provenance each need their own evidence.

The upstream [theorem](https://github.com/anthropics/FlashProve/blob/9e2bdd8ff5bf9c62f18263d7dac189b0400b260c/lean/THEOREM.md), [formal limits](https://github.com/anthropics/FlashProve/blob/9e2bdd8ff5bf9c62f18263d7dac189b0400b260c/lean/LIMITS.md) and [claim guide](https://github.com/anthropics/FlashProve/blob/9e2bdd8ff5bf9c62f18263d7dac189b0400b260c/guide/what-is-proved.md) govern the original relation. The approximate q/2^124 + 2^-101 bound is for the stated Lean verifier/shape/assumptions, not a blanket security level for C++/CUDA or extensions. Completeness and zero knowledge have their own exact-match, fresh-mask, full-size, single-request/leaf-table conditions; do not carry them over to arbitrary batches, clipped-gap policies or new gadgets. Executable correspondence is tested, not formally established for all shipped programs.

## Priorities, workstreams and decision gates

- [#5: P0: close reproducibility gate with complete CPU and bounded GPU receipts](https://github.com/wakesync/flashprove/issues/5)
- [#6: P0: define proof coverage, threat model and soundness obligations](https://github.com/wakesync/flashprove/issues/6)
- [#7: P1: measure proving overhead, resource cost and verified-response latency](https://github.com/wakesync/flashprove/issues/7)
- [#8: P1: quantify integer-model fidelity against pinned BF16 and FP8 references](https://github.com/wakesync/flashprove/issues/8)
- [#9: P1: bind client requests and verified responses without conflating signatures, TEEs and proofs](https://github.com/wakesync/flashprove/issues/9)
- [#10: P2: profile and gate long-context scaling and state continuity](https://github.com/wakesync/flashprove/issues/10)
- [#11: P2: gate GLM and DeepSeek ports on operator feasibility, not model loaders](https://github.com/wakesync/flashprove/issues/11)
- [#12: P2: evaluate selective verification as an explicitly weaker assurance mode](https://github.com/wakesync/flashprove/issues/12)

### P0: reproducibility and soundness coverage first

Close the complete CPU evidence gate without hiding failures or dependency/kernel skips. Reproduce the bounded synthetic GPU workflow only with an authorized resource plan and validated lifecycle controls. Publish source/dependency hashes, exact commands, environment, actual exits, final verdicts, requested/covered positions and proof hashes. Never publish secret commitment seeds or masking state.

In parallel, build an operator-to-constraint and statement-to-client-policy inventory. Exercise malformed inputs, commitment/request substitution, transcript/domain changes, truncation, wrong state prefixes and complete malicious witnesses. Freeze integer rounding, ties, ranges, overflow and nonlinear tables. Check named Lean theorems and axioms, not just library compilation. New relations require renewed security and mask accounting plus independent review. No merge or production designation follows merely from this roadmap.

### P1: measured cost, fidelity and request integration in parallel

**Benchmark contract.** Every result must identify checkpoint/conversion, synthetic versus real weights, precision, context and reply lengths, checked positions, arithmetic/policy, batch, concurrency and workload distribution. Record GPU type/count/VRAM/exclusivity, CPUs/NUMA allocation, host memory, driver/compiler/toolkit and source/binary hashes. Report commit/startup/witness/prove/verify separately; include queue and batch wait, time to first verified output and verified-before-release whole-reply latency. State whether work overlaps and never sum overlapping timings as serial latency.

Denominators must say prompt positions, checked output positions or generated tokens, and whether per GPU or total system. Distinguish steady throughput, cold start and amortized costs with a declared request count. Match the ordinary inference baseline's workload where possible; publish unmatched numerical semantics and hardware as confounders. Record proof bytes, RAM/VRAM/cgroup and storage peaks with measurement method, CPU/GPU time, failures and retry costs. Predeclare repetitions (at least three per admitted benchmark cell), dispersion and stop conditions. Monetary estimates disclose public unit prices, date and included resources; they are not measured invoices or general market claims. Optimize only after this identifies bottlenecks, then rerun correctness and coverage gates.

**Fidelity contract.** Pin the reference checkpoint, tokenizer/template, conversion, precision and engine/kernel behavior. BF16, FP8 and the integer relation are different targets. Fix calibration and held-out splits before tuning. Report per-layer errors, saturation/range violations, routing/index changes, logit margins, greedy agreement, first divergence, whole-reply agreement and perplexity where defined. Separate teacher-forced same-prefix tests from free-running trajectories. Publish sample counts, uncertainty, exclusions and failures across ordinary, repeated, tool-heavy and boundary prompts. Choose acceptance thresholds before held-out evaluation; no fidelity percentage is promised here. Quantization fidelity is empirical, not implied by the soundness theorem.

**Sampling contract.** Greedy exact match is the initial claim. A future sampling relation must bind logits/distribution transform, temperature/top-k/top-p, RNG algorithm and counter order, source/seed commitment, freshness, retries and output draws. Define who can choose the randomness and when; a provider-chosen committed seed alone cannot establish unbiased draws. Prove the transform/draw relation and state the randomness assumptions before claiming verified sampling. Statistical quality studies and audit-selection randomness are separate. Do not use clipped-gap acceptance as proof of sampling.

**Integration contract.** Bind canonical nonce/request digest, model/config/operator/arithmetic/policy versions, tokenizer/template identity, input/output/state commitments, requested/covered positions and proof digest. Test replay, downgrade, ambiguity, rollback, truncation, concurrency and failed-batch behavior. Verify before releasing any covered response or proof material under the applicable hiding obligations. The existing adapter is a narrow admission seam, not transcript binding for arbitrary metadata. Start with software-only envelopes clearly labeled MOCK for attestation; real hardware composition is a separate gate with chain/TCB/freshness checks, measured signing policy, ephemeral key and independent proof verification.

### P2: scale only after profiling; port only after operator feasibility

**Long context.** Establish a bounded context ladder from measured bottlenecks, not the model card's maximum. Specify positional semantics, chunk/prefill/decode agreement at exact rounding boundaries, authenticated KV/recurrent state, prefix ownership and resets. At each new size require honest/malicious proof checks, security/mask accounting, memory/cost measurements and explicit go/no-go. A supplied intermediate state cannot bypass proof of its history. Record refusals and OOMs; do not jump from the 1024-token baseline to a million-token support claim.

**Conditional ports.** GLM-5.3-Flash is a candidate first text-only architecture, conditional on KDA recurrence feasibility. DeepSeek-V4.1-Flash is a distinct later candidate, not a loader alias or promised delivery. Both require top-k and weighted routing unlike Maverick's top-1 input scaling, plus architecture-specific operations. Progress through verifier-fixed same-oracle affine relations, Booleanity/ranges, ordering/permutation, selection and normalization before claiming a router. GLM needs recurrence/convolution, sparse selection and mHC; DeepSeek additionally needs CED/CSA2 state ownership, authenticated Engram access and leakage analysis, and explicit FP4/FP8 semantics. Share gadgets only where semantics really match.

Pin source and precision variants before design. A source/config API response and shard list do not validate weights or tokenizer integrity. First demonstrate a tiny complete synthetic architecture crossing dense/MoE and attention boundaries, including normalization, residuals, head and all requested output coverage. Sparse toy cases must exceed their selection threshold. Require oracle/constraint/formal correspondence, complete malicious-proof rejection, independent review and measured feasibility before checkpoint-scale work. Reject vision/video and speculative paths until their entire relation is specified and proved.

**Selective verification.** Explore only as an explicitly weaker, opt-in policy. Define selection granularity, adversary timing, commitment-before-selection, unpredictable challenge generation, anti-grinding/retry rules and withholding behavior. Derive detection bounds under explicit assumptions and compare empirical attacks/costs to full coverage. If savings are negligible or assumptions unsuitable, stop. Never change the full-coverage default silently.

## Goals and non-goals

Goals: independently reproducible evidence, useful and explicit guarantees, measured overhead reduction, characterized fidelity, safe request integration and evidence-gated extension research.

Not current goals or claims: production readiness, universal Transformer support, floating-point bit equivalence, correctness of an answer's real-world content, immediate long-context/full-checkpoint ports, unqualified privacy/ZK, real TEE support, or a guaranteed speedup. We do not weaken guards, coverage or claims merely to obtain a faster number.

Contributions should identify an issue, exact claim, smallest reproducible experiment and evidence gate. Include failed experiments and open limitations, preserve upstream notices, and remove private paths/host identifiers/credentials from public receipts. Implementation, review, hardware validation and merge decisions remain separate steps.
