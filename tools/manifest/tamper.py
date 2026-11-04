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


# ---- coordinated, schema-valid alternates re-signed by the trusted key (amendment 2) ----

# Single-field mutations of these fields are refused by the schema (a nonsense value), which said
# nothing about whether a VALID alternate is caught. coordinated() gives each one a schema-valid
# alternate. Fields listed under "covers" are what each alternate tests.
FAKE_HF_FILES = ("config.json", "model-00001-of-00001.safetensors")


def coordinated(m, tmp):
    """Yield (name, covers, manifest, flag_overrides) for schema-valid trusted re-signs.

    flag_overrides is what a caller passes to check the changed field against its own files
    (None when no flag can check it on CPU). Every alternate passes check_schema.
    """
    tmp = pathlib.Path(tmp)
    seed = tmp / "client-public-weights-seed.bin"  # stand-in: the seed file a caller holds
    seed.write_bytes(b"client seed file stand-in\n")
    up = tmp / "client-upstream"  # stand-in: what a caller downloaded from the named repo
    up.mkdir(exist_ok=True)
    for n in FAKE_HF_FILES:
        (up / n).write_bytes(b"caller's download of " + n.encode() + b"\n")
    committed = tmp / "client-committed"  # the honest committed set of this fixture is empty
    committed.mkdir(exist_ok=True)

    a = copy.deepcopy(m)
    a["commitment"]["kind"] = "public-weights"
    a["conversion"]["public_weights_seed_sha256"] = "5e" * 32
    yield ("kind hiding->public-weights + made-up seed digest",
           ["commitment.kind", "conversion.public_weights_seed_sha256"], a,
           {"--public-weights-seed": str(seed)})

    b = copy.deepcopy(m)
    b["upstream"] = {"kind": "huggingface", "repo": "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
                     "revision": "0" * 40,
                     "files": [{"path": n, "sha256": "%02x" % i * 32}
                               for i, n in enumerate(FAKE_HF_FILES, 1)]}
    b["conversion"]["committed_files"] = [{"path": "weights.bin", "sha256": "c0" * 32}]
    yield ("upstream synthetic->full fake huggingface + made-up committed_files",
           ["upstream.kind", "conversion.committed_files"], b,
           {"--upstream-dir": str(up), "--committed-dir": str(committed)})

    b2 = copy.deepcopy(b)
    yield ("same, caller passes --upstream-dir only", ["upstream.kind"], b2,
           {"--upstream-dir": str(up)})

    c = copy.deepcopy(m)
    c["conversion"]["committed_files"] = [{"path": "weights.bin", "sha256": "c0" * 32}]
    yield ("committed_files []->one made-up entry (synthetic upstream)",
           ["conversion.committed_files"], c, {"--committed-dir": str(committed)})

    for field in ("C", "theta", "cap", "sT"):
        d = copy.deepcopy(m)
        d["decode_policy"][field] += 1
        d["decode_policy"]["kind"] = "clipped-gap"
        yield ("decode_policy.%s+1 with kind clipped-gap" % field,
               ["decode_policy.%s" % field], d, None)
    e = copy.deepcopy(m)
    e["decode_policy"].update({"kind": "clipped-gap", "cap": 1})
    yield ("decode_policy.kind exact->clipped-gap with cap 1", ["decode_policy.kind"], e, None)

    for field in ("chat_template", "system_prompt"):
        f = copy.deepcopy(m)
        f["serving"][field] = {"none": True}
        yield ("serving.%s digest->none" % field, ["serving.%s" % field], f, None)
    g = copy.deepcopy(m)
    g["serving"]["tokenizer"] = {"none": True}
    yield ("serving.tokenizer files->none", ["serving.tokenizer"], g, None)
