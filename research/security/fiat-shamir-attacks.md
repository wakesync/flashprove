# Two published Fiat-Shamir attacks, mapped onto FlashProve

Issue #37. Scope: **these two attacks**, ePrint 2025/118 and 2026/1838. This is a
source-level desk study and a deterministic CPU transcript-binding probe, not an audit,
a proof of soundness, or a claim about other attacks. Code citations below are at
`29907e5fbe648b9ec246cebf9d757511a751fca2`; the research commits do not change that code.

## Executive finding

**No omitted configuration input was found in the tested path.** The three configuration
files are hashed byte for byte into both the commitment ID and each proof chain's
parameters. With one fixed commitment ID and the original proof, changing the model
parameter, quantization scale, or layout rejected in 5/5 repetitions per mutation. When
using each changed configuration's *new* ID only to observe the transcript, its first
request-chain challenge changed in 5/5 repetitions, but verification still rejected.

**Not all public inputs are present before the first request challenge.** The separate
next-token value `y` is deliberately absent until the output-head segment. The caller's
`y` mutation left the first challenge unchanged in 5/5 repetitions and was rejected later.
The verifier binary and all its built-in constants are not cryptographically identified
by the transcript either; a manually assigned format version stands in for them.

**Paper-level verdicts: unclear for complete applicability to this protocol.** The
published GKR construction is not a direct match for FlashProve's segment commitments,
and no sufficiently expressive statement generator of Fenzi's kind was identified.
However, the uncommitted subcomputations and the full semantic statement coverage were
not exhaustively established. In particular, hashing a plan and observing challenge
changes does **not** establish the hypotheses of Fenzi's Proposition 5.5. No concrete
false-claim acceptance or new exploit was found. These conclusions are narrower than a
verdict that either paper has been ruled out.

The earlier draft's stronger conclusions were corrected after checking the full papers:
Fenzi's formal attack can choose a statement after a **prefix** of challenges, not only
after all of them; a generated plan is not automatically a canonical encoding of the
full relation; and SO-50 explicitly says there is **no** vocabulary-size factor in the
stated hash-query bound.

## 1. What is actually bound, and when

There is no single global "first challenge" shared by commitment creation, leaf linking,
and online proofs. An offline commitment cannot include a future prompt. Below, "first
challenge" means the request chain's first SEND/OOD challenge unless explicitly qualified.

| Public input | Before first request challenge? | Source and limitation |
| --- | --- | --- |
| `policy.txt`, including model dimensions, equation parameters, lookup-call descriptions and acceptance policy | Yes, full bytes via configuration digest | `verifier/src/cp_verify.cpp:843-849` passes the three files in a fixed order to `blocks/frame/heads.h:66-76`, which hashes file count, each length and each byte. `blocks/frame/check.h:60-70` binds the digest before the chain starts. |
| `layout.txt`, the array placement/program-layout description | Yes, full bytes via that digest, plus the derived layout | `blocks/frame/check.h:65-68` binds shape, layout, link identifiers and pending rows. Layout comment changes therefore also change the ID; this is byte binding, not a semantic difference. |
| `KL.bin`, the quantization/scaling parameters | Yes, all words via the same digest | `verifier/src/cp_verify.cpp:849`; supported verifier reads the words and passes all `4 * KL.size()` bytes. The CPU probe changes its first word from 29 to 28. |
| Generated proof plan and parameter objects | Selected serialized fields, yes; not an independent encoding of every equation | `blocks/chain/public.h:200-202,279-289` writes the format word, field/hash settings and round descriptors. Its comment at `:193-199` explicitly lists fields not serialized. `blocks/frame/check.h:60-70` adds codes, shapes and layout. Source-fixed equations and constants remain outside this serialization. |
| Prompt, reply tokens that lie inside the T-token request, padding, and checked range | Yes | `verifier/src/cp_verify.cpp:2470-2471` and `blocks/frame/check.h:73-78` bind both the request item and the raw request-file words. There is no separate prompt/reply split in the transcript; the tokens and range define the claim. |
| Caller-supplied commitment ID | Not literally inserted as an item of the request chain; checked separately | `verifier/src/cp_verify.cpp:2237-2254` recomputes the ID from the configuration and anchor header, then compares it to `-id`. `blocks/frame/heads.h:78-105` includes configuration, anchor name, OOD seeds and answers. The request chain names the **leaf** table root/record and copy number (`blocks/frame/check.h:160,168`, `:73-78`); the leaf proof ties it to the anchor. Flipping only `-id` rejects, rather than producing a new challenge. |
| Separate next token `y` after the T-token request | **No** | `verifier/src/cp_verify.cpp:2428-2432` writes zero in its initial statement slot. The prover's token is received and absorbed at `R_REPLY` by `blocks/iop/req.h:661-671`, before the output head's first message/challenges. It is compared with the caller's value in `blocks/frame/check.h:173-176`; `verifier/src/vf_segments.inc:301-302` also checks it. |
| Verifier source/binary, built-in operation semantics and constants | **No complete source or circuit digest** | The format version is written at `blocks/chain/public.h:200-202`. `docs/limits-further.md:146-150` (SO-63) explicitly warns that equal IDs do not identify equal built-in constants across builds. Fix the trusted verifier build as well as the ID/configuration. This is not evidence that the provider can change the client's trusted binary. |

