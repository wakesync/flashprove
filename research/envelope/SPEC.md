# FlashProve client envelope, version `flashprove-envelope-v1`

Status: research prototype for issue #9. Software only. Not a TEE design, not a privacy design, and
not a statement about any served model. The client verifier is `client_verify.py` in this
directory; the encoding helpers are `envelope.py`; the test vectors are `vectors/` (written by
`make_vectors.py`); the registered run is `experiments/20261111-9-client-envelope/`.

## 1. What the envelope is for

A provider answers a client's request with three things: the reply tokens, a `cp_verify` proof, and
an envelope that ties them to that one request. The client releases the reply to its caller only
after every check in section 5 passes. There is no "accept with warning". A delivery ends in one
of four ways:

| last line | exit | reply released | client state |
|---|---|---|---|
| `RELEASE` | 0 | yes, the release file holds the reply bytes | nonce consumed, envelope digest recorded |
| `REJECT: <check>` | 1 | no release file | byte-identical to before |
| `REJECT: error` | 2 | no release file | byte-identical to before |
| `CONSUMED-UNRELEASED` | 3 | no (the release path does not hold the reply) | nonce consumed, envelope digest recorded |

`REJECT: <check>` is a failed check, including a `cp_verify` timeout. `REJECT: error` is a usage,
input or environment error found before anything is committed, including a release path whose
directory is missing or not writable: the client writes the reply bytes to a uniquely named
temporary file in the release file's directory before it commits the nonce, and if that fails it
stops with `REJECT: error`. `CONSUMED-UNRELEASED` means every check passed and the nonce was
committed, but the last step, which puts the prepared file at the release path, failed (for
example because another file appeared at that path, which the client never overwrites). It fails
closed: the request is lost, not replayable. The client never restores an earlier state after an
output error, so a consumed nonce is never released later. A caller that gets exit 3 must issue a
new request.

(Before the post-registration fix of 2026-11-12, see PREREG amendment 2, a release-file error after
the checks printed `REJECT: error` with the nonce already consumed, which contradicted this section.
The registered run never hit that path.)

The envelope keeps three verdicts apart (section 6). A valid signature does not make a proof valid,
a MOCK attestation is not evidence, and a valid proof says nothing about who ran it or where.

## 2. Encoding

- One JSON object `{"body": {...}, "sig": "<128 hex>"}`, encoded canonically: keys sorted by code
  point at every level, no whitespace, ASCII only, strings with JSON's shortest escapes, integers
  only (no floats, no booleans; flags are 0 or 1), `null` allowed only where section 3 says so.
- The client parses strictly and refuses, as `canonical`: invalid JSON (this is how a truncated
  envelope fails), any duplicate key at any depth, floats, NaN or Infinity, non-ASCII bytes, more than
  65536 bytes, and any input whose bytes differ from the re-encoding of what was parsed (other key
  order, whitespace, escapes, trailing bytes). So exactly one byte string encodes a given body.
- Signature: Ed25519 (RFC 8032) by the provider key over
  `b"flashprove-envelope-v1\x00body\x00" || canonical(body)`. The domain prefix keeps an envelope
  signature from being valid as a signature of anything else the same key signs.
- Digests are SHA-256, lower-case hex. Token files are 32-bit little-endian words, as `cp_verify`
  reads them.

## 3. Fields

Every field below is required, and no other field is allowed at any level (`schema`). For each
field, the last column says what binds it. Words used there:

- **relation**: the `cp_verify` relation itself fixes it. The client checks it by running
  `cp_verify` on files it builds itself, and by comparing `result-v1` fields with its own values.
- **client-recomputed**: the client recomputes it from its own data (its prompt, the bytes it
  received, its own state) and compares. The proof does not bind it.
- **client-pinned**: the client compares it with a value it fixed beforehand from a source other
  than this provider. The proof does not bind it; the envelope's value counts for nothing on its own.
- **signature only**: only the provider's signature stands behind it. It is the provider's word.
- **metadata**: displayed, never used in a decision.

