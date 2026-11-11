#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""STUB cp_verify for debugging the envelope client only. It checks no proof.

It says YES (or WITHIN LIMITS) iff the request, y and proof files are byte-identical to the stored
example next to the given config directory and -id is that example's ID; otherwise `NO: stub`.
Its build= is the fixed STUB_BUILD below, which no real build prints, so a context that pins a real
build never accepts its output. Every line ends with " (stub)" except the two closing lines, which
must look like the real ones for the client's parser; the first line says STUB.
"""

import hashlib
import pathlib
import sys

STUB_BUILD = hashlib.sha256(b"flashprove-envelope-v1 STUB cp_verify, not a verifier").hexdigest()


def main(argv):
    config, ivk, req, y, proof = (pathlib.Path(a) for a in argv[1:6])
    opts = argv[6:]
    ident = opts[opts.index("-id") + 1]
    policy = opts[opts.index("-policy") + 1] if "-policy" in opts else None
    ex = config.parent
    print("STUB cp_verify: checks no proof (stub)")
    same = (req.read_bytes() == (ex / "example.req").read_bytes()
            and y.read_bytes() == (ex / "example.y").read_bytes()
            and proof.read_bytes() == (ex / "example.proof").read_bytes()
            and ident == (ex / "ID.txt").read_text().strip())
    if not same:
        print("NO: stub")
        return 1
    words = list(req.read_bytes()[i:i + 4] for i in range(0, len(req.read_bytes()), 4))
    nums = [int.from_bytes(w, "little") for w in words]
    r, e, T = nums[-2], nums[-1], len(nums) - 2
    first, last = r + 1, min(e, T - 1)
    if policy:
        _, C, theta, cap, s, sh = policy.split(",")
        claim, pol = "policy", "clipped-gap"
        verdict = "WITHIN LIMITS: clipped-gap C=%s theta=%s cap=%s s=%s sh=%s" % (C, theta, cap,
                                                                                   s, sh)
    else:
        C, theta, cap, s, sh = "256", "256", "0", "16", "8"
        claim, pol, verdict = "exact-match", "exact-match", "YES"
    print("result-v1 status=0 claim=%s id=%s bits=128 work=32 work-rounds=38 least-round=128.00 "
          "least-round-without-work=96.23 commitment-assumed-rounds=49 record=1 r=%d e=%d T=%d "
          "tokens=%d..%d y=%s policy=%s C=%s theta=%s cap=%s s=%s sh=%s sT=4 F=24 above-clip=0 "
          "leaf=0 stages=key,leaf,request dw=8 build=%s"
          % (claim, ident, r, e, T, first, last, "yes" if e == T else "no", pol, C, theta, cap,
             s, sh, STUB_BUILD))
    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