Here "configuration" means those **three verifier input files**, not arbitrary Hugging
Face metadata, a tokenizer, stop-token settings, or an external generation program.
`docs/protocol.md:63-71` distinguishes the integer-model claim from those surrounding
choices. Prompt/reply text is represented by caller-supplied token IDs, not hashed as
raw UTF-8 text. Those distinctions matter when asking whether *all* application-level
public inputs are bound.

The hash chaining itself is explicit: `blocks/chain/chain.h:158-168` hashes the
parameter digest, length-prefixed statement and record, and salt/run marker into the
initial state. `blocks/frame/check.h:165-170` completes binding before constructing
`VerifierRounds`. Subsequent queries include the previous state and the prover's latest
message (`blocks/chain/chain.h:171-180`). Later chains bind the batch root and/or earlier
seals (`blocks/frame/check.h:81-87,190-205`).

### Offline challenges and the ID caveat

The anchor's OOD challenges are computed from its name, including configuration and
table shape/root, before the final ID exists. See `blocks/iop/foldeq.h:241-243,303-315`
and `lean/OnBytes/Key/Table.lean:64-98`. Thus an ID mismatch is checked before the file's
proof chains, **not before every hash-derived value**, and prompt/reply are not inputs
to offline challenges. This is the intended separation of offline and online claims.
The probe observes the online first chain, not every offline seed.

`docs/protocol.md:79` says the Lean theorem is at **given public files** and does not
itself establish binding across different public-file sets. That is a theorem-scope gap,
not a reported example of one ID verifying under two configurations. The implementation
hashes the files; the tests below find no such example. Collision resistance, correct
serialization and a fixed trusted verifier are still assumptions, not consequences of
five repeated calls.

### Lean transcript cross-check, by reading rather than a new Lean build

- `lean/Fmt/Rules4.lean:240-276` defines `firstValueW`, `startChainW`, `configDigestW`
  and `publishedIDW` with the same separation of inputs.
- `lean/OnBytes/Params/Given.lean:31-51,81-88` retains the parameter bytes, configuration
  digest and plan in the chain specification.
- `lean/OnBytes/Params/Chains.lean:198-227` reads the first-chain parameters and builds
  its four statement items. Its comment at `:213-218` explicitly excludes the reply.
- `lean/OnBytes/Proof/RequestItem.lean:132-135` likewise specifies a zero reply word.
- `lean/OnBytes/Chain/Step.lean:67-80` starts the chain from parameter digest and statement
  before reading its rounds.
- `lean/OnBytes/Key/Table.lean:67-98` derives the offline table name, seeds and ID.

These definitions support the input-order reading. This lane did not recheck Lean proofs
or prove equivalence of the C++ execution to those definitions.

## 2. The concrete hash versus an ideal oracle

`blocks/hash/hash.h:6-16,35-39` selects BLAKE2b with domain labels and digest-valued
salt/personalization; transcript round calls output 64 bytes, split into state and
challenge material. `blocks/hash/blake2b_f.h:43-49` identifies the concrete 12-round,
64-bit ARX compression function. `blocks/hash/MODE.md:20-30` states the random-oracle
assumption and separately describes the verifier's older second hash mode for public
lists/tables. Raw request words and the three config files also enter the primary
BLAKE2b transcript, so the observed binding does not depend solely on those older digests.
The older mode and its concrete interactions were not cryptanalyzed here.

Both papers attack **concrete instantiations despite random-oracle analyses**. Neither
requires a collision, preimage break, or a weak hash. KRS explicitly attacks strong
Fiat-Shamir with the circuit digest, public input and claimed output already hashed.
Fenzi likewise hashes the generating program; the issue is the distinction between that
program and its generated semantics. Therefore "BLAKE2b is cryptographic", "the Lean
ROM theorem holds", and "every config mutation changes a challenge" cannot dismiss
these attacks.

