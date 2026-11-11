#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write the client envelope test vectors (SPEC.md section 7) into a directory.

  make_vectors.py --out research/envelope/vectors --label registered --build <cp_verify build>
  make_vectors.py --out <tmp dir> --label debug --build <digest>      (debug set: other keys,
                                                                       nonces and session)

Each vector is a directory with context.json (the client's pins), state.json (the client's state
before the step), and steps.json: a list of deliveries, each naming its envelope file, reply file,
proof source (a stored example and a transform), the outstanding nonce it is delivered for, the
client clock and the expected last line. Envelope files are raw bytes on purpose: some vectors are
not canonical. The proof bytes are never stored; they are the stored examples, unchanged or cut by
the named transform, so that no altered proof lives in the repository.

The signing keys are TEST keys derived from a public label. They authenticate nothing outside these
tests. Signing uses tools/manifest/ed25519.py (not constant time; fine for public test keys).
"""

import argparse
import copy
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(REPO / "tools" / "manifest"))

import ed25519  # noqa: E402
import envelope as E  # noqa: E402

T0 = 1793000000  # issued_at of every honest envelope (2026-10-26, a fixed test clock)
NOW = T0 + 10
LIFETIME = 300

EXAMPLES = {
    "exact": {"dir": "examples/accepted-proof", "policy": {"kind": "exact", "bits": 128, "C": 256,
              "theta": 256, "cap": 0, "s": 16, "sh": 8, "sT": 4, "F": 24},
              "end_tokens": [199]},
    "clipped": {"dir": "examples/accepted-proof-clipped-gap",
                "policy": {"kind": "clipped-gap", "bits": 128, "C": 9244130, "theta": 323343,
                           "cap": 1, "s": 16, "sh": 8, "sT": 4, "F": 24},
                "end_tokens": [511]},
}


def secret(label, who):
    return hashlib.sha256(("flashprove-envelope-v1 TEST key %s %s" % (who, label)).encode()).digest()


def nonce(label, name):
    return hashlib.sha256(("flashprove-envelope-v1 TEST nonce %s %s" % (label, name)).encode()).hexdigest()


def tag(label, what):
    return hashlib.sha256(("flashprove-envelope-v1 TEST %s %s" % (what, label)).encode()).hexdigest()


class Fixture:
    def __init__(self, name, label):
        info = EXAMPLES[name]
        d = REPO / info["dir"]
        self.name = name
        self.dir = info["dir"]
        self.id = (d / "ID.txt").read_text().strip()
        words = E.bytes_tokens((d / "example.req").read_bytes())
        self.r, self.e = words[-2], words[-1]
        tokens = words[:-2]
        y = E.bytes_tokens((d / "example.y").read_bytes())[0]
        self.prompt = tokens[: self.r + 1]
        self.reply = tokens[self.r + 1:] + [y]
        self.T = len(tokens)
        self.max_tokens = len(self.reply)
        req_bytes, y_bytes, _ = E.request_file(self.prompt, self.reply, self.r, self.e)
        assert req_bytes == (d / "example.req").read_bytes(), "request rebuild differs"
        assert y_bytes == (d / "example.y").read_bytes(), "y rebuild differs"
        self.proof = (d / "example.proof").read_bytes()
        self.config = E.config_digests(d / "config")
        self.policy = info["policy"]
        self.end_tokens = info["end_tokens"]
        self.finish = "end" if self.reply[-1] in self.end_tokens else "length"
        self.versions = {"tokenizer_sha256": tag(label, "tokenizer of the synthetic model"),
                         "chat_template_sha256": tag(label, "chat template (none: token ids)"),
                         "operator_set": "flashprove-cp-target-small-f2"}
        self.provenance = tag(label, "provenance record %s" % name)

    def pin(self):
        return {"config": self.dir + "/config", "ivk": self.dir + "/ivk",
                "config_sha256": self.config, "provenance_ref": self.provenance,
                "versions": self.versions, "policy": self.policy, "end_tokens": self.end_tokens}


class Gen:
    def __init__(self, label, build):
        self.label = label
        self.build = build
        self.sk = secret(label, "provider")
        self.pk = ed25519.public_key(self.sk).hex()
        self.attacker = secret(label, "attacker")
        self.session = "session-" + label
        self.fx = {n: Fixture(n, label) for n in EXAMPLES}

    def context(self, **over):
        ctx = {"version": E.CONTEXT_VERSION, "provider_key": self.pk, "verifier_build": self.build,
               "min_bits": 128, "max_lifetime_s": 600, "max_skew_s": 60, "require_tee": 0,
               "models": {f.id: f.pin() for f in self.fx.values()}}
        ctx.update(over)
        return ctx

    def body(self, fx, rec, n):
        reply_bytes = E.tokens_bytes(fx.reply)
        return {
            "version": E.VERSION, "sig_alg": "ed25519", "provider_key": self.pk,
            "request": {"session": self.session, "nonce": n, "digest": rec["request_digest"]},
            "state": {"seq": rec["seq"], "prev": rec["prev"]},
            "issued_at": T0, "expires_at": T0 + LIFETIME,
            "model": {"commitment_id": fx.id, "provenance_ref": fx.provenance,
                      "label": "synthetic target_small_f2 (%s)" % fx.name},
            "versions": dict(fx.versions, config_sha256=fx.config, verifier_build=self.build),
            "policy": dict(fx.policy),
            "io": {"prompt_sha256": E.sha256_hex(E.tokens_bytes(fx.prompt)),
                   "reply_sha256": E.sha256_hex(reply_bytes), "reply_tokens": len(fx.reply),
                   "finish": fx.finish,
                   "end_token": fx.reply[-1] if fx.finish == "end" else None},
            "coverage": {"r": fx.r, "e": fx.e, "T": fx.T, "y": "yes" if fx.e == fx.T else "no"},
            "proof": {"system": "cp_verify/result-v1", "sha256": E.sha256_hex(fx.proof),
                      "bytes": len(fx.proof)},
            "attestation": {"kind": "none", "evidence": None},
        }

    def seal(self, body, key=None):
        sig = ed25519.sign(key or self.sk, E.signed_message(body)).hex()
        return E.canonical({"body": body, "sig": sig})

    def state(self):
        return E.new_state(self.session)

    def issue(self, state, name, fx="exact"):
        f = self.fx[fx]
        n = nonce(self.label, name)
        rec = E.issue(state, n, f.id, f.prompt, f.e, f.max_tokens)
        return n, copy.deepcopy(rec)


def step(env, reply, n, proof="exact", transform="none", now=NOW, expect="RELEASE",
         reply_tokens=None):
    return {"envelope": env, "reply": reply, "reply_tokens": reply_tokens, "deliver": n,
            "proof": {"example": proof, "transform": transform}, "now": now, "expect": expect}


def build_vectors(g):
    V = {}
    ex, cg = g.fx["exact"], g.fx["clipped"]

    def one(name, mutate=None, expect="RELEASE", fx="exact", proof=None, transform="none",
            now=NOW, raw=None, ctx=None, reply=None, key=None, kind="reject", desc=""):
        st = g.state()
        n, rec = g.issue(st, name, fx)
        body = g.body(g.fx[fx], rec, n)
        if mutate:
            mutate(body)
        env = g.seal(body, key)
        if raw:
            env = raw(env, body)
        V[name] = {"kind": kind, "description": desc, "context": ctx or g.context(), "state": st,
                   "files": {"env1": env},
                   "steps": [step("env1", reply or g.fx[fx].reply, n, proof or fx, transform, now,
                                  expect)]}

    # ---- accept
    one("A1", kind="accept", desc="honest exact example, fresh session, seq 1")
    one("A2", fx="clipped", kind="accept",
        desc="honest clipped-gap example; client pins the clipped-gap policy and limits")
    st = g.state()
    na, ra = g.issue(st, "A3-a", "exact")
    nb, rb = g.issue(st, "A3-b", "clipped")
    V["A3"] = {"kind": "accept", "description": "two outstanding requests (exact as seq 1, "
               "clipped as seq 2); responses in reverse order, each released to its own slot",
               "context": g.context(), "state": st,
               "files": {"env1": g.seal(g.body(cg, rb, nb)), "env2": g.seal(g.body(ex, ra, na))},
               "steps": [step("env1", cg.reply, nb, "clipped"), step("env2", ex.reply, na)]}
    one("A4", mutate=lambda b: b["model"].__setitem__("label", "meta-llama/Llama-3.1-8B-Instruct"),
        kind="accept", desc="display label names a well-known checkpoint; released, provenance "
        "is the client pin, the label is display text only")
    one("A6", lambda b: b.__setitem__("attestation", {"kind": "MOCK",
                                                      "evidence": "MOCK: not evidence"}),
        kind="accept", desc="honest envelope with a MOCK attestation block; released on signature "
        "and proof, the tee line says MOCK (not evidence)")
    # A5: after A1 was released, the provider re-wraps the unchanged proof under a new nonce.
    st = g.state()
    n1, r1 = g.issue(st, "A5-first")
    env_first = g.seal(g.body(ex, r1, n1))
    E.release(st, n1, env_first)
    n5, r5 = g.issue(st, "A5-second")
    V["A5"] = {"kind": "expected-accept-gap", "description": "unchanged proof of an earlier "
               "release re-wrapped under a new nonce and seq for the same prompt, re-signed. "
               "Released: the proof relation binds no nonce (gap G-05); freshness rests on the "
               "provider signature and the client state only",
               "context": g.context(), "state": st,
               "files": {"env1": g.seal(g.body(ex, r5, n5))},
               "steps": [step("env1", ex.reply, n5)]}

    # ---- substitution
    def sub1(b):
        b["proof"] = {"system": "cp_verify/result-v1", "sha256": E.sha256_hex(cg.proof),
                      "bytes": len(cg.proof)}
    one("SUB1", sub1, "REJECT: proof", proof="clipped",
        desc="clipped-gap proof in the exact envelope, digest updated, re-signed")
    one("SUB2", lambda b: b["model"].__setitem__("commitment_id", cg.id), "REJECT: commitment-pin",
        desc="commitment ID other than the client pin")

    def sub3(b):
        b["model"] = {"commitment_id": cg.id, "provenance_ref": cg.provenance,
                      "label": "synthetic target_small_f2 (clipped)"}
        b["versions"]["config_sha256"] = cg.config
        b["policy"] = dict(cg.policy)
        b["coverage"] = {"r": cg.r, "e": cg.e, "T": cg.T, "y": "no"}
        b["proof"] = {"system": "cp_verify/result-v1", "sha256": E.sha256_hex(cg.proof),
                      "bytes": len(cg.proof)}
    one("SUB3", sub3, "REJECT: commitment-pin", proof="clipped",
        desc="the whole clipped-gap package (ID, config, policy, coverage, proof) answering an "
        "exact request")
    sub4_reply = ex.reply[:-1] + [200]

    def sub4(b):
        b["io"].update({"reply_sha256": E.sha256_hex(E.tokens_bytes(sub4_reply)),
                        "finish": "length", "end_token": None})
    one("SUB4", sub4, "REJECT: proof", reply=sub4_reply,
        desc="reply token y changed 199 to 200, reply digest updated, re-signed (finish=length "
        "so that the end-token check passes and the proof decides)")
    one("SUB5", lambda b: b["versions"].__setitem__("config_sha256", cg.config),
        "REJECT: config-pin", desc="configuration digests of the other example")
    one("SUB6", lambda b: b["model"].__setitem__("provenance_ref", cg.provenance),
        "REJECT: provenance-pin", desc="provenance reference other than the client pin")
    one("SUB7", lambda b: b["versions"].__setitem__("tokenizer_sha256", tag(g.label, "other tok")),
        "REJECT: version-pin", desc="tokenizer digest other than the client pin")

    # ---- signature
    def sig1(env, body):
        other = nonce(g.label, "SIG1-edited")
        return env.replace(body["request"]["nonce"].encode(), other.encode())
    one("SIG1", raw=sig1, expect="REJECT: signature", desc="nonce edited after signing")
    one("SIG2", lambda b: b.__setitem__("provider_key", ed25519.public_key(g.attacker).hex()),
        "REJECT: signature", key=g.attacker, desc="signed by an attacker key")

    # ---- duplicate / unknown / non-canonical
    def dup1(env, body):
        s = '"session":"%s"' % body["request"]["session"]
        return env.replace(s.encode(), (s + ',"session":"%s"' % body["request"]["session"]).encode())
    one("DUP1", raw=dup1, expect="REJECT: canonical",
        desc="duplicate key inside request (same value), bytes signed as sent")

    def dup2(env, body):
        assert env.endswith(b"}")
        return env[:-1] + (',"sig":"%s"}' % json.loads(env)["sig"]).encode()
    one("DUP2", raw=dup2, expect="REJECT: canonical", desc="duplicate top-level key")
    one("UNK1", lambda b: b.__setitem__("debug", 1), "REJECT: schema",
        desc="unknown top-level body field, re-signed")
    one("UNK2", lambda b: b["coverage"].__setitem__("positions", 4), "REJECT: schema",
        desc="unknown field inside coverage, re-signed")

    def nc1(env, body):
        obj = {"sig": json.loads(env)["sig"], "body": body}  # insertion order: not sorted
        return json.dumps(obj, indent=1).encode()
    one("NC1", raw=nc1, expect="REJECT: canonical",
        desc="same content, other whitespace, valid signature of the canonical body")

    # ---- downgrade
    one("DWN1", lambda b: b.__setitem__("version", "flashprove-envelope-v0"), "REJECT: version",
        desc="version flashprove-envelope-v0")
    one("DWN2", lambda b: b["policy"].__setitem__("kind", "clipped-gap"), "REJECT: policy-pin",
        desc="envelope says clipped-gap where the client pins exact")
    one("DWN3", lambda b: b["policy"].__setitem__("bits", 96), "REJECT: policy-pin",
        desc="proof bits 96 where the client pins 128")
    one("DWN4", lambda b: b.__setitem__("attestation", {"kind": "hardware-tee",
                                                        "evidence": "TEST not evidence"}),
        "REJECT: attestation", desc="attestation kind claims a hardware TEE")
    one("DWN5", lambda b: b.__setitem__("sig_alg", "none"), "REJECT: schema",
        desc="signature algorithm none")

    # ---- replay
    st = g.state()
    na, ra = g.issue(st, "RPL1-a")
    nb, rb = g.issue(st, "RPL1-b")
    V["RPL1"] = {"kind": "reject", "description": "envelope for outstanding request A delivered "
                 "for outstanding request B", "context": g.context(), "state": st,
                 "files": {"env1": g.seal(g.body(ex, ra, na))},
                 "steps": [step("env1", ex.reply, nb, expect="REJECT: nonce")]}
    st = g.state()
    n1, r1 = g.issue(st, "RPL2-first")
    env_first = g.seal(g.body(ex, r1, n1))
    E.release(st, n1, env_first)
    g.issue(st, "RPL2-second")
    V["RPL2"] = {"kind": "reject", "description": "the released envelope delivered again for its "
                 "own (consumed) nonce", "context": g.context(), "state": st,
                 "files": {"env1": env_first},
                 "steps": [step("env1", ex.reply, n1, expect="REJECT: nonce-consumed")]}
    st = g.state()
    na, ra = g.issue(st, "RPL3-a")
    nb, rb = g.issue(st, "RPL3-b", "clipped")
    b = g.body(ex, ra, na)
    b["request"]["digest"] = rb["request_digest"]
    V["RPL3"] = {"kind": "reject", "description": "current nonce, request digest of another "
                 "request", "context": g.context(), "state": st, "files": {"env1": g.seal(b)},
                 "steps": [step("env1", ex.reply, na, expect="REJECT: request-digest")]}

    # ---- truncation
    one("TRN1", raw=lambda env, body: env[:-10], expect="REJECT: canonical",
        desc="envelope bytes cut by 10")
    one("TRN2", lambda b: b["coverage"].__setitem__("e", 63), "REJECT: coverage",
        desc="covered range e = 63 where the client asked e = 64, re-signed")
    one("TRN3", expect="REJECT: proof-digest", transform="cut1",
        desc="proof file cut by one byte, envelope digest honest")

    def trn4(b):
        b["proof"] = {"system": "cp_verify/result-v1", "sha256": E.sha256_hex(ex.proof[:-1]),
                      "bytes": len(ex.proof) - 1}
    one("TRN4", trn4, "REJECT: proof", transform="cut1",
        desc="proof cut by one byte, digest updated, re-signed")

    # ---- state rollback
    for name, mut, desc in (
            ("STA1", lambda b, r1e: b["state"].__setitem__("seq", 1),
             "seq equal to the last released seq"),
            ("STA2", lambda b, r1e: b["state"].__setitem__("prev", E.genesis(g.session)),
             "prev is not the last released envelope's digest (genesis instead)")):
        st = g.state()
        n1, r1 = g.issue(st, name + "-first")
        E.release(st, n1, g.seal(g.body(ex, r1, n1)))
        n2, r2 = g.issue(st, name + "-second")
        b = g.body(ex, r2, n2)
        mut(b, None)
        V[name] = {"kind": "reject", "description": desc, "context": g.context(), "state": st,
                   "files": {"env1": g.seal(b)},
                   "steps": [step("env1", ex.reply, n2, expect="REJECT: state")]}

    # ---- end token
    ctx = g.context()
    ctx["models"][ex.id]["end_tokens"] = [5]
    one("END1", expect="REJECT: end-token", ctx=ctx,
        desc="finish=end, but the reply's last token (199) is not in the client's end set {5}")
    one("END2", lambda b: b["io"].__setitem__("end_token", 5), "REJECT: end-token",
        desc="envelope end_token differs from the reply's last token")

    # ---- concurrency / interleaving
    st = g.state()
    na, ra = g.issue(st, "CON1-a")
    nb, rb = g.issue(st, "CON1-b")
    b = g.body(ex, ra, na)
    b["request"]["digest"] = rb["request_digest"]
    V["CON1"] = {"kind": "reject", "description": "two outstanding; envelope carries A's nonce and "
                 "B's request digest", "context": g.context(), "state": st,
                 "files": {"env1": g.seal(b)},
                 "steps": [step("env1", ex.reply, na, expect="REJECT: request-digest")]}
    st = g.state()
    na, ra = g.issue(st, "CON2-a")
    nb, rb = g.issue(st, "CON2-b")
    E.release(st, na, g.seal(g.body(ex, ra, na)))
    b = g.body(ex, rb, nb)
    b["state"] = {"seq": ra["seq"], "prev": ra["prev"]}
    V["CON2"] = {"kind": "reject", "description": "two responses race with the same seq; the "
                 "first was released, the second (for B, claiming A's seq and prev) is refused",
                 "context": g.context(), "state": st, "files": {"env1": g.seal(b)},
                 "steps": [step("env1", ex.reply, nb, expect="REJECT: state")]}

    # ---- expiry
    one("EXP1", expect="REJECT: expired", now=T0 + LIFETIME + 1, desc="client clock after expires_at")

    def exp2(b):
        b["issued_at"] = NOW + 61
        b["expires_at"] = NOW + 61 + LIFETIME
    one("EXP2", exp2, "REJECT: expired", desc="issued_at beyond the 60 s clock skew in the future")
    one("EXP3", lambda b: b.__setitem__("expires_at", T0 + 601), "REJECT: expired",
        desc="lifetime 601 s, longer than the client maximum 600 s")
    return V


def write(out, V, g):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=False)
    index = {"label": g.label, "provider_key": g.pk, "verifier_build": g.build, "vectors": {}}
    for name, v in V.items():
        d = out / name
        d.mkdir()
        (d / "context.json").write_bytes(E.canonical(v["context"]))
        (d / "state.json").write_bytes(E.canonical(v["state"]))
        for fname, data in v["files"].items():
            (d / (fname + ".envelope")).write_bytes(data)
        steps = []
        for s in v["steps"]:
            rb = E.tokens_bytes(s["reply"])
            rname = "%s.reply" % s["envelope"]
            (d / rname).write_bytes(rb)
            steps.append({"envelope": s["envelope"] + ".envelope", "reply": rname,
                          "deliver": s["deliver"], "proof": s["proof"], "now": s["now"],
                          "expect": s["expect"]})
        meta = {"name": name, "kind": v["kind"], "description": v["description"],
                "steps": steps}
        (d / "steps.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n")
        index["vectors"][name] = {"kind": v["kind"], "expect": [s["expect"] for s in steps]}
    (out / "INDEX.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    sums = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append("%s  %s" % (hashlib.sha256(p.read_bytes()).hexdigest(),
                                    p.relative_to(out).as_posix()))
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--build", required=True, help="cp_verify build digest the client pins")
    a = ap.parse_args()
    g = Gen(a.label, a.build)
    V = build_vectors(g)
    write(a.out, V, g)
    kinds = {}
    for v in V.values():
        kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    print("wrote %d vectors to %s: %s" % (len(V), a.out, json.dumps(kinds, sort_keys=True)))


if __name__ == "__main__":
    main()
