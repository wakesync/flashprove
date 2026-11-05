# tools/manifest: signed model manifest for a commitment

Threat model mitigations M1 and M2 (PR #54) as a detached, ed25519-signed JSON file, and a client
check that runs next to `cp_verify`. The prover is unchanged. Standard library only.

## What a manifest binds

| field | what | checked by `verify` against |
|---|---|---|
| `commitment.id` | the FlashProve commitment ID | `cp_verify -id` (and its `id=`) |
| `commitment.kind` | `public-weights` or `hiding` | signer's word, even with `--public-weights-seed`: that flag checks the seed file against the digest, not the kind against the commitment, so a false `public-weights` with a seed file the signer ships is accepted, and nothing checks a claimed `hiding`; only rederivation checks the kind |
| `upstream` | `huggingface`: repo, 40-hex revision, sha256 of every file; or `synthetic`: generator + seed | `--upstream-dir` (rehash, refuse unlisted files), else signer's word (kind, repo, revision, files) |
| `conversion` | script path + sha256, repo commit, version, params, sha256 of committed files, public-weights seed digest | `--recipe` (or explicit `--no-recipe`: digest is then the signer's word), `--committed-dir`, `--public-weights-seed`, else signer's word; params/version/commit: signer's word, checkable by rederivation |
| `configuration` | sha256 of `policy.txt`, `KL.bin`, `layout.txt` | the `--config` files |
| `serving` | tokenizer files, chat template, system prompt (each a digest or `{"none": true}`), end tokens | `--tokenizer-dir`, `--chat-template`, `--system-prompt`, `--no-*`, `--end-tokens` (all required) |
| `decode_policy` | `exact` or `clipped-gap` + C, theta, cap, s, sh, sT, F | `policy.txt` and `cp_verify`'s `result-v1` |
| `verifier.build_digest` | the `build=` that `cp_verify` prints | `cp_verify`'s `result-v1` |
| `signer` | name, public key | the key the CALLER passes with `--signer-key` (never the manifest's own) |

Canonical form: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)` plus a
newline. Signature: ed25519 over `b"flashprove-manifest-v1 signature\n" + manifest bytes`, 64 raw
bytes in `<manifest>.sig`. Unknown or missing keys are refused. A field declared `none` must be
acknowledged with `--no-<field>`, `--end-tokens` is required, and the recipe needs `--recipe FILE`
or an explicit `--no-recipe`, so leaving a serving or recipe flag out refuses instead of skipping
the check. The rehash flags `--upstream-dir`, `--committed-dir` and `--public-weights-seed` stay
optional (the caller may not hold a 232 GB checkpoint): without them `upstream.*`,
`conversion.committed_files` and `conversion.public_weights_seed_sha256` are the signer's word, and
a trusted signer can change them to other schema-valid values undetected. `commitment.kind` is the
signer's word with or without the flags (measured, see Tests).

A rehashed directory (`--tokenizer-dir`, `--upstream-dir`, `--committed-dir`) must hold only plain
files and directories: any symlink in it is refused. A field meaning none has the one encoding
`{"none": true}`. A manifest nested too deeply to parse is refused.

Verification refuses a public key or an R of small order ([8]P the identity) and otherwise uses the
cofactorless equation [S]B = R + [k]A. A cofactored verifier (some libsodium modes) can disagree
with it on edge-case signatures; honest RFC 8032 signatures verify under both.

## Use

```sh
python3 tools/manifest/manifest.py keygen signer.secret signer.pub
python3 tools/manifest/manifest.py sign draft.json signer.secret manifest.json   # writes manifest.json.sig
python3 tools/manifest/manifest.py verify manifest.json manifest.json.sig \
  --signer-key signer.pub --cp-verify bin/cp_verify \
  --config CONFIG --ivk IVK --request REQ --y Y --proof PROOF \
  --tokenizer-dir TOK --chat-template TEMPLATE --system-prompt PROMPT --end-tokens 2 \
  (--recipe SCRIPT | --no-recipe) [--committed-dir DIR] [--upstream-dir DIR] [--public-weights-seed FILE]
```

Exit 0 and `manifest: ACCEPTED` only if every check passes and `cp_verify` says `YES`; else exit 1
and `manifest: REFUSED: <field>: <why>`. `--end-tokens none` means the empty list.

The signer key must come from a source you trust (a registry, a pinned file), not from the server.
`ed25519.py` signs in non-constant time: sign real manifests with OpenSSL, libsodium or the
`cryptography` package (same bytes, RFC 8032 is deterministic).

## Tests

`python3 -m pytest -q tools/manifest` (needs `bin/cp_verify`, from `verifier/build.sh`). Every
manifest field is tampered three ways. In the test, `SIGNERS_WORD_SINGLE` lists exactly which
one-field changes a trusted signer can make undetected, `SCHEMA_ONLY` which one-field refusals
came from the schema alone, and `SIGNERS_WORD_UNLESS_FLAG` which fields a schema-valid coordinated
change (`tamper.coordinated`) gets past unless the matching rehash flag is passed (3 fields), and
`SIGNERS_WORD_COORDINATED_ALWAYS` the one it gets past even with the flag (`commitment.kind`, with
a seed file the signer ships): 11 fields always the signer's word plus 3 unless a flag, 14 of 37.
Small-order keys and R, leaving out a required flag, symlinks in a rehashed directory, a deeply
nested manifest and `{"none": 1}` are tested too. Results: `experiments/20261104-58-signed-manifest/RESULTS.md`.

## Limits

Detached: the manifest is not inside the configuration or the proof. It does not prove the
signer told the truth about what the client cannot rehash; rederiving the commitment ID from the
manifest's recipe (public-weights commitments only, needs an H100) is what checks that.