| Field | Meaning | Bound by |
|---|---|---|
| `version` | `flashprove-envelope-v1` exactly. No negotiation; any other string is refused (`version`) | client-pinned |
| `sig_alg` | `ed25519` exactly (`schema`) | client-pinned |
| `provider_key` | the provider's Ed25519 public key. The signature is checked under the client's pinned key, never under this field; the field must also equal the pin | client-pinned |
| `request.session` | the client's session name | client-recomputed (state) |
| `request.nonce` | 32 random bytes the client chose for this request | client-recomputed (state): must be outstanding and not consumed. **Not bound by the relation** (gap G-05) |
| `request.digest` | SHA-256 over `"flashprove-envelope-v1\0request\0"` and the canonical object {session, nonce, prompt_sha256, r, e, max_tokens, commitment_id} as the client issued it | client-recomputed |
| `state.seq` | the sequence number the client gave this request | client-recomputed (state) |
| `state.prev` | digest of the last envelope the client released in this session before issuing this request, or the session's genesis digest | client-recomputed (state) |
| `issued_at`, `expires_at` | unix seconds | signature only, checked against the client's clock and limits (`expired`) |
| `model.commitment_id` | the FlashProve commitment ID | **relation** (`cp_verify -id`, and `id=` in `result-v1`), and client-pinned: the client takes the ID it pinned for this request, never this field |
| `model.provenance_ref` | digest of the provenance record (for example a signed manifest, `tools/manifest`) that ties the commitment to a checkpoint | client-pinned. Not bound by the relation. This envelope never turns a provider's model name into checkpoint provenance |
| `model.label` | free text, such as a model name | **metadata** only |
| `versions.tokenizer_sha256` | tokenizer files digest | client-pinned. Not bound by the relation (gap G-04: the proof is about token ids) |
| `versions.chat_template_sha256` | chat template digest | client-pinned. Not bound by the relation |
| `versions.config_sha256` | digests of `policy.txt`, `KL.bin`, `layout.txt` | client-pinned against the client's own copies; those copies are bound by the relation through the commitment ID |
| `versions.operator_set` | name of the operator set of the configuration | client-pinned. Not bound by the relation beyond what the configuration files fix |
| `versions.verifier_build` | `cp_verify` source digest | client-pinned, and compared with `build=` of `result-v1`. A tampered binary can print any digest, so this is a consistency check, not evidence of which build ran |
| `policy.kind` | `exact` or `clipped-gap` | **relation** (`claim=`, `policy=`, last line) and client-pinned |
| `policy.bits` | 128 | client-pinned (`-bits` default, `bits=128`); anything else is a downgrade |
| `policy.C`, `theta`, `cap`, `s`, `sh`, `sT`, `F` | the policy numbers | **relation** (`-policy`, `result-v1` fields) and client-pinned |
| `io.prompt_sha256` | digest of the prompt token file | client-recomputed. The prompt enters the relation only through the request file the client builds |
| `io.reply_sha256`, `io.reply_tokens` | digest and length of the reply token file | client-recomputed from the received bytes. The reply enters the relation through the client's request file |
| `io.finish` | `end` (stopped at an end token) or `length` (stopped at max_tokens) | client-recomputed against the client's pinned end-token set. Not bound by the relation (point 8 of docs/verifying.md) |
| `io.end_token` | the end token, or null under `length` | client-recomputed |
| `coverage.r`, `e`, `T`, `y` | the covered range | **relation** (`r=`, `e=`, `T=`, `tokens=`, `y=`) and client-recomputed: r, e from the client's request, T and y from the received reply |
| `proof.system` | `cp_verify/result-v1` exactly | client-pinned |
| `proof.sha256`, `proof.bytes` | digest and length of the proof bytes | signature only; checked before `cp_verify` runs (`proof-digest`) so that what is checked is what was signed |
| `attestation.kind` | `none` or `MOCK` | see section 6. Any other kind is refused (`attestation`) |
| `attestation.evidence` | null or a string | metadata; never parsed |

What the relation binds, in one sentence: the commitment ID, the configuration behind it, the
policy and its numbers, and the exact request file (prompt tokens, reply tokens but the last, r, e)
with y. Everything else in the envelope is either client-recomputed, client-pinned, the provider's
signed word, or display text.

## 4. Client state

The client keeps, per session: `next_seq`, the outstanding requests (nonce, seq, prev, pinned
commitment ID, prompt, r, e, max_tokens, request digest), the consumed nonces, and the released
envelopes' digests in order. `issue` fixes seq and prev when the request is sent, so that two
responses for the same slot cannot both be released, and an old envelope cannot be replayed into a
new slot. A release consumes the nonce and appends the envelope digest before the reply bytes are
handed out.

