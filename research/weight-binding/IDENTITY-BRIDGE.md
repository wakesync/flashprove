# Design note: joining an attested loaded-weight identity to the weight commitment of a proof (issue #210)

Part of #36 and #6. Agenda U1 / U3 / Q2 / Q5. Registration: [PREREG](../../experiments/20261117-210-identity-bridge/PREREG.md), amendment A-1. Verdict: [RESULTS](../../experiments/20261117-210-identity-bridge/RESULTS.md).

Base: every `path:line` in this note is at main `5583d7f82b549454cdb6374d2fd347dfd9781976`.
Desk note. It changes no code, runs nothing and reports no measurement. It is a specification and an obligation matrix, not a proof and not a design that has been built. "Unknown" marks what this note did not establish.

Vendor material is used from three public pages only, named V1, V2 and V3 in section 8. Every statement taken from them is **from public documentation, not verified by us**, and is marked `[V1]`, `[V2]` or `[V3]`. Nothing here comes from any deployment, and no feature of any deployment is assumed.

## 1. Answer in three lines

1. **The join goes through one public revision that the client itself authorizes, not through the enclave.** From that revision the client, or an auditor it trusts, recomputes three things: the package root, the checkpoint id and the conversion id. It accepts a proof only under a commitment that a key-file claim binds to that conversion id. It never compares a package root with a tensor root (they hash different encodings), and it never takes the mapping between them from a signer.
2. **On main today the join cannot be made for Qwen.** Of the 18 edges, 4 are established on main within a stated scope (E7, E8a, E8b, E11), 5 rest on public vendor documentation only (E1, E2, E3, E4, E5a), 5 are proposed code (E6a, E8c, E10, E12, E13) and 4 are unsolved obligations (E5b, E6b, E9, E14). The edge that would bind the committed integers to the converted checkpoint, E9, has a research fixture on four tiny tensors and no bound that covers a derived point: only a fixed-pair bound is stated (section 5.3, O-1). Even with E9, a proof does not identify the physical run (E14).
3. **A proof and an attestation answer different questions and neither repairs the other.** All 11 named counterexamples have a rejecting obligation or the word UNRESOLVED in section 6. Code on main performs the rejecting check for one of them inside a stated scope (9), for three in part at hash level (2, 3, 4), and for none of the other seven (1, 5, 6, 7, 8, 10, 11). No case was run, so that is a count of the checks that exist, not of attacks seen to pass. A runtime that returns the same acceptable output from another engine stays undetectable by proof alone, by construction.

## 2. Scope, method, and what changed on main since the issue's snapshot

**Scope.** One typed chain from a client's approval of a measurement to the statement a proof is about, and the list of what must be checked at each step. Out of scope, as the issue says: a converter, a proof relation, an experiment, attestation parsing, model bytes, a live route, a GPU.

**Method.** Each evidence file the issue names was read in full on the base commit, with line numbers, and so were `research/weight-binding/DESIGN.md`, `research/envelope/SPEC.md` and `research/weight-binding/keyfile/README.md`. Every other file cited was read at the cited lines and their surroundings only, not in full; a statement elsewhere in those files that bears on an edge could have been missed. The three vendor pages were fetched on 2026-11-17 and read as published. V1 and V3 were fetched once. V2 was fetched twice: the first fetch was cut at 16,000 characters by the lane's own limit, and most of this note was written from it; the second fetch, at 11:13Z, returned the whole page, and the statements marked `[V2]` were then checked against it. That check changed the rollback rows (E1 and counterexample 7), which now say what the page says about a router. Each page opens by telling the reader to fetch a documentation index at another address; that is page content, it was not followed, and no other vendor address was fetched.

**What "established on main" means here.** Main has code and a merged result that performs the check named in the edge, inside the scope the row states. The row keeps the result's own label (hash level; measured, unreplicated; fixture). It is never a soundness claim, and a result on a subset stays a result on that subset.

**Changes since snapshot `83299f194b80f62feca170a28650b390add3fbdc`.** `git diff --stat` between the snapshot and the base, restricted to the seven evidence directories, `research/weight-binding`, `research/envelope` and `tools/manifest`:

| file | change | bears on |
|---|---|---|
| `experiments/20261112-149-leaf-v2/RESULTS.md` | +40 lines: two limits addenda from PR #191 (lines 96-134) | E8b, counterexample 4 |
| `research/weight-binding/README.md` | the same finding, stated for readers (lines 67-76, 121-123) | E8b |
| `research/weight-binding/test_wb_leafv2_evidence.py` | +162 lines of reader tests | E8b (readers only) |

The other six evidence files are byte-identical to the snapshot.

- **PR #191 bears on E8b.** The leaf-v2 readers give a full H3 `PASS` to truncated, reordered or substituted run files, because the status is computed on a union of runs and no record says which run produced it (`experiments/20261112-149-leaf-v2/RESULTS.md:118-130`). It is a statement about run-file provenance. It does not change a leaf, a tree or the opening verifier, and the committed H3 does not depend on the union (`:116`). It is used below as evidence that a subset can be reported as complete when nothing binds completeness.
- **PR #199 bears on no edge.** It changes one admission test of the CPU verifier (`H dh <= 2^20` in place of `H dh = d`). No proof with unequal widths exists and Qwen is still refused (`docs/qwen-port.md:56`).
- The other pull requests merged in that range were not read for this note. Only the fact that they do not touch the files above was checked.

## 3. Four separate guarantees

The issue asks for these to be stated separately. Each row says what the guarantee can say, what it cannot, and what stands behind it on main.

| | guarantee | can say | cannot say | on main |
|---|---|---|---|---|
| (a) | hardware-backed evidence of physical loading and execution | a machine whose boot chain has this measurement produced this report; a key belongs to that boot; reads of a weight volume were checked against a root `[V2]` `[V3]` | that the computation on those bytes was the model's; that a conversion is correct; anything at all if the hardware root, the firmware in the trusted base or the enclave is compromised | nothing is verified. The client "verifies no TEE evidence" and refuses any attestation kind but `none` and `MOCK` (`research/envelope/SPEC.md:98`, `:225-230`) |
| (b) | proof of output consistency against committed weights | under exact match, a `YES` is meant to tie a reply to the one fixed integer model under the commitment ID the client held beforehand (`docs/limits.md:169-171`), on the request file the client built itself (`docs/verifying.md:222-227`) | whose weights the commitment holds (`blocks/frame/heads.h:89-90`); where, when or for whom it ran (`research/coverage/inventory.yaml:1024-1026`, G-05); that an attestation is true; anything about confidentiality | exists for the upstream path on stored synthetic examples. For the programs the last step and the binding of weights to the ID are not shown (`docs/limits.md:171-174`). No Qwen proof exists (`docs/qwen-port.md:6-8`) |
| (c) | authenticity of a receipt | the holder of a key said these bytes (`research/envelope/SPEC.md:223-224`) | that what the bytes say is true: "a signature authenticates the signer, not the truth of what it signed" (`experiments/20261104-58-signed-manifest/RESULTS.md:90`) | Ed25519 envelope under a client-pinned key, TEST keys only (`research/envelope/SPEC.md:49-51`, `:243-244`) |
| (d) | authorization of the chosen checkpoint | nothing cryptographic. It is the client's decision: this revision, this conversion rule, this measurement | that the decision is a good one | the client must get the ID before the prompt, from the party that vouches for the model, over a channel the server does not control (`docs/verifying.md:38-41`). "The provider alone chooses the weights" (`docs/limits.md:176`) |

Which edge belongs to which guarantee (edges are defined in section 5):

