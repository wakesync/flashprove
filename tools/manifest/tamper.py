# SPDX-License-Identifier: Apache-2.0
"""Fixture and tamper enumeration for manifest.py, shared by test_manifest.py and the experiment.

The fixture is the stored example examples/accepted-proof (synthetic weights, hiding commitment,
exact match), with a manifest that tells the truth about it. That example has a synthetic
vocabulary and no tokenizer, so the serving fields point at small fixture files written here
(a tokenizer.json, a chat template, a system prompt): they test the binding, not a real model.
"""

import copy
import json
import pathlib
import re
import shutil
import subprocess

import ed25519
import manifest as mf

REPO = pathlib.Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "examples" / "accepted-proof"
CP_VERIFY = REPO / "bin" / "cp_verify"
TRUSTED_SECRET = bytes(range(32))  # test key only
ATTACKER_SECRET = bytes(range(32, 64))  # test key only


def build_digest():
    """The build= that the local cp_verify prints for the stored example."""
    out = subprocess.run(
        [str(CP_VERIFY), "config", "ivk", "example.req", "example.y", "example.proof",
         "-id", (EXAMPLE / "ID.txt").read_text().strip(), "-q"],
        cwd=EXAMPLE, capture_output=True, text=True, timeout=600,
    ).stdout
    return re.search(r" build=([0-9a-f]{64})", out).group(1)


def make_fixture(tmp, build):
    tmp = pathlib.Path(tmp)
    (tmp / "tokenizer").mkdir()
    (tmp / "tokenizer" / "tokenizer.json").write_text('{"model":{"type":"WordLevel","vocab_size":512}}\n')
    (tmp / "tokenizer" / "tokenizer_config.json").write_text('{"eos_token_id":null}\n')
    (tmp / "chat_template.jinja").write_text("{% for m in messages %}{{ m.content }}{% endfor %}\n")
    (tmp / "system_prompt.txt").write_text("You are a test fixture.\n")
    recipe = REPO / "prover" / "examples" / "run_target_example.sh"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()
    tok = sorted(p.name for p in (tmp / "tokenizer").iterdir())
    m = {
        "format": mf.FORMAT,
        "commitment": {"id": (EXAMPLE / "ID.txt").read_text().strip(), "kind": "hiding"},
        "upstream": {"kind": "synthetic", "generator": "made-up-blocks", "seed": 31},
        "conversion": {
            "script": "prover/examples/run_target_example.sh",
            "script_sha256": mf.sha256_file(recipe),
            "repo_commit": head,
            "version": "cp_commit serving build, configuration target_small_f2_roomy",
            "params": {"config": "prover/examples/target_small_f2_roomy", "M": 1,
                       "weights": "made-up-blocks"},
            "committed_files": [],
            "public_weights_seed_sha256": None,
        },
        "configuration": {n: mf.sha256_file(EXAMPLE / "config" / n) for n in mf.CONFIG_FILES},
        "serving": {
            "tokenizer": {"files": [{"path": n, "sha256": mf.sha256_file(tmp / "tokenizer" / n)}
                                    for n in tok]},
            "chat_template": {"sha256": mf.sha256_file(tmp / "chat_template.jinja")},
            "system_prompt": {"sha256": mf.sha256_file(tmp / "system_prompt.txt")},
            "end_tokens": [],
        },
        "decode_policy": {"kind": "exact", "C": 256, "theta": 256, "cap": 0, "s": 16, "sh": 8,
                          "sT": 4, "F": 24},
        "verifier": {"build_digest": build, "source_commit": head},
        "signer": {"name": "test signer (fixture key)",
                   "public_key": ed25519.public_key(TRUSTED_SECRET).hex()},
    }
    (tmp / "trusted.pub").write_text(ed25519.public_key(TRUSTED_SECRET).hex() + "\n")
    return m, recipe


def write_signed(tmp, m, secret=TRUSTED_SECRET, name="manifest.json"):
    data = mf.canonical(m)
    p = pathlib.Path(tmp) / name
    p.write_bytes(data)
    (pathlib.Path(tmp) / (name + ".sig")).write_bytes(ed25519.sign(secret, mf.signed_bytes(data)))
    return p, pathlib.Path(tmp) / (name + ".sig")


def verify_argv(tmp, manifest_path, sig_path, recipe, overrides=None):
    tmp = pathlib.Path(tmp)
    o = {
        "--signer-key": str(tmp / "trusted.pub"),
        "--config": str(EXAMPLE / "config"),
        "--ivk": str(EXAMPLE / "ivk"),
        "--request": str(EXAMPLE / "example.req"),
        "--y": str(EXAMPLE / "example.y"),
        "--proof": str(EXAMPLE / "example.proof"),
        "--cp-verify": str(CP_VERIFY),
        "--tokenizer-dir": str(tmp / "tokenizer"),
        "--chat-template": str(tmp / "chat_template.jinja"),
        "--system-prompt": str(tmp / "system_prompt.txt"),
        "--end-tokens": "none",
        "--recipe": str(recipe),
    }
    o.update(overrides or {})
    argv = ["verify", str(manifest_path), str(sig_path)]
    for k, v in o.items():
        if v is None:
            continue
        argv += [k] if v is True else [k, v]
    return argv


def leaves(obj, path=()):
    """Every leaf (and every empty container) of the manifest, as a JSON path."""
    if isinstance(obj, dict) and obj:
        for k in sorted(obj):
            yield from leaves(obj[k], path + (k,))
    elif isinstance(obj, list) and obj:
        for i, v in enumerate(obj):
            yield from leaves(v, path + (i,))
    else:
        yield path


def mutate_value(v):
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return v + 1
    if v is None:
        return "0" * 64
    if isinstance(v, str):
        if re.fullmatch(r"[0-9a-f]+", v):
            return ("1" if v[-1] != "1" else "2").join([v[:-1], ""])
        return v + "x"
    if isinstance(v, list):
        return [0]
    if isinstance(v, dict):
        return {"x": 1}
    raise TypeError(v)


def mutated(m, path):
    m2 = copy.deepcopy(m)
    cur = m2
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = mutate_value(cur[path[-1]])
    return m2


def path_name(path):
    return ".".join(str(p) for p in path)


def copy_example(tmp):
    d = pathlib.Path(tmp) / "example-copy"
    shutil.copytree(EXAMPLE, d)
    return d


def flip_byte(path, offset=None):
    data = bytearray(pathlib.Path(path).read_bytes())
    i = len(data) // 2 if offset is None else offset
    data[i] ^= 0x01
    pathlib.Path(path).write_bytes(bytes(data))


def dump(obj):
    return json.dumps(obj, indent=1, sort_keys=True)
