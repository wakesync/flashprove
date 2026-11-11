#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed client verifier for the FlashProve client envelope (flashprove-envelope-v1).

SPEC.md in this directory is the normative text; this file implements its client rules.

Two commands:
  issue    record an outstanding request in the client's state file. The client, not the
           provider, picks the nonce, the sequence number and the previous-state digest.
  deliver  check one provider response (envelope, reply bytes, proof bytes) against the
           outstanding request it is delivered for, and release the reply only if every check passes.

deliver prints three separate verdict lines (`signature:`, `tee:`, `proof:`), then a last line:
`RELEASE` (exit 0) or `REJECT: <check>` (exit 1). Exit 2 is a usage or environment error; nothing is
released. On anything but RELEASE no release file is written and the state file is not touched.
The checks run in the fixed order of SPEC.md section 5; the first failing check names the reject.

Software only. A `MOCK` attestation is printed as MOCK and is never evidence. Any other attestation
kind is refused, because this client verifies no TEE evidence.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(HERE.parent.parent / "tools" / "manifest"))

import ed25519  # noqa: E402
import envelope as E  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX128 = re.compile(r"^[0-9a-f]{128}$")
EXIT_RELEASE, EXIT_REJECT, EXIT_ERROR = 0, 1, 2

OUTER_KEYS = {"body", "sig"}
BODY_KEYS = {"version", "sig_alg", "provider_key", "request", "state", "issued_at", "expires_at",
             "model", "versions", "policy", "io", "coverage", "proof", "attestation"}
SUB_KEYS = {
    "request": {"session", "nonce", "digest"},
    "state": {"seq", "prev"},
    "model": {"commitment_id", "provenance_ref", "label"},
    "versions": {"tokenizer_sha256", "chat_template_sha256", "config_sha256", "operator_set",
                 "verifier_build"},
    "policy": {"kind", "bits", "C", "theta", "cap", "s", "sh", "sT", "F"},
    "io": {"prompt_sha256", "reply_sha256", "reply_tokens", "finish", "end_token"},
    "coverage": {"r", "e", "T", "y"},
    "proof": {"system", "sha256", "bytes"},
    "attestation": {"kind", "evidence"},
}
CONFIG_KEYS = {"policy.txt", "KL.bin", "layout.txt"}
POLICY_NUMBERS = ("C", "theta", "cap", "s", "sh", "sT", "F")


class Reject(Exception):
    def __init__(self, check, why):
        super().__init__(why)
        self.check = check
        self.why = why


def need(cond, check, why):
    if not cond:
        raise Reject(check, why)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _hex64(v):
    return isinstance(v, str) and HEX64.match(v) is not None


