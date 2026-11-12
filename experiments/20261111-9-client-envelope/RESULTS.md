# RESULTS: 20261111-9-client-envelope

Issue #9. Verdict vs the PREREG threshold: **PASS** (measured, unreplicated; descriptive tests on
two stored synthetic examples, not a soundness claim). The registered numbers below were measured
on the pre-fix client at fb63aa8. After the run, two reviews found that client unsafe for
concurrent processes sharing a state file; it was fixed and tested after the run (PREREG
amendment 2, section "Post-registration fix and checks" below). That section is not part of the
registered result.

## In plain language

We wrote a versioned envelope (`research/envelope/SPEC.md`) that a provider sends with a reply and a
`cp_verify` proof, and a client (`research/envelope/client_verify.py`) that refuses to hand the reply
on unless every check passes. The client builds the request file for `cp_verify` from its own prompt
and the reply bytes it received, takes the model ID and policy from its own pins, and keeps its own
record of nonces and sequence numbers. On 41 committed vectors, run 5 times each, every one of the 35
attack vectors was refused at the check it was registered for, and no refused vector released a reply
or changed the client's state. All 6 accept vectors released, including the registered gap A5: the
same proof re-wrapped under a new nonce is released, because the proof itself binds no nonce.

## Numbers (source: `runs/registered/summary.json`, rows: `runs/registered/rows.jsonl`)

Registered run: 2026-11-11T23:13:41Z to 23:15:05Z (84 s of a 30 min budget), 5 repetitions, order
reversed on even repetitions, `taskset -c 13-15` under the host's heavy-job gate, `cp_verify -j 1`,
cp_verify build `ea191b01...bd66` (binary sha256 in ENV.json). 210 rows.

| | vectors | passing in 5 of 5 runs | steps passed |
|---|---|---|---|
| reject | 35 | 35 | 175 / 175 |
| accept (incl. A5 expected-accept gap) | 6 | 6 | 35 / 35 |
| reject vectors that released a reply in any run | | 0 | |

Reject vectors by the check that refused them (each 5 of 5, each at its registered check):

- `canonical` 4 (DUP1, DUP2, NC1, TRN1), `version` 1 (DWN1), `schema` 3 (UNK1,
  UNK2, DWN5), `signature` 2 (SIG1, SIG2), `attestation` 1 (DWN4), `expired` 3 (EXP1-3),
  `nonce` 1 (RPL1), `nonce-consumed` 1 (RPL2), `request-digest` 2 (RPL3, CON1), `state` 3 (STA1,
  STA2, CON2), `commitment-pin` 2 (SUB2, SUB3), `config-pin` 1 (SUB5), `provenance-pin` 1 (SUB6),
  `version-pin` 1 (SUB7), `policy-pin` 2 (DWN2, DWN3), `coverage` 1 (TRN2), `end-token` 2 (END1,
  END2), `proof-digest` 1 (TRN3), `proof` 3 (SUB1, SUB4, TRN4).
- Only 3 of the 35 reject vectors reach `cp_verify`; the other 32 are refused by client-side checks
  before any proof is run. The 3 proof rejections: SUB1 and TRN4 `NO: proof-refused`, SUB4
  `NO: reply-differs` (cp_verify's own name; the PREREG registered the client check `proof`, which
  any nonzero cp_verify exit gives).
- So 32 of 35 refusals are **application checks outside the proof** (signature, client state, client
  pins, canonical parse). They bind only what the client pinned or recorded; they say nothing of the
  relation.

Timing (diagnostic only, shared loaded host, deterministic inputs; 5 runs per vector):

| quantity | n | median | SD | min | max |
|---|---|---|---|---|---|
| `cp_verify` wall on released steps (all accept vectors) | 35 | 1.430 s | 0.047 | 1.380 | 1.618 |
| client overhead on released steps (client total minus cp_verify) | 35 | 0.0144 s | 0.0015 | 0.0127 | 0.0188 |
| A1 cp_verify (exact) | 5 | 1.417 s | 0.023 | 1.380 | 1.438 |
| A2 cp_verify (clipped gap) | 5 | 1.430 s | 0.051 | 1.403 | 1.535 |