Concurrent client processes. Every state change (`issue` and `deliver`) is one transaction under an
exclusive `flock` on a sidecar file `<state>.lock` next to the state file: the client takes the
lock, reads the state, runs every check (for `deliver`, all 15 of section 5, `cp_verify`
included), writes the new state and puts the release file in place, and only then releases the
lock. So client processes that share one state file are serialised: a nonce is released at most
once, two releases of different nonces both stay recorded, and an `issue` racing a `deliver` keeps
both changes. The state is never read before the lock is held, so a stale snapshot is never
written back. The cost is that deliveries on one state file run one at a time (including their
`cp_verify` calls). The lock is advisory: it serialises processes running this client, not other
programs that write the state file, and it needs a filesystem with working `flock` (a local
filesystem; not checked on network filesystems).

One state file, one name. The lock and every read, write, rename and directory fsync use the real
path of the state file: the path as given, with every symlink (of the file or of a directory on
the way) and every `.` and `..` resolved (`realpath`). So a symlink to the state file, a path
through a symlinked directory, and a relative and an absolute path to the same file all take the
same lock `<real path>.lock`, and a symlink is never replaced by the rename. A hard link cannot
be resolved to one name, so a state file with more than one hard link (`st_nlink > 1`) is refused
with `REJECT: error`, state untouched, before it is read; so is a state file that is not a
regular file, a path that resolves to another file once the lock is held, and (checked again just
before the commit) a state file whose inode or link count changed while the lock was held. Not
covered: one file reached through a bind mount or a second mount of its filesystem has two real
paths and one link, so this rule does not join them; keep one state file on one path. (Before
the 2026-11-12 second fix the lock and the rename used the path as given, and a symlink or hard
link alias of one state file released one nonce twice; see RESULTS.)

Availability limit. Taking the lock has no timeout: a client process that holds it blocks every
other client process on that state file until it finishes. In practice the hold is bounded by the
holder's `cp_verify` timeout (`--timeout`, default 300 s) plus the file writes, and the lock is
released when the holder exits or is killed. A holder that hangs elsewhere (for example on a stuck
filesystem) blocks the others indefinitely. This is a known availability limit, not a safety one:
waiting never releases anything.

Writes. The state file and the release file are written to a uniquely named temporary file in the
same directory (`mkstemp`), fsynced, then moved into place (the state with an atomic rename, the
release file with a hard link that never overwrites an existing file), and the directory is
fsynced. A crash before the state rename leaves the old state and no release. A crash after it
leaves the nonce consumed and possibly no release file: fail closed, the request is lost. Power
loss is covered only as far as the filesystem honours fsync; this is not tested.

(The registered run measured the client before this transaction rule existed, at fb63aa8. That
client read the state before its checks and wrote it back without a lock, with a fixed temporary
name `<state>.tmp`, and two reviews of PR #122 showed that concurrent processes could then release
one nonce twice or lose a consumption. The registered vectors are sequential and did not cover
this. See PREREG amendment 2 and RESULTS.)

## 5. Client checks, in this order

The first failing check names the reject (`REJECT: <check>`).

1. `canonical`: strict canonical parse of the envelope bytes (section 2).
2. `version`: `body.version` equals `flashprove-envelope-v1`.
3. `schema`: exactly the fields of section 3, each of its type; `sig_alg` is `ed25519`.
4. `signature`: Ed25519 under the client's pinned provider key; `provider_key` equals the pin.
5. `attestation`: kind `none` or `MOCK`; refused if the client requires TEE evidence (it cannot
   verify any) or if the kind claims hardware evidence.
6. `expired`: `issued_at < expires_at`, lifetime at most the client maximum (600 s in the
   vectors), `issued_at <= now + skew` (60 s), `now < expires_at`.
7. `nonce-consumed`, then `nonce`: the nonce was not released before; it is the nonce of the
   outstanding request this response is delivered for, in this session.
8. `request-digest`: equals the digest the client computed when it issued the request.
9. `state`: seq and prev equal the values fixed at issue.
10. `commitment-pin`, `config-pin`, `provenance-pin`, `version-pin`, `policy-pin`: each equals the
    client's pin for the request's model.
11. `coverage`: r and e as requested; T and y from the received reply.
12. `reply-digest`: prompt digest, reply digest and length match; reply at most max_tokens.
13. `end-token`: no end token before the last reply token; under `end` the last token is a pinned
    end token and equals `io.end_token`; under `length` the reply is max_tokens long.