def check_schema(body):
    """Exactly the keys of SPEC.md section 3 at every level, each of its type. Unknown = reject."""
    need(set(body) == BODY_KEYS, "schema", "body keys: unknown %s, missing %s"
         % (sorted(set(body) - BODY_KEYS), sorted(BODY_KEYS - set(body))))
    for name, keys in SUB_KEYS.items():
        sub = body[name]
        need(isinstance(sub, dict), "schema", "%s is not an object" % name)
        need(set(sub) == keys, "schema", "%s keys: unknown %s, missing %s"
             % (name, sorted(set(sub) - keys), sorted(keys - set(sub))))
    need(body["sig_alg"] == "ed25519", "schema", "sig_alg %r: only ed25519" % body["sig_alg"])
    need(_hex64(body["provider_key"]), "schema", "provider_key")
    rq = body["request"]
    need(isinstance(rq["session"], str) and 0 < len(rq["session"]) <= 64, "schema", "session")
    need(_hex64(rq["nonce"]) and _hex64(rq["digest"]), "schema", "request.nonce/digest")
    need(_int(body["issued_at"]) and _int(body["expires_at"]), "schema", "times")
    need(_int(body["state"]["seq"]) and body["state"]["seq"] >= 1, "schema", "state.seq")
    need(_hex64(body["state"]["prev"]), "schema", "state.prev")
    m = body["model"]
    need(_hex64(m["commitment_id"]), "schema", "model.commitment_id")
    need(m["provenance_ref"] is None or _hex64(m["provenance_ref"]), "schema",
         "model.provenance_ref")
    need(isinstance(m["label"], str) and len(m["label"]) <= 200, "schema", "model.label")
    v = body["versions"]
    for k in ("tokenizer_sha256", "chat_template_sha256", "verifier_build"):
        need(_hex64(v[k]), "schema", "versions.%s" % k)
    need(isinstance(v["operator_set"], str) and 0 < len(v["operator_set"]) <= 64, "schema",
         "versions.operator_set")
    cs = v["config_sha256"]
    need(isinstance(cs, dict) and set(cs) == CONFIG_KEYS, "schema", "versions.config_sha256 keys")
    need(all(_hex64(x) for x in cs.values()), "schema", "versions.config_sha256 values")
    p = body["policy"]
    need(p["kind"] in ("exact", "clipped-gap"), "schema", "policy.kind")
    need(all(_int(p[k]) for k in ("bits",) + POLICY_NUMBERS), "schema", "policy numbers")
    io = body["io"]
    need(_hex64(io["prompt_sha256"]) and _hex64(io["reply_sha256"]), "schema", "io digests")
    need(_int(io["reply_tokens"]) and io["reply_tokens"] >= 1, "schema", "io.reply_tokens")
    need(io["finish"] in ("end", "length"), "schema", "io.finish")
    need(io["end_token"] is None or _int(io["end_token"]), "schema", "io.end_token")
    c = body["coverage"]
    need(all(_int(c[k]) for k in ("r", "e", "T")), "schema", "coverage numbers")
    need(c["y"] in ("yes", "no"), "schema", "coverage.y")
    pr = body["proof"]
    need(pr["system"] == "cp_verify/result-v1", "schema", "proof.system")
    need(_hex64(pr["sha256"]) and _int(pr["bytes"]) and pr["bytes"] >= 0, "schema", "proof")
    a = body["attestation"]
    need(isinstance(a["kind"], str) and len(a["kind"]) <= 64, "schema", "attestation.kind")
    need(a["evidence"] is None or isinstance(a["evidence"], str), "schema",
         "attestation.evidence")


def run_cp_verify(args, model, root, req_bytes, y_bytes, proof_bytes, want):
    """cp_verify in a private temporary directory, on the request file the client built itself.
    Accept only exit 0, result-v1 exactly once as the second-to-last line, every compared field
    equal, and the expected verdict as the last line (verifier/docs/output.md)."""
    p = model["policy"]
    with tempfile.TemporaryDirectory(prefix="fp-envelope-") as work:
        w = pathlib.Path(work)
        (w / "request.req").write_bytes(req_bytes)
        (w / "request.y").write_bytes(y_bytes)
        (w / "response.proof").write_bytes(proof_bytes)
        words = [args.cp_verify, str(root / model["config"]), str(root / model["ivk"]),
                 "request.req", "request.y", "response.proof", "-id", want["id"], "-j", "1", "-q"]
        if p["kind"] == "clipped-gap":
            words += ["-policy", "clipped-gap,%d,%d,%d,%d,%d" % (p["C"], p["theta"], p["cap"],
                                                                  p["s"], p["sh"])]
        t0 = time.perf_counter()
        try:
            done = subprocess.run(words, cwd=work, capture_output=True, text=True,
                                  timeout=args.timeout, env={"PATH": "/usr/bin:/bin"})
        except subprocess.TimeoutExpired:
            args.cp_verify_s = time.perf_counter() - t0
            raise Reject("proof", "cp_verify timed out: unproved") from None
        args.cp_verify_s = time.perf_counter() - t0
    lines = done.stdout.rstrip("\n").split("\n")
    args.cp_verify_exit = done.returncode
    args.cp_verify_last = lines[-1] if lines else ""
    need(not any(line.startswith("TEST BUILD:") for line in lines), "proof", "test build")
    need(done.returncode == 0, "proof", "cp_verify exit %d, last line %r"
         % (done.returncode, args.cp_verify_last))
    results = [line for line in lines if line.startswith("result-v1 ")]
    need(len(results) == 1 and len(lines) >= 2 and lines[-2] == results[0], "proof",
         "result-v1 not exactly once as the second-to-last line")
    fields = {}
    for word in results[0].split(" ")[1:]:
        need("=" in word, "proof", "result-v1 word without '='")
        k, val = word.split("=", 1)
        need(k not in fields, "proof", "result-v1 field %s twice" % k)
        fields[k] = val
    first, last = want["r"] + 1, min(want["e"], want["T"] - 1)
    expect = {"status": "0", "id": want["id"], "bits": "128", "record": "1",
              "r": str(want["r"]), "e": str(want["e"]), "T": str(want["T"]), "y": want["y"],
              "tokens": "%d..%d" % (first, last) if first <= last else "none",
              "stages": "key,leaf,request", "build": want["build"]}
    for k in POLICY_NUMBERS:
        expect[k] = str(p[k])
    if p["kind"] == "exact":
        expect.update({"claim": "exact-match", "policy": "exact-match"})
        verdict = "YES"
    else:
        expect.update({"claim": "policy", "policy": "clipped-gap"})
        verdict = "WITHIN LIMITS: clipped-gap C=%d theta=%d cap=%d s=%d sh=%d" % (
            p["C"], p["theta"], p["cap"], p["s"], p["sh"])
    for k, val in expect.items():
        need(fields.get(k) == val, "proof", "result-v1 %s=%r, expected %r" % (k, fields.get(k),
                                                                               val))
    need(lines[-1] == verdict, "proof", "last line %r, expected %r" % (lines[-1], verdict))
    return results[0], verdict


