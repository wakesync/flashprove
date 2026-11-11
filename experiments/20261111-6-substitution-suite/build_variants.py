#!/usr/bin/env python3
"""Builds the programs that suite.py runs, besides bin/cp_verify (verifier/build.sh builds that one).

- bin/subst6/dom1/cp_verify: cp_verify with LABEL_FIRST_CHAIN 0x46524d01 -> 0x46524d00 (C-DOM1).
- bin/subst6/dom2/cp_verify: cp_verify with LABEL_ONE_TIME_CHAIN, LABEL_PROOF_SHARED_CHAIN and
  LABEL_PROOF_SECOND_CHAIN each + 0x10 (C-DOM2). The label order that blocks/frame/configure.h
  asserts is kept.
- bin/subst6/handoff.bin: research/operators/qwen_handoff/handoff.cpp, unchanged, with the flags of
  that directory's run.py.
- bin/subst6/handoff_fp94.bin: the same source with its transcript domain bytes 'F','P','9','3'
  replaced by 'F','P','9','4' (H-DOM1, H-DOM2).

Changed sources are overlay copies under bin/subst6/overlay/; the tracked sources are never written.
The cp_verify variants use verifier/build.sh's compiler flags (copied here) with the overlay
directory first on the include path. Writes runs/build.json (refuses to overwrite).

Usage: python3 experiments/20261111-6-substitution-suite/build_variants.py
"""
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "bin" / "subst6"
OVL = OUT / "overlay"

HARDEN = ["-D_GLIBCXX_ASSERTIONS", "-U_FORTIFY_SOURCE", "-D_FORTIFY_SOURCE=3", "-fstack-protector-strong",
          "-fstack-clash-protection", "-ftrivial-auto-var-init=zero", "-fPIE", "-pie",
          "-Wl,-z,relro,-z,now,-z,noexecstack"]
if platform.machine() == "x86_64":
    HARDEN.append("-fcf-protection=full")
HANDOFF_FLAGS = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-fno-ipa-modref", "-DBLK_FIELD=2", "-DBLK_HASH=1"]


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def overlay_heads(name, replacements):
    src = ROOT / "blocks/frame/heads.h"
    text = src.read_text()
    for old, new in replacements:
        if text.count(old) != 1:
            raise RuntimeError("insertion point changed: " + old)
        text = text.replace(old, new)
    d = OVL / name / "frame"
    d.mkdir(parents=True, exist_ok=True)
    (d / "heads.h").write_text(text)
    return OVL / name, hashlib.sha256(text.encode()).hexdigest()


def build_cpv(name, replacements):
    inc, digest = overlay_heads(name, replacements)
    outdir = OUT / name
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = (["g++", "-O2", "-fno-ipa-modref"] + HARDEN +
           ["-std=c++17", "-Wall", "-Wextra", "-Wuninitialized", "-Werror=unused-result", "-Wno-misleading-indentation",
            "-pthread", "-I" + str(inc), "-I.", "-I../../blocks", "-I../../prover", "-DBLK_FIELD=2",
            "-DBLK_COUNT_HASH_CALLS=1", "-DSERVING_BUILD=1", "-DDIGEST_WORDS=8",
            '-DVF_SOURCE_DIGEST="' + digest + '"', "-o", str(outdir / "cp_verify"), "cp_verify.cpp"])
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT / "verifier/src", capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-4000:])
    return {"binary": "bin/subst6/%s/cp_verify" % name, "binary_sha256": sha(outdir / "cp_verify"),
            "overlay_heads_sha256": digest, "replacements": replacements, "seconds": round(time.time() - t0, 1),
            "flags": [c.replace(str(ROOT), "<repo>") for c in cmd[:-3]]}


def build_handoff(name, fp94):
    src = ROOT / "research/operators/qwen_handoff/handoff.cpp"
    text = src.read_text()
    if fp94:
        old = "std::vector<u8> hdr={'F','P','9','3'};"
        if text.count(old) != 1:
            raise RuntimeError("handoff domain insertion point changed")
        text = text.replace(old, "std::vector<u8> hdr={'F','P','9','4'};")
    d = OVL / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "handoff.cpp").write_text(text)
    out = OUT / (name + ".bin")
    cmd = ["g++"] + HANDOFF_FLAGS + ["-I", "blocks", "-I", "research/operators/qwen_handoff",
                                     str(d / "handoff.cpp"), "-o", str(out)]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-4000:])
    return {"binary": "bin/subst6/%s.bin" % name, "binary_sha256": sha(out),
            "source_sha256": hashlib.sha256(text.encode()).hexdigest(), "seconds": round(time.time() - t0, 1),
            "flags": HANDOFF_FLAGS + ["-I", "blocks", "-I", "research/operators/qwen_handoff"]}


def main():
    rec = ROOT / "experiments/20261111-6-substitution-suite/runs/build.json"
    if rec.exists():
        print("refusing to overwrite " + str(rec.relative_to(ROOT)))
        return 2
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc = {"started_utc": started, "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
           "affinity": sorted(os.sched_getaffinity(0)), "builds": {}}
    doc["builds"]["cp_verify"] = {"binary": "bin/cp_verify", "binary_sha256": sha(ROOT / "bin/cp_verify"),
                                  "note": "built by verifier/build.sh before this script"}
    doc["builds"]["handoff"] = build_handoff("handoff", False)
    doc["builds"]["handoff_fp94"] = build_handoff("handoff_fp94", True)
    doc["builds"]["dom1"] = build_cpv("dom1", [("LABEL_FIRST_CHAIN = 0x46524d01", "LABEL_FIRST_CHAIN = 0x46524d00")])
    doc["builds"]["dom2"] = build_cpv("dom2", [("LABEL_ONE_TIME_CHAIN = 0x46524d02", "LABEL_ONE_TIME_CHAIN = 0x46524d12"),
                                               ("LABEL_PROOF_SHARED_CHAIN = 0x46524d03", "LABEL_PROOF_SHARED_CHAIN = 0x46524d13"),
                                               ("LABEL_PROOF_SECOND_CHAIN = 0x46524d04", "LABEL_PROOF_SECOND_CHAIN = 0x46524d14")])
    doc["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec.parent.mkdir(parents=True, exist_ok=True)
    with open(rec, "x") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({k: v["binary_sha256"] for k, v in doc["builds"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
