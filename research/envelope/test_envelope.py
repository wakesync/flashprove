#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the client envelope. No real cp_verify needed.

  python3 research/envelope/test_envelope.py

1. The strict parser refuses duplicate keys, floats, booleans, whitespace, key order and truncation.
2. make_vectors.py reproduces the committed vectors/ byte for byte (SHA256SUMS).
3. The debug vector set passes against the STUB verifier (run_suite.py --debug, one run), and the
   STUB's build digest is not accepted under the registered context (its build pin is the real one).
"""

import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import envelope as E  # noqa: E402


def refuses(data):
    try:
        E.parse_canonical(data)
    except E.NotCanonical:
        return True
    return False


def test_parser():
    good = E.canonical({"a": 1, "b": {"c": "x", "d": None}})
    assert E.parse_canonical(good) == {"a": 1, "b": {"c": "x", "d": None}}
    for bad in (b'{"a":1,"a":1}', b'{"b":{"c":1,"c":1}}', b'{"a":1.0}', b'{"a":true}',
                b'{"a": 1}', b'{"b":1,"a":2}', good[:-1], good + b" ", b'{"a":NaN}',
                '{"a":"\u00e9"}'.encode("utf-8"), b'{"a":"\\u0041"}'):
        assert refuses(bad), bad
    print("parser: ok")


def test_reproduce():
    vec = HERE / "vectors"
    index = json.loads((vec / "INDEX.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "v"
        subprocess.run([sys.executable, str(HERE / "make_vectors.py"), "--out", str(out),
                        "--label", index["label"], "--build", index["verifier_build"]],
                       check=True, capture_output=True)
        a = (out / "SHA256SUMS").read_text()
        b = (vec / "SHA256SUMS").read_text()
        assert a == b, "regenerated vectors differ from the committed ones"
    print("reproduce: ok (%d files)" % len(b.splitlines()))


def test_debug_suite():
    with tempfile.TemporaryDirectory() as tmp:
        done = subprocess.run([sys.executable, str(REPO / "experiments" /
                                                   "20261111-9-client-envelope" / "run_suite.py"),
                               "--debug", "--runs", "1", "--out", str(pathlib.Path(tmp) / "o")],
                              capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "verdict=PASS" in done.stdout
    print("debug suite (STUB verifier, debug vectors): ok")


def test_stub_not_accepted_under_registered_pin():
    ctx = E.parse_canonical((HERE / "vectors" / "A1" / "context.json").read_bytes())
    sys.path.insert(0, str(HERE))
    import stub_cp_verify
    assert ctx["verifier_build"] != stub_cp_verify.STUB_BUILD
    print("stub build is not the registered pin: ok")


if __name__ == "__main__":
    test_parser()
    test_reproduce()
    test_stub_not_accepted_under_registered_pin()
    test_debug_suite()
    print("test_envelope: all ok")
