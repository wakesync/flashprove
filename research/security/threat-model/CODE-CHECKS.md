# Specific checks against this repository (base `ce4ceef0`)

Each check: question, answer, evidence (file:line), status label. "Read" means established by
reading source or docs, not by running.

## C1. Is the model commitment tied to a published upstream hash anyone can check?

**No.** The commitment ID hashes four things: the configuration digest, the anchor's name (root and
shape), the anchor's OOD seeds and the OOD answers (`blocks/frame/heads.h:78-99`, `published_id`).
None is an upstream artifact hash. The code says so: "The ID does not say whose weights the table
contains. That an ID belongs to a model of some name is its publisher's claim, outside the
protocol" (`blocks/frame/heads.h:88-89`). Status: read.

What does exist, partially:
- **`-public-weights` determinism.** For already-public weights, `cp_commit -public-weights <32-byte
  file>` derives the seed from a public file, so "the same call on the same weights directory
  (model files, wsums.txt, fold.txt), configuration and 32-byte file gives the same key file, leaf
  files and commitment ID, which anyone can compare with published ones"
  (`prover/common/public_weights.h:6-13`). That makes the ID **recomputable** by a third party from
  public inputs. It is the closest thing to an upstream pin. Cross-machine equality has been
  compared "for Maverick's 4-bit files alone" (same file, lines 11-12; cited from the comment, not
  rerun here).
- **Per-file SHA-256 markers.** Under `-public-weights`, each model file needs a
  `<name>.weights-are-public` marker holding its SHA-256 (`prover/hash_commitment/public_weights_markers.h:9-14`).
  The SHA-256 is checked against the file, but it does not enter the commitment ID and nobody signs it.
- **Example pins.** `examples/maverick/run.sh:73-75` pins a Hugging Face repo + revision, and
  `examples/maverick/weights.sha256` pins file hashes. These are text in a git repo, not a signature
  chain to the original publisher, and the repo is a third party's GGUF conversion.

Gap: a recomputable ID is only as trustworthy as the recomputer's inputs. Nobody signs "these GGUF
bytes are an honest conversion of publisher P's checkpoint at revision R", and nothing in the ID
says which inputs to recompute from. **Mitigation M1.**

## C2. Can a prover swap weights between commit and prove?

**Swap is detected; the swapped batch fails.** `cp_prove` re-reads the model's `*.gguf` files from
the directory recorded in `isk.txt` at prove time (`prover/prover/isk.cuh:206-224`). So the files
*can* be replaced on disk. But the opening of a leaf table recomputes "the lowest stored Merkle node
above every drawn column" and must match before any column word is written [hc-own-node]; a batch
that fails releases only empty `.failed` files (`prover/tests/one_changed_weight.sh:7-16`). The test
`gpu.one_changed_weight` (one bit of one weight flipped) and `gpu.other_weights_nothing_leaves` (all
weights replaced) are in `SUITE.md:195,259`, both GPU tests; not rerun here (no GPU).

Even if `cp_prove` were patched to skip that check, the verifier binds the proof to the anchor named
by the ID (`verifier/src/cp_verify.cpp:2239-2254`), so a proof over other weights would need to
defeat the binding of the weight tables, which is the soundness question (row LIM-2, below).

