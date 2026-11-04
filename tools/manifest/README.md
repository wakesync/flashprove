# tools/manifest: signed model manifest for a commitment

Threat model mitigations M1 and M2 (PR #54) as a detached, ed25519-signed JSON file, and a client
check that runs next to `cp_verify`. The prover is unchanged. Standard library only.

## What a manifest binds

| field | what | checked by `verify` against |
|---|---|---|
| `commitment.id`, `.kind` | the FlashProve commitment ID; `public-weights` or `hiding` | `cp_verify -id` (and its `id=`) |
| `upstream` | `huggingface`: repo, 40-hex revision, sha256 of every file; or `synthetic`: generator + seed | `--upstream-dir` (rehash, refuse unlisted files), else signer's word |
| `conversion` | script path + sha256, repo commit, version, params, sha256 of committed files, public-weights seed digest | `--recipe`, `--committed-dir`, `--public-weights-seed`; params/version/commit: signer's word, checkable by rederivation |
| `configuration` | sha256 of `policy.txt`, `KL.bin`, `layout.txt` | the `--config` files |
| `serving` | tokenizer files, chat template, system prompt (each a digest or `{"none": true}`), end tokens | `--tokenizer-dir`, `--chat-template`, `--system-prompt`, `--no-*`, `--end-tokens` |
| `decode_policy` | `exact` or `clipped-gap` + C, theta, cap, s, sh, sT, F | `policy.txt` and `cp_verify`'s `result-v1` |
| `verifier.build_digest` | the `build=` that `cp_verify` prints | `cp_verify`'s `result-v1` |
| `signer` | name, public key | the key the CALLER passes with `--signer-key` (never the manifest's own) |

Canonical form: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)` plus a
newline. Signature: ed25519 over `b"flashprove-manifest-v1 signature\n" + manifest bytes`, 64 raw
bytes in `<manifest>.sig`. Unknown or missing keys are refused. A field declared `none` must be
acknowledged with `--no-<field>`, so a client cannot skip a check by omission.

## Use

```sh
python3 tools/manifest/manifest.py keygen signer.secret signer.pub
python3 tools/manifest/manifest.py sign draft.json signer.secret manifest.json   # writes manifest.json.sig
python3 tools/manifest/manifest.py verify manifest.json manifest.json.sig \
  --signer-key signer.pub --cp-verify bin/cp_verify \
  --config CONFIG --ivk IVK --request REQ --y Y --proof PROOF \
  --tokenizer-dir TOK --chat-template TEMPLATE --system-prompt PROMPT --end-tokens 2 \
  [--recipe SCRIPT] [--committed-dir DIR] [--upstream-dir DIR] [--public-weights-seed FILE]
```

Exit 0 and `manifest: ACCEPTED` only if every check passes and `cp_verify` says `YES`; else exit 1
and `manifest: REFUSED: <field>: <why>`. `--end-tokens none` means the empty list.

The signer key must come from a source you trust (a registry, a pinned file), not from the server.
`ed25519.py` signs in non-constant time: sign real manifests with OpenSSL, libsodium or the
`cryptography` package (same bytes, RFC 8032 is deterministic).

## Tests

`python3 -m pytest -q tools/manifest` (needs `bin/cp_verify`, from `verifier/build.sh`). Every
manifest field is tampered three ways; `SIGNERS_WORD` in the test lists exactly which fields a
trusted signer can change undetected. Results: `experiments/20261104-58-signed-manifest/RESULTS.md`.

## Limits

Detached: the manifest is not inside the configuration or the proof. It does not prove the
signer told the truth about what the client cannot rehash; rederiving the commitment ID from the
manifest's recipe (public-weights commitments only, needs an H100) is what checks that.
