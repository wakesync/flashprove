#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Signed model manifest for a FlashProve commitment: make, sign and verify.

A manifest is a detached statement, signed by whoever vouches for a model, that ties one FlashProve
commitment ID to:
  - the upstream checkpoint (Hugging Face repo, revision, SHA-256 of every file used), or a named
    synthetic generator;
  - the conversion recipe that made the committed integer artifact (script, its digest, the repo
    commit it ran from, version, parameters, digests of the committed files, the -public-weights
    seed file's digest if the commitment is public);
  - the three configuration files that cp_verify reads (policy.txt, KL.bin, layout.txt);
  - what the server puts around a client's message: tokenizer files, chat template, system prompt,
    end tokens (each a digest, or an explicit "none");
  - the decode policy (exact match, or clipped gap with its limits);
  - the cp_verify build digest (the build= field of its result-v1 line).

`verify` refuses (exit 1) on any mismatch between the manifest, the signer key that the CALLER
names (never one taken from the manifest), the files the caller holds and what cp_verify prints.
It does not change and does not replace cp_verify: it runs it, with the manifest's ID.

What it cannot check: whether the signer told the truth about fields the caller has no files for.
commitment.kind is always the signer's word: --public-weights-seed rehashes a seed file against
conversion.public_weights_seed_sha256, but nothing compares that with what the commitment is, so a
signer who claims public-weights and ships a matching seed file is accepted; only rederivation
(rerun the recipe, get the same ID) checks the kind. upstream.* (kind, repo, revision, files, or
generator and seed), conversion.committed_files and conversion.public_weights_seed_sha256 are the
signer's word unless the caller passes --upstream-dir / --committed-dir / --public-weights-seed so
they are rehashed; conversion.script_sha256 is the signer's word under --no-recipe. See README.md.

Standard library only (ed25519.py next to this file).
"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ed25519  # noqa: E402

FORMAT = "flashprove-manifest-v1"
DOMAIN = b"flashprove-manifest-v1 signature\n"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
CONFIG_FILES = ("policy.txt", "KL.bin", "layout.txt")
POLICY_FIELDS = ("C", "theta", "cap", "s", "sh", "sT", "F")
EXACT = {"C": 256, "theta": 256, "cap": 0, "sT": 4}


class Refusal(Exception):
    """The manifest, a file or cp_verify's answer does not fit. str() says which field."""


# ---- canonical bytes ----


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"


def signed_bytes(manifest_bytes):
    return DOMAIN + manifest_bytes


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---- schema (strict: no unknown key, no missing key) ----


def _keys(obj, where, required, optional=()):
    if not isinstance(obj, dict):
        raise Refusal("%s: not an object" % where)
    missing = [k for k in required if k not in obj]
    extra = [k for k in obj if k not in required and k not in optional]
    if missing:
        raise Refusal("%s: missing key %s" % (where, missing[0]))
    if extra:
        raise Refusal("%s: unknown key %s" % (where, extra[0]))


def _hex64(value, where):
    if not isinstance(value, str) or not HEX64.match(value):
        raise Refusal("%s: not 64 lowercase hex digits" % where)


def _str(value, where):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise Refusal("%s: not a non-empty string" % where)


def _int(value, where):
    if type(value) is not int or not 0 <= value < 2**32:
        raise Refusal("%s: not an integer in [0, 2**32)" % where)


def _file_list(files, where, allow_empty=False):
    if not isinstance(files, list) or (not files and not allow_empty):
        raise Refusal("%s: not a%s list" % (where, "" if allow_empty else " non-empty"))
    seen = set()
    for i, entry in enumerate(files):
        _keys(entry, "%s[%d]" % (where, i), ("path", "sha256"))
        _str(entry["path"], "%s[%d].path" % (where, i))
        p = entry["path"]
        if p.startswith("/") or ".." in p.split("/") or p in seen:
            raise Refusal("%s[%d].path: absolute, has .., or repeated" % (where, i))
        seen.add(p)
        _hex64(entry["sha256"], "%s[%d].sha256" % (where, i))
    if [e["path"] for e in files] != sorted(seen):
        raise Refusal("%s: paths not sorted" % where)


def is_none(obj):
    """True only for {"none": true}: one encoding (1 and 1.0 compare equal to True, so no ==)."""
    return isinstance(obj, dict) and list(obj) == ["none"] and obj["none"] is True


def _digest_or_none(obj, where):
    if is_none(obj):
        return
    _keys(obj, where, ("sha256",))
    _hex64(obj["sha256"], where + ".sha256")


def check_schema(m):
    _keys(m, "manifest", ("format", "commitment", "upstream", "conversion", "configuration",
                          "serving", "decode_policy", "verifier", "signer"))
    if m["format"] != FORMAT:
        raise Refusal("format: not %s" % FORMAT)

    c = m["commitment"]
    _keys(c, "commitment", ("id", "kind"))
    _hex64(c["id"], "commitment.id")
    if c["kind"] not in ("public-weights", "hiding"):
        raise Refusal("commitment.kind: not public-weights or hiding")

    u = m["upstream"]
    if not isinstance(u, dict) or u.get("kind") not in ("huggingface", "synthetic"):
        raise Refusal("upstream.kind: not huggingface or synthetic")
    if u["kind"] == "huggingface":
        _keys(u, "upstream", ("kind", "repo", "revision", "files"))
        _str(u["repo"], "upstream.repo")
        if not isinstance(u["revision"], str) or not HEX40.match(u["revision"]):
            raise Refusal("upstream.revision: not a 40-hex commit (a branch name can move)")
        _file_list(u["files"], "upstream.files")
    else:
        _keys(u, "upstream", ("kind", "generator", "seed"))
        _str(u["generator"], "upstream.generator")
        _int(u["seed"], "upstream.seed")

    v = m["conversion"]
    _keys(v, "conversion", ("script", "script_sha256", "repo_commit", "version", "params",
                            "committed_files", "public_weights_seed_sha256"))
    _str(v["script"], "conversion.script")
    _hex64(v["script_sha256"], "conversion.script_sha256")
    if not isinstance(v["repo_commit"], str) or not HEX40.match(v["repo_commit"]):
        raise Refusal("conversion.repo_commit: not a 40-hex commit")
    _str(v["version"], "conversion.version")
    if not isinstance(v["params"], dict):
        raise Refusal("conversion.params: not an object")
    for k, val in v["params"].items():
        if not isinstance(val, (str, int)) or isinstance(val, bool):
            raise Refusal("conversion.params.%s: not a string or integer" % k)
    _file_list(v["committed_files"], "conversion.committed_files",
               allow_empty=u["kind"] == "synthetic")
    if c["kind"] == "public-weights":
        _hex64(v["public_weights_seed_sha256"], "conversion.public_weights_seed_sha256")
    elif v["public_weights_seed_sha256"] is not None:
        raise Refusal("conversion.public_weights_seed_sha256: must be null for a hiding commitment")

    cfg = m["configuration"]
    _keys(cfg, "configuration", CONFIG_FILES)
    for name in CONFIG_FILES:
        _hex64(cfg[name], "configuration." + name)

    s = m["serving"]
    _keys(s, "serving", ("tokenizer", "chat_template", "system_prompt", "end_tokens"))
    if not is_none(s["tokenizer"]):
        _keys(s["tokenizer"], "serving.tokenizer", ("files",))
        _file_list(s["tokenizer"]["files"], "serving.tokenizer.files")
    _digest_or_none(s["chat_template"], "serving.chat_template")
    _digest_or_none(s["system_prompt"], "serving.system_prompt")
    if not isinstance(s["end_tokens"], list):
        raise Refusal("serving.end_tokens: not a list")
    for i, t in enumerate(s["end_tokens"]):
        _int(t, "serving.end_tokens[%d]" % i)

    d = m["decode_policy"]
    _keys(d, "decode_policy", ("kind",) + POLICY_FIELDS)
    for name in POLICY_FIELDS:
        _int(d[name], "decode_policy." + name)
    is_exact = all(d[k] == v for k, v in EXACT.items())
    if d["kind"] != ("exact" if is_exact else "clipped-gap"):
        raise Refusal("decode_policy.kind: does not match its limits")

    vf = m["verifier"]
    _keys(vf, "verifier", ("build_digest", "source_commit"))
    _hex64(vf["build_digest"], "verifier.build_digest")
    if not isinstance(vf["source_commit"], str) or not HEX40.match(vf["source_commit"]):
        raise Refusal("verifier.source_commit: not a 40-hex commit")

    g = m["signer"]
    _keys(g, "signer", ("name", "public_key"))
    _str(g["name"], "signer.name")
    _hex64(g["public_key"], "signer.public_key")


# ---- load + signature ----


def load(manifest_bytes, signature, trusted_key):
    """Parse, check canonical form, schema and signature. Return the manifest dict."""
    if len(trusted_key) != 32:
        raise Refusal("signer key: not 32 bytes")
    if not ed25519.verify(trusted_key, signed_bytes(manifest_bytes), signature):
        raise Refusal("signature: does not verify under the trusted signer key")
    try:
        m = json.loads(manifest_bytes.decode("ascii"))
        same = canonical(m) == manifest_bytes
    except (UnicodeDecodeError, ValueError) as e:
        raise Refusal("manifest: not ASCII JSON (%s)" % e)
    except RecursionError:
        raise Refusal("manifest: nested too deeply to parse")
    if not same:
        raise Refusal("manifest: not in canonical form")
    check_schema(m)
    if bytes.fromhex(m["signer"]["public_key"]) != trusted_key:
        raise Refusal("signer.public_key: not the trusted signer key")
    return m


# ---- binding checks ----


def parse_policy_file(data):
    values = {}
    for line in data.decode("ascii").splitlines():
        words = line.split(" ")
        if len(words) == 2 and words[0] in POLICY_FIELDS:
            if words[0] in values:
                raise Refusal("policy.txt: repeats %s" % words[0])
            values[words[0]] = int(words[1])
    return values


def check_config(m, config_dir):
    for name in CONFIG_FILES:
        if sha256_file(os.path.join(config_dir, name)) != m["configuration"][name]:
            raise Refusal("configuration.%s: file digest differs" % name)
    values = parse_policy_file(pathlib.Path(config_dir, "policy.txt").read_bytes())
    for name in POLICY_FIELDS:
        if values.get(name) != m["decode_policy"][name]:
            raise Refusal("decode_policy.%s: differs from policy.txt" % name)


def check_files(entries, root, where):
    """Rehash a directory: every listed file matches, nothing else is there. Symlinks and anything
    other than plain files and directories inside root are refused (a walk that does not follow a
    symlinked directory would miss what is in it; one that follows it can loop or leave root)."""
    root = pathlib.Path(root)
    listed = {e["path"] for e in entries}
    present = set()
    for top, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = pathlib.Path(top, name)
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                raise Refusal("%s: %s is a symlink" % (where, rel))
            if name in files:
                if not p.is_file():
                    raise Refusal("%s: %s is not a plain file" % (where, rel))
                present.add(rel)
    for e in entries:
        p = root / e["path"]
        if e["path"] not in present:
            raise Refusal("%s: %s missing" % (where, e["path"]))
        if sha256_file(p) != e["sha256"]:
            raise Refusal("%s: %s digest differs" % (where, e["path"]))
    extra = sorted(present - listed)
    if extra:
        raise Refusal("%s: %s is present but not listed" % (where, extra[0]))


def check_serving(m, args):
    s = m["serving"]
    if is_none(s["tokenizer"]):
        if not args.no_tokenizer:
            raise Refusal("serving.tokenizer: manifest says none; pass --no-tokenizer to accept")
    else:
        if not args.tokenizer_dir:
            raise Refusal("serving.tokenizer: pass --tokenizer-dir")
        check_files(s["tokenizer"]["files"], args.tokenizer_dir, "serving.tokenizer.files")
    for field, path_arg, none_arg in (("chat_template", args.chat_template, args.no_chat_template),
                                      ("system_prompt", args.system_prompt, args.no_system_prompt)):
        want = s[field]
        if is_none(want):
            if path_arg or not none_arg:
                raise Refusal("serving.%s: manifest says none; pass --no-%s and no file"
                              % (field, field.replace("_", "-")))
        else:
            if not path_arg:
                raise Refusal("serving.%s: pass the file you used" % field)
            if sha256_file(path_arg) != want["sha256"]:
                raise Refusal("serving.%s: file digest differs" % field)
    if args.end_tokens is None:
        raise Refusal("serving.end_tokens: pass --end-tokens (comma list, or none for the empty list)")
    if args.end_tokens != s["end_tokens"]:
        raise Refusal("serving.end_tokens: differ from --end-tokens")


def check_recipe(m, args):
    v = m["conversion"]
    if bool(args.recipe) == bool(args.no_recipe):
        raise Refusal("conversion.script_sha256: pass exactly one of --recipe FILE or --no-recipe "
                      "(--no-recipe leaves the recipe digest the signer's word)")
    if args.recipe and sha256_file(args.recipe) != v["script_sha256"]:
        raise Refusal("conversion.script_sha256: recipe file digest differs")
    if args.committed_dir:
        check_files(v["committed_files"], args.committed_dir, "conversion.committed_files")
    if args.upstream_dir:
        if m["upstream"]["kind"] != "huggingface":
            raise Refusal("upstream: --upstream-dir given but upstream is synthetic")
        check_files(m["upstream"]["files"], args.upstream_dir, "upstream.files")
    if args.public_weights_seed:
        want = v["public_weights_seed_sha256"]
        if want is None or sha256_file(args.public_weights_seed) != want:
            raise Refusal("conversion.public_weights_seed_sha256: seed file digest differs")


def run_cp_verify(m, args):
    words = [args.cp_verify, args.config, args.ivk, args.request, args.y, args.proof,
             "-id", m["commitment"]["id"], "-q"]
    done = subprocess.run(words, capture_output=True, text=True, timeout=args.timeout,
                          env={"PATH": "/usr/bin:/bin"})
    lines = done.stdout.rstrip("\n").split("\n")
    if done.returncode != 0 or len(lines) < 2 or lines[-1] != "YES":
        raise Refusal("cp_verify: exit %d, last line %r" % (done.returncode, lines[-1:]))
    result = lines[-2]
    if not result.startswith("result-v1 "):
        raise Refusal("cp_verify: no result-v1 line before YES")
    fields = dict(w.split("=", 1) for w in result.split(" ")[1:] if "=" in w)
    if fields.get("status") != "0":
        raise Refusal("cp_verify: status not 0")
    if fields.get("id") != m["commitment"]["id"]:
        raise Refusal("commitment.id: differs from cp_verify's id=")
    if fields.get("build") != m["verifier"]["build_digest"]:
        raise Refusal("verifier.build_digest: differs from cp_verify's build=")
    for name in POLICY_FIELDS:
        if fields.get(name) != str(m["decode_policy"][name]):
            raise Refusal("decode_policy.%s: differs from cp_verify's %s=" % (name, name))
    want_claim = "exact-match" if m["decode_policy"]["kind"] == "exact" else "clipped-gap"
    if fields.get("policy") != want_claim:
        raise Refusal("decode_policy.kind: cp_verify says policy=%s" % fields.get("policy"))
    return result


def verify(args):
    manifest_bytes = pathlib.Path(args.manifest).read_bytes()
    signature = pathlib.Path(args.signature).read_bytes()
    trusted = bytes.fromhex(pathlib.Path(args.signer_key).read_text().strip())
    m = load(manifest_bytes, signature, trusted)
    check_config(m, args.config)
    check_serving(m, args)
    check_recipe(m, args)
    return m, run_cp_verify(m, args)


# ---- CLI ----


def cmd_keygen(args):
    secret = os.urandom(32)
    fd = os.open(args.secret_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(secret.hex() + "\n")
    pathlib.Path(args.public_out).write_text(ed25519.public_key(secret).hex() + "\n")


def cmd_sign(args):
    m = json.loads(pathlib.Path(args.manifest_json).read_text())
    secret = bytes.fromhex(pathlib.Path(args.secret).read_text().strip())
    m["signer"]["public_key"] = ed25519.public_key(secret).hex()
    check_schema(m)
    data = canonical(m)
    pathlib.Path(args.out).write_bytes(data)
    pathlib.Path(args.out + ".sig").write_bytes(ed25519.sign(secret, signed_bytes(data)))


def add_verify_args(p):
    p.add_argument("manifest")
    p.add_argument("signature")
    p.add_argument("--signer-key", required=True, help="file: the signer's public key, hex, from a source you trust")
    p.add_argument("--config", required=True)
    p.add_argument("--ivk", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--y", required=True)
    p.add_argument("--proof", required=True)
    p.add_argument("--cp-verify", required=True)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--tokenizer-dir")
    p.add_argument("--no-tokenizer", action="store_true")
    p.add_argument("--chat-template")
    p.add_argument("--no-chat-template", action="store_true")
    p.add_argument("--system-prompt")
    p.add_argument("--no-system-prompt", action="store_true")
    p.add_argument("--end-tokens", help="required: comma list of end token ids, or none", type=lambda t: [int(x) for x in t.split(",") if x] if t != "none" else [])
    p.add_argument("--recipe", help="the conversion script; required unless --no-recipe")
    p.add_argument("--no-recipe", action="store_true",
                   help="do not rehash the recipe; conversion.script_sha256 is then the signer's word")
    p.add_argument("--committed-dir")
    p.add_argument("--upstream-dir")
    p.add_argument("--public-weights-seed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("secret_out")
    k.add_argument("public_out")
    s = sub.add_parser("sign")
    s.add_argument("manifest_json")
    s.add_argument("secret")
    s.add_argument("out")
    v = sub.add_parser("verify")
    add_verify_args(v)
    args = parser.parse_args(argv)
    if args.cmd == "keygen":
        cmd_keygen(args)
        return 0
    if args.cmd == "sign":
        cmd_sign(args)
        return 0
    try:
        m, result = verify(args)
    except Refusal as r:
        print("manifest: REFUSED: %s" % r)
        return 1
    print(result)
    print("manifest: ACCEPTED id=%s signer=%s" % (m["commitment"]["id"], m["signer"]["name"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
