# SPDX-License-Identifier: Apache-2.0
"""Shared encoding for the FlashProve client envelope, version flashprove-envelope-v1.

SPEC.md in this directory is the normative text. This module holds only the canonical encoding,
the strict parser, the digests and the domain-separated messages, so that the client verifier and
the vector generator encode the same bytes the same way.
"""

import hashlib
import json
import struct

VERSION = "flashprove-envelope-v1"
SIGNED_DOMAIN = b"flashprove-envelope-v1\x00body\x00"
REQUEST_DOMAIN = b"flashprove-envelope-v1\x00request\x00"
GENESIS_DOMAIN = b"flashprove-envelope-v1\x00genesis\x00"
CONTEXT_VERSION = "flashprove-envelope-client-context-v1"
STATE_VERSION = "flashprove-envelope-client-state-v1"
MAX_ENVELOPE_BYTES = 65536


class NotCanonical(Exception):
    pass


def _check_value(value, where):
    """Only objects, arrays, ASCII strings, integers and null. No floats, no booleans."""
    if value is None:
        return
    if isinstance(value, bool) or isinstance(value, float):
        raise NotCanonical("%s: booleans and floats are not allowed" % where)
    if isinstance(value, int):
        if value < -(2**63) or value >= 2**63:
            raise NotCanonical("%s: integer out of range" % where)
        return
    if isinstance(value, str):
        if not value.isascii():
            raise NotCanonical("%s: non-ASCII string" % where)
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _check_value(item, "%s[%d]" % (where, i))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise NotCanonical("%s: non-ASCII key" % where)
            _check_value(item, "%s.%s" % (where, key))
        return
    raise NotCanonical("%s: unsupported type" % where)


def canonical(obj):
    """Sorted keys, no whitespace, ASCII only. The one encoding that is accepted."""
    _check_value(obj, "$")
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _pairs(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise NotCanonical("duplicate key %r" % key)
        seen.add(key)
    return dict(pairs)


def _no_float(text):
    raise NotCanonical("float %r not allowed" % text)


def _no_constant(text):
    raise NotCanonical("constant %r not allowed" % text)


def parse_canonical(data):
    """Parse bytes strictly and require that they are exactly the canonical encoding.

    Refuses: more than MAX_ENVELOPE_BYTES, non-ASCII bytes, invalid JSON (truncated input),
    duplicate keys at any depth, floats, NaN/Infinity, and any byte sequence that differs from the
    re-encoding of what was parsed (key order, whitespace, escapes, trailing bytes).
    """
    if len(data) > MAX_ENVELOPE_BYTES:
        raise NotCanonical("longer than %d bytes" % MAX_ENVELOPE_BYTES)
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise NotCanonical("not ASCII") from None
    try:
        obj = json.loads(text, object_pairs_hook=_pairs, parse_float=_no_float,
                         parse_constant=_no_constant)
    except NotCanonical:
        raise
    except ValueError as failure:
        raise NotCanonical("not valid JSON: %s" % failure) from None
    if canonical(obj) != data:
        raise NotCanonical("bytes differ from the canonical encoding")
    return obj


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def tokens_bytes(tokens):
    return struct.pack("<%dI" % len(tokens), *tokens)


def bytes_tokens(data):
    if len(data) % 4:
        raise ValueError("token file length is not a multiple of 4")
    return list(struct.unpack("<%dI" % (len(data) // 4), data))


def signed_message(body):
    return SIGNED_DOMAIN + canonical(body)


def request_digest(session, nonce, prompt, r, e, max_tokens, commitment_id):
    fields = {"session": session, "nonce": nonce, "prompt_sha256": sha256_hex(tokens_bytes(prompt)),
              "r": r, "e": e, "max_tokens": max_tokens, "commitment_id": commitment_id}
    return sha256_hex(REQUEST_DOMAIN + canonical(fields))


def genesis(session):
    return sha256_hex(GENESIS_DOMAIN + session.encode("ascii"))


def new_state(session):
    return {"version": STATE_VERSION, "session": session, "next_seq": 1, "outstanding": {},
            "consumed": [], "released": []}


def issue(state, nonce, model_id, prompt, e, max_tokens):
    """The client's own record of a request: it, not the provider, picks seq and prev."""
    prev = state["released"][-1]["envelope_sha256"] if state["released"] else genesis(
        state["session"])
    seq = state["next_seq"]
    r = len(prompt) - 1
    rec = {"seq": seq, "prev": prev, "model": model_id, "prompt": list(prompt), "r": r, "e": e,
           "max_tokens": max_tokens,
           "request_digest": request_digest(state["session"], nonce, prompt, r, e, max_tokens,
                                             model_id)}
    state["outstanding"][nonce] = rec
    state["next_seq"] = seq + 1
    return rec


def release(state, nonce, envelope_bytes):
    rec = state["outstanding"].pop(nonce)
    state["consumed"].append(nonce)
    state["released"].append({"nonce": nonce, "seq": rec["seq"],
                              "envelope_sha256": sha256_hex(envelope_bytes)})


def config_digests(config_dir):
    import pathlib
    d = pathlib.Path(config_dir)
    return {name: sha256_hex((d / name).read_bytes()) for name in ("policy.txt", "KL.bin",
                                                                     "layout.txt")}


def request_file(prompt, reply, r, e):
    """The request file that the client gives cp_verify: prompt and reply but the last token, then
    r and e; and the y file: the reply's last token. Built from the client's own prompt and the reply
    bytes it received, never from a file the provider sent."""
    tokens = list(prompt) + list(reply[:-1])
    return tokens_bytes(tokens + [r, e]), tokens_bytes([reply[-1]]), len(tokens)
