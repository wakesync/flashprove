# SPDX-License-Identifier: Apache-2.0
"""Tests for tools/manifest. Run: python3 -m pytest -q tools/manifest

Three kinds of tamper, for every field of the manifest (enumerated mechanically by tamper.leaves):
  1. field changed, original signature kept            -> must refuse (signature)
  2. field changed, re-signed by an attacker key        -> must refuse (signer key is the caller's)
  3. field changed, re-signed by the TRUSTED key        -> must refuse iff the field is bound to
     something the caller holds (a file, cp_verify's output); otherwise the field is the signer's
     word, and the test asserts exactly which fields those are (SIGNERS_WORD), so a new unbound
     field cannot slip in unnoticed.
Plus: every bound file swapped for a one-byte-changed copy, non-canonical JSON, signature bit flip,
wrong trusted key, RFC 8032 vectors, cross-check against `cryptography` if installed.
"""

import json
import os
import pathlib
import random
import shutil

import pytest

import ed25519
import manifest as mf
import tamper as t

needs_verifier = pytest.mark.skipif(not t.CP_VERIFY.is_file(),
                                    reason="bin/cp_verify is not built (run verifier/build.sh)")

# Fields that no caller-side file or cp_verify output pins, in the fixture's configuration. With
# --upstream-dir / --committed-dir / --public-weights-seed on a real model, upstream.files,
# conversion.committed_files and the seed digest move out of this set (tested below).
SIGNERS_WORD = {
    "signer.name",
    "upstream.generator",
    "upstream.seed",
    "conversion.script",  # the path label; the script's digest is bound via --recipe
    "conversion.repo_commit",
    "conversion.version",
    "conversion.params.M",
    "conversion.params.config",
    "conversion.params.weights",
    "verifier.source_commit",
}


@pytest.fixture(scope="module")
def build():
    return t.build_digest()


@pytest.fixture()
def fx(tmp_path, build):
    m, recipe = t.make_fixture(tmp_path, build)
    return tmp_path, m, recipe


def run(tmp, m, recipe, secret=t.TRUSTED_SECRET, overrides=None, raw=None, sig=None):
    mp, sp = t.write_signed(tmp, m, secret)
    if raw is not None:
        mp.write_bytes(raw)
    if sig is not None:
        sp.write_bytes(sig)
    return mf.main(t.verify_argv(tmp, mp, sp, recipe, overrides))


# ---- ed25519 ----

