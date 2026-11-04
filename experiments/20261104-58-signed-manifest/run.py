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
    out = {"rows": [], "untampered": [], "rfc8032": None, "cross_check": None}
    build = t.build_digest()
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        m, recipe = t.make_fixture(tmp, build)

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
    }
    out["host"] = {"python": platform.python_version(), "machine": platform.machine()}
    (HERE / "numbers.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["summary"], indent=1))
    print(json.dumps({"rfc8032": out["rfc8032"], "cross_check": out["cross_check"]}))


if __name__ == "__main__":
    main()
