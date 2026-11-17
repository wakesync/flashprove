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