14. `proof-digest`: proof length and SHA-256 equal the signed values.
15. `proof`: `cp_verify` on the request file the client builds from its own prompt and the received
    reply (`envelope.request_file`), with the pinned ID and policy, `-j 1 -q`, in a private
    temporary directory, with a timeout. Accept only exit 0, no `TEST BUILD:` line, exactly one
    `result-v1` line as the second-to-last line, every compared field equal (status, claim, id,
    bits, record, r, e, T, tokens, y, policy and its numbers, stages, build), and the expected last
    line (`YES`, or `WITHIN LIMITS: clipped-gap ...` under a clipped gap, which is released as
    within limits, never as exact).

Only then, still under the state lock of section 4: write the reply bytes to a temporary file in
the release directory (on failure `REJECT: error`, nothing committed), consume the nonce and record
the envelope digest (the state rename is the commit), put the release file in place (on failure
`CONSUMED-UNRELEASED`), print `RELEASE`.

### Verified before release, and what is not done here

- Timeout: a `cp_verify` timeout is a reject (`proof`), never a release.
- Abort or restart: the client writes state only on release, atomically, so a crash before release
  leaves the request outstanding and nothing released. A crash between the state write and the
  reply write leaves the nonce consumed and the reply unreleased: fail closed (the request is then
  lost, not replayable). An output failure at that point is reported as `CONSUMED-UNRELEASED`
  (section 1). A crash can leave a uniquely named `.<name>.*.tmp` file in the state or release
  directory; it is never read by the client. A temporary file left next to the release path holds
  the verified reply bytes (it was written before the commit), so a crash after the commit can
  leave the reply on disk under a temporary name even though it was not released. Such a file is
  not a release and must not be handed on as one.
- Batch proofs: one envelope covers one request and one proof. A batch is released only if every
  member's envelope passes; this prototype has no batch envelope.
- Mask exhaustion and the provider-side budget of proofs on one commitment are outside the client's
  view (inventory gap G-03). Not checked here.
- Latency is measured in the registered run for the stored examples only; it belongs to the
  benchmark track (issue #7) and is not a claim.

## 6. Three verdicts, none a stand-in for another

`deliver` prints these three lines on every call that gets past argument parsing, `REJECT: error`
and `CONSUMED-UNRELEASED` included; a verdict not reached reads `not checked`. (Before the
2026-11-12 fix, the `REJECT: error` paths printed only the error and the last line.) A usage error
found by the argument parser prints its usage message only. `issue` prints none of them:

- `signature:` the provider's Ed25519 signature authenticates that the holder of the pinned key
  said these bytes. It says nothing about whether what it says is true.
- `tee:` TEE evidence would authenticate a measurement under hardware and TCB trust. This client
  verifies no TEE evidence. A `MOCK` block is printed as `MOCK (not evidence ...)` and is accepted
  only as display; a client that requires TEE evidence refuses every envelope. A real TEE milestone
  needs certificate chain, TCB and freshness checks, a measured signing policy, an attested ephemeral
  key and an independent client proof check; GPU confidentiality needs its own accelerator and
  channel evidence. None of that is here.
- `proof:` `cp_verify` checks the stated relation on the client's own request file. It does not
  authenticate a provider, and it binds no nonce, time or session (G-05): the same proof is valid for
  the same request file at any time. Freshness and slot binding come from the signature and the
  client's state, not from the proof.

## 7. Test vectors

`vectors/` holds 41 vectors: 6 accept (A5 is a registered expected accept that confirms gap G-05;
A6, added by PREREG amendment 1, carries a MOCK attestation) and 35 reject, as listed in the PREREG. Each vector directory has `context.json` (the client's
pins), `state.json` (the client's state before the step), `steps.json` (deliveries and the expected
last line) and the envelope and reply bytes. Proof bytes are the stored examples
(`examples/accepted-proof`, `examples/accepted-proof-clipped-gap`), unchanged or cut by one byte as
`steps.json` names; no altered proof is stored. The provider and attacker keys are TEST keys derived
from a public label in `make_vectors.py`; they authenticate nothing. The tokenizer, chat template and
provenance digests in the vectors are TEST digests of labels, not of real files: the examples' model
is synthetic and has no tokenizer.

Reproduce the vectors byte for byte: `python3 research/envelope/make_vectors.py --out <new dir>
--label registered --build <the build= of your cp_verify>`, then compare with `vectors/SHA256SUMS`.
