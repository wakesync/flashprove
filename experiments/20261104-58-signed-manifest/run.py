#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure the PREREG metrics of 20261104-58-signed-manifest. CPU only. Writes numbers.json.

Needs bin/cp_verify (verifier/build.sh). Run from the repository root:
    python3 experiments/20261104-58-signed-manifest/run.py
"""

import contextlib
import io
import json
import pathlib
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "manifest"))
import ed25519  # noqa: E402
import manifest as mf  # noqa: E402
import tamper as t  # noqa: E402

N_UNTAMPERED = 10


def run(tmp, m, recipe, secret=t.TRUSTED_SECRET, overrides=None, raw=None, sig=None):
    mp, sp = t.write_signed(tmp, m, secret)
    if raw is not None:
        mp.write_bytes(raw)
    if sig is not None:
        sp.write_bytes(sig)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = mf.main(t.verify_argv(tmp, mp, sp, recipe, overrides))
    return code, buf.getvalue().strip().splitlines()[-1]


def main():
    out = {"rows": [], "untampered": [], "coordinated": [], "omission": [], "rfc8032": None,
           "cross_check": None, "small_order": None}
    build = t.build_digest()
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        m, recipe = t.make_fixture(tmp, build)
        base_m = json.loads(json.dumps(m))

        # untampered, n = 10
        for i in range(N_UNTAMPERED):
            t0 = time.perf_counter()
            code, last = run(tmp, m, recipe)
            out["untampered"].append({"i": i, "exit": code, "last": last,
                                      "wall_s": time.perf_counter() - t0})

        # every field x 3 tamper kinds
        good_sig = t.write_signed(tmp, m)[1].read_bytes()
        for path in t.leaves(m):
            name = t.path_name(path)
            bad = t.mutated(m, path)
            for kind, kw in (("orig-sig", {"sig": good_sig}),
                             ("attacker-sig", {"secret": t.ATTACKER_SECRET}),
                             ("trusted-sig", {})):
                code, last = run(tmp, bad, recipe, **kw)
                out["rows"].append({"field": name, "kind": kind, "exit": code, "last": last})
            bad2 = json.loads(json.dumps(bad))
            bad2["signer"]["public_key"] = ed25519.public_key(t.ATTACKER_SECRET).hex()
            code, last = run(tmp, bad2, recipe, secret=t.ATTACKER_SECRET)
            out["rows"].append({"field": name, "kind": "attacker-sig+key", "exit": code,
                                "last": last})

        # file substitutions
        subs = []
        for which in ("policy.txt", "KL.bin", "layout.txt"):
            c = t.copy_example(tmp / ("c-" + which))
            t.flip_byte(c / "config" / which, offset=-2 if which == "policy.txt" else None)
            subs.append(("config/" + which, {"--config": str(c / "config")}))
        for which in ("example.proof", "example.req", "example.y", "ivk/key.bin", "ivk/leaf/0.bin"):
            c = t.copy_example(tmp / ("p-" + which.replace("/", "_")))
            t.flip_byte(c / which)
            subs.append((which, {"--ivk": str(c / "ivk"), "--request": str(c / "example.req"),
                                 "--y": str(c / "example.y"), "--proof": str(c / "example.proof")}))
        for which, src in (("tokenizer.json", tmp / "tokenizer" / "tokenizer.json"),
                           ("chat_template", tmp / "chat_template.jinja"),
                           ("system_prompt", tmp / "system_prompt.txt"),
                           ("recipe", recipe)):
            dst = tmp / ("s-" + which)
            if which == "tokenizer.json":
                shutil.copytree(tmp / "tokenizer", dst)
                t.flip_byte(dst / "tokenizer.json")
                subs.append((which, {"--tokenizer-dir": str(dst)}))
            else:
                shutil.copy(src, dst)
                t.flip_byte(dst)
                flag = {"chat_template": "--chat-template", "system_prompt": "--system-prompt",
                        "recipe": "--recipe"}[which]
                subs.append((which, {flag: str(dst)}))
        extra = tmp / "s-extra-tok"
        shutil.copytree(tmp / "tokenizer", extra)
        (extra / "added_tokens.json").write_text("{}\n")
        subs.append(("tokenizer extra file", {"--tokenizer-dir": str(extra)}))
        (tmp / "other.pub").write_text(ed25519.public_key(t.ATTACKER_SECRET).hex() + "\n")
        subs.append(("wrong trusted key", {"--signer-key": str(tmp / "other.pub")}))
        subs.append(("end tokens differ", {"--end-tokens": "2"}))
        for name, over in subs:
            code, last = run(tmp, m, recipe, overrides=over)
            out["rows"].append({"field": name, "kind": "file-substitution", "exit": code,
                                "last": last})
        # amendment 2 arms (no threshold): coordinated schema-valid alternates re-signed by the
        # trusted key, each without and (where one exists) with the flag that checks it; and
        # leaving out each now-required flag
        (tmp / "coord").mkdir()
        for name, covers, bad, flags in t.coordinated(m, tmp / "coord"):
            mf.check_schema(bad)
            code, last = run(tmp, bad, recipe)
            out["coordinated"].append({"alternate": name, "covers": covers, "flag": None,
                                       "exit": code, "last": last})
            if flags is not None:
                code, last = run(tmp, bad, recipe, overrides=flags)
                out["coordinated"].append({"alternate": name, "covers": covers,
                                           "flag": sorted(flags), "exit": code, "last": last})
        for name, over, bad in (
                ("--end-tokens left out", {"--end-tokens": None}, m),
                ("--recipe left out, no --no-recipe", {"--recipe": None}, m),
                ("both --recipe and --no-recipe", {"--no-recipe": True}, m),
                ("--no-recipe, honest manifest", {"--recipe": None, "--no-recipe": True}, m),
                ("--no-recipe, script_sha256 changed + trusted re-sign",
                 {"--recipe": None, "--no-recipe": True},
                 dict(m, conversion=dict(m["conversion"], script_sha256="ab" * 32)))):
            code, last = run(tmp, bad, recipe, overrides=over)
            out["omission"].append({"case": name, "exit": code, "last": last})

        for i in range(0, 64, 7):
            sig = bytearray(good_sig)
            sig[i] ^= 0x80
            code, last = run(tmp, m, recipe, sig=bytes(sig))
            out["rows"].append({"field": "signature byte %d" % i, "kind": "sig-bitflip",
                                "exit": code, "last": last})
        pretty = json.dumps(m, indent=2, sort_keys=True).encode() + b"\n"
        code, last = run(tmp, m, recipe, raw=pretty,
                         sig=ed25519.sign(t.TRUSTED_SECRET, mf.signed_bytes(pretty)))
        out["rows"].append({"field": "non-canonical JSON", "kind": "encoding", "exit": code,
                            "last": last})

    # RFC 8032 + cross-check
    sys.path.insert(0, str(REPO / "tools" / "manifest"))
    import test_manifest as tm
    ok = 0
    for sk, pk, msg, sig in tm.RFC8032:
        sk, pk, msg, sig = map(bytes.fromhex, (sk, pk, msg, sig))
        ok += ed25519.public_key(sk) == pk and ed25519.sign(sk, msg) == sig and ed25519.verify(pk, msg, sig)
    out["rfc8032"] = {"matched": ok, "total": len(tm.RFC8032)}
    # small-order keys and R (amendment 2): forgeries that the bare cofactorless equation accepts
    ident = bytes.fromhex(tm.SMALL_ORDER[0])
    forged = ed25519._compress(ed25519._mul(123456789, ed25519.G)) + (123456789).to_bytes(32, "little")
    sk = bytes(range(32))
    pub = ed25519.public_key(sk)
    a, _ = ed25519._secret_expand(sk)
    small_a, small_r = 0, 0
    for enc in tm.SMALL_ORDER:
        a_enc = bytes.fromhex(enc)
        t_pt = ed25519._decompress(a_enc)
        small_a += all(not ed25519.verify(a_enc, b"m", ed25519._compress(
            ed25519._add(ed25519._mul(7, ed25519.G), ed25519._decompress(bytes.fromhex(t2))))
            + (7).to_bytes(32, "little")) for t2 in tm.SMALL_ORDER)
        k = int.from_bytes(ed25519._sha512(a_enc + pub + b"m"), "little") % ed25519.L
        small_r += not ed25519.verify(pub, b"m", a_enc + ((k * a) % ed25519.L).to_bytes(32, "little"))
        assert ed25519.is_small_order(t_pt)
    out["small_order"] = {
        "identity_key_forgery_refused": not ed25519.verify(ident, b"any message at all", forged),
        "small_order_keys_all_forgeries_refused": small_a, "small_order_r_refused": small_r,
        "total": len(tm.SMALL_ORDER)}
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519 as ref
        import cryptography
        rng = random.Random(1104)
        agree = 0
        for _ in range(64):
            sk = rng.randbytes(32)
            msg = rng.randbytes(rng.randrange(0, 300))
            agree += ed25519.sign(sk, msg) == ref.Ed25519PrivateKey.from_private_bytes(sk).sign(msg)
        out["cross_check"] = {"agree": agree, "total": 64, "cryptography": cryptography.__version__}
    except ImportError:
        out["cross_check"] = "not run: cryptography not installed"

    # summary
    rows = out["rows"]
    must_refuse = [r for r in rows if r["kind"] != "trusted-sig"]
    trusted = [r for r in rows if r["kind"] == "trusted-sig"]
    walls = [u["wall_s"] for u in out["untampered"]]
    schema_only = set()
    by_name = {t.path_name(p): p for p in t.leaves(base_m)}
    for r in trusted:
        if r["exit"] == 1:
            path = by_name[r["field"]]
            try:
                mf.check_schema(t.mutated(base_m, path))
            except mf.Refusal:
                schema_only.add(r["field"])
    out["summary"] = {
        "untampered_accepted": sum(u["exit"] == 0 for u in out["untampered"]),
        "untampered_n": len(out["untampered"]),
        "verify_wall_s": {"median": statistics.median(walls), "sd": statistics.stdev(walls),
                          "min": min(walls), "max": max(walls), "n": len(walls),
                          "note": "whole verify call: manifest checks plus one cp_verify process on the stored small example"},
        "fields": len(trusted),
        "must_refuse_total": len(must_refuse),
        "must_refuse_refused": sum(r["exit"] == 1 for r in must_refuse),
        "trusted_resign_refused": sum(r["exit"] == 1 for r in trusted),
        "trusted_resign_accepted_fields": sorted(r["field"] for r in trusted if r["exit"] == 0),
        "trusted_resign_refused_schema_only": sorted(schema_only),
        "trusted_resign_refused_bound": sorted(r["field"] for r in trusted if r["exit"] == 1
                                               and r["field"] not in schema_only),
        "coordinated_alternates": len({c["alternate"] for c in out["coordinated"]}),
        "coordinated_accepted_without_flag": sorted(c["alternate"] for c in out["coordinated"]
                                                    if c["flag"] is None and c["exit"] == 0),
        "coordinated_refused_with_flag": sorted(c["alternate"] for c in out["coordinated"]
                                                if c["flag"] is not None and c["exit"] == 1),
        "coordinated_accepted_with_flag": sorted(c["alternate"] for c in out["coordinated"]
                                                 if c["flag"] is not None and c["exit"] == 0),
        "signers_word_unless_flag_fields": sorted({f for c in out["coordinated"]
                                                   if c["flag"] is None and c["exit"] == 0
                                                   for f in c["covers"]}),
        "omission": {c["case"]: c["exit"] for c in out["omission"]},
    }
    out["host"] = {"python": platform.python_version(), "machine": platform.machine()}
    (HERE / "numbers.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["summary"], indent=1))
    print(json.dumps({"rfc8032": out["rfc8032"], "cross_check": out["cross_check"],
                      "small_order": out["small_order"]}))


if __name__ == "__main__":
    main()