BLAKE2b and a commitment algorithm are expressible by general Boolean/arithmetic
circuits. The open question is whether the **admitted FlashProve computation or an
uncommitted subcomputation** can implement the needed self-reference and challenge
correlation within its operator, range, shape and resource constraints. Calling BLAKE2b
from the verifier is not itself such a circuit embedding. Conversely, absence of a named
hash operator is not a proof that the model family cannot express one. No such embedding
or impossibility proof was produced in this lane.

## 3. ePrint 2025/118: Khovratovich, Rothblum and Soukhanov

Full paper read: 11 December 2025 version, 23 pages. Theorems 1/2, Section 3,
Section 4's universal-computation variants, and Section 5 are the relevant parts.

### Mechanism and preconditions

1. **GKR plus an input/witness commitment, with the relevant internal computation not
   committed.** The basic theorem assumes `Pi_comm,d`, not every sumcheck-based system.
   The attacker builds `C*(w)` that interprets `w` as its own circuit digest, computes
   `comm(w)` and the FS challenge `gamma`, and outputs `(gamma, gamma-1)`. The claimed
   output `(0,0)` is impossible, but its multilinear extension agrees with the real
   output at challenge `r = gamma`. After that transition, the rest of the proof can
   be generated honestly (Construction 1, pp. 9-10).
2. **Adversarial circuit choice with enough depth/expressivity.** Theorem 1 requires
   depth at least `d_comm + d_hash + O(1)`. Theorem 2 backdoors an arbitrary admissible
   circuit without changing its functionality. Hashing the circuit description does
   not prevent either construction: its digest can be supplied as witness data.
3. **Known concrete hash/commitment parameters.** They must be available to construct
   the correlation, or handled through the universal-computation variants.
4. **For the fixed-circuit variants:** Section 4.1 needs a suitable universal evaluator,
   enough execution budget, and a commitment implementation whose code fits the witness
   size requirement. Section 4.2 uses universal GKR with decomposable commitments,
   including additive commitments or suitable batching. A syntactic search for hash
   gates does not rule these out.

### Mapping

- **Different commitment structure, partially blocking the direct construction.**
  `blocks/iop/req.h:413-433` commits oracle messages segment by segment, with additional
  commit points inside subproofs, then draws seeds. It does **not** commit the entire
  model trace before the first challenge. The first segment's message precedes its
  challenge; later segments' commitments come later. This is relevant to the
  intermediate-commitment mitigation in Section 5, but does not by itself certify all
  subcomputations against the extended attack.
- **Uncommitted values remain.** SO-57 (`docs/limits-all-rows.tsv:696`) names lookup
  keys, product-tree inner nodes and an attention vector. `blocks/iop/lkp.h:17-21`
  requires claims on unsent keys to be reduced to sent values; it does not enforce the
  caller's full reduction. Moreover `:8-10` says online request lookups use the separate
  `verifier/src/vf_lookup_argument.h`, so inspecting `lkp.h` alone is insufficient.
  KRS Remark 3 says canonical simple product/lookup circuits do not *seem* susceptible;
  it is useful context, not a theorem covering these implementations.
- **Provider control is real but restricted.** The provider chooses files/weights, not
  an arbitrary GKR circuit or the client's binary. The transcript binds these files
  (`blocks/frame/heads.h:66-76`), but that is not a KRS defense by itself. Whether a
  malicious model can realize the attack through the remaining uncommitted computations
  is unestablished.
- **Hash knowledge is available.** BLAKE2b and format labels are public. Prover-chosen
  transcript salts are not verifier-secret challenges and do not supply a defense.
  Root/configuration-dependent commitment inputs would have to be handled by an actual
  embedding; this study does not establish or exclude it.

**Verdict: unclear.** The exact `Pi_comm,d` construction is not directly instantiated by
this segmented protocol, and no attack was demonstrated. Full non-applicability would
need a bound on the relevant uncommitted computation or a structural proof excluding the
KRS correlation, including its extended/universal variants. The mutation probe provides
neither.

## 4. ePrint 2026/1838: Fenzi

Full paper read: 9 September 2026 version, 34 pages, including the attack-generator
appendix. Relevant formal results: Definitions 3.2-3.4 and 5.2; Theorems 3.7/3.10;
Corollary 3.11; Construction 5.4 and **Proposition** 5.5; Lemmas 6.5 and 7.5.

### Mechanism and preconditions

