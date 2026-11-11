# Results: substitution and transcript negative suite (issue #6)

**PASS against the PREREG threshold, measured and unreplicated.** These are verifier rejection tests on two stored synthetic CPU examples and on the research two-chunk handoff prototype. Finite tests on fixed toy fixtures do not establish soundness.

## Plain-language result

We took complete, honestly made proofs and swapped in pieces that belong to something else: another configuration, another request, another reply, a different transcript domain label, a damaged proof file, a different starting state. We then ran each through the real verifier (or, for tokenizer cases, the client-side manifest and integration checks), five times each, next to an unaltered control.

- All 235 control runs were accepted.
- All 225 hostile runs with a registered rejection were rejected, each by the check registered for it (or a check of the registered class). No hostile case was accepted.
- The two cases registered as "expected accept" were accepted 10 of 10, as registered: replaying an unaltered proof (no freshness or client binding, gap G-05) and a bare `cp_verify` call that takes no tokenizer at all (gap G-04). These are known open gaps, confirmed, not new findings.
- 170 of the 225 rejections came from the proof verifiers (`proof-refused`, `key-refused`, handoff proof verifier), 55 from application validation on public values outside the proof (ID, policy, proof-file header/length, manifest digests, end token, handoff initial-root opening). 40 of the 170 (the reviewer's "about 40") are structural parse refusals inside the proof verifiers, not relation checks: C-MAL1, C-MAL2, C-MAL3, C-MAL5, C-MAL6, H-MAL1, H-MAL2, H-MAL4 (cut-short opening, missing salt, bytes left over), 8 cases x 5 runs = 40. So 170 is not 170 constraint violations.

No named negative was added: no hostile case was accepted.

## Registered run

- Harness: `suite.py` at commit 5f78314 (committed before the run), run once through the heavy-job gate, `taskset -c 6-11`, `cp_verify -j 1`.
- Started 2026-11-11T04:48:48Z, finished 04:55:07Z, 378 s of a 1800 s budget, `partial: false`. No run excluded, no rerun.
- 47 cases x 5 repetitions = 235 rows in `runs/registered.jsonl`, each with the control and the hostile call (command, exit, full output, last line, time), whether the control accepted, whether the hostile call was rejected by the intended check, and the observed kind. Input SHA-256s in `runs/registered.summary.json`. Builds and binary digests in `runs/build.json`; environment in `ENV.json`.
- Handoff: D = 8, C = 2, seeds 201..205 (one per repetition). Honest, FP94-domain and complete hostile proofs are generated inside the run (`generation` field). Proof files and altered inputs stay under the ignored `bin/subst6/registered/`, reproducible from the commands; their hashes are receipts.
- Order alternated per repetition as registered (control first on odd, case first on even).

## Per-case results

Kind is what the observed rejecting line is: **proof constraint** = the proof's own transcript or sub-proof checks; **application validation** = a comparison on public values outside the proof. "Intended" = rejected with the registered exit code and line (or a line of the registered class) while the same repetition's control accepted.

| Case | Verdict | Hostile accepted / n | Controls accepted / n | Rejecting line (all 5 runs) | Kind |
|---|---|---:|---:|---|---|
| C-CFG1 | PASS | 0/5 | 5/5 | `NO: model-statement` | application validation |
| C-CFG1b | PASS | 0/5 | 5/5 | `NO: policy` | application validation |
| C-CFG2 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-CFG3 | PASS | 0/5 | 5/5 | `NO: key-refused` | proof constraint |
| C-CFG3b | PASS | 0/5 | 5/5 | `NO: model-statement` | application validation |
| C-DOM1 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-DOM2 | PASS | 0/5 | 5/5 | `NO: key-refused` | proof constraint |
| C-MAL1 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-MAL2 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-MAL3 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-MAL4 | PASS | 0/5 | 5/5 | `NO: cp-proof-length` | application validation |
| C-MAL5 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-MAL6 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-MAL7 | PASS | 0/5 | 5/5 | `NO: cp-proof-head` | application validation |
| C-MAL8 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-MAL9 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-PFX1 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-REQ1 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-REQ2 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-REQ3 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-REQ4 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-REQ5 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-RPL1 | PASS | 0/5 | 5/5 | `NO: proof-refused` | proof constraint |
| C-RPL2 | PASS (expected accept) | 5/5 | 5/5 | `YES` | accepted, registered gap G-05 (IS-16) |
| C-TOK1 | PASS | 0/5 | 5/5 | `manifest: REFUSED: serving.tokenizer.files: tokenizer.json digest differs` | application validation |
| C-TOK2 | PASS | 0/5 | 5/5 | `manifest: REFUSED: serving.chat_template: file digest differs` | application validation |
| C-TOK3 | PASS | 0/5 | 5/5 | `manifest: REFUSED: serving.end_tokens: differ from --end-tokens` | application validation |
| C-TOK4 | PASS | 0/5 | 5/5 | `check_proof: rejected: the last checked token is 199, not one of your end tokens` | application validation |
| C-TOK5 | PASS (expected accept) | 5/5 | 5/5 | `YES` | accepted, registered gap G-04 (IS-13) |
| C-TOK6 | PASS | 0/5 | 5/5 | `manifest: REFUSED: signature: does not verify under the trusted signer key` | application validation |
| H-CFG1 | PASS | 0/5 | 5/5 | `accept=false`, "a nonce does not give the proof of work that its round asks for" | proof constraint |
| H-CFG2 | PASS | 0/5 | 5/5 | `accept=false`, same | proof constraint |
| H-DOM1 | PASS | 0/5 | 5/5 | `accept=false`, same | proof constraint |
| H-DOM2 | PASS | 0/5 | 5/5 | `accept=false`, same | proof constraint |
| H-MAL1 | PASS | 0/5 | 5/5 | `accept=false`, "an opening is cut short or holds a symbol that is not in canonical form" | proof constraint |
| H-MAL2 | PASS | 0/5 | 5/5 | `accept=false`, "bytes are left over at the end of the proof" | proof constraint |
| H-MAL3 | PASS | 0/5 | 5/5 | `accept=false`, "BASE: the masked message in the proof does not satisfy the linear claim" | proof constraint |
| H-MAL4 | PASS | 0/5 | 5/5 | `accept=false`, "the chain's salt is missing" | proof constraint |
| H-PFX1 | PASS | 0/5 | 5/5 | `accept=false`, "a nonce does not give the proof of work ..." | proof constraint |
| H-PFX2 | PASS | 0/5 | 5/5 | `FAIL: verifier initial root opening` | application validation |
| H-PFX3 | PASS | 0/5 | 5/5 | `accept=false`, "a nonce does not give the proof of work ..." | proof constraint |
| H-PFX4 | PASS | 0/5 | 5/5 | `accept=false`, "BASE: the masked message ... linear claim" | proof constraint |
| H-PFX5 | PASS | 0/5 | 5/5 | `accept=false`, "BASE: the masked message ... linear claim" | proof constraint |
| H-REQ1 | PASS | 0/5 | 5/5 | `accept=false`, "a nonce does not give the proof of work ..." | proof constraint |
| H-REQ2 | PASS | 0/5 | 5/5 | `accept=false`, same | proof constraint |
| H-REQ3 | PASS | 0/5 | 5/5 | `accept=false`, same | proof constraint |
| H-RPL1 | PASS | 0/5 | 5/5 | `accept=false`, same | proof constraint |

Every case gave the same line in all five runs. Seconds per call (median, SD, min, max over five) are in `runs/registered.summary.json`; they are diagnostic only on a shared loaded host.

## Reading the results

- **Statement binding on the handoff.** When the verifier's statement differs from the one the proof was made for (model or weights identifier, request, an output word, a pre-conv input word, initial state or history with a correctly recomputed root, another seed's whole statement, or a foreign transcript domain), the handoff verifier's first failing check is the proof-of-work nonce of a round. That is what one expects when the statement enters the transcript before the first challenge: the challenges the verifier derives differ from the ones the prover answered. It shows the statement is absorbed, not more.
- **Complete hostile witnesses on the handoff (H-PFX4, H-PFX5).** The prover wrote a full witness from the wrong initial state (or a changed intermediate state), kept every product gate, and emitted a complete proof; the generator itself reports 1 to 2 violated affine relations as a diagnostic. The verifier rejects at the linear claim. These are in-proof rejections of complete proofs, of the kind #93 tested at the prover side.
- **Inconsistent public opening (H-PFX2).** A statement whose initial state does not match its own root is refused by the SHA-256 opening check before any proof check (application validation). That check is outside the proof, as `research/operators/qwen_handoff/README.md` says.
- **cp_verify request/prefix changes.** Every change to the request (other example's request, one token, a swap, r widened to 59, another reply token, prompt token 0) ends `proof-refused`; none is caught by a form check first. This is consistent with IS-05 (request bound in the first chain's first query, PR #41) on these two fixtures.
- **Config.** Another example's config is stopped by the ID comparison (C-CFG1) or the policy comparison (C-CFG1b), both caller-side validations (G-OB2). Under that config's own complete public files and ID but this example's proof (C-CFG2) the proof itself is refused. Appending a 30-byte comment line (`# subst6 byte binding control` and its newline) to layout.txt, under that config's recomputed ID, ends `key-refused` (C-CFG3), the same as PR #41; under the original ID it ends `NO: model-statement` (C-CFG3b).
- **Domain labels.** cp_verify builds with a changed first-chain label (C-DOM1) or changed one-time/proof chain labels (C-DOM2) reject the unaltered example inside the proof. C-DOM2 changes three labels together and is refused at the key stage, which uses the one-time chain first, so it shows only that the one-time label enters the transcript; the PROOF_SHARED and PROOF_SECOND labels are not shown separately. This shows the first-chain and one-time labels enter the transcript; it does not give a client a way to identify the verifier binary it runs (IS-17 stays open, G-05).
- **Malformed proofs.** Empty file and a header bit flip are refused by the proof-file reader (`cp-proof-length`, `cp-proof-head`, application validation); every other truncation, extension and bit flip ends `proof-refused`. The handoff verifier refuses all four malformed proofs inside its proof parser/verifier.
- **Tokenizer policy.** All tokenizer, template, end-token and signer substitutions are stopped only by client-side tools (`tools/manifest`, `integrations/check_proof.py`). cp_verify itself binds token ids only (C-TOK5 accepted, IS-13).

## What this does not establish

- No soundness claim. 47 fixed cases on two synthetic 64-token examples and one D8/C2 research prototype at a research security target with deterministic coins.
- Hostile cases are chosen by us; a stronger adversary could choose the witness or transcript adaptively. Only H-PFX4/H-PFX5 build complete hostile witnesses; the other cases reuse honest proofs under altered statements or damaged files.
- Application-validation rejections bind only when the caller states the value itself (G-OB2). A client that takes ID, policy or range from the prover gets no protection from them.
- Tokenizer and manifest checks are a client-side research tool, not part of cp_verify.
- Replication: none. One registered run.
- Substitutions not tested here (gaps of this suite): the reply file `example.y` alone, the handoff statement's `layer` field, the key file `ivk/key.bin` alone without its config (C-CFG2 swaps both), and the leaf/entry file alone. A reviewer's spot check (not part of the registered result, https://github.com/wakesync/flashprove/pull/108#issuecomment-6788059539) reports the first two rejected: `NO: reply-differs` and handoff `accept=false`.

## Deviations

- PREREG amendments 1 to 4 (dated in PREREG.md, all before the harness was written or run): domain-label values changed to satisfy the label-order static assert; C-CFG1 split into C-CFG1 (with `-policy`) and C-CFG1b (without); C-CFG3 changes layout.txt instead of policy.txt, plus C-CFG3b; per-case controls named.
- Lane handoff: lane subst6 wrote the PREREG, amendments, harness and builds and started the registered run. It ended at about 04:50Z on a model-provider content filter, not a code failure. Lane subst6b took over the same clone after the run had finished, checked that the run completed (`partial: false`, 235 rows) and wrote ENV.json, this file, the results.yaml row and the inventory notes. No registered file was edited and no run was repeated.
- Amendment heading times. The headings of amendments 1 and 2-4 in PREREG.md (04:38Z, 04:50Z) were approximate times written by hand. The commits are the record: c83a152 at 04:32:23Z, a3e1f0e at 04:39:41Z, harness 5f78314 at 04:48:21Z, registered start 04:48:48Z. The headings are left as written (PREREG amendment 6).
- Push order. Only the PREREG commit (177adb4) was pushed before the run (04:27Z). The amendment and harness commits were pushed together with the results at about 05:04Z, so their order before the run rests on local commit times and the producer clone's reflog, not on a remote timestamp.
- Debug pass. The registered `--debug` pass (handoff seed 909 at D = 4, C = 1, disjoint from the registered seeds 201..205 and shape D8/C2) was run before the registered run, as PREREG Runs allows. Its inputs show as `handoff-909/*` hashes in `runs/registered.summary.json`; it is not evidence.
- Review fixes after the run (PREREG amendments 5 and 6): a separate reproduction mode, `suite.py --reproduce DIR --budget-min N`, because the registered mode keeps a fixed stop at 2026-11-11T06:40Z and records no case after it. The registered mode and its receipts are unchanged. Regression test `test_reproduce.py`, receipt `runs/replay-check.json`. Wording corrections above (30-byte comment, proof-verifier bucket, C-DOM2, untested substitutions). No number or verdict changed.
- The registered run's start record says `gate_granted: process start`: the harness logs its own process start, which is when the gate had already granted the slot (it was launched through the gate).

## Reproduce

From the repository root, CPU only:

```
bash verifier/build.sh
python3 experiments/20261111-6-substitution-suite/build_variants.py
python3 experiments/20261111-6-substitution-suite/suite.py --reproduce bin/subst6/repro-1 --budget-min 45
python3 experiments/20261111-6-substitution-suite/test_reproduce.py
```

`build_variants.py` refuses to overwrite `runs/build.json`; in a fresh clone rename the committed one first, or compare the printed digests against it. `--reproduce DIR --budget-min N` is a new run, not the registered one: no fixed wall-clock stop, a budget of N minutes from its own start, output in a new DIR outside `runs/` (`reproduce.jsonl`, `reproduce.summary.json`, altered inputs in `DIR/work/`), every record marked `mode: reproduce`. It exits 0 only if every planned case and repetition ran and passed, 1 if one failed, 3 if the run is incomplete or empty. `--reps K` and `--cases A,B,...` run a subset (example: `--reps 1 --cases C-CFG3,H-PFX1`). The full 47 x 5 took 378 s in the registered run on 6 cores of a loaded host. Compare the per-case lines with `runs/registered.summary.json`.

The registered mode (`--out`, default `runs/registered.jsonl`) is kept exactly as registered, with its fixed stop at 2026-11-11T06:40Z: called later it does its setup, records no case, writes `partial: true` and exits 0. Do not use it to reproduce. `--dry-run` builds the altered cp_verify inputs and prints the command lines without calling a checker; `--debug` runs the handoff cases on the disjoint seed 909 at D4/C1.

`test_reproduce.py` sets the clock past 06:40Z and checks that the registered mode still stops before any case, that `--reproduce` runs a real slice (C-CFG3, C-RPL2, H-PFX1, one repetition) with exit 0, that a reproduction out of budget exits 3, and that a DIR under `runs/` is refused. Its receipt is `runs/replay-check.json` (refuses to overwrite; rename it to rerun).