| guarantee | edges |
|---|---|
| (a) hardware evidence | E2, E3, E4, E5a, E5b, E14 |
| (b) proof | E9, E10, E11, E12 |
| (c) receipt authenticity | E13 (E3 says which key) |
| (d) authorization | E1, E7 |
| public recomputation, no trust in the provider | E6a, E8a, E8b, E8c, and the recomputable part of E6b (the pin of the revision's configuration). The runtime part of E6b rests on E5b, group (a) |

Three rules follow, and the rest of the note keeps to them.

1. **A compromised enclave can sign anything**, including a false mapping from a package root to a weight commitment. So no edge of group (b) or of the recomputation group may take an input from a signer. A mapping the client did not recompute, or did not get from a party it authorizes under (d), is an assertion.
2. **A proof protects against a false mapping only where it checks the mapping itself.** That needs E9 (the committed table is the converted checkpoint) and E11 (the statement is the client's exact request and reply). Without E9, a valid proof is consistent with any weights the committer chose.
3. **No inference proof shows that an attestation is true, and none recovers confidentiality that was lost.** The proof and the attestation are checked independently, and a pass of one is never shown as a pass of the other (`README.md:98`; `docs/research-roadmap.md:38-39`; `research/envelope/SPEC.md:37-38`).

## 4. Objects and their exact canonical bytes

H is SHA-256. `lp(x)` is the 8-byte little-endian length of x followed by x (`research/weight-binding/wb_manifest.py:32-33`). "Not defined" means neither main nor the vendor pages read here fix the bytes.

| node | object | exact canonical bytes | defined where |
|---|---|---|---|
| N0 | client authorization policy | not defined. Proposed content: the public revision (repository and commit), the conversion rule version, the pack schema, the approved configuration source and minimum release, the commitment ID per request, the acceptance policy | this note (section 7); the envelope's canonical JSON rules could carry it (`research/envelope/SPEC.md:42-48`) |
| N1 | hardware attestation report and its measurement | a hardware-signed report over the measured firmware, kernel and initrd; the SHA-256 of the configuration file is embedded in the kernel command line, and the boot process checks the file on disk against that attested hash `[V2]`. Report layout: the hardware vendor's, not read here (Unknown) | `[V2]` |
| N2 | attested receipt key | the SPKI DER public key as lowercase hex, with its declared id and a format address, in the attestation document's key material `[V3]` | `[V3]` |
| N3 | package root | a dm-verity root hash over a read-only volume image; it is the leading part of the configuration's package value and depends on the pinned revision and a numbered pack schema `[V1]` | `[V1]` |
| N4a | file bytes as read from the package volume | the blocks of that volume | `[V1]` `[V2]` |
| N4b | in-memory inventory: the tensors, configuration and runtime settings the engine computes with | **not defined anywhere** | none |
| N5 | checkpoint id | leaf `H(0x00, "fp-wb-leaf-v1", lp(name), lp(dtype), lp(shape as compact JSON), sha256(tensor source bytes))`, sorted by name; node `H(0x01, "fp-wb-node-v1", l, r)`; id `H("fp-wb-id-v1", n as u64 LE, root)` | `research/weight-binding/wb_manifest.py:36-38`, `:41-42`, `:66-67`; `research/weight-binding/DESIGN.md:99-101` |
| N6 | conversion id | config pin `H("fp-wb-config-v2", lp(typed canonical fields))`; leaf v1 = canonical `{block, cls, sources, rule}` under `fp-wb-conv-leaf-v1`; id `H("fp-wb-conv-id-v1", checkpoint id, lp(rule version), config pin, n as u64 LE, root)`. Leaf v2 adds `e` and `int_sha256` under `fp-wb-conv-leaf-v2`; the only v2 id that exists is a subset id under `fp-wb-conv-subset-v2` | `research/weight-binding/wb_conv.py:203-204`, `:341-346`, `:361-362`; `research/weight-binding/wb_leafv2.py:53`, `:180-181` |
| N7 | native proof-weight commitment (commitment ID) | one hash, under its own domain, of the configuration digest, the anchor table's name, the anchor record's seeds and its answers | `blocks/frame/heads.h:78-91` |
| N8 | statement | the commitment ID, the configuration behind it, the policy and its numbers, and the exact request file (prompt tokens, reply tokens but the last, r, e) with y. Token files are 32-bit little-endian words. **There is no state root in this statement** | `research/envelope/SPEC.md:101-103`, `:52-53` |
| N9 | receipt | canonical JSON `{"body", "sig"}`; Ed25519 over `"flashprove-envelope-v1\0body\0"` followed by the canonical body | `research/envelope/SPEC.md:42-51` |

Two consequences that the edges rely on:

- **N3 and N5 hash different encodings of the same data.** N3 is a root over volume blocks that depends on a file layout `[V1]`. N5 is a root over per-tensor leaves, and deliberately not over files: all 18 shard file hashes of the two pins differ although 1,129 of 1,199 tensors are identical (`research/weight-binding/DESIGN.md:116-117`). No string comparison between the two means anything.
- **N5, N6 and N7 are three different hashes of three different things** (source bytes, a conversion description with integers, a committed table). On main only the first two are linked by construction (N6 hashes N5). The link from N6 to N7 is edge E9.

## 5. The bridge: every edge, typed

Each edge has the seven fields the issue lists and exactly one status:

- **MAIN**: established on main, inside the scope the row states and with the result's own label.
- **VENDOR**: documented by the vendor only. From public documentation, not verified by us. Main has no code that checks it.
- **PROPOSED**: proposed code. The check is specified here or in a design on main; it is not built, or it is built only for a neighbouring object.
- **UNSOLVED**: an unsolved cryptographic obligation. No construction on main or in the pages read here discharges it.

An edge that is not split takes the status of its weakest necessary part (PREREG A-1). "Verifier" always means a party other than the producer.

### 5.1 Approval, attestation, key, package (E1 to E4)

**E1. N0 to N1: this measurement is one the client approves. Status: VENDOR.**

| field | value |
|---|---|
| producer | a release pipeline publishes a signed bundle of expected measurements for a tagged configuration, recorded in a public append-only log `[V2]` |
| independent verifier | the client, which compares the attested measurement with one it approves. A vendor SDK does this `[V2]`; main has no such check |
| exact canonical bytes | the expected measurements in the signed bundle `[V2]`. Predicate layout not read here (Unknown) |
| authorization source | the client's policy N0. It must name a configuration source and a release, not accept "whatever the log holds" |
| binding mechanism | signature on the bundle plus log inclusion `[V2]` |
| update / rollback rule | a new release gives a new measurement `[V2]`. For one arrangement, a router enclave in front of model enclaves, the page says the router resolves the latest release of the model's repository, compares the attested measurement with it, never routes to an enclave that does not match, and stops routing to one whose attestation has expired `[V2]`. For a client that verifies an enclave directly, the pages read here do not say an older release is refused: the client's policy must carry a minimum release (counterexample 7) |
| availability dependency | the transparency log and the release host, or a cache of them. A cache can withhold material but not forge it `[V2]` |

**E2. Hardware root to N1: the report is genuine and carries this measurement. Status: VENDOR.**

| field | value |
|---|---|
| producer | the processor, which measures firmware, kernel and initrd at boot and signs the report `[V2]` |
| independent verifier | the client, checking the certificate chain to the hardware vendor's root `[V2]`. Main parses no attestation |
| exact canonical bytes | the hardware-signed report. Layout not read here (Unknown) |
| authorization source | the hardware vendor's root key, and the client's choice to trust it and a minimum platform version |
| binding mechanism | hardware signature and certificate chain `[V2]` |
| update / rollback rule | platform version and revocation checks. Not described in the pages read here (Unknown) |
| availability dependency | the hardware vendor's certificate service, or a cache `[V2]` |

The engine of interest runs on a GPU. The page says the boot process checks each GPU's attestation and aborts the boot if that fails, so that a client verifying the processor's report verifies the GPU configuration transitively `[V2]`. The client therefore sees no GPU evidence of its own: it rests on the measured boot code having made that check.

**E3. N1 to N2: this key was generated inside the measured boot the report describes. Status: VENDOR.**

| field | value |
|---|---|
| producer | the enclave generates the key pair before containers start; the measured configuration declares the key and the one container that receives it `[V3]` |
| independent verifier | the client, which must verify the attestation against the expected workload before trusting the key entry `[V3]` |
| exact canonical bytes | the SPKI DER public key, lowercase hex, with its id and format address `[V3]` |
| authorization source | the measured configuration (which key, which container) and E1 |
| binding mechanism | the attestation document endorses the public key `[V3]` |
| update / rollback rule | the key is the same for the life of one boot; a reboot, deploy or update generates new keys, and a client that pins a key must verify fresh attestation before replacing it `[V3]` |
| availability dependency | a fresh attestation document from the serving enclave |

Limits stated by the page itself: the feature is in beta; the granted application can read and copy its private key, so its handling of the key is part of the trusted workload; a container with administrative authority over the enclave can reach other containers' keys `[V3]`. So E3 says which boot a key belongs to. It does not say that a signature under that key was made by the code the client expects.

**E4. N1 to N3: the measured configuration fixes this package root. Status: VENDOR.**

| field | value |
|---|---|
| producer | the configuration file names the pinned revision and the package value, which begins with the root hash `[V1]` |
| independent verifier | the client reads the root from the configuration it approved under E1. Anyone can rebuild the package from the pinned revision and declared schema and compare roots `[V1]`. Not done by us |
| exact canonical bytes | the SHA-256 of the configuration file, embedded in the kernel command line `[V2]`; the root hash inside the package value `[V1]` |
| authorization source | E1 |
| binding mechanism | the boot process checks the configuration on disk against the attested hash `[V2]` |
| update / rollback rule | new weights need a new configuration and a new release `[V1]` |
| availability dependency | the public configuration repository |

E4 fixes which root the enclave was told to accept. Whether that root is the checkpoint the client chose is E6a and E7, and is not something the enclave decides.

### 5.2 Loading, the two encodings, and authorization (E5a to E7)

**E5a. N3 to N4a: bytes read from the package volume are the bytes under the package root. Status: VENDOR.**

| field | value |
|---|---|
| producer | the kernel's dm-verity layer validates each disk read against the root; the volume is mounted read-only `[V1]` `[V2]` |
| independent verifier | none outside the enclave. A client sees only the root in the measured configuration (E4) |
| exact canonical bytes | volume blocks under a Merkle root `[V2]` |
| authorization source | E4 |
| binding mechanism | per-read hash check; the enclave rejects a volume that does not match `[V2]` |
| update / rollback rule | the volume is read-only; a different volume needs a different root, hence a new configuration |
| availability dependency | none at request time |

**E5b. N4a to N4b: what the engine holds and computes with is exactly those bytes. Status: UNSOLVED.**

| field | value |
|---|---|
| producer | the loader and the inference engine inside the workload container |
| independent verifier | **none exists.** Neither main nor the pages read here name a check on what a loaded program does with the bytes it read |
| exact canonical bytes | not defined (N4b has no encoding) |
| authorization source | the measured container image and its command line, through E1 |
| binding mechanism | only indirect: the image and command are measured, so the client knows which program was started. That is a promise about a program's identity, not evidence of its behaviour |
| update / rollback rule | none |
| availability dependency | none |

What E5b would have to cover, each one a way for N4b to differ from N4a with every earlier edge intact:

- **Runtime dtype and quantization.** An engine can cast or quantize after reading. The served model in the one served result on main is described as BF16 "as reported by the deployment configuration (not independently hashed)" (`experiments/20261112-131-served-reply-agreement/RESULTS.md:21`).
- **Adapters and anything read from elsewhere.** Weights added, merged or replaced after load, from a second volume, a writable path, or the network. The pages read here describe an opt-in writable volume class that is "not part of the attestation measurement" `[V2]`.
- **Engine settings that change the function** and are in no checkpoint file: the chat template in force, sampling settings, a system prompt, a steering hook.
- **Which engine.** A measured image that contains two code paths.

This note names no construction that closes E5b by attestation alone. The proof side makes most of it unnecessary instead: if E9, E10 and E11 hold, the reply is shown consistent with the committed integers whatever the engine did. What then remains of E5b is exactly counterexample 11 and edge E14.

**E6a. N3 to N5: the package root and the checkpoint id are two encodings of the same public revision. Status: PROPOSED.**

| field | value |
|---|---|
| producer | nobody today. Proposed: a public, re-runnable derivation that takes the pinned revision and outputs both roots |
| independent verifier | the client or an auditor: rebuild the package from the revision and schema and compare with N3 `[V1]`; hash each tensor's source bytes from the same revision and compare with N5 (`research/weight-binding/wb_manifest.py:36-38`) |
| exact canonical bytes | the revision identifier (repository and commit) that both derivations start from; then N3 and N5 as in section 4 |
| authorization source | N0 names the revision |
| binding mechanism | **common preimage, recomputed.** Both roots are deterministic functions of the same public files. They are never compared with each other |
| update / rollback rule | a new revision changes both; a new pack schema changes N3 only `[V1]`; a new leaf version changes N5 only |
| availability dependency | the public revision must stay retrievable; the packing tool at the declared schema `[V1]` |

What exists: the N5 side, for two pins (1,199 leaves each, `experiments/20261110-36-weight-binding/RESULTS.md:78`), and a statement in the public pages that the N3 side is reproducible `[V1]`. What does not exist: any run by us of the N3 side, and any document that records both under one revision. For weights that are not public this edge has no recomputation, and falls back to a signer's word.

Main's own design already points at this join in three lines: a package root and a per-tensor manifest "can name the same tensors, which joins them", "Not designed further here" (`research/weight-binding/DESIGN.md:272-275`). This edge is the part that sentence leaves open. The two roots do not name the same bytes, so the join is the shared revision and two recomputations, not a correspondence between the roots.

**E6b. N4b configuration to the config pin inside N6: the configuration the runtime uses equals the configuration whose pin enters the conversion id. Status: UNSOLVED (PREREG A-2; it was PROPOSED before review).**

| field | value |
|---|---|
| producer | the conversion's config pin over 24 text fields and 3 top-level fields, typed, failing closed on unknown keys (`experiments/20261111-91-conversion-id/RESULTS.md:16-18`) |
| independent verifier | for the runtime side, **none exists**: whether the engine uses that file unmodified is E5b, which is UNSOLVED. For the file side, the client recomputes the pin from the revision's configuration file. That checks the configuration file of the revision. It does not check what a running engine uses |
| exact canonical bytes | `H("fp-wb-config-v2", lp(typed canonical fields))` (`research/weight-binding/wb_conv.py:203-204`) |
| authorization source | N0 (revision and rule version) |
| binding mechanism | file side only: the pin is hashed into the conversion id (`research/weight-binding/wb_conv.py:361-362`). Between the pin and what a runtime uses: none |
| update / rollback rule | any pinned field change gives a new conversion id; an unknown key refuses |
| availability dependency | none beyond the revision |

The parts of this edge, and which exist:

| part | standing |
|---|---|
| the pin itself, recomputed by the client from the revision's configuration file and hashed into the conversion id | exists on main, measured at hash level. It is the same pin that E8a carries, and it says nothing about a runtime |
| the pinned fields equal what the configuration under the commitment ID uses | proposed code: "Not built" (`research/weight-binding/DESIGN.md:198`) |
| the configuration a running engine uses equals the pinned one | no check exists. This is E5b's assertion, restricted to the configuration, and E5b is UNSOLVED |

Why the status is UNSOLVED and not PROPOSED. The registered wording of the edge is that the configuration the runtime uses equals the pinned one (PREREG A-1), so the third part is what the edge itself asserts, not a dependency of it. An edge that is not split takes the status of its weakest necessary part (PREREG A-1). That is the rule applied to E14 in section 5.4, and the E10 exception explained there does not fit: E10's own assertion can hold whatever E9 says, while E6b's own assertion is about the runtime. A reviewer pointed this out (PREREG A-2 has the reason and the link). The first two parts are not made stronger or weaker by the change. Fields deliberately left out of the pin are listed with reasons (`experiments/20261111-91-conversion-id/RESULTS.md:68`).

**E7. N0 to N5: the checkpoint id is the checkpoint the client chose. Status: MAIN (hash level, open weights only).**

| field | value |
|---|---|
| producer | anyone: the id is a function of the public pin only, with no commitment and no randomness (`research/weight-binding/DESIGN.md:59-62`) |
| independent verifier | the client, by recomputing it, or by holding an id from a party it trusts (`research/weight-binding/DESIGN.md:47-48`) |
| exact canonical bytes | N5 in section 4 |
| authorization source | the client's own choice of revision. This is guarantee (d): no cryptography makes the choice |
| binding mechanism | recomputation and comparison of 32 bytes; openings checked for a canonical index and path (`experiments/20261110-36-weight-binding/RESULTS.md:64-66`) |
| update / rollback rule | a new revision is a new id. Nothing links an old id to a new one |
| availability dependency | the public revision |

Scope of MAIN: per-tensor ids for two pins were built and each refuses the other's manifest and all 70 changed-tensor openings (`experiments/20261110-36-weight-binding/RESULTS.md:16-18`). It is hash bookkeeping: "Nothing in this experiment is a proof" (`:7`). The id covers all 1,199 source tensors, while the conversion design covers the 851 text tensors only (`research/weight-binding/DESIGN.md:167-171`).

### 5.3 Conversion and the table (E8a to E9)

The registered E8 says: the conversion leaf root is the complete, correct conversion of that checkpoint. "Complete" and "correct" are separate, and so is "for which blocks". For open weights the verifier of all three parts is anyone with the public revision and a CPU: the conversion is a deterministic public function, so the check is to recompute it. That is a recomputation, not a proof, and it is only as good as the determinism of the rule across machines.

**E8a. N5 to N6, structure: config pin, per-block class, ordered sources, rule text, inventory. Status: MAIN (hash level; rule text, not executable).**

| field | value |
|---|---|
| producer | anyone, from the checkpoint id, the rule version and the configuration (`research/weight-binding/DESIGN.md:63-70`) |
| independent verifier | the client or an auditor, by rebuilding it. Two builds per pin were byte-identical (`experiments/20261111-91-conversion-id/RESULTS.md:27`) |
| exact canonical bytes | N6 leaf v1 and id in section 4 |
| authorization source | N0: the rule version is the client's choice, like the revision |
| binding mechanism | Merkle tree over 722 leaves; the id hashes the checkpoint id, rule version, config pin, leaf count and root (`research/weight-binding/wb_conv.py:361-362`) |
| update / rollback rule | any change of rule text, class, source order or pinned config field gives a new id. Ids already changed once, when the config pin was corrected (`experiments/20261111-91-conversion-id/RESULTS.md:30-33`) |
| availability dependency | the revision |

Scope of MAIN: 128 of 128 named tests, including 21 same-tensor config cases refused and an inventory of 851 = 498 + 224 + 129 enforced by the builder (`experiments/20261111-91-conversion-id/RESULTS.md:23-26`, `:43`, `:62`). What it is not: "The rule strings are descriptions, not executable code" (`:66`). The id binds which rule text is named. It does not show that any integers follow that rule.

**E8b. N5 to N6, executable integers for the 78 registered plain-matrix blocks. Status: MAIN (hash level; this subset only).**

| field | value |
|---|---|
| producer | the executable matrix rule on the pinned bytes gives an exponent `e` and an integer hash `int_sha256` per block (`experiments/20261112-149-leaf-v2/RESULTS.md:44`) |
| independent verifier | anyone re-running the rule from the public pins. Two full runs in opposite orders agreed on all 78 blocks of both pins (`experiments/20261112-149-leaf-v2/RESULTS.md:15`). One implementation, one host type (`experiments/20261112-149-leaf-v2/RESULTS.md:47`, `:52`) |
| exact canonical bytes | leaf v2 = the v1 leaf plus `e` (an integer in [-64, 64]) and `int_sha256` (64 lowercase hex), under `fp-wb-conv-leaf-v2`; subset id under `fp-wb-conv-subset-v2` over (checkpoint id, rule version, config pin, n, root) (`research/weight-binding/wb_leafv2.py:53`, `:180-181`, `:209-219`) |
| authorization source | N0 |
| binding mechanism | Merkle opening against a held subset id; a v1 leaf or a v1 conversion-id opening is refused under the v2 id (`experiments/20261112-149-leaf-v2/RESULTS.md:16`) |
| update / rollback rule | a new leaf version has new domain tags |
| availability dependency | the revision, fetched by range request |

Scope of MAIN: 70 changed tensors and 8 controls, all of class `matrix_plain`. The subset ids "are not model conversion ids" (`experiments/20261112-149-leaf-v2/RESULTS.md:20`). The run files carry no provenance a reader can check (`experiments/20261112-149-leaf-v2/RESULTS.md:130`; section 2).

**E8c. N5 to N6, every remaining block and the complete tree. Status: PROPOSED.**

| field | value |
|---|---|
| producer | nobody today: "the 722-block leaf-v2 tree for a pin (55.6 GB per pin) is not built" (`experiments/20261112-149-leaf-v2/RESULTS.md:49`) |
| independent verifier | as E8b, once a rule is executable for every class; a second implementation is needed before agreement means more than one program repeating itself (`experiments/20261112-149-leaf-v2/RESULTS.md:52`) |
| exact canonical bytes | a full-model id in the v2 leaf format does not exist. It must not reuse the subset tag, and it must fix the leaf count to the inventory's 722 |
| authorization source | N0 |
| binding mechanism | the same tree, over all 722 leaves, with the count and the inventory checked by the builder as in E8a |
| update / rollback rule | as E8a |
| availability dependency | the revision; about 55.6 GB of source bytes per pin to read once |

What is missing, by the item the issue lists:

| item | where it lives | standing on main |
|---|---|---|
| plain matrices outside the subset | 128 plain-matrix blocks in all (`experiments/20261111-91-conversion-id/RESULTS.md:55`), 78 done, so 50 remain (counted here) | same rule as E8b, not run |
| folded norms | 129 norm tensors have no block of their own; each is bound through the matrix that reads it, whose leaf must name the norm's source leaf and the rule step, including the gain's form `1 + w` (`research/weight-binding/DESIGN.md:154`, `:172-173`) | 368 norm-folded matrix blocks: rule is text only (`experiments/20261112-149-leaf-v2/RESULTS.md:48`). The folded constant is a placeholder that would change the id (`experiments/20261111-91-conversion-id/RESULTS.md:67`) |
| transforms (derived cells) | `cA` comes from `A_log` through `exp`, in a named float format, then rounding; `dt_bias` and the gated-norm gain have their own rules (`research/weight-binding/DESIGN.md:156`) | 224 weight-cell blocks: text only |
| embedding and output head | two blocks, the head with the final norm folded in (`research/weight-binding/DESIGN.md:154`) | text only (`experiments/20261112-149-leaf-v2/RESULTS.md:48`) |
| dtype and quantization in the conversion | the rule fixes BF16 to binary32 exactly, then round-to-nearest-even at a per-block exponent to integers of magnitude at most 4,095 (`research/weight-binding/wb_conv.py:209`). A quantized or re-exponented copy has other integers and another id (`research/weight-binding/DESIGN.md:195`) | executable for plain matrices only |
| adapters | an adapter merged before conversion is a different checkpoint, hence a different N5 and N6. An adapter applied at run time is not in the conversion at all: that is E5b | no adapter case is tested anywhere on main (Unknown) |
| lookup tables | public function tables (activation, rotary, softmax) are not weights. They belong to the configuration under the commitment ID; the CPU verifier compares 24 table digests of a dense file with tables it computes itself, in planning calls only (`experiments/20261113-156-dense-table-digests/RESULTS.md:11-13`, `:143-145`, `:155-157`) | not part of N6; part of N7's configuration |

**E9. N6 to N7: the native commitment commits to exactly the converted leaves. Status: UNSOLVED.**

| field | value |
|---|---|
| producer | the committer, who alone sees the table. Today a per-tensor integer hash is "checked at commit time by the committer only; not in the ID, not seen by `cp_verify`" (`research/weight-binding/DESIGN.md:33`) |
| independent verifier | the client, through a key-file claim per block: the multilinear extension of the block's committed integers, at a point derived after the commitment, equals a value the verifier recomputes from the integers the conversion id names (`research/weight-binding/DESIGN.md:71-80`, `:125-133`). Or an auditor with a GPU, by rederiving the commitment from public weights (`:202-206`) |
| exact canonical bytes | points `H("fp-wb-point-v2", commitment ID, conversion id, block name, i)` mapped into the field (`research/weight-binding/DESIGN.md:73-74`). The Qwen placement of blocks in the table is not defined (`:246-247`) |
| authorization source | N0 holds both ids; the verifier never reads expected values from a proof (`research/weight-binding/keyfile/README.md:48-50`) |
| binding mechanism | proposed: one batched linear claim in the key file's one-time test. Order matters and is fixed: ids, then commitment, then points, then responses (`research/weight-binding/DESIGN.md:82-84`) |
| update / rollback rule | one set of responses per committed table. A new commitment needs a new key file |
| availability dependency | the key file; for open weights, the integers to recompute from |

What exists: a CPU research fixture that binds four length-four public tensors to a held checkpoint and conversion manifest inside the native key proof. Three complete substituted-table proofs were rejected by the native linear-claim check in 10 of 10 runs each (`experiments/20261111-36-keyfile-tensor-binding/RESULTS.md:5`, `:21-27`).

Why the status is UNSOLVED and not PROPOSED:

- That fixture "uses test-only hand plans; no error-accounting, hiding, Fiat-Shamir/grinding or soundness theorem is established" (`experiments/20261111-36-keyfile-tensor-binding/RESULTS.md:82`). Only a fixed-pair Schwartz-Zippel bound is stated for the design, and "adaptive grinding can amplify the error above the fixed-pair figure, by an amount not analysed" (`research/weight-binding/DESIGN.md:86-93`, `:260-262`).
- For the released programs, the binding of the weights to the commitment ID has not been shown at all (`docs/limits.md:173-174`).
- "No proof binds the committed table to this id" (`experiments/20261111-91-conversion-id/RESULTS.md:70`), and leaf v2 "does not show which integers a prover used" (`experiments/20261112-149-leaf-v2/RESULTS.md:50`).

This is the edge on which the whole join turns. Section 9 names the theorem and the format it needs (O-1, O-2). This note does not attempt either.

### 5.4 Statement, state, receipt, physical execution (E10 to E14)

**E10. N7 to N8: the proof's statement is checked against that weight commitment. Status: PROPOSED (for Qwen).**

| field | value |
|---|---|
| producer | the prover |
| independent verifier | the client, running a verifier it built itself with the ID it pinned (`docs/verifying.md:220-230`) |
| exact canonical bytes | the commitment ID passed as `-id` and echoed as `id=` in the result line (`research/envelope/SPEC.md:80`) |
| authorization source | N0: the ID is pinned before the prompt is sent (`docs/verifying.md:228-230`) |
| binding mechanism | every relation that reads a weight must read it from the committed table at an address the configuration fixes: matrix products, weight cells, folded norms, ranges, exponents (`research/weight-binding/DESIGN.md:147-159`) |
| update / rollback rule | a new commitment ID is not linked to the old one by any proof (`docs/verifying.md:44-45`) |
| availability dependency | the proof, the key file, the client's own verifier build |

What exists: for the upstream path on stored synthetic examples, a wrong ID is refused by the verifier itself (`NO: model-statement`, `experiments/20261104-58-signed-manifest/RESULTS.md:36-37`), and the client envelope refuses a substituted commitment before any proof runs (`experiments/20261111-9-client-envelope/RESULTS.md:40`). Why the edge is PROPOSED: the key file covers the upstream unit kinds only, with no Qwen layout (`research/weight-binding/DESIGN.md:32`); the Qwen weight cells and their tie to the table are "designed, counted, not built" (`:153`); "one gap is enough to serve another model" (`:147-148`); and no Qwen proof exists (`docs/qwen-port.md:6-8`). The soundness theorem on main is about the Lean verifier at full size and exact match, not about new operators (`research/coverage/inventory.yaml:1039-1041`).

**E11. N8 request and output: the statement is the client's exact request and the reply it was shown, as token ids. Status: MAIN (token ids; stored synthetic examples).**

| field | value |
|---|---|
| producer | the client itself: it builds the request file from its own prompt and the reply bytes it received (`experiments/20261111-9-client-envelope/RESULTS.md:16-18`) |
| independent verifier | the client's own run of the verifier on that file (`research/envelope/SPEC.md:184-190`) |
| exact canonical bytes | token files of 32-bit little-endian words; prompt and reply digests are SHA-256 of those files (`research/envelope/SPEC.md:52-53`, `:91-92`) |
| authorization source | the client's own prompt |
| binding mechanism | the relation fixes the request file (prompt tokens, reply tokens but the last, r, e) with y (`research/envelope/SPEC.md:101-103`) |
| update / rollback rule | one request file per request; a reply that differs is refused (`NO: reply-differs`, `experiments/20261111-9-client-envelope/RESULTS.md:44-45`) |
| availability dependency | the reply must reach the client as token ids |

Scope of MAIN: 41 vectors on two synthetic stored examples, "not a soundness claim" (`experiments/20261111-9-client-envelope/RESULTS.md:3-4`, `:97`). Outside the relation, by design: who chose the prompt tokens, which tokenizer and template made them, and tokens before r or after e (`research/coverage/inventory.yaml:1021-1023`, G-04); whether the reply is complete (`research/envelope/SPEC.md:93`). A route that returns text and counts only cannot satisfy this edge: there the ids are "reconstructed, not observed" (`experiments/20261112-131-served-reply-agreement/RESULTS.md:72`).

**E12. N8 state: a state root in the statement has an authenticated origin. Status: PROPOSED.**

| field | value |
|---|---|
| producer | the prover claims an output root; the client supplies the input root |
| independent verifier | the client. Proposed rule: an input root is accepted only if it is the genesis value the client computes itself, or the output root of a proof this client accepted earlier in the same session and recorded in its own state |
| exact canonical bytes | not defined for a real statement. The research prototype uses a field-native hash commitment of state, history and a private salt (`experiments/20261111-93-hidden-root-handoff/RESULTS.md:7`) |
| authorization source | the client's own session state |
| binding mechanism | inside the proof, open the input commitment, run from those cells, recompute the output commitment (`experiments/20261111-93-hidden-root-handoff/RESULTS.md:7`) |
| update / rollback rule | the client records the last accepted root with a sequence number and refuses an older one, as the envelope does for `state.seq` and `state.prev` (`research/envelope/SPEC.md:77-78`, `:108-113`) |
| availability dependency | the client's state file. Losing it means starting again from genesis |

What exists: continuity prototypes on synthetic state. Each one takes its first root on trust: "the first root is trusted as given" (`experiments/20261111-35-conv-history-binding/RESULTS.md:59`); the initial root is "produced here by the trusted test harness" and how a real verifier gets it "is out of scope" (`experiments/20261111-93-hidden-root-handoff/RESULTS.md:80`); in the first harness the link between chunks is a comparison of hashes "done outside the proofs" (`experiments/20261109-34-qwen-state-commit/RESULTS.md:13`). The prototype's sponge is unvetted and chain length is checked outside the proof (`research/coverage/inventory.yaml:1030-1032`, G-07). The upstream statement has no state root at all (section 4, N8).

**E13. N2 to N9 to N8: the receipt is signed by the attested key of this boot and names this statement. Status: PROPOSED.**

| field | value |
|---|---|
| producer | the serving workload that holds the private half of N2 |
| independent verifier | the client: first E1 to E3 on a fresh attestation document, then the signature under that key, then the checks the envelope already has (nonce outstanding, request digest, sequence, expiry, proof digest; `research/envelope/SPEC.md:165-190`) |
| exact canonical bytes | the envelope's canonical body under its domain prefix (`research/envelope/SPEC.md:42-51`), extended with the measurement, the attested key id and a digest of the attestation document (section 7; not built) |
| authorization source | N0 through E1 and E3, in place of a provider key pinned beforehand with no tie to a boot |
| binding mechanism | signature; a client-chosen 32-byte nonce for freshness (`research/envelope/SPEC.md:75`); the proof digest is signed so that what is checked is what was signed (`:97`) |
| update / rollback rule | a key lives for one boot and the client re-verifies attestation when it changes `[V3]`; a nonce is released at most once (`research/envelope/SPEC.md:112-113`) |
| availability dependency | the client's state file and clock; a fresh attestation document |

What exists: the envelope, signed by a client-pinned TEST key, with 35 of 35 attack vectors refused (`experiments/20261111-9-client-envelope/RESULTS.md:18-21`). What does not: any tie between the signing key and an attestation. The client refuses every attestation kind that claims hardware evidence (`research/envelope/SPEC.md:98`, `:169-170`), and the specification lists what a real milestone needs (`:227-230`). Freshness comes from the signature and the client's state, never from the proof: the same proof re-wrapped under a new nonce is released (`experiments/20261111-9-client-envelope/RESULTS.md:19-21`, `:100-101`).

A receipt is guarantee (c). It says the key holder vouched for these bytes. A compromised enclave signs a false receipt as easily as a true one.

**E14. Physical execution to N8: the engine that physically ran is the one the proof describes. Status: UNSOLVED. A proof cannot supply this edge.**

| field | value |
|---|---|
| producer | the hardware and the measured boot, through E2, E4 and E5a `[V2]` |
| independent verifier | the client, as far as E1 to E5a reach. Nothing on main |
| exact canonical bytes | none. No object ties a physical run to a statement |
| authorization source | E1 |
| binding mechanism | none between the engine and the proof. The evidence says a measured program was started with access to a verified volume. It does not say that program produced the reply: that is E5b |
| update / rollback rule | none |
| availability dependency | none |

The statement of a proof holds the commitment ID, the configuration, the policy, the request file and y (`research/envelope/SPEC.md:101-103`). It holds nothing about a machine, an engine or a time, and it "does not authenticate a provider" (`:231-233`). Any engine that returns the same tokens satisfies the same statement, and the proof can be made on another machine. So this edge has exactly one possible source, hardware-backed evidence, and that source is limited by E5b.

Why UNSOLVED and not VENDOR: the vendor pages document that a measured program was started with a verified volume (E2, E4, E5a). They do not document, and nothing else supplies, that this program produced the reply. The edge needs E5b, which is UNSOLVED, and an edge takes the status of its weakest necessary part (PREREG A-1). An earlier commit of this note (`e859e22`) gave E14 the status VENDOR. That overstated it and is corrected here.

The same rule does not move E10 to UNSOLVED, and the difference is this. What E14 itself asserts, that the engine which ran is the proved one, contains E5b's assertion as a part. What E10 asserts, that a statement is checked against a commitment, is a relation between N7 and N8 that can hold whatever N7 contains; it exists today for the upstream path. E10 depends on E9 for the join to mean anything (section 9.1), not for its own assertion. A reviewer who reads the rule more strictly would class E10 as UNSOLVED too; the count would then be PROPOSED 4, UNSOLVED 5, and nothing else in the note would change.

E6b is the other way round, and it is UNSOLVED since PREREG A-2: what E6b itself asserts is about the runtime, so E5b's assertion is a part of it, as it is for E14 (section 5.2).

### 5.5 All edges at a glance

| edge | says | status | guarantee |
|---|---|---|---|
| E1 | measurement approved | VENDOR | (d) |
| E2 | report genuine | VENDOR | (a) |
| E3 | key belongs to this boot | VENDOR | (a) |
| E4 | configuration fixes package root | VENDOR | (a) |
| E5a | reads match package root | VENDOR | (a) |
| E5b | engine computes with those bytes | UNSOLVED | (a) |
| E6a | package root and checkpoint id share one revision | PROPOSED | recomputation |
| E6b | runtime config equals pinned config | UNSOLVED (runtime side rests on E5b; the pin of the revision's file is recomputable) | (a) for the runtime side; recomputation for the pin |
| E7 | checkpoint id is the chosen checkpoint | MAIN, hash level, open weights | (d) |
| E8a | conversion id structure | MAIN, hash level, rule text | recomputation |
| E8b | integers for 78 plain-matrix blocks | MAIN, hash level, subset | recomputation |
| E8c | integers for all 722 blocks, full tree | PROPOSED | recomputation |
| E9 | commitment holds the converted leaves | UNSOLVED | (b) |
| E10 | statement checked against the commitment | PROPOSED for Qwen | (b) |
| E11 | statement is the client's exact token ids | MAIN, synthetic examples | (b) |
| E12 | state root has an authenticated origin | PROPOSED | (b) |
| E13 | receipt under the attested key names the statement | PROPOSED | (c) |
| E14 | the physical engine is the proved one | UNSOLVED, not suppliable by proof | (a) |

Counts: MAIN 4, VENDOR 5, PROPOSED 5, UNSOLVED 4, 18 edges in all. Before review the note had PROPOSED 6, UNSOLVED 3; the one change is E6b (PREREG A-2). No edge is MAIN for the full Qwen model under proof.

## 6. Attack / obligation table: the eleven named counterexamples

Each counterexample gets the obligation that would reject it (which edge, which check, who runs it), the standing of that check on main, and a designation. Three designations are used, and a row can carry more than one when the counterexample has parts:

- **REJECTED ON MAIN**: code on main performs the rejecting check, inside the scope stated.
- **OBLIGATION, NOT BUILT**: the rejecting check is specified and needs no new cryptography, but no code performs it.
- **UNRESOLVED**: no rejecting check is available, because it rests on an UNSOLVED edge or because none can exist.

An obligation that is not built is not a rejection. For every case not marked REJECTED ON MAIN, no implemented end-to-end rejecting obligation for the bridge specified here is established. That is a statement about which checks exist. It is not a statement that a client on main accepts the case: nothing was run, so no attack was observed to be accepted, and none is reported. Three things are kept apart in this section:

- **An unsupported input is refused.** Main's envelope client is fail-closed on attestation. It refuses every attestation kind that claims hardware evidence, and it refuses every envelope when the client requires TEE evidence (`research/envelope/client_verify.py:241-250`; `research/envelope/SPEC.md:169-170`, `:225-230`; `experiments/20261111-9-client-envelope/RESULTS.md:65-69`). The CPU verifier's admission test still refuses Qwen (`docs/qwen-port.md:56`), and no Qwen proof exists (`docs/qwen-port.md:6-8`). By that reading of the code and the specification, a case that presents hardware attestation, or a Qwen proof, is outside what main's client supports. That was read, not run. A refusal of that kind checks no relation of the bridge and joins nothing. It is not a working identity bridge and is not counted as a rejection of a counterexample.
- **A relation has no coverage.** No code on main checks the relation the obligation names. This is what NOT BUILT and UNRESOLVED mean here, and what "none" means in the summary column of section 6.3.
- **An attack is observed to be accepted.** Not observed, for any case. This note ran nothing.

### 6.1 Counterexamples 1 to 6

**1. Unrelated but valid package / proof roots.** The enclave attests a genuine package root for revision A. The proof verifies under a genuine commitment made from revision B. Each check passes alone.

- Rejecting obligation: the client names one revision R in N0 and recomputes, without any input from the provider, the package root for R (E6a) and the checkpoint and conversion ids for R (E7, E8). It rejects unless the attested root equals the recomputed one and the commitment is bound to the recomputed conversion id by a key-file claim (E9). It never compares the two roots with each other, and it never accepts a signed statement that they correspond.
- On main: the ids for R can be recomputed at hash level (E7, E8a). Nothing recomputes a package root. Nothing binds a commitment to a conversion id: "A commitment says nothing about which model it is" (`research/coverage/inventory.yaml:1012-1014`, G-01).
- Designation: **UNRESOLVED.** The package half is an obligation not built (E6a). The proof half rests on E9, which is UNSOLVED. Until E9 holds, the two roots stay unrelated for any verifier.

**2. Wrong config with the same tensor names.** Every tensor is the right one; the configuration differs (layer schedule, norm epsilon, rotary base, head counts).

- Rejecting obligation: the config pin inside the conversion id (E8a), and for the serving runtime E6b. The client recomputes the pin from the revision's configuration and holds the resulting id. That recomputation reaches the revision's file, not a running engine.
- On main: 21 same-tensor config cases are refused under the honest id, the schema fails closed on unknown keys, and the pin changed the ids when it was corrected (`experiments/20261111-91-conversion-id/RESULTS.md:23`, `:16`, `:30-33`). Hash level. Which fields change the function "is still a judgement" (`:68`).
- Designation: **REJECTED ON MAIN at hash level, for the conversion id.** Two parts remain. That the pinned fields equal what the configuration under the commitment ID uses: **OBLIGATION, NOT BUILT** (`research/weight-binding/DESIGN.md:198`). That the serving runtime uses that configuration: **UNRESOLVED** (E6b, which is UNSOLVED because it rests on E5b).

**3. Exponent / integer-hash swap.** A leaf carries the exponent of one block or pin with the integer hash of another, or either value altered.

- Rejecting obligation: leaf v2 binds `e` and `int_sha256` together with the block name, class, sources and rule in one leaf under one id (E8b). The client checks openings against the id it recomputed.
- On main: the opening verifier refuses every constructed case, "including wrong or swapped e_b / int_sha256_b and the other pin's values": 15 kinds on the two new fields (`experiments/20261112-149-leaf-v2/RESULTS.md:44`, `:16`). Hash level, 78 blocks.
- Designation: **REJECTED ON MAIN at hash level, for the 78 registered blocks.** For the other 644 blocks no such fields exist: **OBLIGATION, NOT BUILT** (E8c). That a prover's committed table holds the integers the leaf names: **UNRESOLVED** (E9; `experiments/20261112-149-leaf-v2/RESULTS.md:50`).

**4. Subset root presented as the full tree.** A root over some blocks is offered where a root over all 722 is expected.

- Rejecting obligation: (i) a subset id and a model id have different domain tags; (ii) the leaf count is hashed into the id; (iii) the client's policy fixes the count to the inventory's 722 and the kind to "full", and takes neither from the opening; (iv) under proof, the number of key-file claims equals the inventory count and is derived by the verifier, not read from the key file.
- On main: (i) holds, tags `fp-wb-conv-subset-v2` against `fp-wb-conv-id-v1`, and a v1 conversion-id opening is refused under a v2 id (`research/weight-binding/wb_leafv2.py:53`; `experiments/20261112-149-leaf-v2/RESULTS.md:16`). (ii) holds: an opening with n changed is refused (`research/weight-binding/test_wb_leafv2.py:128-132`). (iii) does not exist: the opening verifier takes n from the opening (`research/weight-binding/wb_leafv2.py:237`, `:246`), and no full-model v2 id exists to pin. (iv) does not exist.
- A warning from main's own history: with nothing binding completeness, the leaf-v2 readers reported a full `PASS` for cut run files, completed by a union with another run (`experiments/20261112-149-leaf-v2/RESULTS.md:118-126`). That is about run files, not ids, but it is the same failure shape.
- Designation: **REJECTED ON MAIN in part, at hash level** (i, ii). Pinned count and kind: **OBLIGATION, NOT BUILT** (E8c). Claim count under proof: **UNRESOLVED** (E9).

**5. Authorized root but alternate loader.** The package root is the approved one and every read is checked. The program that loads it is not the one the client assumes, or it loads something else as well.

- Rejecting obligation, attestation side: the approved measurement fixes the container image and its command line (E1, E4), so the client knows which program was started. Nothing checks what that program does with the bytes (E5b).
- Rejecting obligation, proof side: do not rely on the loader at all. If the commitment is bound to the conversion id (E9), the statement is checked against it (E10) and the statement is the client's own token ids (E11), a reply from any other loader fails unless it gives the same tokens.
- On main: no rejecting check on either side. No attestation is verified, and E9 and E10 do not hold for Qwen.
- Designation: **UNRESOLVED.** The attestation side rests on E5b (UNSOLVED). The proof side rests on E9 (UNSOLVED) and E10 (PROPOSED).

**6. Hot-swapped adapter.** After an honest load, weights are added or replaced in memory.

- Rejecting obligation: as counterexample 5. The measured boot fixes what was started, not what memory holds later; only a proof against bound weights speaks to the reply itself. The acceptance policy matters: under a tolerance policy a changed model's reply can pass, so the obligation requires exact match (`research/weight-binding/DESIGN.md:193`).
- On main: nothing for Qwen. A related measurement on a small synthetic model, with an honest prover only: under exact match 0 of 57 changed steered replies were accepted, under the shipped clipped-gap policy 5 of 54 were (`README.md:28`). No cheating prover was tested there, and it is not an adapter test.
- Designation: **UNRESOLVED** (E5b; the proof side needs E9, E10 and exact match). An adapter that happens to give the same tokens is counterexample 11.

### 6.2 Counterexamples 7 to 11

**7. Rollback to old approved code.** The enclave runs an older release that was approved once and has since been superseded, for example one with a known defect. Its measurement is genuine and is in the public log.

- Rejecting obligation: the client's policy N0 carries a minimum release, or an explicit list of approved measurements with an expiry, and rejects a measurement outside it (E1). An append-only log shows that a release existed; it does not say the release is still approved.
- On main: nothing. No attestation is verified. The pages read here say a changed configuration needs a new release with a new measurement, and describe a router enclave that admits only model enclaves matching "the latest release" of the model's repository `[V2]`. That is a rollback rule for that arrangement, run by the router and resting on the router's own measurement being approved by the client, which is the same question one level up. The pages do not say that a client verifying directly refuses an older release.
- Related, also open: nothing links a new commitment ID to an old one (`docs/verifying.md:44-45`), so the same rule is needed for commitments. And platform-version rollback at the hardware level is not described in the pages read here (Unknown, E2).
- Designation: **OBLIGATION, NOT BUILT** (E1, policy side). It needs no new cryptography, only a policy field and a check. For the hardware platform version: **UNRESOLVED** in this note, because the material read does not cover it.

**8. Receipt key from another boot.** A receipt is signed by a key that was genuinely attested, but in a different boot, a different enclave or an earlier deployment whose key was copied out.

- Rejecting obligation: the client verifies a fresh attestation document from the enclave it is talking to, takes the public key from that document's key material (E3), and accepts a receipt only under that key and only for a nonce it issued after that verification (E13). A key lives for one boot and must be re-verified when it changes `[V3]`.
- On main: nothing. The envelope's signing key is a key the client pinned beforehand, with no tie to a boot (`research/envelope/SPEC.md:73`), and any attestation kind that claims hardware evidence is refused (`:98`).
- A limit that the obligation does not remove: the granted application can read and copy its private key `[V3]`. If the key leaves the enclave during the same boot, a receipt made elsewhere verifies. The nonce stops replay of an old receipt; it does not stop a live signer outside the enclave. The same documentation describes a different key, the enclave's TLS key, as non-exportable `[V2]`. That key binds a live channel to the enclave. It is not a receipt: nothing signed under it is left for the client to keep or to show a third party.
- Designation: **OBLIGATION, NOT BUILT** for a key from another boot (E3, E13). For a key copied out within the same boot: **UNRESOLVED**.

**9. Output reconstructed from different token ids.** The text shown to the client is the same, but the token ids the model produced differ from the ids the proof is about.

- Rejecting obligation: the reply reaches the client as token ids; the client builds the request file from its own prompt ids and those reply ids, and runs the verifier itself (E11). The statement is then about exactly those ids. The client's displayed text is its own decoding of those ids.
- On main: the client envelope does this, and a reply that differs is refused (`research/envelope/SPEC.md:184-190`; `experiments/20261111-9-client-envelope/RESULTS.md:44-45`). Scope: two synthetic stored examples.
- What it does not cover: the tokenizer and template that turned the user's text into prompt ids are pins outside the relation (`research/coverage/inventory.yaml:1021-1023`, G-04). And a route that returns only text cannot meet the obligation: there the ids are rebuilt, and "Equal counts are necessary, not sufficient for equal ids" (`experiments/20261112-131-served-reply-agreement/RESULTS.md:27`).
- Designation: **REJECTED ON MAIN, inside that scope**, on the condition that the route delivers token ids. Where it delivers text only: **UNRESOLVED**, and the case is not a proof case at all.

**10. State root without authenticated origin.** A statement about a later window starts from a state root the prover supplied. The root is well formed and the window proof verifies from it.

- Rejecting obligation: the client accepts an input root only if it computed it itself (genesis) or recorded it as the output root of a proof it accepted earlier in the same session (E12). "A supplied intermediate state cannot bypass proof of its history" (`docs/research-roadmap.md:74`).
- On main: continuity only, on synthetic state, with the first root trusted as given in every prototype (`experiments/20261111-35-conv-history-binding/RESULTS.md:59`; `experiments/20261111-93-hidden-root-handoff/RESULTS.md:80`). No client keeps accepted roots, and the upstream statement has no state root.
- Designation: **OBLIGATION, NOT BUILT** (E12, the client-side rule). The proof-side part, a vetted state commitment with the chain length inside the proof, is open research on main (`research/coverage/inventory.yaml:1030-1032`, G-07): **UNRESOLVED**.

**11. A malicious runtime returning the same acceptable output.** The serving engine is not the committed model: other weights, another precision, a cache, a different machine. For this request it returns exactly the tokens the committed integer model would give. A valid proof is produced, by any machine that holds the committed weights.

- Rejecting obligation by proof: **none, and none can exist.** The proof's statement is the commitment, the configuration, the policy and the token ids (`research/envelope/SPEC.md:101-103`). The honest run and this run have the same statement. A verifier that accepts one accepts the other. This is not a defect of a particular proof system: a proof of a relation over public inputs carries no information about which process produced those inputs.
- What a proof does give here: the output is consistent with the committed weights. If that is all the client needs, this case does it no harm.
- What only hardware-backed evidence could add: that a measured program with access to a verified volume was running (E14). That evidence stops at E5b, and a compromised enclave defeats it.
- What neither gives: confidentiality. If the engine that saw the prompt was not the attested one, the prompt was exposed, and no proof recovers that.
- Designation: **UNRESOLVED, by construction. Undetectable by proof alone.** The acceptance rule of the issue requires this row to stay so, and it does.

### 6.3 Summary

The fourth column says which rejecting check code on main performs. "None" means no such check exists on main. It does not mean the case was run and accepted: nothing was run (see the three distinctions at the head of this section).

| # | counterexample | rejecting edges | rejecting check on main today | designation |
|---|---|---|---|---|
| 1 | unrelated but valid package / proof roots | E6a, E7, E8, E9 | none | UNRESOLVED (E9) |
| 2 | wrong config, same tensor names | E8a, E6b | rejected at hash level for the conversion id | REJECTED ON MAIN in part; rest NOT BUILT and UNRESOLVED (E6b, E5b) |
| 3 | exponent / integer-hash swap | E8b, E8c, E9 | rejected at hash level, 78 blocks | REJECTED ON MAIN in part; rest NOT BUILT and UNRESOLVED (E9) |
| 4 | subset root presented as full tree | E8b, E8c, E9 | tags and count hashed; count not pinned | REJECTED ON MAIN in part; rest NOT BUILT and UNRESOLVED (E9) |
| 5 | authorized root, alternate loader | E5b, or E9 + E10 + E11 | none | UNRESOLVED |
| 6 | hot-swapped adapter | E5b, or E9 + E10 + E11 with exact match | none | UNRESOLVED |
| 7 | rollback to old approved code | E1 (minimum release) | none | OBLIGATION, NOT BUILT; platform version UNRESOLVED |
| 8 | receipt key from another boot | E3, E13 | none | OBLIGATION, NOT BUILT; key copied within a boot UNRESOLVED |
| 9 | output rebuilt from different token ids | E11 | rejected, synthetic examples, ids delivered | REJECTED ON MAIN in scope; text-only routes UNRESOLVED |
| 10 | state root without authenticated origin | E12 | none | OBLIGATION, NOT BUILT; proof side UNRESOLVED |
| 11 | malicious runtime, same acceptable output | none possible by proof | none | UNRESOLVED by construction |

The matrix is non-circular in this sense: no obligation takes as input a value that only the party being checked can supply. Every recomputation starts from the revision in N0; the attestation edges start from the hardware root; the receipt starts from a nonce the client chose. Where a row would need the provider's word, it is marked UNRESOLVED instead.

## 7. Schema example (synthetic identifiers only)

Two documents: the policy the client writes before it sends anything (N0), and the evidence bundle it assembles for one request. **Every value below is made up.** Digests are a repeated two-hex-digit pattern, names begin with `example` or `synthetic`, and nothing is taken from any real deployment, model, key or measurement. This is a shape for discussion. It is not a format on main, nothing parses it, and the field names are proposals.

Each field of the bundle carries a `basis`, which is the point of the schema: a reader must be able to see, per field, whether the client recomputed it, verified it against hardware, verified it by proof, or was merely told it.

| basis | meaning |
|---|---|
| `client-chosen` | the client's own decision (guarantee d) |
| `client-recomputed` | derived by the client or its auditor from the public revision |
| `hardware-verified` | checked against a hardware root by the client (guarantee a). Not available on main |
| `proof-verified` | fixed by the relation, checked by the client's own verifier (guarantee b) |
| `signed-only` | only a signature stands behind it (guarantee c) |
| `asserted` | the provider's word, unsigned or signed; never used in a decision |

**Policy (N0), written before the request:**

```json
{
  "format": "example-bridge-policy-v0",
  "checkpoint": {
    "revision": "synthetic-org/synthetic-model@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "checkpoint_id": "1111111111111111111111111111111111111111111111111111111111111111",
    "n_source_tensors": 12
  },
  "conversion": {
    "rule_version": "synthetic-conv-rules-v0",
    "config_pin": "2222222222222222222222222222222222222222222222222222222222222222",
    "conversion_id": "3333333333333333333333333333333333333333333333333333333333333333",
    "kind": "full",
    "n_blocks": 8
  },
  "package": {
    "pack_schema": 1,
    "package_root": "4444444444444444444444444444444444444444444444444444444444444444"
  },
  "commitment_id": "5555555555555555555555555555555555555555555555555555555555555555",
  "acceptance": {"policy": "exact", "bits": 128},
  "attestation": {
    "required": 1,
    "config_source": "synthetic-org/synthetic-deploy-config",
    "min_release": 7,
    "receipt_key_id": "example-receipt"
  },
  "state": {"genesis_root": "6666666666666666666666666666666666666666666666666666666666666666"}
}
```

`package_root` (4444...) and `checkpoint_id` (1111...) are different strings and are meant to be. Both come from the same `revision`; neither is ever compared with the other. `kind` and `n_blocks` are pinned here so that an opening cannot supply its own count (counterexample 4). `min_release` is the rollback rule (counterexample 7).

**Evidence bundle for one request:**

```json
{
  "format": "example-bridge-evidence-v0",
  "request": {
    "nonce": "7777777777777777777777777777777777777777777777777777777777777777",
    "prompt_sha256": "8888888888888888888888888888888888888888888888888888888888888888",
    "basis": "client-chosen"
  },
  "attestation": {
    "measurement": "9999999999999999999999999999999999999999999999999999999999999999",
    "release": 7,
    "package_root": "4444444444444444444444444444444444444444444444444444444444444444",
    "receipt_key_spki": "abababababababababababababababababababababababababababababababab",
    "document_sha256": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
    "basis": "hardware-verified",
    "edges": ["E1", "E2", "E3", "E4"]
  },
  "weights": {
    "checkpoint_id": {"value": "1111111111111111111111111111111111111111111111111111111111111111", "basis": "client-recomputed", "edge": "E7"},
    "conversion_id": {"value": "3333333333333333333333333333333333333333333333333333333333333333", "basis": "client-recomputed", "edge": "E8"},
    "package_root": {"value": "4444444444444444444444444444444444444444444444444444444444444444", "basis": "client-recomputed", "edge": "E6a"},
    "table_binding": {"key_file_claims": 8, "basis": "proof-verified", "edge": "E9"}
  },
  "proof": {
    "commitment_id": "5555555555555555555555555555555555555555555555555555555555555555",
    "reply_sha256": "efefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefef",
    "verdict": "YES",
    "basis": "proof-verified",
    "edges": ["E10", "E11"]
  },
  "state": {
    "input_root": "6666666666666666666666666666666666666666666666666666666666666666",
    "input_origin": "genesis",
    "basis": "client-recomputed",
    "edge": "E12"
  },
  "receipt": {
    "signed_by": "example-receipt",
    "names_nonce": 1,
    "names_proof_sha256": 1,
    "basis": "signed-only",
    "edge": "E13"
  },
  "provider_says": {
    "model_label": "synthetic-model",
    "runtime_dtype": "example-dtype",
    "engine": "example-engine",
    "basis": "asserted"
  },
  "not_covered": ["E5b", "E6b", "E14"]
}
```

How a client would read it:

1. Every `client-recomputed` value must equal the policy's value. The provider supplies none of them.
2. `attestation.package_root` must equal the policy's `package_root`, and `attestation.release` must be at least `min_release`.
3. `proof.commitment_id` must equal the policy's, the verifier must have been run by the client on its own request file, and `table_binding.key_file_claims` must equal the policy's `n_blocks`.
4. The receipt must verify under `receipt_key_spki` from this bundle's attestation, and must name this nonce and this proof digest.
5. `provider_says` is displayed and decides nothing. `not_covered` is always shown.

A bundle that can be built from what is on main today would have `attestation.basis` absent (no hardware evidence is verified), `table_binding` absent (E9), `conversion.kind` equal to `subset` (E8b), and `state` absent. That bundle does not join anything, and a client should not present it as if it did.

## 8. Source map

Every statement in sections 1 to 7 carries its source where it is made: a `path:line` on main at the base commit, or a `[V1]` / `[V2]` / `[V3]` mark. This section lists the sources and what each is used for.

**How the citations were checked.** Each cited range was read by the lane on the base commit before it was written down. Separately, a small script kept outside the repository confirmed that every backticked path and `path:line` citation in this file names a file that exists and a range inside that file (0 problems; the count at the final commit is in RESULTS.md). That script checks existence and range only. It does not check that the lines say what the note says; that rests on the reading. It is not the optional checker of the PREREG, and its passing is not evidence for any edge.

### 8.1 Public documentation (from public documentation, not verified by us)

Fetched on 2026-11-17 (V2 twice, section 2), read as published, used as data only. Nothing in them was run, reproduced or checked against any system.

| mark | page | used for |
|---|---|---|
| V1 | `https://docs.tinfoil.sh/containers/models.md` | N3 and N4a; E4, E5a, E6a: a package with a dm-verity root built from a pinned revision and a numbered pack schema; the root is in the configuration; the package is described as reproducible by third parties; mounted read-only |
| V2 | `https://docs.tinfoil.sh/verification/attestation-architecture.md` (fetched twice, the second time in full; see section 2) | N1; E1, E2, E4, E5a, E14; counterexample 7: what is measured at boot; the configuration hash in the kernel command line and the boot-time check; signed expected measurements in a public log; certificate chain to the hardware root; caches cannot forge; a writable volume class outside the measurement; a router that admits only enclaves matching the latest release |
| V3 | `https://docs.tinfoil.sh/containers/attested-keys.md` | N2; E3, E13; counterexample 8: keys generated in the enclave before containers start; the public key in the attestation document's key material; one key per boot; beta status; the granted application can read and copy its private key |

Not used from these pages: any identifier, example value, host name, command or product claim beyond the mechanisms above. The pages' linked blog post, specification and repositories were not read.

### 8.2 Main at `5583d7f82b549454cdb6374d2fd347dfd9781976`

| source | lines cited | used for |
|---|---|---|
| `experiments/20261110-36-weight-binding/RESULTS.md` (#87) | 7, 16-18, 64-66, 78 | E7; N5: per-tensor ids for two pins, hash level, not a proof |
| `experiments/20261111-91-conversion-id/RESULTS.md` (#100) | 16-18, 23-27, 30-33, 43, 55, 62, 66-68, 70 | E6b, E8a, E8c, E9; counterexample 2: config pin, inventory, rule text not executable, no proof binds the table |
| `experiments/20261112-149-leaf-v2/RESULTS.md` (#151, addenda #191) | 15, 16, 20, 44, 47-50, 52, 96-134 | E8b, E8c, E9; counterexamples 3 and 4; section 2 |
| `experiments/20261111-36-keyfile-tensor-binding/RESULTS.md` (#121) | 5, 21-27, 82 | E9: the small-key fixture and its limits |
| `experiments/20261104-58-signed-manifest/RESULTS.md` (#59) | 36-37, 90 | guarantee (c); E10 |
| `experiments/20261111-9-client-envelope/RESULTS.md` (#122) | 3-4, 16-21, 40, 44-45, 65-69, 97, 100-101 | E10, E11, E13; counterexample 9; section 6 (a claimed hardware attestation is refused) |
| `experiments/20261112-131-served-reply-agreement/RESULTS.md` (#133) | 21, 27, 72 | E5b, E11; counterexample 9: reported identity, rebuilt ids |
| `research/weight-binding/DESIGN.md` | 32-33, 47-48, 59-93, 99-101, 116-117, 125-133, 147-159, 167-173, 193, 195, 198, 202-206, 246-247, 260-262, 272-275 | N5, N6; E6a, E6b, E7, E8a, E8c, E9, E10; counterexamples 2 and 6 |
| `research/weight-binding/wb_manifest.py`, `research/weight-binding/wb_conv.py`, `research/weight-binding/wb_leafv2.py`, `research/weight-binding/test_wb_leafv2.py` | as cited in sections 4 to 6 | exact bytes of N5 and N6; counterexample 4 |
| `research/weight-binding/README.md`, `research/weight-binding/keyfile/README.md` | 67-76, 121-123; 43-46, 48-50 | section 2; E9 |
| `research/envelope/SPEC.md` | 37-38, 42-53, 73-98, 101-103, 108-113, 165-190, 223-233, 243-244 | N8, N9; guarantees (a) to (c); E10 to E14; counterexamples 8, 9, 11; section 6 (fail-closed refusal) |
| `research/envelope/client_verify.py` | 241-250 | section 6 and section 10: the client refuses a claimed hardware attestation kind, and refuses every envelope when TEE evidence is required |
| `blocks/frame/heads.h` | 78-91 | N7: what the commitment ID hashes, and that it does not say whose weights |
| `docs/limits.md` | 169-176 | guarantees (b), (d); E9 |
| `docs/verifying.md` | 38-45, 220-230 | guarantee (d); E10; counterexample 7 |
| `research/coverage/inventory.yaml` | 1012-1014, 1021-1026, 1030-1032, 1039-1041 | gaps G-01, G-04, G-05, G-07, G-OB3 |
| `docs/qwen-port.md` | 6-8, 56 | no Qwen proof exists; PR #199 |
| `docs/research-roadmap.md`, `README.md` | 38-39, 74; 28, 98 | rule 3 of section 3; counterexamples 6 and 10 |
| `experiments/20261109-34-qwen-state-commit/RESULTS.md`, `experiments/20261111-35-conv-history-binding/RESULTS.md`, `experiments/20261111-93-hidden-root-handoff/RESULTS.md` | 13; 59; 7, 80 | E12; counterexample 10 |
| `experiments/20261113-156-dense-table-digests/RESULTS.md` | 11-13, 143-145, 155-157 | lookup tables (E8c table) |

### 8.3 Statements with no external source

These are this note's own, and are proposals or reasoning, not findings:

- the edge list and the split of E5, E6 and E8 (PREREG and amendment A-1);
- the "common preimage, recomputed" rule of E6a, the pinned count and kind of counterexample 4, the minimum release of counterexample 7, and the state-origin rule of E12;
- the schema of section 7;
- the argument of counterexample 11 and E14 that a proof over public inputs cannot identify the process that produced them. It is an argument from what the statement contains, not a theorem proved here;
- two counts derived here from cited figures: 50 remaining plain-matrix blocks (128 less 78) and 644 remaining blocks (722 less 78).

## 9. Dependencies, named open obligations, and stop rule

### 9.1 Dependencies between edges

- E6a, E7 and E8 all start from the revision in N0. Without a client-chosen revision none of them means anything.
- E9 needs E8c: a table can only be bound to a complete conversion id if one exists. Binding to a subset id proves nothing about the blocks outside it.
- E10 needs E9. Without it, a statement checked against a commitment is checked against weights the committer chose.
- E13 needs E1, E2 and E3. Without them the receipt key is a provider key and the receipt is guarantee (c) only.
- E14 needs E5b, and E5b has no known check. So E14 is UNSOLVED: what the vendor pages document is what was started, not what produced the reply.
- E6b needs E5b for the same reason, restricted to the configuration: no check says what configuration a running engine uses. So E6b is UNSOLVED (PREREG A-2). Its file side, the pin recomputed from the revision's configuration, is the pin E8a carries and does not depend on E5b; the equality of the pinned fields with the configuration under the commitment ID is proposed code, not built.
- E12 is independent of the weight chain. It is needed only for statements that start from carried state.

### 9.2 Named open obligations

The issue says: if a new soundness theorem or format is needed, name it and stop. Both are needed. They are named here and not attempted.

| id | kind | what is needed | for | where main stands |
|---|---|---|---|---|
| O-1 | **new soundness theorem** | a bound for the per-block evaluation claim when the evaluation point is derived by hashing the commitment: the committer can re-randomise the commitment and try again, so the fixed-pair Schwartz-Zippel figure is not the error. The analysis must count the committer's hash queries over the commitment, the point index and the block name | E9 | only the fixed-pair bound is stated; the analysis is listed as open (`research/weight-binding/DESIGN.md:86-93`, `:260-262`) |
| O-2 | **new format** | a key-file format version carrying one batched claim per effective block, with the Qwen placement of blocks in the weight table and a range proof on that layout | E9, E10 | "Needs a protocol change: a new item in the key file's first chain, a format version, and the Qwen placement" (`research/weight-binding/DESIGN.md:209-210`); the fixture format is research only (`research/weight-binding/keyfile/README.md:43-46`) |
| O-3 | proposed code, large | executable conversion rules for the 644 blocks outside the subset, the complete 722-leaf v2 tree, and a second independent implementation | E8c | text only for those classes (`experiments/20261112-149-leaf-v2/RESULTS.md:48-49`, `:52`) |
| O-4 | proposed code | a full-model v2 id with its own domain tag, and a client policy that pins the leaf count and the kind | E8c, counterexample 4 | not built |
| O-5 | proposed code, outside this repository's current scope | a client that verifies hardware evidence: certificate chain, platform version, freshness, measurement policy with a minimum release, attested key | E1, E2, E3, E13, counterexamples 7 and 8 | the envelope specification lists the same needs and builds none (`research/envelope/SPEC.md:227-230`) |
| O-6 | proposed code | a public derivation that records, for one revision, the package root and the checkpoint id, re-runnable by a third party | E6a, counterexample 1 | not built; the package side has never been run by us |
| O-7 | open, no construction known to this note | evidence that a loaded engine computes with exactly the bytes it read, covering dtype, quantization, adapters, settings and the configuration in use | E5b, E6b, E14, counterexamples 2 (runtime part), 5, 6 and 11 | none |
| O-8 | proposed code plus open research | a client-side rule for the origin of state roots, and a vetted state commitment with the chain length inside the proof | E12, counterexample 10 | prototypes with a trusted first root (`research/coverage/inventory.yaml:1030-1032`) |

O-1 and O-2 are the two items the issue's stop rule is about. O-7 is not a missing theorem: it is a question no proof system in this repository addresses, and this note does not claim it can be closed.

### 9.3 Stop rule

This note stops here. It does not design the O-2 format, attempt the O-1 analysis, write a converter, or add a checker. Any of O-1 to O-8 needs its own issue, registration and review. The smallest follow-up that involves a GPU is, per the issue, a separate decision and is not filed by this note.

## 10. What this note does not establish

- **Nothing was run.** No model, weight, attestation, key, proof or route was touched. Every status is a reading of main and of three public pages.
- **No vendor statement was verified.** The five VENDOR edges are descriptions from public documentation. Whether any system behaves as described is not known to this note. Most of the note was written from a cut copy of one page (V2); its `[V2]` statements were checked against the full page afterwards (section 2).
- **No Qwen proof exists**, so no edge of group (b) holds for Qwen. E11 is MAIN for token ids on two synthetic stored examples only.
- **The MAIN edges are hash-level bookkeeping or application checks, measured and unreplicated.** E7, E8a and E8b are not proofs. E8b covers 78 of 722 blocks and is not full Qwen support, and nothing here should be read as saying the conversion of the model is done or correct.
- **The obligations in section 6 are not rejections, and a missing rejection is not an observed acceptance.** Where a row says NOT BUILT or UNRESOLVED, no implemented end-to-end rejecting obligation for the specified bridge is established. No counterexample was run against any client, so no acceptance was observed. Main's envelope client refuses any attestation kind that claims hardware evidence, and any envelope when TEE evidence is required (`research/envelope/client_verify.py:241-250`). That refusal is not a working identity bridge: it checks no relation of the bridge.
- **Completeness of the edge list is not shown.** The 18 edges come from the issue's wording and one reading of the evidence. An attack that fits no listed edge would not appear in this matrix. The eleven counterexamples are the issue's list, not an exhaustive one.
- **The argument that counterexample 11 is undetectable by proof alone is an argument, not a theorem.** It rests on what the statement contains.
- **Hidden weights are not treated.** Every recomputation edge assumes public weights. With hidden weights the client cannot recompute, and E6a, E7 and E8 fall back to a party the client trusts.
- **Confidentiality, privacy and zero knowledge are out of scope.** No edge says a prompt or a weight stayed secret.
- **The schema of section 7 is a discussion shape.** It is not a format, nothing parses it, and its field names bind nobody.
- Not replicated and not reviewed at the time of writing.
