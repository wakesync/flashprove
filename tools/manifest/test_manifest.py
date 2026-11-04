# SPDX-License-Identifier: Apache-2.0
"""Tests for tools/manifest. Run: python3 -m pytest -q tools/manifest

Three kinds of tamper, for every field of the manifest (enumerated mechanically by tamper.leaves):
  1. field changed, original signature kept            -> must refuse (signature)
  2. field changed, re-signed by an attacker key        -> must refuse (signer key is the caller's)
  3. field changed, re-signed by the TRUSTED key        -> must refuse iff the field is bound to
     something the caller holds (a file, cp_verify's output); otherwise the field is the signer's
     word, and the test asserts exactly which fields those are (SIGNERS_WORD_SINGLE), so a new
     unbound field cannot slip in unnoticed. It also asserts which refusals were the schema's
     alone (SCHEMA_ONLY), and test_coordinated_trusted_resign re-signs schema-valid alternates of
     those (SIGNERS_WORD_UNLESS_FLAG: signer's word unless the matching flag is passed).
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

# What the trusted signer can change undetected, in the fixture's configuration (synthetic upstream,
# hiding commitment, no committed files), when the caller passes the required flags
# (--end-tokens, --recipe) but none of --upstream-dir / --committed-dir / --public-weights-seed.
#
# SIGNERS_WORD_SINGLE: a one-field mutation re-signed by the trusted key is accepted.
SIGNERS_WORD_SINGLE = {
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
# SIGNERS_WORD_UNLESS_FLAG: the one-field mutation is refused only by the schema (a nonsense value),
# but a coordinated, schema-valid alternate re-signed by the trusted key is accepted unless the
# caller passes the matching flag (tamper.coordinated): commitment.kind and the seed digest
# (--public-weights-seed), upstream.* (--upstream-dir), conversion.committed_files
# (--committed-dir). conversion.script_sha256 joins this set when the caller passes --no-recipe.
SIGNERS_WORD_UNLESS_FLAG = {
    "commitment.kind",
    "conversion.public_weights_seed_sha256",
    "upstream.kind",
    "conversion.committed_files",
}
SIGNERS_WORD = SIGNERS_WORD_SINGLE | SIGNERS_WORD_UNLESS_FLAG
# One-field mutations that check_schema alone refuses (no file or cp_verify output involved).
SCHEMA_ONLY = {
    "format", "commitment.kind", "upstream.kind", "conversion.committed_files",
    "conversion.public_weights_seed_sha256", "decode_policy.kind", "decode_policy.C",
    "decode_policy.theta", "decode_policy.cap", "decode_policy.sT",
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


# The 8 points of small order (orders 1, 2, 4, 8), canonical encodings. [8]P is the identity.
SMALL_ORDER = [
    "0100000000000000000000000000000000000000000000000000000000000000",  # identity, order 1
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",  # (0, -1), order 2
    "0000000000000000000000000000000000000000000000000000000000000000",  # order 4
    "0000000000000000000000000000000000000000000000000000000000000080",  # order 4
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",  # order 8
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",  # order 8
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",  # order 8
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",  # order 8
]


def test_small_order_points_are_small_order():
    for enc in SMALL_ORDER:
        pt = ed25519._decompress(bytes.fromhex(enc))
        assert pt is not None and ed25519.is_small_order(pt), enc
    assert not ed25519.is_small_order(ed25519.G)


def test_identity_key_forgery_refused():
    # Under the bare cofactorless equation, A = identity, R = [r]B, S = r verifies for ANY message.
    identity = bytes.fromhex(SMALL_ORDER[0])
    r = 123456789
    forged = ed25519._compress(ed25519._mul(r, ed25519.G)) + r.to_bytes(32, "little")
    for msg in (b"any message at all", b"", mf.signed_bytes(b"{}\n")):
        assert not ed25519.verify(identity, msg, forged)


@pytest.mark.parametrize("enc", SMALL_ORDER)
def test_small_order_public_key_refused(enc):
    # For a small-order A, [k]A cycles through at most 8 points: with R = [r]B - [k]A and S = r the
    # equation holds whenever we pick that R. Build such a forgery and check it is refused.
    a_enc = bytes.fromhex(enc)
    a_pt = ed25519._decompress(a_enc)
    msg = b"forged under a small-order key"
    r = 987654321
    # find R = [r]B + T for torsion T such that k(R) makes [k]A = T; try all 8 candidates
    refused = 0
    for t_enc in SMALL_ORDER:
        t_pt = ed25519._decompress(bytes.fromhex(t_enc))
        big_r = ed25519._compress(ed25519._add(ed25519._mul(r, ed25519.G), t_pt))
        sig = big_r + r.to_bytes(32, "little")
        refused += not ed25519.verify(a_enc, msg, sig)
    assert refused == len(SMALL_ORDER)
    assert ed25519.is_small_order(a_pt)


@pytest.mark.parametrize("enc", SMALL_ORDER)
def test_small_order_r_refused(enc):
    # A real key, a signature whose R is a small-order point and S = 0: [0]B = identity and
    # R + [k]A is not, unless A's multiple cancels, so also check a hand-made equation-satisfying
    # case: with A = [a]B, R = T (small order), [S]B = T + [k][a]B has no solution for T != 0,
    # but R = identity, S = k*a mod L does. Both must be refused.
    sk = bytes(range(32))
    pub = ed25519.public_key(sk)
    a, _ = ed25519._secret_expand(sk)
    msg = b"small-order R"
    r_enc = bytes.fromhex(enc)
    k = int.from_bytes(ed25519._sha512(r_enc + pub + msg), "little") % ed25519.L
    sig = r_enc + ((k * a) % ed25519.L).to_bytes(32, "little")
    if enc == SMALL_ORDER[0]:  # identity R: the bare equation holds; must still refuse
        assert ed25519._equal(ed25519._mul((k * a) % ed25519.L, ed25519.G),
                              ed25519._add(ed25519._decompress(r_enc),
                                           ed25519._mul(k, ed25519._decompress(pub))))
    assert not ed25519.verify(pub, msg, sig)


def test_small_order_key_refused_by_manifest_load(tmp_path):
    identity = bytes.fromhex(SMALL_ORDER[0])
    r = 42
    forged = ed25519._compress(ed25519._mul(r, ed25519.G)) + r.to_bytes(32, "little")
    with pytest.raises(mf.Refusal, match="signature"):
        mf.load(b"{}\n", forged, identity)


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
    schema_only = set()
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
        else:
            try:
                mf.check_schema(bad)
            except mf.Refusal:
                schema_only.add(name)
    assert accepted_by_trusted == SIGNERS_WORD_SINGLE
    assert schema_only == SCHEMA_ONLY


@needs_verifier
def test_coordinated_trusted_resign(fx):
    """Schema-valid alternates re-signed by the trusted key: accepted without the matching flag
    (signer's word), refused with it. Fields with no such flag must refuse without one."""
    tmp, m, recipe = fx
    unless_flag = set()
    for name, covers, bad, flags in t.coordinated(m, tmp):
        mf.check_schema(bad)  # really schema-valid
        code = run(tmp, bad, recipe)
        if flags is None:
            assert code == 1, name
        else:
            assert code == 0, name  # nothing the caller holds pins it
            assert run(tmp, bad, recipe, overrides=flags) == 1, name
            unless_flag.update(covers)
    assert unless_flag == SIGNERS_WORD_UNLESS_FLAG


@needs_verifier
def test_omitting_end_tokens_or_recipe_refused(fx):
    tmp, m, recipe = fx
    assert run(tmp, m, recipe, overrides={"--end-tokens": None}) == 1
    assert run(tmp, m, recipe, overrides={"--recipe": None}) == 1
    assert run(tmp, m, recipe, overrides={"--no-recipe": True}) == 1  # both given
    assert run(tmp, m, recipe, overrides={"--recipe": None, "--no-recipe": True}) == 0
    m["conversion"]["script_sha256"] = "ab" * 32
    assert run(tmp, m, recipe, overrides={"--recipe": None, "--no-recipe": True}) == 0  # disclosed
    assert run(tmp, m, recipe) == 1


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
