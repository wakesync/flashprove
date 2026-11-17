# Design note: joining an attested loaded-weight identity to the weight commitment of a proof (issue #210)

Part of #36 and #6. Agenda U1 / U3 / Q2 / Q5. Registration: [PREREG](../../experiments/20261117-210-identity-bridge/PREREG.md), amendment A-1. Verdict: [RESULTS](../../experiments/20261117-210-identity-bridge/RESULTS.md).

Base: every `path:line` in this note is at main `5583d7f82b549454cdb6374d2fd347dfd9781976`.
Desk note. It changes no code, runs nothing and reports no measurement. It is a specification and an obligation matrix, not a proof and not a design that has been built. "Unknown" marks what this note did not establish.

Vendor material is used from three public pages only, named V1, V2 and V3 in section 8. Every statement taken from them is **from public documentation, not verified by us**, and is marked `[V1]`, `[V2]` or `[V3]`. Nothing here comes from any deployment, and no feature of any deployment is assumed.

## 1. Answer in three lines

1. **The join goes through one public revision that the client itself authorizes, not through the enclave.** From that revision the client, or an auditor it trusts, recomputes three things: the package root, the checkpoint id and the conversion id. It accepts a proof only under a commitment that a key-file claim binds to that conversion id. It never compares a package root with a tensor root (they hash different encodings), and it never takes the mapping between them from a signer.
2. **On main today the join cannot be made for Qwen.** Of the 18 edges, 4 are established on main within a stated scope (E7, E8a, E8b, E11), 6 rest on public vendor documentation only (E1, E2, E3, E4, E5a, E14), 6 are proposed code (E6a, E6b, E8c, E10, E12, E13) and 2 are unsolved obligations (E5b, E9). The edge that would make a proof say which weights ran, E9, has a research fixture on four tiny tensors and no security bound.
3. **A proof and an attestation answer different questions and neither repairs the other.** All 11 named counterexamples have a rejecting obligation or the word UNRESOLVED in section 6. Main rejects one of them today inside a stated scope (9), three in part at hash level (2, 3, 4) and seven not at all (1, 5, 6, 7, 8, 10, 11). A runtime that returns the same acceptable output from another engine stays undetectable by proof alone, by construction.

## 2. Scope, method, and what changed on main since the issue's snapshot

**Scope.** One typed chain from a client's approval of a measurement to the statement a proof is about, and the list of what must be checked at each step. Out of scope, as the issue says: a converter, a proof relation, an experiment, attestation parsing, model bytes, a live route, a GPU.

**Method.** Each evidence file the issue names was read in full on the base commit, with line numbers. The three vendor pages were fetched once each on 2026-11-17 and read as published. Each page opens by telling the reader to fetch a documentation index at another address; that is page content, it was not followed, and no other vendor address was fetched. One page (V2) was read up to a 16,000 character cut; nothing after the cut is used.

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
| public recomputation, no trust in the provider | E6a, E6b, E8a, E8b, E8c |

Three rules follow, and the rest of the note keeps to them.

