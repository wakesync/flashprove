# RESULTS: 20261104-58-signed-manifest

Issue #58. **Verdict: PASS** against the registered threshold. Measured, unreplicated, CPU only,
synthetic stored example. Raw data: `numbers.json` (every row with exit code and the refusal
line). Runner: `run.py`. Tests: `tools/manifest/test_manifest.py` (61 passed).

**Re-measured after PREREG amendment 3** (2026-11-05 UTC, after the second independent review of
PR #59 at `94966765`): `commitment.kind` is now counted as the signer's word even with
`--public-weights-seed` (a matching-seed coordinated row pins it), and the code refuses symlinks in
rehashed directories, `{"none": 1}` / `{"none": 1.0}` and too-deeply nested manifests. All numbers
below are from the re-run at code commit `c0d16125`. Every registered row (174 rows, exit code and
refusal line) is identical to the amendment 2 run.

Earlier runs, kept in git history: amendment 2 (`numbers.json` at `2699b0a0`, code `3bfec225`):
same registered counts, verify median 1.414 s (SD 0.026, min 1.383, max 1.452, n = 10). First
measurement (`numbers.json` at `078d7429`): same registered counts, verify median 1.44 s (SD 0.10,
min 1.40, max 1.75, n = 10).

| registered metric | result | threshold | |
|---|---|---|---|
| tampers refused, registered arms | **137 / 137** | 100% | PASS |
| untampered accepted (`cp_verify` exit 0, `YES`, manifest ACCEPTED) | **10 / 10** | 10 / 10, 0 false refusals | PASS |
| RFC 8032 section 7.1 vectors 1-3 | **3 / 3** | all | PASS |
| cross-check vs `cryptography` 41.0.7, 64 random messages, seed 1104 | **64 / 64** identical signatures | (not registered as a threshold) | |
| verify wall time, whole call incl. one `cp_verify` | median **1.407 s**, SD 0.027, min 1.380, max 1.471 (n = 10) | none | info |

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

## ed25519: small-order points (amendment 2, no threshold)

Before amendment 2, `ed25519.verify` accepted the identity as a public key with R = [r]B, S = r for
any message (found by the independent review). It now refuses a public key A or a commitment R
with [8]A or [8]R the identity. Measured: the identity-key forgery is refused; for each of the 8
small-order encodings as A, all 8 forgeries R = [r]B + T, S = r are refused (8 / 8 keys); for each
of the 8 as R under a real key, S = k*a is refused (8 / 8; with R the identity the bare equation
holds, so this case was accepted before). RFC 8032 vectors and the `cryptography` cross-check still
match. Verification is **cofactorless** ([S]B = R + [k]A), as in the RFC's reference code. A
cofactored verifier (e.g. some libsodium modes) can disagree with it on edge-case signatures;
honest signatures verify under both.

## Amendment arms: changed fields re-signed by the trusted key (no threshold)

**One-field mutations (first amendment).** 37 fields: 27 refused, 10 accepted. But 10 of the 27
refusals come from the schema alone (the mutation is a nonsense value, e.g. kind "hidingx"):
`format`, `commitment.kind`, `upstream.kind`, `conversion.committed_files`,
`conversion.public_weights_seed_sha256`, `decode_policy.{kind,C,theta,cap,sT}`. The other 17 are
refused against something the client holds (configuration files, serving files, recipe, end
tokens, the trusted key) or by `cp_verify` (`commitment.id`, `verifier.build_digest`). The 10
accepted, signer's word only: `signer.name`, `upstream.generator`, `upstream.seed`,
`conversion.script` (path label), `conversion.repo_commit`, `conversion.version`,
`conversion.params.{M,config,weights}`, `verifier.source_commit`.

**Coordinated, schema-valid alternates (amendments 2 and 3).** 13 alternates (12 from amendment 2,
plus the matching-seed row of amendment 3), each re-signed by the trusted key, run with the required
flags and without, then with, the rehash flag that checks it:

| alternate | without the rehash flag | with it |
|---|---|---|
| `commitment.kind` hiding to public-weights + made-up seed digest | **ACCEPTED** (`cp_verify` YES) | refused with `--public-weights-seed` (the digest does not match the caller's file) |
| `commitment.kind` hiding to public-weights + digest of a seed file the signer ships (amendment 3) | **ACCEPTED** | **ACCEPTED** with `--public-weights-seed` and that file (`cp_verify` YES) |
| upstream synthetic to a full made-up huggingface upstream + made-up `committed_files` | **ACCEPTED** | refused with `--upstream-dir --committed-dir` |
| same, caller passes `--upstream-dir` only | **ACCEPTED** | refused with `--upstream-dir` |
| `committed_files` empty to one made-up entry (synthetic upstream) | **ACCEPTED** | refused with `--committed-dir` |
| decode policy C, theta, cap, sT each +1 with kind clipped-gap; kind to clipped-gap with cap 1 | refused (`policy.txt`) | (no flag needed) |
| chat template, system prompt, tokenizer to `none` | refused (needs `--no-*`) | (no flag needed) |

So the decode-policy fields are bound (to `policy.txt` and `cp_verify`'s output), but
**`upstream.*`, `conversion.committed_files` and `conversion.public_weights_seed_sha256` are the
signer's word unless the caller passes `--upstream-dir`, `--committed-dir`,
`--public-weights-seed`, and `commitment.kind` is the signer's word even with those flags.**
`--public-weights-seed` rehashes a seed file against the signed digest; nothing compares that with
what the commitment is, so a signer who claims `public-weights` and ships a matching seed file is
accepted. Amendment 2 listed `commitment.kind` under "unless a flag"; that was wrong (its row used
a made-up digest, so it showed that a mismatched digest is refused, not that the kind is checked),
and amendment 3 corrects it. On this fixture that makes 14 fields the signer's word: **11 always**
(the 10 above plus `commitment.kind`) and **3 unless the caller passes the matching rehash flag**.
`commitment.kind` matters most: it decides whether rederivation is possible at all, and only
rederivation checks it.

This is expected: a signature authenticates the signer, not the truth of what it signed. The
signer's word fields become checkable only by rehashing files the client holds, or by rederivation
(rerun the recipe, get the same ID), which needs `cp_commit` on an H100 and a `-public-weights`
commitment. The rehash flags are unit-tested on synthetic files, not on a real checkpoint.

## Omission (amendment 2, no threshold)

Before amendment 2, leaving out `--end-tokens` or `--recipe` skipped that check (ACCEPTED), and two
registered file substitutions ("end tokens differ", "recipe") refused only because the harness
passed the flag. Now: `--end-tokens` left out: refused. `--recipe` left out without `--no-recipe`:
refused. Both given: refused. `--no-recipe` with the honest manifest: accepted, and with
`conversion.script_sha256` changed and re-signed by the trusted key: also accepted, as disclosed
(under `--no-recipe` the recipe digest is the signer's word). The rehash flags `--upstream-dir`,
`--committed-dir`, `--public-weights-seed` stay optional, so omitting them is not refused; their
fields are listed as the signer's word above.

## Hardening (amendment 3, no threshold)

Each was found by the second review and is now refused, with a unit test and a runner row
(`numbers.json` `hardening_rows`), all re-signed by the trusted key unless noted:

| case | before (review at `94966765`) | now |
|---|---|---|
| extra `added_tokens.json` in a symlinked subdirectory of `--tokenizer-dir` | ACCEPTED (`rglob` does not descend into it) | refused: `sub is a symlink` |
| manifest nested 100000 deep | uncaught `RecursionError` (traceback, exit 1) | refused: `nested too deeply to parse` |
| `serving.system_prompt` / `serving.chat_template` set to `{"none": 1}` or `{"none": 1.0}` | accepted as none | refused (4 of 4 rows) |

Any symlink inside a rehashed directory is refused, file or directory, listed or not: a caller who
keeps a tokenizer or checkpoint behind symlinks (as a Hugging Face cache does) must copy or
dereference it first.

## Not shown

- No real model, no real tokenizer or chat template (fixture files stand in); Maverick manifest
  not built (would need its 232 GB of weights to hash, out of scope).
- Binding is client-side and detached: the manifest digest is not inside the configuration or the
  proof (threat model M1 says that needs a parser change, untested).
- `ed25519.py` signing is not constant time; it is for tests. Verification works on public data.
- No independent replication yet. The amendment 2 and 3 changes were made after results and after
  review; the registered threshold did not change.

Proposed claim (for the reviewer; the ledger entry is `signed-manifest` in `research/results.yaml`,
nothing added to `loop/claims.json`): "tools/manifest refuses 137 of 137 registered tampers and
accepts 10 of 10 untampered verifies of the stored small example; on that fixture 14 of 37 fields
are the signer's word (11 always, including `commitment.kind`, and 3 unless the caller passes the
matching rehash flag)."