Per-vector figures for every vector are in `summary.json` (`per_vector`). A refused vector that does
not reach `cp_verify` costs about 0.06 s of process wall (Python start included).

## Three verdicts in the output

Every row records the three lines separately: `signature:` (valid under the pinned key, or INVALID),
`tee:` (`none`, `MOCK (not evidence ...)`, or REFUSED for a claimed hardware kind), `proof:` (the
cp_verify verdict on the client's own request file, or REFUSED). A6 shows MOCK released only as
display; DWN4 shows a claimed hardware attestation refused. No row shows a TEE pass, because this
client verifies no TEE evidence.

## Deviations from the PREREG

- Amendment 1 (before the run, in the PREREG): A6 added (MOCK accept vector); fixture details fixed by
  the code (clipped example end set {511} and `finish = length`; SUB4 signed with `finish = length`;
  TEST digests for tokenizer, template, provenance).
- The debug mode (STUB verifier, `debug` label vectors, temporary directories) ran several times
  before the registered run, as the PREREG allows. `cp_verify` was run once by hand on each unaltered
  example to read its output, as the PREREG allows. The `research/envelope/vectors/` directory was
  generated twice before the registered run (the second time after changing NC1's encoding); neither
  set was given to the client before the registered run, and the committed set is the one the run
  used (`vector_sums_sha256` in the summary).
- Two agent sessions shared this clone briefly at the start (lane STATE log, outside the repo).
  The duplicate session wrote and committed 6695101, the registered PREREG, pushed it and opened
  this PR, then stopped writing (22:41:41Z). The session that owns the lane and did the run
  committed 2fc685b (the 38 to 35 count fix) right after 6695101, then drafted a different design
  of its own (an alternative PREREG naming `tools/envelope/client.py` and `fp-envelope/1`) in the
  working tree, discarded it uncommitted (22:39:08Z) and adopted the registered PREREG at 2fc685b.
  So the run was done by the session that did not write the registered design. The STATE log
  records no code for the discarded alternative and none was committed; its text cannot be
  recovered. Registration-before-code holds: 6695101 and 2fc685b change only PREREG.md, 2fc685b only
  fixes a count, and the first code commit is d4856a4.
- After the registered run: PREREG amendment 2 and the client fix (next section). The registered
  run files in `runs/registered/` are unchanged.

## What this does not establish

- No soundness: 41 finite vectors on two synthetic stored examples. The envelope is a research
  prototype with no independent review yet.
- No freshness from the proof: A5 confirms gap G-05. Freshness and slot binding rest on the
  provider's signature and the client's own state.
- No checkpoint identity: provenance is a client pin of a digest; nothing here checks that a real
  checkpoint stands behind it. The model label is display text. The tokenizer and template digests are
  pins, not bound by the relation (gap G-04).
- No TEE claim, no privacy claim, no confidentiality claim. Mock attestation stays MOCK.
- No batch envelope, no mask-exhaustion check (G-03), no real network, no real provider.
- Timing is one host, loaded, two tiny examples; not a benchmark (issue #7 owns latency).
- Concurrent use was not covered by the registered vectors: they are sequential (CON1 and CON2 are
  sequential state checks). The pre-fix client that the registered run measured was unsafe for
  concurrent processes on one state file. Fixed and tested after the run, see Amendments
  (amendment 2) and the next section; that test is a post-registration check, not a registered
  result, and covers one local filesystem and client processes running this code only.
- `versions.verifier_build` is compared with the `build=` digest the `cp_verify` binary prints
  about itself (SPEC section 3). A tampered binary can print any digest, so this does not show which
  binary ran.

## Post-registration fix and checks (after the registered run; no threshold)

What was found (PR #122 reviews, round 1, both families, at head 3db2f6eb): with the pre-fix
client, two `deliver` processes on one state file could both release one nonce, and two concurrent
releases of different nonces could lose a consumption, after which the lost nonce released again.
A release-file error after the checks returned `REJECT: error` with the nonce already consumed.

What changed in `research/envelope/client_verify.py` (the 15 checks and their order are unchanged):
- `issue` and `deliver` each run as one transaction under an exclusive `flock` on `<state>.lock`:
  read the state under the lock, check, commit, release the lock. No stale snapshot is written.
- Temporary files have unique names (`mkstemp`, same directory), are fsynced, moved into place, and
  the directory is fsynced.
- Output contract (SPEC section 1): the release output is prepared before the nonce is committed;
  if that fails, `REJECT: error` (exit 2) with the state unchanged. If putting the prepared file at
  the release path fails after the commit, the new verdict `CONSUMED-UNRELEASED` (exit 3): nonce
  consumed, reply not released, never replayable. No old state is ever restored.
- `REJECT: error` from `deliver` now prints the three verdict lines too.

Re-run of the 41 vectors on the fixed client, `runs/postfix/` (`run_suite.py --registered --runs 5`,
slot granted 2026-11-12T00:19:21Z, `taskset -c 10-11` under the heavy-job gate, same cp_verify build
and binary sha256 as ENV.json, same vector set sha256). `compare_postfix.py` compares it step by
step with `runs/registered/`; output `runs/postfix/compare.json`:

| | registered (pre-fix, fb63aa8) | post-fix |
|---|---|---|
| steps | 210 | 210 |
| steps with a different exit, last line, release or state change | | 0 |
| reject steps refused at the registered check | 175 / 175 | 175 / 175 |
| reject steps that released or changed state | 0 | 0 |
| accept steps released | 35 / 35 | 35 / 35 |
| reject vectors reaching cp_verify | SUB1, SUB4, TRN4 | SUB1, SUB4, TRN4 |

Timing of the post-fix re-run, diagnostic only (other cores, other load, not comparable with the
registered timing and not a claim): cp_verify on released steps median 1.678 s (SD 0.052, min
1.578, max 1.795, n 35); client overhead median 0.0150 s (SD 0.0019, 0.0134 to 0.0225).

Concurrency and output-failure tests, `research/envelope/test_concurrency.py` (real cp_verify, own
TEST label, every client call its own OS process, concurrent calls released by one barrier, each
concurrent case 20 times), output in `runs/postfix-concurrency/`:

| case | fixed client (`fixed-client.json`) | pre-fix client at 3db2f6e (`prefix-client-3db2f6e.json`) |
|---|---|---|
| same nonce, 3 processes at once: exactly one RELEASE, nonce consumed once | 20 / 20 | 0 / 20 (all 3 released, every time) |
| two distinct nonces at once: both RELEASE, both consumed, replay of either `REJECT: nonce-consumed` | 20 / 20 | 0 / 20 |
| `issue` racing `deliver`: both changes kept | 20 / 20 | 11 / 20 (9 lost updates) |
| release directory missing: `REJECT: error`, state byte-identical | 1 / 1 | 0 / 1 (state changed) |
| post-commit output failure: `CONSUMED-UNRELEASED`, nonce consumed, other file untouched, second delivery `REJECT: nonce-consumed` | 1 / 1 | 0 / 1 (no such step in that client; second delivery released) |

The pre-fix column runs the same test file against the client file of the reviewed head 3db2f6e;
it shows the tests detect the defect. The reviewers' own probe scripts were also re-run against
both clients (outside the repository; see the PR comment): on the pre-fix client they reproduce
both reviews' findings, on the fixed client the concurrency and release-error cases behave as
above and every other probe gives the same verdict as before.

These are post-registration checks of one fix, on one host and one local filesystem. They are not
a replication of the registered run and add no soundness claim.