1. **A compromised enclave can sign anything**, including a false mapping from a package root to a weight commitment. So no edge of group (b) or of the recomputation group may take an input from a signer. A mapping the client did not recompute, or did not get from a party it authorizes under (d), is an assertion.
2. **A proof protects against a false mapping only where it checks the mapping itself.** That needs E9 (the committed table is the converted checkpoint) and E11 (the statement is the client's exact request and reply). Without E9, a valid proof is consistent with any weights the committer chose.
3. **No inference proof shows that an attestation is true, and none recovers confidentiality that was lost.** The proof and the attestation are checked independently, and a pass of one is never shown as a pass of the other (`README.md:98`; `docs/research-roadmap.md:38-39`; `research/envelope/SPEC.md:37-38`).

## 4. Objects and their exact canonical bytes

H is SHA-256. `lp(x)` is the 8-byte little-endian length of x followed by x (`research/weight-binding/wb_manifest.py:32-33`). "Not defined" means neither main nor the vendor pages read here fix the bytes.

| node | object | exact canonical bytes | defined where |
|---|---|---|---|
| N0 | client authorization policy | not defined. Proposed content: the public revision (repository and commit), the conversion rule version, the pack schema, the approved configuration source and minimum release, the commitment ID per request, the acceptance policy | this note (section 7); the envelope's canonical JSON rules could carry it (`research/envelope/SPEC.md:42-48`) |
| N1 | hardware attestation report and its measurement | a hardware-signed report over the measured firmware, kernel and initrd; the SHA-256 of the configuration file sits in the measured kernel command line `[V2]`. Report layout: the hardware vendor's, not read here (Unknown) | `[V2]` |
| N2 | attested receipt key | the SPKI DER public key as lowercase hex, with its declared id and a format address, in the attestation document's key material `[V3]` | `[V3]` |
| N3 | package root | a dm-verity root hash over a read-only volume image; it is the leading part of the configuration's package value and depends on the pinned revision and a numbered pack schema `[V1]` | `[V1]` |
| N4a | file bytes as read from the package volume | the blocks of that volume | `[V1]` `[V2]` |
| N4b | in-memory inventory: the tensors, configuration and runtime settings the engine computes with | **not defined anywhere** | none |
| N5 | checkpoint id | leaf `H(0x00, "fp-wb-leaf-v1", lp(name), lp(dtype), lp(shape as compact JSON), sha256(tensor source bytes))`, sorted by name; node `H(0x01, "fp-wb-node-v1", l, r)`; id `H("fp-wb-id-v1", n as u64 LE, root)` | `research/weight-binding/wb_manifest.py:36-38`, `:41-42`, `:66-67`; `research/weight-binding/DESIGN.md:99-101` |
| N6 | conversion id | config pin `H("fp-wb-config-v2", lp(typed canonical fields))`; leaf v1 = canonical `{block, cls, sources, rule}` under `fp-wb-conv-leaf-v1`; id `H("fp-wb-conv-id-v1", checkpoint id, lp(rule version), config pin, n as u64 LE, root)`. Leaf v2 adds `e` and `int_sha256` under `fp-wb-conv-leaf-v2`; the only v2 id that exists is a subset id under `fp-wb-conv-subset-v2` | `research/weight-binding/wb_conv.py:203-204`, `:341-346`, `:361-362`; `research/weight-binding/wb_leafv2.py:53`, `:180-181` |
| N7 | native proof-weight commitment (commitment ID) | one hash, under its own domain, of the configuration digest, the anchor table's name, the anchor record's seeds and its answers | `blocks/frame/heads.h:78-91` |
| N8 | statement | the commitment ID, the configuration behind it, the policy and its numbers, and the exact request file (prompt tokens, reply tokens but the last, r, e) with y. Token files are 32-bit little-endian words. **There is no state root in this statement** | `research/envelope/SPEC.md:101-102`, `:52-53` |
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
| update / rollback rule | a new release gives a new measurement `[V2]`. Nothing in the pages read here says an older release is refused: the client's policy must carry a minimum release (counterexample 7) |
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
| exact canonical bytes | the SHA-256 of the configuration file in the measured kernel command line `[V2]`; the root hash inside the package value `[V1]` |
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

**E6b. N4b configuration to the config pin inside N6. Status: PROPOSED.**

| field | value |
|---|---|
| producer | the conversion's config pin over 24 text fields and 3 top-level fields, typed, failing closed on unknown keys (`experiments/20261111-91-conversion-id/RESULTS.md:16-18`) |
| independent verifier | the client recomputes the pin from the revision's configuration file. Whether the engine uses that file unmodified is E5b |
| exact canonical bytes | `H("fp-wb-config-v2", lp(typed canonical fields))` (`research/weight-binding/wb_conv.py:203-204`) |
| authorization source | N0 (revision and rule version) |
| binding mechanism | the pin is hashed into the conversion id (`research/weight-binding/wb_conv.py:361-362`) |
| update / rollback rule | any pinned field change gives a new conversion id; an unknown key refuses |
| availability dependency | none beyond the revision |

The pin exists and is measured at hash level. The edge is PROPOSED, not MAIN, because two parts are missing: nothing ties the pin to what a runtime uses, and the design also requires the pinned fields to equal what the configuration under the commitment ID uses, which is "Not built" (`research/weight-binding/DESIGN.md:198`). Fields deliberately left out of the pin are listed with reasons (`experiments/20261111-91-conversion-id/RESULTS.md:68`).

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
| independent verifier | anyone re-running the rule from the public pins. Two full runs in opposite orders agreed on all 78 blocks of both pins (`:15`). One implementation, one host type (`:47`, `:52`) |
| exact canonical bytes | leaf v2 = the v1 leaf plus `e` (an integer in [-64, 64]) and `int_sha256` (64 lowercase hex), under `fp-wb-conv-leaf-v2`; subset id under `fp-wb-conv-subset-v2` over (checkpoint id, rule version, config pin, n, root) (`research/weight-binding/wb_leafv2.py:53`, `:180-181`, `:209-219`) |
| authorization source | N0 |
| binding mechanism | Merkle opening against a held subset id; a v1 leaf or a v1 conversion-id opening is refused under the v2 id (`experiments/20261112-149-leaf-v2/RESULTS.md:16`) |
| update / rollback rule | a new leaf version has new domain tags |
| availability dependency | the revision, fetched by range request |

Scope of MAIN: 70 changed tensors and 8 controls, all of class `matrix_plain`. The subset ids "are not model conversion ids" (`:20`). The run files carry no provenance a reader can check (`:130`; section 2).

**E8c. N5 to N6, every remaining block and the complete tree. Status: PROPOSED.**

| field | value |
|---|---|
| producer | nobody today. "The 722-block leaf-v2 tree for a pin (55.6 GB per pin) is not built" (`experiments/20261112-149-leaf-v2/RESULTS.md:49`) |
| independent verifier | as E8b, once a rule is executable for every class; a second implementation is needed before agreement means more than one program repeating itself (`:52`) |
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
| embedding and output head | two blocks, the head with the final norm folded in | text only |
| dtype and quantization in the conversion | the rule fixes BF16 to binary32 exactly, then round-to-nearest-even at a per-block exponent to integers of magnitude at most 4,095 (`research/weight-binding/wb_conv.py:209`). A quantized or re-exponented copy has other integers and another id (`research/weight-binding/DESIGN.md:195`) | executable for plain matrices only |
| adapters | an adapter merged before conversion is a different checkpoint, hence a different N5 and N6. An adapter applied at run time is not in the conversion at all: that is E5b | no adapter case is tested anywhere on main (Unknown) |
| lookup tables | public function tables (activation, rotary, softmax) are not weights. They belong to the configuration under the commitment ID; the CPU verifier compares 24 table digests of a dense file with tables it computes itself, in planning calls only (`experiments/20261113-156-dense-table-digests/RESULTS.md:143-145`, `:155-157`) | not part of N6; part of N7's configuration |

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

- That fixture "uses test-only hand plans; no error-accounting, hiding, Fiat-Shamir/grinding or soundness theorem is established" (`:82`). Only a fixed-pair Schwartz-Zippel bound is stated for the design, and "adaptive grinding can amplify the error above the fixed-pair figure, by an amount not analysed" (`research/weight-binding/DESIGN.md:86-93`, `:260-262`).
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
| binding mechanism | the relation fixes the request file (prompt tokens, reply tokens but the last, r, e) with y (`research/envelope/SPEC.md:101-102`) |
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
| binding mechanism | inside the proof, open the input commitment, run from those cells, recompute the output commitment (`:7`) |
| update / rollback rule | the client records the last accepted root with a sequence number and refuses an older one, as the envelope does for `state.seq` and `state.prev` (`research/envelope/SPEC.md:77-78`, `:108-113`) |
| availability dependency | the client's state file. Losing it means starting again from genesis |

What exists: continuity prototypes on synthetic state. Each one takes its first root on trust: "the first root is trusted as given" (`experiments/20261111-35-conv-history-binding/RESULTS.md:59`); the initial root is "produced here by the trusted test harness" and how a real verifier gets it "is out of scope" (`experiments/20261111-93-hidden-root-handoff/RESULTS.md:80`); in the first harness the link between chunks is a comparison of hashes "done outside the proofs" (`experiments/20261109-34-qwen-state-commit/RESULTS.md:13`). The prototype's sponge is unvetted and chain length is checked outside the proof (`research/coverage/inventory.yaml:1030-1032`, G-07). The upstream statement has no state root at all (section 4, N8).

**E13. N2 to N9 to N8: the receipt is signed by the attested key of this boot and names this statement. Status: PROPOSED.**

| field | value |
|---|---|
| producer | the serving workload that holds the private half of N2 |
| independent verifier | the client: first E1 to E3 on a fresh attestation document, then the signature under that key, then the checks the envelope already has (nonce outstanding, request digest, sequence, expiry, proof digest; `research/envelope/SPEC.md:165-190`) |
| exact canonical bytes | the envelope's canonical body under its domain prefix (`research/envelope/SPEC.md:42-51`), extended with the measurement, the attested key id and a digest of the attestation document (section 7; not built) |
| authorization source | N0 through E1 and E3. Not a long-lived provider key pinned out of band |
| binding mechanism | signature; a client-chosen 32-byte nonce for freshness (`research/envelope/SPEC.md:75`); the proof digest is signed so that what is checked is what was signed (`:97`) |
| update / rollback rule | a key lives for one boot and the client re-verifies attestation when it changes `[V3]`; a nonce is released at most once (`research/envelope/SPEC.md:112-113`) |
| availability dependency | the client's state file and clock; a fresh attestation document |

What exists: the envelope, signed by a client-pinned TEST key, with 35 of 35 attack vectors refused (`experiments/20261111-9-client-envelope/RESULTS.md:18-21`). What does not: any tie between the signing key and an attestation. The client refuses every attestation kind that claims hardware evidence (`research/envelope/SPEC.md:98`, `:169-170`), and the specification lists what a real milestone needs (`:227-230`). Freshness comes from the signature and the client's state, never from the proof: the same proof re-wrapped under a new nonce is released (`experiments/20261111-9-client-envelope/RESULTS.md:19-21`, `:100-101`).

A receipt is guarantee (c). It says the key holder vouched for these bytes. A compromised enclave signs a false receipt as easily as a true one.

**E14. Physical execution to N8: the engine that physically ran is the one the proof describes. Status: VENDOR. A proof cannot supply this edge.**

| field | value |
|---|---|
| producer | the hardware and the measured boot, through E2, E4 and E5a `[V2]` |
| independent verifier | the client, as far as E1 to E5a reach. Nothing on main |
| exact canonical bytes | none. No object ties a physical run to a statement |
| authorization source | E1 |
| binding mechanism | none between the engine and the proof. The evidence says a measured program was started with access to a verified volume. It does not say that program produced the reply: that is E5b |
| update / rollback rule | none |
| availability dependency | none |

The statement of a proof holds the commitment ID, the configuration, the policy, the request file and y (`research/envelope/SPEC.md:101-102`). It holds nothing about a machine, an engine or a time, and it "does not authenticate a provider" (`:231-233`). Any engine that returns the same tokens satisfies the same statement, and the proof can be made on another machine. So this edge has exactly one possible source, hardware-backed evidence, and that source is limited by E5b.

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
| E6b | runtime config equals pinned config | PROPOSED | recomputation |
| E7 | checkpoint id is the chosen checkpoint | MAIN, hash level, open weights | (d) |
| E8a | conversion id structure | MAIN, hash level, rule text | recomputation |
| E8b | integers for 78 plain-matrix blocks | MAIN, hash level, subset | recomputation |
| E8c | integers for all 722 blocks, full tree | PROPOSED | recomputation |
| E9 | commitment holds the converted leaves | UNSOLVED | (b) |
| E10 | statement checked against the commitment | PROPOSED for Qwen | (b) |
| E11 | statement is the client's exact token ids | MAIN, synthetic examples | (b) |
| E12 | state root has an authenticated origin | PROPOSED | (b) |
| E13 | receipt under the attested key names the statement | PROPOSED | (c) |
| E14 | the physical engine is the proved one | VENDOR, not suppliable by proof | (a) |

Counts: MAIN 4, VENDOR 6, PROPOSED 6, UNSOLVED 2. No edge is MAIN for the full Qwen model under proof.