def deliver(args, ctx, state, root, env_bytes, reply_bytes, proof_bytes, now):
    """Every check of SPEC.md section 5, in order. Returns the release record or raises Reject."""
    v = args.verdicts
    # 1 canonical bytes
    try:
        outer = E.parse_canonical(env_bytes)
    except E.NotCanonical as failure:
        raise Reject("canonical", str(failure)) from None
    need(isinstance(outer, dict) and set(outer) == OUTER_KEYS, "schema", "outer keys")
    body = outer["body"]
    need(isinstance(body, dict), "schema", "body is not an object")
    # 2 version: exactly the one this client speaks, no negotiation
    need(body.get("version") == E.VERSION, "version",
         "version %r; this client accepts only %r" % (body.get("version"), E.VERSION))
    # 3 schema
    check_schema(body)
    need(isinstance(outer["sig"], str) and HEX128.match(outer["sig"]), "schema", "sig")
    # 4 signature under the client's pinned provider key, never under the key the envelope names
    pinned = ctx["provider_key"]
    ok = ed25519.verify(bytes.fromhex(pinned), E.signed_message(body), bytes.fromhex(outer["sig"]))
    v["signature"] = ("valid under the pinned provider key (authenticates the provider's "
                      "statement, not its truth)" if ok else "INVALID under the pinned key")
    need(ok, "signature", "signature does not verify under the pinned provider key")
    need(body["provider_key"] == pinned, "signature", "provider_key is not the pinned key")
    # 5 attestation: software only
    kind = body["attestation"]["kind"]
    if kind == "none":
        v["tee"] = "none (no TEE evidence offered; none checked)"
    elif kind == "MOCK":
        v["tee"] = "MOCK (not evidence: no measurement, chain, TCB or freshness checked)"
    else:
        v["tee"] = "REFUSED (kind %r claims hardware evidence; this client verifies none)" % kind
        raise Reject("attestation", "attestation kind %r cannot be verified here" % kind)
    need(ctx["require_tee"] == 0, "attestation", "client requires TEE evidence; none verifiable")
    # 6 time
    need(body["expires_at"] > body["issued_at"], "expired", "expires_at not after issued_at")
    need(body["expires_at"] - body["issued_at"] <= ctx["max_lifetime_s"], "expired",
         "lifetime longer than the client maximum")
    need(body["issued_at"] <= now + ctx["max_skew_s"], "expired", "issued_at in the future")
    need(now < body["expires_at"], "expired", "expired")
    # 7 nonce: delivered for an outstanding request of this session, never released before
    rq = body["request"]
    slot = args.deliver
    need(rq["nonce"] not in state["consumed"] and slot not in state["consumed"],
         "nonce-consumed", "nonce already released")
    need(slot in state["outstanding"] and rq["nonce"] == slot, "nonce",
         "envelope nonce is not the nonce of the request it was delivered for")
    need(rq["session"] == state["session"], "nonce", "session differs")
    req = state["outstanding"][slot]
    # 8 request digest, recomputed from the client's own record
    need(rq["digest"] == req["request_digest"], "request-digest",
         "request digest differs from the client's own request")
    # 9 state: seq and prev are the ones the client fixed when it issued the request
    need(body["state"]["seq"] == req["seq"], "state", "seq %d, request issued as seq %d"
         % (body["state"]["seq"], req["seq"]))
    need(body["state"]["prev"] == req["prev"], "state", "prev differs from the client's record")
    # 10 pins
    model_id = req["model"]
    model = ctx["models"][model_id]
    need(body["model"]["commitment_id"] == model_id, "commitment-pin",
         "commitment_id is not the one the client pinned for this request")
    need(body["versions"]["config_sha256"] == model["config_sha256"], "config-pin",
         "configuration digests differ from the client's pinned files")
    need(body["model"]["provenance_ref"] == model["provenance_ref"], "provenance-pin",
         "provenance reference differs from the client pin")
    for k in ("tokenizer_sha256", "chat_template_sha256", "operator_set"):
        need(body["versions"][k] == model["versions"][k], "version-pin", "versions.%s" % k)
    need(body["versions"]["verifier_build"] == ctx["verifier_build"], "version-pin",
         "versions.verifier_build")
    p, mp = body["policy"], model["policy"]
    need(p["kind"] == mp["kind"], "policy-pin", "policy %r, client pins %r" % (p["kind"],
                                                                              mp["kind"]))
    need(p["bits"] == ctx["min_bits"], "policy-pin", "bits %d, client pins %d"
         % (p["bits"], ctx["min_bits"]))
    for k in POLICY_NUMBERS:
        need(p[k] == mp[k], "policy-pin", "policy.%s" % k)
    # 11 coverage
    try:
        reply = E.bytes_tokens(reply_bytes)
    except ValueError:
        raise Reject("reply-digest", "reply bytes are not whole tokens") from None
    need(len(reply) >= 1, "reply-digest", "empty reply")
    prompt = req["prompt"]
    T = len(prompt) + len(reply) - 1
    want_y = "yes" if req["e"] == T else "no"
    c = body["coverage"]
    need(c["r"] == req["r"] and c["e"] == req["e"], "coverage",
         "covered r=%d e=%d, requested r=%d e=%d" % (c["r"], c["e"], req["r"], req["e"]))
    need(c["T"] == T and c["y"] == want_y, "coverage", "T or y differs from the received reply")
    # 12 io: the client's prompt and the bytes it received
    need(body["io"]["prompt_sha256"] == E.sha256_hex(E.tokens_bytes(prompt)), "reply-digest",
         "prompt digest differs from the client's prompt")
    need(body["io"]["reply_sha256"] == E.sha256_hex(reply_bytes)
         and body["io"]["reply_tokens"] == len(reply), "reply-digest",
         "reply digest or length differs from the received reply")
    need(len(reply) <= req["max_tokens"], "reply-digest", "reply longer than max_tokens")
    # 13 end token (outside the proof: point 8 of docs/verifying.md)
    ends = set(model["end_tokens"])
    need(not any(t in ends for t in reply[:-1]), "end-token", "end token before the reply's end")
    if body["io"]["finish"] == "end":
        need(body["io"]["end_token"] == reply[-1], "end-token",
             "envelope end_token differs from the reply's last token")
        need(reply[-1] in ends, "end-token", "reply's last token is not a client end token")
    else:
        need(body["io"]["end_token"] is None, "end-token", "finish=length with an end_token")
        need(len(reply) == req["max_tokens"] and reply[-1] not in ends, "end-token",
             "finish=length, but the reply is short of max_tokens or ends in an end token")
    # 14 proof bytes are the ones the provider signed for
    need(len(proof_bytes) == body["proof"]["bytes"]
         and E.sha256_hex(proof_bytes) == body["proof"]["sha256"], "proof-digest",
         "proof bytes differ from the envelope's digest")
    # 15 the proof relation, on the client's own request file
    req_bytes, y_bytes, t_len = E.request_file(prompt, reply, req["r"], req["e"])
    need(t_len == T, "coverage", "internal: T")
    want = {"id": model_id, "r": req["r"], "e": req["e"], "T": T, "y": want_y,
            "build": ctx["verifier_build"]}
    try:
        result, verdict = run_cp_verify(args, model, root, req_bytes, y_bytes, proof_bytes, want)
    except Reject as rej:
        v["proof"] = "REFUSED (%s)" % rej.why
        raise
    v["proof"] = "%s (cp_verify on the client's own request file)" % verdict
    return {"nonce": slot, "seq": req["seq"], "model": model_id, "verdict": verdict,
            "covered": {"r": req["r"], "e": req["e"], "T": T, "y": want_y},
            "label": body["model"]["label"], "result_v1": result}