1. **A self-referential semantic scheme.** An instance describes a program that produces
   the effective statement, with enough expressivity and budget to produce a function
   of its own code and of the concrete FS challenge (Definitions 3.2, 4.2; Lemma 4.4).
   The hash is computed in the **statement generator**, not necessarily in the proved
   circuit. Preventing hash computation in witness constraints alone is insufficient.
2. **Programmability after a challenge prefix.** The attacker can send initial messages,
   then choose false semantics as a function of the first `i` challenges, and complete
   an accepting transcript for every later challenge (Definition 3.3). It need not wait
   until the entire transcript is complete. The concrete attacks have **i = 1**.
3. **The transcript does not already canonically bind those generated semantics.**
   Hashing the generator's code alone permits the quine construction. In the multilinear
   attack, a fixed witness codeword precedes `r`, and generated rows with
   `A = B = 0`, `C_b = (r_1 - b_1)e_0` make an impossible relation's zerocheck vanish.
   In the univariate attack, `C_0 = -rho e_0`, `C_1 = e_0` cancel under the batching
   challenge while the relation remains unsatisfiable (Lemmas 6.5, 7.5).
4. **Efficiency and completion conditions.** The generator must have sufficient time
   for diagonalization relative to hash/prover cost. The concrete continuations require
   the relevant efficient, perfectly complete lincheck/evaluation prover. Merkle
   commitments to the witness alone do not prevent these attacks (Theorem 3.10).

### Mapping

- **Ordinary config-file substitution is blocked in the measured path.** Configuration
  bytes, request words and generated descriptors precede the online first challenge,
  as Section 1 traces. The CPU probe finds distinct IDs and challenges, not a same-ID
  config substitution. This excludes the tested missing-input failure, not the full
  concrete-hash diagonalization.
- **The required programmable generator was not identified.** FlashProve parses numeric
  parameters and layout/call lists and constructs fixed model subproofs, rather than
  executing arbitrary provider-supplied code to output R1CS matrices.
  `verifier/src/cp_verify.cpp:1012-1025` exemplifies the fixed parameter scanner;
  `verifier/src/vf_segments.inc:283-302` dispatches the built-in segment checks.
  This is a material difference from the paper's generated-R1CS constructions. It is
  not a proof that every possible configuration-induced semantic map lacks the required
  self-reference.
- **Do not assert Proposition 5.5 from the plan hash.** That reduction uses challenges
  from `id(val(x))`, a canonical encoding of the generated statement, and requires the
  lifted and base verifiers to have exactly matching challenges and decisions. The
  current binder serializes plan fields and shapes plus a config digest, not an audited
  canonical encoding of every equation, coefficient, table and constant of the relation.
  `blocks/chain/public.h:193-199` lists omitted plan fields; SO-63 lists unbound built-in
  constants. Some omissions may be fixed/derived and harmless, but that must be shown.
  No such reduction was established. An ID equality check does not itself disprove the
  paper's semantic-verifier property either.
- **Deferred `y` is a real prefix-binding exception, not a demonstrated attack.** It
  enters before the output-head checks (`blocks/iop/req.h:661-676`), and changing the
  caller's expectation alone leaves the old proof's embedded `y` untouched. The unchanged
  `R_REPLY` digest in that test therefore does **not** show that the prover's token is
  unbound at `R_REPLY`. To claim an attack one would need to construct false semantics
  and a successful continuation after earlier challenges, not just a reusable prefix.
  To rule the attack out, "bound before its own segment" is not sufficient without
  checking dependencies from earlier segments. No such full construction or exclusion
  was produced. SO-50 (`docs/limits-further.md:137-141`) records prefix reuse and says
  the bound counts hash queries with **no vocabulary-size factor**.

**Verdict: unclear.** The paper's executable-generator precondition and false-statement
programmability have not been demonstrated for FlashProve. Conversely, complete semantic
binding sufficient to invoke Proposition 5.5 has not been demonstrated either. The
measured config binding is favorable evidence against a simple omission, not a resolution
of those formal preconditions.

## 5. CPU evidence and interpretation

Companion: `experiments/20261103-fiat-shamir-binding/`, PREREG committed before code.
The production verifier supplies the verdict; a separate read-only trace build supplies
the first-query digest and a challenge drawn on a copy of the chain. Its exit code and
last line agree with production for every recorded baseline/mutation pair.

Eleven cases, five deterministic paired repetitions each: 55 pairs. There are ten
semantic mutation types and one layout-comment control, not 55 independent attacks.