RFC8032 = [  # section 7.1, tests 1-3: secret, public, message, signature
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


@pytest.mark.parametrize("sk,pk,msg,sig", RFC8032)
def test_rfc8032_vectors(sk, pk, msg, sig):
    sk, pk, msg, sig = map(bytes.fromhex, (sk, pk, msg, sig))
    assert ed25519.public_key(sk) == pk
    assert ed25519.sign(sk, msg) == sig
    assert ed25519.verify(pk, msg, sig)
    assert not ed25519.verify(pk, msg + b"\0", sig)


def test_cross_check_with_cryptography():
    c = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
    rng = random.Random(1104)
    for _ in range(64):
        sk = rng.randbytes(32)
        msg = rng.randbytes(rng.randrange(0, 300))
        ref = c.Ed25519PrivateKey.from_private_bytes(sk)
        assert ed25519.sign(sk, msg) == ref.sign(msg)
        pub = ref.public_key().public_bytes_raw()
        assert ed25519.public_key(sk) == pub
        assert ed25519.verify(pub, msg, ref.sign(msg))


def test_signature_s_not_reduced_is_refused():
    sk = bytes(32)
    sig = ed25519.sign(sk, b"m")
    s = int.from_bytes(sig[32:], "little") + ed25519.L
    assert not ed25519.verify(ed25519.public_key(sk), b"m", sig[:32] + s.to_bytes(32, "little"))


# ---- the honest path ----


@needs_verifier
def test_untampered_accepts(fx, capsys):
    tmp, m, recipe = fx
    assert run(tmp, m, recipe) == 0
    out = capsys.readouterr().out
    assert "manifest: ACCEPTED" in out and "result-v1 status=0" in out


@needs_verifier
def test_none_fields_need_explicit_flags(fx):
    tmp, m, recipe = fx
    m["serving"]["system_prompt"] = {"none": True}
    assert run(tmp, m, recipe) == 1  # caller still passes a system prompt file
    assert run(tmp, m, recipe, overrides={"--system-prompt": None}) == 1  # no --no-system-prompt
    assert run(tmp, m, recipe, overrides={"--system-prompt": None, "--no-system-prompt": True}) == 0


# ---- tamper: every field ----


def all_fields(build, tmp):
    m, _ = t.make_fixture(tmp, build)
    return [p for p in t.leaves(m)]


@needs_verifier
def test_every_field_tamper(tmp_path, build):
    m, recipe = t.make_fixture(tmp_path, build)
    paths = list(t.leaves(m))
    assert len(paths) >= 25
    accepted_by_trusted = set()
    for path in paths:
        name = t.path_name(path)
        bad = t.mutated(m, path)
        # 1. original signature kept
        good_sig = t.write_signed(tmp_path, m)[1].read_bytes()
        assert run(tmp_path, bad, recipe, sig=good_sig) == 1, name
        # 2. attacker re-signs (with or without putting its own key in signer.public_key)
        assert run(tmp_path, bad, recipe, secret=t.ATTACKER_SECRET) == 1, name
        bad2 = json.loads(json.dumps(bad))
        if isinstance(bad2.get("signer"), dict):
            bad2["signer"]["public_key"] = ed25519.public_key(t.ATTACKER_SECRET).hex()
        assert run(tmp_path, bad2, recipe, secret=t.ATTACKER_SECRET) == 1, name
        # 3. the trusted signer itself signs the changed field
        if run(tmp_path, bad, recipe) == 0:
            accepted_by_trusted.add(name)
    assert accepted_by_trusted == SIGNERS_WORD


@needs_verifier
@pytest.mark.parametrize("which", ["policy.txt", "KL.bin", "layout.txt"])
def test_config_file_swap(fx, which):
    tmp, m, recipe = fx
    d = t.copy_example(tmp)
    t.flip_byte(d / "config" / which, offset=-2 if which == "policy.txt" else None)
    assert run(tmp, m, recipe, overrides={"--config": str(d / "config")}) == 1


@needs_verifier
@pytest.mark.parametrize("which", ["tokenizer", "chat_template", "system_prompt", "recipe"])
def test_serving_file_swap(fx, which):
    tmp, m, recipe = fx
    target = {"tokenizer": tmp / "tokenizer" / "tokenizer.json",
              "chat_template": tmp / "chat_template.jinja",
              "system_prompt": tmp / "system_prompt.txt"}.get(which)
    over = {}
    if which == "recipe":
        target = tmp / "recipe.sh"
        shutil.copy(recipe, target)
        over["--recipe"] = str(target)
    t.flip_byte(target)
    assert run(tmp, m, recipe, overrides=over) == 1


@needs_verifier
def test_extra_tokenizer_file_refused(fx):
    tmp, m, recipe = fx
    (tmp / "tokenizer" / "special_tokens_map.json").write_text("{}\n")
    assert run(tmp, m, recipe) == 1


@needs_verifier
def test_missing_serving_files_refused(fx):
    tmp, m, recipe = fx
    for k in ("--tokenizer-dir", "--chat-template", "--system-prompt"):
        assert run(tmp, m, recipe, overrides={k: None}) == 1, k


@needs_verifier
def test_end_tokens_mismatch(fx):
    tmp, m, recipe = fx
    assert run(tmp, m, recipe, overrides={"--end-tokens": "2"}) == 1


@needs_verifier
@pytest.mark.parametrize("which", ["example.proof", "example.req", "example.y", "ivk/key.bin",
                                   "ivk/leaf/0.bin"])
def test_proof_side_swap_refused_by_cp_verify(fx, which):
    tmp, m, recipe = fx
    d = t.copy_example(tmp)
    t.flip_byte(d / which)
    over = {"--ivk": str(d / "ivk"), "--request": str(d / "example.req"),
            "--y": str(d / "example.y"), "--proof": str(d / "example.proof")}
    assert run(tmp, m, recipe, overrides=over) == 1


@needs_verifier
def test_wrong_trusted_key(fx):
    tmp, m, recipe = fx
    (tmp / "other.pub").write_text(ed25519.public_key(t.ATTACKER_SECRET).hex() + "\n")
    assert run(tmp, m, recipe, overrides={"--signer-key": str(tmp / "other.pub")}) == 1


@needs_verifier
def test_signature_bit_flips(fx):
    tmp, m, recipe = fx
    good = t.write_signed(tmp, m)[1].read_bytes()
    for i in range(0, 64, 7):
        sig = bytearray(good)
        sig[i] ^= 0x80
        assert run(tmp, m, recipe, sig=bytes(sig)) == 1, i


@needs_verifier
def test_non_canonical_json_refused(fx):
    tmp, m, recipe = fx
    pretty = json.dumps(m, indent=2, sort_keys=True).encode() + b"\n"
    from tamper import TRUSTED_SECRET
    sig = ed25519.sign(TRUSTED_SECRET, mf.signed_bytes(pretty))  # signed, but not canonical
    assert run(tmp, m, recipe, raw=pretty, sig=sig) == 1


@needs_verifier
def test_unknown_and_missing_keys_refused(fx):
    tmp, m, recipe = fx
    m2 = json.loads(json.dumps(m))
    m2["extra"] = 1
    assert run(tmp, m2, recipe) == 1
    m3 = json.loads(json.dumps(m))
    del m3["serving"]["system_prompt"]
    assert run(tmp, m3, recipe) == 1


@needs_verifier
def test_policy_kind_must_match_limits(fx):
    tmp, m, recipe = fx
    m["decode_policy"]["kind"] = "clipped-gap"
    assert run(tmp, m, recipe) == 1


# ---- optional rehash of upstream / committed files / public-weights seed ----


def test_upstream_and_committed_files_rehashed(tmp_path):
    up = tmp_path / "up"
    up.mkdir()
    (up / "model.safetensors").write_bytes(b"w" * 1000)
    (up / "config.json").write_text("{}\n")
    entries = [{"path": n, "sha256": mf.sha256_file(up / n)} for n in sorted(os.listdir(up))]
    mf.check_files(entries, up, "upstream.files")
    t.flip_byte(up / "model.safetensors")
    with pytest.raises(mf.Refusal, match="model.safetensors digest differs"):
        mf.check_files(entries, up, "upstream.files")
    (up / "model.safetensors").write_bytes(b"w" * 1000)
    (up / "adapter.safetensors").write_bytes(b"a")
    with pytest.raises(mf.Refusal, match="adapter.safetensors is present but not listed"):
        mf.check_files(entries, up, "upstream.files")


def test_huggingface_revision_must_be_a_commit(tmp_path, build):
    m, _ = t.make_fixture(tmp_path, build)
    m["upstream"] = {"kind": "huggingface", "repo": "org/model", "revision": "main",
                     "files": [{"path": "a", "sha256": "0" * 64}]}
    with pytest.raises(mf.Refusal, match="revision"):
        mf.check_schema(m)
    m["upstream"]["revision"] = "a" * 40
    m["conversion"]["committed_files"] = [{"path": "b", "sha256": "1" * 64}]
    mf.check_schema(m)


def test_public_weights_needs_seed_digest(tmp_path, build):
    m, _ = t.make_fixture(tmp_path, build)
    m["commitment"]["kind"] = "public-weights"
    with pytest.raises(mf.Refusal, match="public_weights_seed"):
        mf.check_schema(m)
