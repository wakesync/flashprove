# RESULTS: 20261104-58-signed-manifest

Issue #58. **Verdict: PASS** against the registered threshold. Measured, unreplicated, CPU only,
synthetic stored example. Raw data: `numbers.json` (every row with exit code and the refusal
line). Runner: `run.py`. Tests: `tools/manifest/test_manifest.py` (31 passed).

| registered metric | result | threshold | |
|---|---|---|---|
| tampers refused, registered arms | **137 / 137** | 100% | PASS |
| untampered accepted (`cp_verify` exit 0, `YES`, manifest ACCEPTED) | **10 / 10** | 10 / 10, 0 false refusals | PASS |
| RFC 8032 section 7.1 vectors 1-3 | **3 / 3** | all | PASS |
| cross-check vs `cryptography` 41.0.7, 64 random messages, seed 1104 | **64 / 64** identical signatures | (not registered as a threshold) | |
| verify wall time, whole call incl. one `cp_verify` | median **1.44 s**, SD 0.10, min 1.40, max 1.75 (n = 10) | none | info |

The 137 registered tampers: 37 manifest fields (every JSON leaf, enumerated mechanically) x 3
arms (original signature kept; re-signed by an attacker key; attacker key also written into
`signer.public_key`) = 111, plus 15 file substitutions (3 configuration files, 5 proof-side files,
tokenizer file, extra tokenizer file, chat template, system prompt, recipe script, wrong trusted
key, end tokens), 10 signature bit flips, 1 non-canonical JSON. The n = 10 untampered runs repeat a
deterministic check; they are not independent trials.

Who refused the proof-side swaps: `cp_verify` itself (`NO: proof-refused` for proof and request,
`NO: token-range` for y, `NO: key-refused`, `NO: entry-refused`); the manifest layer then refuses on
its non-zero exit. A changed `commitment.id` re-signed by the trusted key is refused by `cp_verify`
(`NO: model-statement`), which is where the manifest's ID meets the proof.

## Amendment arm: changed field re-signed by the trusted key (no threshold)

37 fields: 27 refused because the client holds something to check them against, 10 accepted
because only the signer's word stands behind them in this fixture:
`signer.name`, `upstream.generator`, `upstream.seed`, `conversion.script` (path label),
`conversion.repo_commit`, `conversion.version`, `conversion.params.{M,config,weights}`,
`verifier.source_commit`.

This is expected and is the point: a signature authenticates the signer, not the truth of what it
signed. Those fields become checkable only by rederivation (rerun the recipe, get the same ID),
which needs `cp_commit` on an H100 and a `-public-weights` commitment. For a real model,
`upstream.files`, `conversion.committed_files` and the public seed digest are rehashed when the
client passes `--upstream-dir`, `--committed-dir`, `--public-weights-seed` (unit-tested on
synthetic files, not on a real checkpoint).

## Not shown

- No real model, no real tokenizer or chat template (fixture files stand in); Maverick manifest
  not built (would need its 232 GB of weights to hash, out of scope).
- Binding is client-side and detached: the manifest digest is not inside the configuration or the
  proof (threat model M1 says that needs a parser change, untested).
- `ed25519.py` signing is not constant time; it is for tests. Verification works on public data.
- No independent replication yet.

Proposed claim (for the reviewer, not added to `research/results.yaml` or `loop/claims.json`):
"tools/manifest refuses 137 of 137 registered tampers and accepts 10 of 10 untampered verifies of
the stored small example; 10 of 37 fields are the signer's word only."
