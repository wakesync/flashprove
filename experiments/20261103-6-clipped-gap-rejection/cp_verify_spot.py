#!/usr/bin/env python3
# cp_verify spot checks for the clipped-gap rejection study (PREREG.md). CPU only: no new proof can be
# made without the GPU prover, so every call uses the stored honest proof of
# examples/accepted-proof-clipped-gap. Two labeled kinds of call:
#   binding-spot-check: the stored proof with an attacked reply (one per attack class). A NO here shows
#       that the proof is bound to the reply it was made for. It is NOT a rejection by the policy's limits.
#   policy-named: the stored honest files with -policy naming a tighter (C, theta, cap). A NO here shows
#       that cp_verify refuses a policy other than the one the commitment fixed. It is NOT a rejection
#       by the limits either.
# Plus the control: the stored files as they are, with the shipped policy (must be WITHIN LIMITS).
#
# usage: cp_verify_spot.py REPO OUT.json
import json
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

repo, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
ex = repo / "examples" / "accepted-proof-clipped-gap"
reply_json = json.loads((repo / "prover/examples/target_small_f2_gap/reply.json").read_text())
other_json = json.loads((repo / "prover/examples/target_small_f2_gap/other_prompt.json").read_text())
ID = (ex / "ID.txt").read_text().strip()
SHIPPED = "clipped-gap,9244130,323343,1,16,8"
T, V = 64, 512
END = V - 1


def request_bytes(prompt, reply):
    """As in prover/examples/target_small_f2_gap/README.md, request(): prompt, reply, zeros to T, r, e."""
    assert prompt and reply and len(prompt) + len(reply) <= T + 1
    return struct.pack("<%dI" % (T + 2), *(prompt + reply + [0] * T)[:T], len(prompt) - 1, len(prompt) + len(reply) - 1)


assert request_bytes(reply_json["prompt_token_ids"], reply_json["reply_token_ids"]) == (ex / "example.req").read_bytes(), \
    "request builder does not reproduce the stored example.req"


def call(req: bytes, policy: str):
    with tempfile.TemporaryDirectory() as d:
        r = Path(d) / "x.req"
        r.write_bytes(req)
        p = subprocess.run([str(repo / "bin/cp_verify"), str(ex / "config"), str(ex / "ivk"), str(r), str(ex / "example.y"),
                            str(ex / "example.proof"), "-id", ID, "-policy", policy, "-q"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
    last = [l for l in p.stdout.splitlines() if l.strip()][-1] if p.stdout.strip() else ""
    return {"exit": p.returncode, "last_line": last}


p0, r0 = reply_json["prompt_token_ids"], reply_json["reply_token_ids"]
rng = random.Random(20261103)
rows = []


def swapped(k, kind):
    r = list(r0)
    for j in rng.sample(range(len(r)), k):
        r[j] = rng.choice([x for x in range(END) if x != r[j]]) if kind == "rand" else (r[j] + 1) % END
    return r


rows.append(dict(kind="control", cls="honest (stored files)", policy=SHIPPED, **call(request_bytes(p0, r0), SHIPPED)))
attacked = {
    "rand-1": (p0, swapped(1, "rand")),
    "rand-4": (p0, swapped(4, "rand")),
    "rand-16": (p0, swapped(16, "rand")),
    "rand-reply": (p0, [rng.randrange(END) for _ in r0]),
    "other-prompt (stored other_prompt.json)": (other_json["prompt_token_ids"], other_json["reply_token_ids"]),
    "trunc-half": (p0, r0[: len(r0) // 2]),
    "trunc-1": (p0, r0[:-1]),
}
for name, (p, r) in attacked.items():
    rows.append(dict(kind="binding-spot-check", cls=name, policy=SHIPPED, **call(request_bytes(p, r), SHIPPED)))
for pol in ("clipped-gap,9244130,100000,1,16,8", "clipped-gap,9244130,323343,0,16,8", "clipped-gap,500000,50000,0,16,8",
            "exact-match,256,256,0,16,8"):
    rows.append(dict(kind="policy-named", cls="honest (stored files)", policy=pol, **call(request_bytes(p0, r0), pol)))
ver = subprocess.run([str(repo / "bin/cp_verify"), str(ex / "config"), str(ex / "ivk"), str(ex / "example.req"), str(ex / "example.y"),
                      str(ex / "example.proof"), "-id", ID, "-policy", SHIPPED], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
build = [w for l in ver.stdout.splitlines() if l.startswith("result-v1") for w in l.split() if w.startswith("build=")]
out.write_text(json.dumps({"cp_verify_build": build[0] if build else None, "id": ID, "rows": rows}, indent=1) + "\n")
for row in rows:
    print("%-20s %-40s %-36s exit %d  %s" % (row["kind"], row["cls"], row["policy"], row["exit"], row["last_line"][:80]))