def load_canonical(path):
    return E.parse_canonical(pathlib.Path(path).read_bytes())


def write_atomic(path, data):
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def fail(why):
    print("client_verify: error: %s" % why)
    print("REJECT: error")
    sys.exit(EXIT_ERROR)


def cmd_issue(args):
    ctx = load_canonical(args.context)
    state = load_canonical(args.state)
    if args.model not in ctx["models"]:
        fail("model not pinned in the context")
    if not HEX64.match(args.nonce):
        fail("nonce: 64 hex digits")
    if args.nonce in state["outstanding"] or args.nonce in state["consumed"]:
        fail("nonce reused")
    prompt = E.bytes_tokens(pathlib.Path(args.prompt).read_bytes())
    rec = E.issue(state, args.nonce, args.model, prompt, args.e, args.max_tokens)
    write_atomic(args.state, E.canonical(state))
    print("issued seq=%d nonce=%s prev=%s" % (rec["seq"], args.nonce, rec["prev"]))
    return 0


def cmd_deliver(args):
    t0 = time.perf_counter()
    args.cp_verify_s, args.cp_verify_exit, args.cp_verify_last = 0.0, None, None
    args.verdicts = {"signature": "not checked", "tee": "not checked", "proof": "not checked"}
    root = pathlib.Path(args.root).resolve()
    ctx = load_canonical(args.context)
    state = load_canonical(args.state)
    if ctx.get("version") != E.CONTEXT_VERSION or state.get("version") != E.STATE_VERSION:
        fail("context or state version")
    if pathlib.Path(args.release).exists():
        fail("release file exists already")
    env_bytes = pathlib.Path(args.envelope).read_bytes()
    reply_bytes = pathlib.Path(args.reply).read_bytes()
    proof_bytes = pathlib.Path(args.proof).read_bytes()
    try:
        record, failure = deliver(args, ctx, state, root, env_bytes, reply_bytes, proof_bytes,
                                  args.now), None
    except Reject as rej:
        record, failure = None, rej
    v = args.verdicts
    print("signature: %s" % v["signature"])
    print("tee: %s" % v["tee"])
    print("proof: %s" % v["proof"])
    print("cp_verify: exit=%s seconds=%.6f last=%r" % (args.cp_verify_exit, args.cp_verify_s,
                                                       args.cp_verify_last))
    print("client: seconds=%.6f" % (time.perf_counter() - t0))
    if failure is not None:
        print("why: %s" % failure.why)
        print("REJECT: %s" % failure.check)
        return EXIT_REJECT
    E.release(state, record["nonce"], env_bytes)
    write_atomic(args.state, E.canonical(state))
    write_atomic(args.release, reply_bytes)
    print("release: verdict=%r covered=%s" % (record["verdict"],
                                              E.canonical(record["covered"]).decode()))
    print("provenance: client pin %s; the envelope label %r is display text, not provenance"
          % (record["model"], record["label"]))
    print("RELEASE")
    return EXIT_RELEASE


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("issue")
    i.add_argument("--context", required=True)
    i.add_argument("--state", required=True)
    i.add_argument("--model", required=True)
    i.add_argument("--nonce", required=True)
    i.add_argument("--prompt", required=True)
    i.add_argument("--e", type=int, required=True)
    i.add_argument("--max-tokens", type=int, required=True)
    d = sub.add_parser("deliver")
    d.add_argument("--context", required=True)
    d.add_argument("--state", required=True)
    d.add_argument("--root", required=True, help="directory the context's paths start from")
    d.add_argument("--deliver", required=True, help="nonce of the outstanding request")
    d.add_argument("--envelope", required=True)
    d.add_argument("--reply", required=True)
    d.add_argument("--proof", required=True)
    d.add_argument("--now", type=int, required=True, help="client clock, unix seconds")
    d.add_argument("--release", required=True)
    d.add_argument("--cp-verify", required=True)
    d.add_argument("--timeout", type=float, default=300.0)
    args = ap.parse_args(argv)
    try:
        return cmd_issue(args) if args.cmd == "issue" else cmd_deliver(args)
    except (OSError, E.NotCanonical, KeyError, TypeError, ValueError) as failure:
        fail(repr(failure))


if __name__ == "__main__":
    sys.exit(main())