Caveat, from the repo's own limits: binding of the weights to the ID "has not been shown" for the
released programs (`docs/limits.md:169-174`). Row LIM-2 reports lying key files with an anchor
altered at up to 65,536 of 8,388,608 positions per row accepted by an unedited `cp_verify`, argued on
paper to still decode to the same weights (cited from `docs/limits-all-rows.tsv`, row LIM-2,
measured there, not on the released programs). So "no weight swap" rests on the Reed-Solomon
decoding argument, not on a test that a lying anchor decodes to *different* weights ("by report, no
anchor built to decode to other weights was tried", same row). Status: read; the #46 lane's
"identity binding exists" holds at the design level and at the `cp_prove` refusal level; the
cryptographic binding claim is an argument, not a theorem about the programs.

## C3. Does the verifier trust anything from the prover unauthenticated?

| Input | Who supplies it | Authenticated? | Evidence |
|---|---|---|---|
| `policy.txt`, `KL.bin`, `layout.txt` | provider | Yes, byte-for-byte in the ID | `blocks/frame/heads.h:66-76`; PR #41 5/5 per mutation (measured) |
| key file, leaf file | provider | Checked by `cp_verify` on every call; the ID covers the anchor's name and OOD answers, not the key file's proofs | `docs/architecture.md:226-227`; `docs/limits-all-rows.tsv` row SO-8.3 |
| decode policy (exact vs clipped gap, C/theta/cap) | provider, inside `policy.txt` | Bound by the ID. But **chosen** by the provider; a client must pass `-policy` matching its own expectation, and without `-policy` a clipped-gap call ends `NO: policy` | `verifier/docs/parameter-file.md:19`; `verifier/src/cp_verify.cpp:2942` |
| tokenizer, chat template, end-token ids | model publisher | **No** | `docs/architecture.md:223` |
| system prompt / template tokens | whoever builds the window | **Only as token IDs** | `docs/operators-duties.md:681-685` |
| prompt token IDs | client, or server under `--chat` | Client-built windows are the client's own. With `--chat` the server chooses them; the example client caps the exit at 24, never 0 | `integrations/ask_and_check.py:10-12,167-168` |
| sampling parameters | provider | **No**, not checked under any policy | `docs/protocol.md:43` |
| verifier binary | client builds it | Not identified by the transcript | `research/security/fiat-shamir-attacks.md:20-21,53` |

Status: read. No unauthenticated **cryptographic** input was found beyond what PR #41 already lists.
The unauthenticated inputs are all **semantic**: template, tokenizer, end tokens, sampling, and who
chose the prompt tokens.

## C4. Prompt-injection surface: the proof binds the prompt, so who chose the system prompt?

The proof binds the window's token IDs and nothing about their origin. In ordinary chat serving, the
server applies the chat template and may prepend a system prompt; then the **server** chooses those
tokens. Operators are told to "Submit the token IDs that the model really worked on ... with the
chat template's tokens and whatever your front end added" (`docs/operators-duties.md:681-683`). So:

- A malicious provider can put a trigger (date, deployment tag, any sleeper trigger) in the system
  prompt, get a backdoored behavior out of the committed model, and the proof correctly binds it.
  A client that only compares "my user message is a substring" would not notice (inferred).
- The defense exists in our example client: with `--prompt-ids` the client builds the window itself
  and the server's `prompt_token_ids` must equal it (`integrations/ask_and_check.py:355`); with
  `--chat` the best exit is 24 (`integrations/ask_and_check.py:10-12`). The REFERENCE doc says to
  compare the echoed IDs with your own (`integrations/vllm/REFERENCE.md:24`). Good design; it puts
  the burden on the client knowing the published chat template exactly.
- Gap: there is no published, hashed **chat template + system prompt** bound with the ID. A client
  that wants "the provider's advertised system prompt" has no authenticated source for it.
  **Mitigation M2** (a manifest that covers template, system prompt, tokenizer and end tokens).

## C5. Clipped-gap weakness as a steering channel, stacked with a sleeper trigger

Inputs from PR #50 (**merged**, main `a6c5a8e6`, checked at its merged parent `b645f670`) and PR #51
(**merged**, main `c46d21ee`, checked at `0c93d0ea`; evidence unchanged at the merged head `b9246e8e`), both unreplicated, synthetic small model, H100. **Honest-prover path only**: every out-of-limits reply was
refused by the honest `cp_prove`, so `cp_verify` never judged an out-of-limits proof.
- PR #51: one swap then greedy continuation proved and accepted `WITHIN LIMITS` 15/16 (float second
  choice) and 13/16 (random token) under shipped limits `C=9244130 theta=323343 cap=1`.
- PR #50: runtime steering at |dose| 0.05, 5 of 54 changed replies proved and accepted under clipped
  gap. Under exact match the honest prover refused all 57 changed replies; no proof of them was
  made, so this is not a measurement of `cp_verify` rejecting one.
- Docs: "As many tokens as the second bound allows may cost more than C, and these can be any
  tokens, at any positions" (`docs/protocol.md:47`), and the hidden costs are a prover-chosen
  witness (`docs/limits.md:302-306`).

Two mechanisms carry these acceptances, and they are different limits:
- **cap (one position over C), #51.** `cp_verify` prints `above-clip=1` on #51's accepted lines (the
  policy bound). From #51's cost vectors (`intervals.json` there, `accepted_using_cap`, shipped): all
  13 accepted random-token swaps use the one allowed position over C, and 3 of the 15 accepted
  float-second-choice swaps do. The other 12 of those 15 are under C everywhere and pass on theta.
- **theta (the mean bound), #50.** `above-clip=0` on all 21 clipped-gap proofs in #50, so cap = 1
  was never used. Each of the 5 accepted steered replies has one or two costs above 256 but under C,
  and passes on mean(min(cost, C)) <= theta = 323,343 alone (#50 RESULTS, "the limit that lets these
  through is the theta mean bound, not cap").

Stack (inferred): the clipped-gap limits give the provider a branch choice, either as the one
position over C that cap allows or as one or two costly tokens absorbed by the theta mean over the
reply (room grows with reply length, about theta x len). A sleeper's harmful branch only needs to be
*reachable* (rank 2 at one position), not dominant. After the swap the model's own greedy
continuation follows the harmful branch at near-zero cost. So a partially suppressed backdoor (safety
tuning pushed it to rank 2) becomes provable under clipped gap. That exact match closes this stack is
by design, not measured (see above); it costs integer serving (`docs/architecture.md:141-146`).
**Mitigation M4.**

## C6. Fiat-Shamir (#41) status

PR #41 (merged, issue #37 closed): configuration is bound byte for byte before any challenge;
prompt, reply, range mutations change the first challenge 5/5 and are rejected; `y` is bound late
(at the output head) and still rejected 5/5; paper-level verdicts for ePrint 2025/118 and 2026/1838
are "unclear", with no concrete forgery found (`research/security/fiat-shamir-attacks.md:8-30`;
measured, re-executed by a review lane, not independently replicated). Relevance to sleepers: none
directly. FS soundness protects "the proof is of the committed model"; a sleeper is in the committed
model. Open FS items (verifier-binary identity, uncommitted subcomputations) affect A5 (colluding
verifier), not sleepers.

## C7. Is there anything in the code that looks at weight *content* for safety?

Only range checks: the worst-case check that no prompt can push a forward-pass value out of range
(`prover/README.md:53`, `scales/worst-case-bounds.md`) and the anchor range proof
(`docs/architecture.md:128-131`). These are about arithmetic validity, not behavior. Nothing scans
for backdoors, and nothing should claim to (Goldwasser et al. 2022 show planted backdoors that are
undetectable for their constructions; cited). Status: read.