- Baseline: 55/55 `YES`, exit 0.
- Semantic mutations: 0/50 accepted. Three config mutations at the original ID:
  0/15 accepted, all `NO: model-statement`, exit 1. Comment control: 0/5 accepted.
- At diagnostic changed IDs, four config cases change the first challenge 5/5 each;
  all still reject. These IDs are not the client's original ID.
- Four request-word cases: first challenge changes 5/5 each, all reject.
- `y`: first challenge unchanged 5/5, all reject later at `NO: reply-differs`.
- Invalid shortened range: rejects before the request chain; not a binding measurement.
- Wrong caller ID: rejects at the ID comparison; not a challenge mutation measurement.

For each per-case Boolean indicator, n = 5, population SD = 0 and min = max = median:
0 for mutation acceptance; 1 for observed challenge changes in the config/request cases;
0 for challenge change under caller-`y` mutation. Repeating fixed inputs demonstrates
repeatability only. Status of these numbers: **measured, unreplicated** (a separate-lane
re-execution on the same inputs and source reproduced them; that is not an independent
replication). See RESULTS.md and raw JSON for full verdict/receipt details.

**Against prereg:** fixed-ID rejection passes. The universal early-binding clause fails
literally because `y` neither changes the first challenge nor rejects before it. Reporting
that exception does not turn it into an early-binding pass. This is a negative result for
that clause, not evidence of a false-claim accept. The original PASS-only summary was
corrected without changing the pre-registered threshold.

## 6. Open work

1. Trace the unsent lookup keys, product-tree nodes and attention vector through every
   consuming verifier equation; bound their ability to host a KRS correlation. Start
   from caller duty (2) in the header comment of `verifier/src/vf_lookup_argument.h`:
   the lookup argument enters none of the call list, table, `pub[]`, mask-row and plan
   values into the transcript itself, and `forestPlan` binds only v, d, the plane count and
   the shift flag, so each caller must fix the rest before the first challenge. That is the
   online path the CPU probe never exercised.
2. Define the exact semantic statement for the supported model family, including tables
   and constants. Determine whether the initial transcript canonically binds it and
   whether a Proposition 5.5 reduction can actually be written.
3. Analyze `y`'s dependency on earlier segments under Fenzi's prefix-programmability
   definition. A prover-side changed-token proof is different from the caller-only
   mutation here.
4. Broaden regression inputs to valid combined range/token changes, other configurations,
   and offline challenges. The present study covers one synthetic fixture, no newly
   generated proofs, no GPU and no real-model weights.

The public guide's "not examined" sentence should eventually link to this **partial
examination**, not be replaced with a claim that these attacks are excluded. Keep the
cross-configuration theorem caveat and SO-50/SO-63 caveats intact. No public vulnerability
issue was created by this study.

## A short question for an expert reviewer

Fenzi's Proposition 5.5 needs challenges derived from `id(val(x))`. FlashProve's first
query holds the raw bytes of the three configuration files plus serialized plan fields,
shapes and layout, while the per-segment equations and some constants are fixed in the
verifier source. Is hashing the raw generator inputs (rather than a canonical encoding
of every generated equation) enough for the Proposition 5.5 reduction, provided the map
from those files to the relation is a fixed, non-programmable function of the trusted
verifier build? Or does the reduction need the generated relation itself hashed?

## References and version receipts

Full PDFs were available in the lane's paper cache and read including the technical
sections and appendices. The landing pages were also retrieved; direct PDF retrieval on
the follow-up read returned HTTP 403, so the versioned cached PDF bytes, not the abstracts
or failed downloads, are the basis of the analysis.

- Khovratovich, Rothblum, Soukhanov, [ePrint 2025/118](https://eprint.iacr.org/2025/118),
  *How to Prove False Statements: Practical Attacks on Fiat-Shamir*, 11 December 2025.
  PDF SHA-256: `deac65104cd4f2c143a0b75cfb9a0ff99e4f042a891e9bb0b87969260b882035`.
- Fenzi, [ePrint 2026/1838](https://eprint.iacr.org/2026/1838), *How to prove more false
  statements: Fiat-Shamir limitations on (generated) R1CS*, 9 September 2026.
  PDF SHA-256: `c27d486433a2af467848b7058d7e95e7fbff32f8b50cf6c881ed606800023310`.
- Existing implementation/design context: `docs/protocol.md`, `blocks/hash/MODE.md`,
  `docs/limits-further.md` SO-50/SO-63, `docs/limits-all-rows.tsv` SO-57/SO-57.1.
