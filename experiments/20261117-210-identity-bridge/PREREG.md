# PREREG: 20261117-210-identity-bridge

Issue: #210 (part of #36 and #6; agenda U1/U3/Q2/Q5). Lane: bridge210. Date (UTC): 2026-11-17T09:01Z. Base commit: main `5583d7f82b549454cdb6374d2fd347dfd9781976`.

This registers one bounded desk deliverable before any other content exists on this branch. It is a specification and an obligation matrix. It is not an experiment: no model, no weights, no attestation parsing, no live route, no GPU, no measurement.

At the time of this commit the lane has read the issue body and the repository layout only. It has not yet read any of the evidence files the issue names. The edge list below is therefore the list of edges to be typed, taken from the issue's wording, not a finding.

## Hypothesis

A client that wants to join an attested loaded-weight identity to the weight commitment used in a proof needs a chain of typed edges, and on main at the base commit at least one edge of that chain is not a verified relation (it is a signed assertion, a vendor-documented promise, proposed code, or an unsolved cryptographic obligation). The note will say which, edge by edge. The hypothesis is falsified if every edge turns out to be established on main, in which case the note says so with the citations.

## Metric

No number is measured. The deliverable is judged on completeness of a matrix:

- every edge listed under "Edges to be typed" carries all seven fields (producer, independent verifier, exact canonical bytes, authorization source, binding mechanism, update / rollback rule, availability dependency) and exactly one status out of four: established on main, documented by vendor only, proposed code, unsolved cryptographic obligation;
- every one of the eleven named counterexamples carries either an explicit rejecting obligation (which edge, which check, who runs it) or the word UNRESOLVED;
- every statement in the note has a source: a path and line on main at a recorded commit, or a public document URL labelled "from public documentation, not verified by us".

## Sections of the note

The note will live at `research/weight-binding/IDENTITY-BRIDGE.md` (next to the existing `research/weight-binding/DESIGN.md`), with these sections:

1. Answer in three lines.
2. Scope, method, base commit, and what changed on main since the issue's snapshot `83299f194b80f62feca170a28650b390add3fbdc` for each evidence file the issue names (including whether later merged results, for example PR #191 and PR #199, bear on an edge).
3. The four separate guarantees: (a) hardware-backed evidence of physical loading / execution, (b) proof of output consistency against committed weights, (c) authenticity of a receipt, (d) authorization of the chosen checkpoint. What each can and cannot say, and which edges belong to which.
4. Objects (nodes) and their exact canonical bytes.
5. The bridge: every edge, typed, with all seven fields and one status.
6. Attack / obligation table: the eleven named counterexamples.
7. Schema example with synthetic identifiers only.
8. Source map: every statement to a main path and line, or a public document URL.
9. Dependencies, named open obligations (any new soundness theorem or format is named here and not built), and stop rule.
10. What this note does not establish.

A short `experiments/20261117-210-identity-bridge/RESULTS.md` will state the verdict against the acceptance and FAIL rules below.

## Edges to be typed

Nodes: N0 client authorization policy; N1 hardware attestation report and its measurement; N2 attested receipt key; N3 package root; N4 actual loaded tensor / config inventory; N5 checkpoint root; N6 conversion identity and complete conversion leaf root; N7 native proof-weight commitment; N8 request / output / state statement; N9 receipt.

| edge | from, to | what it must say |
|---|---|---|
| E1 | N0 to N1 | this measurement is one the client approves |
| E2 | hardware root to N1 | the report is genuine and carries this measurement |
| E3 | N1 to N2 | this receipt key was generated inside the measured boot that the report describes |
| E4 | N1 to N3 | the measured configuration fixes this package root |
| E5 | N3 to N4 | the tensors and config the runtime actually loaded are the ones in the package (loader, runtime dtype / quantization, adapters) |
| E6 | N4 to N5 | the loaded inventory equals the checkpoint the per-tensor hashes commit to (two different encodings) |
| E7 | N0 to N5 | the checkpoint root is the checkpoint the client chose (authorization of the checkpoint) |
| E8 | N5 to N6 | the conversion leaf root is the complete, correct conversion of that checkpoint under a pinned config and rule (folded norms, adapters, lookup tables, transforms, dtype / quantization) |
| E9 | N6 to N7 | the native proof-weight commitment commits to exactly those converted leaves |
| E10 | N7 to N8 | the proof's statement is checked against that weight commitment |
| E11 | N8 request / output | the statement's request and output are the client's exact request and the reply it was shown (token IDs, not reconstructed text) |
| E12 | N8 state | the statement's state root has an authenticated origin |
| E13 | N2 to N9 to N8 | the receipt is signed by the attested key of this boot and names this statement (authenticity, freshness) |
| E14 | physical execution to N8 | the engine that physically ran is the one the proof describes (expected: not an edge a proof can supply) |

If reading the evidence shows an edge must be split, merged or renamed, that is recorded under Amendments with the reason. No edge is dropped silently.

## Named counterexamples (from the issue, verbatim)

1. unrelated but valid package/proof roots
2. wrong config with same tensor names
3. exponent/integer-hash swap
4. subset root presented as full tree
5. authorized root but alternate loader
6. hot-swapped adapter
7. rollback to old approved code
8. receipt key from another boot
9. output reconstructed from different token IDs
10. state root without authenticated origin
11. a malicious runtime returning the same acceptable output

## Acceptance threshold

As the issue states it:

> Finish when every edge is typed/classified and every named counterexample has an explicit rejecting obligation or an honest UNRESOLVED designation

> Acceptance is a complete, non-circular obligation matrix, not every attack magically solved. Require the same-output physical-engine counterexample to remain undetectable by proof alone.

A counterexample without a rejecting obligation is marked UNRESOLVED. It is not argued away.

