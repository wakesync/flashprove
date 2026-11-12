# research/envelope: client envelope and fail-closed client verifier (issue #9)

Research prototype. Software only. Not a TEE design, not a privacy design, not a statement about any
served model. `SPEC.md` is the normative text; this file says what is here, what is and is not
covered, and how to reproduce every number.

## What is here

- `SPEC.md`: the envelope `flashprove-envelope-v1`, field by field with what binds each field, the
  client state and its concurrency rule, the 15 ordered client checks, the four ways a delivery can
  end (`RELEASE`, `REJECT: <check>`, `REJECT: error`, `CONSUMED-UNRELEASED`).
- `envelope.py`: canonical encoding, strict parser, digests, domain-separated messages, the state
  helpers `issue` and `release`.
- `client_verify.py`: the client. `issue` records a request; `deliver` checks one response and
  releases the reply only if every check passes.
- `make_vectors.py`: writes the 41 test vectors in `vectors/` from public TEST labels.
- `stub_cp_verify.py`: a stub verifier for the debug mode only. It is never accepted under the
  registered context.
- `test_envelope.py`: unit tests (parser, byte-for-byte vector regeneration, debug suite).
- `test_concurrency.py`: post-registration regression tests with the real `cp_verify` and several
  OS processes started behind a barrier (same nonce, distinct nonces, issue racing deliver, release
  directory missing, post-commit output failure).

## What is proved, what the client recomputes

- `cp_verify` (the shipped verifier) checks the stated relation for the commitment ID, the
  configuration behind it, the policy and its numbers, and the exact request file (prompt tokens,
  reply tokens but the last, r, e) with y. The client builds that request file itself, from its own
  prompt and the reply bytes it received, and takes the ID and policy from its own pins.
- The client itself recomputes or compares everything else: the canonical encoding, the Ed25519
  signature under its pinned provider key, the nonce, seq and prev against its own state, the
  request digest, the pins (commitment, config, provenance, tokenizer and template digests,
  verifier build, policy), the covered range, the reply and prompt digests, the end token and the
  proof digest. These are application checks; the proof does not bind them.

## What is not covered

- No soundness result: finite vectors on two synthetic stored examples.
- No freshness from the proof (gap G-05): the proof binds no nonce, time or session.
- No checkpoint identity (gap G-04): provenance, tokenizer and template are client pins only.
- No TEE, privacy or confidentiality: `MOCK` attestation stays MOCK, other kinds are refused.
- No batch envelope, no mask-exhaustion check (gap G-03), no network, no real provider.
- Concurrency: the registered vectors are sequential. Serialisation of concurrent client processes
  on one state file (an advisory `flock` on `<state>.lock`) was added after the registered run and is
  tested by `test_concurrency.py` only, on one local filesystem. It does not cover other programs
  writing the state file, network filesystems, or power loss beyond what fsync gives.
- `versions.verifier_build` is compared with what the binary itself prints (`build=`); it does not
  show which binary ran.

## Reproduce

From the repository top, CPU only:

```
verifier/build.sh                                        # bin/cp_verify, about two minutes
python3 research/envelope/test_envelope.py               # parser, vectors byte for byte, debug suite
python3 research/envelope/make_vectors.py --out /tmp/v --label registered --build <build>
diff /tmp/v/SHA256SUMS research/envelope/vectors/SHA256SUMS
python3 experiments/20261111-9-client-envelope/run_suite.py --registered \
    --cp-verify bin/cp_verify --runs 5 --out /tmp/envelope-run
python3 research/envelope/test_concurrency.py --cp-verify bin/cp_verify --repeats 20 \
    --out /tmp/concurrency.json
```

`<build>` is the `build=` digest that `verifier/build.sh` prints on its first line; the vectors pin
`ea191b014747c2c6c5c3c4622a06fa51bbda1c2591b314678c717f351663bd66` (`vectors/INDEX.json`). A build
with another digest regenerates other vectors and is refused by the registered context
(`version-pin`). `run_suite.py` refuses an
output directory that exists. The registered numbers are in
`experiments/20261111-9-client-envelope/runs/registered/` (pre-fix client, fb63aa8); the
post-registration re-run on the fixed client is in `runs/postfix/`; the concurrency test output of
this PR is `experiments/20261111-9-client-envelope/runs/postfix-concurrency/`. See that directory's
`RESULTS.md` for what each set shows.