## Kill criterion

As the issue states it:

> FAIL if any signed assertion is silently promoted to proof or a subset result to full Qwen support. If a new soundness theorem/format is needed, name it and stop rather than expanding into a build.

Wall stop: three hours, ending 2026-11-17T12:00:00Z. At the stop the lane commits what exists and writes an honest PARTIAL or FAIL. The stop does not move.

Limits: desk and synthetic document vectors only, 512 MiB cap, CPU only. No experiments, no real attestation parsing claims, no model bytes, no weight conversion, no live route, no GPU, no deployment, no credentials, no new benchmark.

## Runs

None. Nothing is measured, so there is no n, no warmup and no seed.

An optional checker may be added after this commit. If it is, it reads synthetic documents only (the schema example and a machine-readable copy of the matrix), is deterministic, stays under 512 MiB, and is run twice with identical outcomes recorded. It checks the shape of the documents (fields present, one status per edge, every counterexample answered or UNRESOLVED). It does not check any cryptographic relation and its passing is not evidence that any edge holds.

## Prior art

Listed from the lane's general knowledge at registration. None of these was re-read for this commit, and the note will cite only what it actually reads.

- On main (to be re-read at the base commit before use): the weight-binding, conversion-identity, leaf-v2, key-file tensor binding, signed-manifest, client-envelope and served-reply-agreement results the issue names (#87, #100, #151, #121, #59, #122, #133).
- Remote attestation: the RATS architecture (RFC 9334) and its roles (attester, verifier, relying party, endorser, reference value provider); confidential-VM attestation (AMD SEV-SNP, Intel TDX) with measured launch and report data; GPU attestation for confidential computing.
- Measured storage: dm-verity root hashes over read-only block devices.
- Vendor documentation the issue links, read as published and labelled "from public documentation, not verified by us": `https://docs.tinfoil.sh/containers/models.md`, `https://docs.tinfoil.sh/verification/attestation-architecture.md`, `https://docs.tinfoil.sh/containers/attested-keys.md`.
- Supply-chain provenance: in-toto / SLSA attestations and model signing, which are signed assertions about build steps, not proofs of them.
- Verifiable inference: zkML systems that commit to weights inside the proof statement (for example EZKL, zkLLM), where the statement binds to a weight commitment but not to where those weights came from.

What is new here: a single typed chain for this repository that keeps four guarantees apart (physical execution evidence, proof of output consistency, receipt authenticity, checkpoint authorization) and marks, per edge, whether main verifies the relation or only carries an assertion of it.

## Amendments

(empty at registration)

### A-1, 2026-11-17T10:20Z: interruption, successor lane, and three edges split

Written before any note content exists on this branch. At this point the branch holds the registration commit only.

**Interruption.** Lane bridge210 registered this deliverable (09:01Z), read the evidence, and stopped at 09:20Z without writing any part of the note: its session ended on an output-length limit. It left no uncommitted work. Lane bridge210b (same model, a new session) continues on the same branch and pull request from 10:02Z. The successor re-read every evidence file itself on the base commit and fetched the three public vendor pages again; the first lane's reading notes were used as a list of places to look, not as facts.

**The wall stop does not move.** It stays 2026-11-17T12:00:00Z as registered. The 42 minutes between the two sessions count against the three hours. If the note is incomplete at the stop, the result is PARTIAL and says which edges are typed.

**Edges split, with the reason.** Reading the evidence showed that E5, E6 and E8 each join parts that have different producers, different verifiers and different statuses, so one status per edge would hide a gap. No edge is dropped; the registered wording of each is covered by its parts.

| registered edge | split into | reason |
|---|---|---|
| E5 (N3 to N4) | E5a: bytes read from the package volume are the bytes under the package root. E5b: what the runtime holds and computes with is exactly those bytes (loader, runtime dtype / quantization, adapters, anything read from elsewhere) | E5a is a block-level read check described in the public vendor pages. E5b is a statement about the behaviour of the loaded program, for which neither main nor the vendor pages read here name any check. N4 is split to match: N4a (file bytes as read), N4b (in-memory inventory) |
| E6 (N4 to N5) | E6a: the package root and the checkpoint id are two encodings of the same public revision (file-system image against per-tensor leaves). E6b: the configuration the runtime uses equals the configuration whose pin enters the conversion id | the tensor side and the config side are bound by different objects on main (checkpoint id; config pin inside the conversion id, DESIGN 2.0), and the config side also has to say which runtime settings are in no config file at all |
| E8 (N5 to N6) | E8a: the conversion id structure (config pin, per-block class, ordered sources, rule text, inventory). E8b: executable integers (exponent, integer hash) for the 78 registered plain-matrix blocks. E8c: the same for every remaining block, and the complete 722-leaf tree | on main these three have different standing: E8a and E8b are measured at hash level, E8c is not built. A single status for E8 would either promote a subset to the full model or hide what exists |

The edge list after this amendment has 18 edges: E1 to E4, E5a, E5b, E6a, E6b, E7, E8a, E8b, E8c, E9 to E14.

**Clarifications that change no rule.**

- An edge that is not split takes the status of its weakest necessary part, and the row says which parts exist.
- E14 was registered as "expected: not an edge a proof can supply". It still gets one of the four statuses, for the only kind of evidence that speaks to it (hardware-backed), and the row says a proof cannot supply it.
- A counterexample is answered either with a rejecting obligation (the edge, the check, who runs it, and the status of that check) or with UNRESOLVED. An obligation that is not built is listed as an obligation with its status; it is not reported as a rejection that exists. Where an obligation rejects only part of a counterexample, the remaining part is marked UNRESOLVED in the same row.
- No checker is added. The optional checker of the Runs section is not used.
