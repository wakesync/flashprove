# RESULTS: 20261117-210-identity-bridge

Issue #210 (part of #36 and #6). PREREG: [PREREG.md](PREREG.md), first commit `fd515f1994aa4930f39b2ef8b5061a2a119397bf`, amendment A-1 in `9e5b37cfd4f328a10e5081a7422b43603fa8271b`, amendment A-2 (after review) in `af2dd65312ac621d82d0fa10a2604cac16ea41a6`, amendment A-3 (second session of the fix round) in `75fbba1f1ace175362725be8e95622242e687ffa`. Base: main `5583d7f82b549454cdb6374d2fd347dfd9781976`.

The deliverable is the note [research/weight-binding/IDENTITY-BRIDGE.md](../../research/weight-binding/IDENTITY-BRIDGE.md).

**This is a desk specification. Nothing was run and nothing was measured.** No model, weight, attestation, key, proof or route was touched. There is no number here to replicate, no `research/results.yaml` entry and no proposed claim.

## Verdict against the registration

**The registered acceptance rule is met, by the lane's own reading. Not reviewed.** A round-1 review of an earlier head was split (one approval, one request for changes); the corrections it asked for are listed under "Corrections after review" below, and the text as corrected has not been reviewed. The hypothesis is not falsified: at least one edge is not a verified relation on main. In fact 14 of 18 are not.

| registered item | result |
|---|---|
| every edge carries all seven fields and exactly one status | 18 edges (after amendment A-1), 7 fields each, one status each (note section 5) |
| every named counterexample has a rejecting obligation or UNRESOLVED | 11 of 11 answered (note section 6) |
| every statement has a source | a `path:line` on main or a `[V1]` / `[V2]` / `[V3]` mark where the statement is made, and a source map (note section 8). The note's own proposals and reasoning are listed as such in 8.3 |
| the same-output physical-engine counterexample stays undetectable by proof alone | yes: counterexample 11 is UNRESOLVED by construction |
| FAIL rule: a signed assertion promoted to proof | not found by the lane in its own text. Every signature is classed as guarantee (c), and no edge of the proof or recomputation groups takes an input from a signer |
| FAIL rule: a subset result promoted to full Qwen support | not found by the lane in its own text. E8b is stated as 78 of 722 blocks; the full tree is a separate edge, E8c, with status PROPOSED |
| new soundness theorem or format: name it and stop | both are needed and both are named, O-1 and O-2 (note section 9.2). Neither is attempted |
| wall stop 2026-11-17T12:00:00Z | this file was written at 11:21Z, with all ten registered sections of the note already committed. The corrections after review were made after the stop. They are a deviation from it, they add no edge and no evidence, and they are listed under "Corrections after review" |

The two FAIL-rule rows are the author checking its own work. An independent reader is the test of them.

## The answer

1. The join goes through one public revision that the client itself authorizes. The client recomputes the package root, the checkpoint id and the conversion id from that revision, and accepts a proof only under a commitment that a key-file claim binds to the conversion id. A package root and a tensor root are never compared with each other.
2. On main the join cannot be made for Qwen. The edge that would bind the committed integers to the converted checkpoint (E9) has a four-tensor research fixture and no bound that covers a derived point (only a fixed-pair bound is stated). Even with E9, a proof does not identify the physical run.
3. A proof and an attestation answer different questions. A runtime that returns the same acceptable output from another engine is undetectable by proof alone.

## Edges by status

| status | count | edges |
|---|---|---|
| established on main, in a stated scope | 4 | E7 (hash level, open weights), E8a (hash level, rule text), E8b (hash level, 78 of 722 blocks), E11 (token ids, synthetic examples) |
| documented by vendor only | 5 | E1, E2, E3, E4, E5a |
| proposed code | 5 | E6a, E8c, E10, E12, E13 |
| unsolved cryptographic obligation | 4 | E5b, E6b, E9, E14 |

18 edges in all. Before review this table had proposed code 6 and unsolved 3; the one change is E6b, which moved to unsolved (PREREG A-2). No edge is established on main for the full Qwen model under proof.

## Counterexamples

| # | counterexample | designation |
|---|---|---|
| 1 | unrelated but valid package / proof roots | UNRESOLVED (rests on E9) |
| 2 | wrong config with same tensor names | rejected on main at hash level for the conversion id; equality with the committed configuration not built; runtime use UNRESOLVED (E6b, which rests on E5b) |
| 3 | exponent / integer-hash swap | rejected on main at hash level for 78 blocks; other 644 blocks not built; the prover's table UNRESOLVED |
| 4 | subset root presented as full tree | rejected on main in part (distinct tags, hashed count); pinned count and kind not built; claim count under proof UNRESOLVED |
| 5 | authorized root but alternate loader | UNRESOLVED |
| 6 | hot-swapped adapter | UNRESOLVED |
| 7 | rollback to old approved code | obligation, not built; hardware platform version UNRESOLVED |
| 8 | receipt key from another boot | obligation, not built; a key copied out within the same boot UNRESOLVED |
| 9 | output reconstructed from different token IDs | rejected on main on synthetic examples when the route delivers token ids; text-only routes UNRESOLVED |
| 10 | state root without authenticated origin | obligation, not built; proof side UNRESOLVED |
| 11 | a malicious runtime returning the same acceptable output | UNRESOLVED by construction, undetectable by proof alone |

Code on main performs the rejecting check for one of the eleven inside a stated scope (9), for three in part at hash level (2, 3, 4), and for none of the other seven. "Obligation, not built" is not a rejection, and it is not an observed acceptance either: for those cases no implemented end-to-end rejecting obligation for the specified bridge is established. Nothing was run, so no attack was observed to be accepted. Main's envelope client refuses a claimed hardware attestation kind, and any envelope when TEE evidence is required (`research/envelope/client_verify.py:241-250` on main). That refusal checks no relation of the bridge and is not a working identity bridge.

## What is not established

- No vendor statement was verified. The five vendor-only edges are descriptions from three public pages.
- No Qwen proof exists, so no proof edge holds for Qwen.
- The four edges established on main are hash-level bookkeeping or application checks, measured and unreplicated in their own results. They are not proofs.
- The edge list is not shown to be complete. It comes from the issue's wording and one reading of the evidence. The eleven counterexamples are the issue's list.
- That counterexample 11 cannot be detected by proof alone is an argument from what the statement contains, not a theorem proved here.
- Hidden weights are not treated: every recomputation edge assumes public weights.
- Confidentiality, privacy and zero knowledge are out of scope.
- The schema example is a discussion shape with made-up values. Nothing parses it.

## Deviations and corrections

1. **Two lanes.** The registering lane stopped at 09:20Z on an output-length limit, before writing any of the note. A successor lane (same model, new session) continued from 10:02Z on the same branch. Recorded in amendment A-1 before any note content was committed. The 42 minutes between sessions count against the three-hour stop, which did not move.
2. **Three edges split** (E5, E6, E8 into seven), recorded in amendment A-1 with reasons, before the note. No edge was dropped.
3. **E14 changed status after it was pushed.** Commit `e859e22` gave E14 the status "documented by vendor only". On re-reading, the vendor pages document that a measured program was started, not that it produced the reply, and the edge depends on E5b, which is unsolved. It is now "unsolved". The note says so where the edge is defined. The earlier commit is left in the history.
4. **One vendor page was first read cut short.** The note was drafted from a copy of the attestation-architecture page cut at 16,000 characters by the lane's own fetch limit. The page was then fetched in full and its marked statements checked. The cut part describes a router that admits only enclaves matching the latest release, which the first draft of the rollback rows (E1, counterexample 7) had said the pages did not describe. Those rows were rewritten.
5. **No checker.** The optional checker of the PREREG was not added. A lane-side script, not in this repository, confirmed that the 213 backticked path and line citations in the note name files that exist and ranges inside them (0 problems). It checks nothing about what the cited lines say.
6. **Reading depth.** The seven evidence files the issue names, `research/weight-binding/DESIGN.md`, `research/envelope/SPEC.md` and the key-file README were read in full. Every other cited file was read at the cited lines and their surroundings only.
7. **Prior art.** The PREREG lists RFC 9334, confidential-VM attestation, in-toto / SLSA and zkML systems from general knowledge. None of them was read for this note and none is cited in it.
8. **One status is a judgement call.** E10 is classed "proposed code" although the join needs E9, which is unsolved. The note gives the reason where E14 is defined: what E10 itself asserts does not contain E9's assertion, while what E14 asserts contains E5b's. A stricter reading of the weakest-part rule would class E10 as unsolved, giving proposed 4 and unsolved 5 (after the E6b correction below). Nothing else in the note depends on the choice.

## Process

- Commits after the registration: amendment A-1 alone, then the note in four content commits and one correction commit, then this file, then one more commit to the note (the E10 paragraph of item 8) and this update. No amend, no rebase, no force-push.
- Before each push: `scripts/check-no-host-paths.sh` ok, `scripts/update-results.py --check` ok, `scripts/check-claims.py` ok.
- After the round-1 review: amendment A-2 alone, then the corrections to the note, then this file. Same rules: commits on top of the reviewed head, no amend, no rebase, no force-push.
- The session that made those commits ended before it pushed them. A second session checked them, kept them unchanged, and added on top: amendment A-3 alone, three small commits to the note, then this update. Same rules. See "Corrections after review, second session" at the end.
- Not replicated. The text as corrected is not reviewed: a fresh review pair is needed at the new head. This pull request is a draft.

## Corrections after review (2026-11-17T13:20Z)

Round 1 reviewed head `614782d96c654f4f615c92d2adf7c66be00d5780` and was split. One reviewer approved with five nonblocking items ([comment](https://github.com/wakesync/flashprove/pull/215#issuecomment-6948402534), "A" below). One requested changes with three must-fix and two nonblocking items ([comment](https://github.com/wakesync/flashprove/pull/215#issuecomment-6948422134), "C" below). A fix lane (a new session) made the corrections below on top of that head. Each item was fixed as if both reviewers had asked for it. Nothing was run and nothing was measured in this round either. No status moved to the stronger side. The registration and amendment A-1 are byte for byte unchanged; the round is recorded in PREREG amendment A-2.

Every sentence that was replaced is quoted here as it stood at the reviewed head. "Note" is `research/weight-binding/IDENTITY-BRIDGE.md`; "RESULTS" is this file.

### 1. E6b is reclassified from proposed code to unsolved (C, must-fix 1)

The registered wording of E6b is that the configuration the runtime uses equals the pinned one. The note handed that runtime part to E5b, which is unsolved, and still called the edge proposed code. Under the registered rule (an edge that is not split takes the status of its weakest necessary part) the edge is unsolved. The reviewer also allowed a further split; it was not taken, for the reason given in PREREG A-2. Counts are now: established on main 4, vendor only 5, proposed code 5, unsolved 4, 18 edges.

Replaced:

- Note, section 1: "6 are proposed code (E6a, E6b, E8c, E10, E12, E13) and 3 are unsolved obligations (E5b, E9, E14)."
- Note, section 3, guarantee table: "public recomputation, no trust in the provider | E6a, E6b, E8a, E8b, E8c"
- Note, section 5.2, heading: "E6b. N4b configuration to the config pin inside N6. Status: PROPOSED."
- Note, section 5.2, E6b verifier row: "the client recomputes the pin from the revision's configuration file. Whether the engine uses that file unmodified is E5b"
- Note, section 5.2, E6b binding row and update row: "the pin is hashed into the conversion id" and "any pinned field change gives a new conversion id; an unknown key refuses" (both kept and extended)
- Note, section 5.2, paragraph under E6b: "The pin exists and is measured at hash level. The edge is PROPOSED, not MAIN, because two parts are missing: nothing ties the pin to what a runtime uses, and the design also requires the pinned fields to equal what the configuration under the commitment ID uses, which is "Not built""
- Note, section 5.4, E10 paragraph: "the count would then be PROPOSED 5, UNSOLVED 4, and nothing else in the note would change."
- Note, section 5.5, table row: "E6b | runtime config equals pinned config | PROPOSED | recomputation"
- Note, section 5.5: "Counts: MAIN 4, VENDOR 5, PROPOSED 6, UNSOLVED 3."
- Note, section 6.1, counterexample 2: "Rejecting obligation: the config pin inside the conversion id (E8a, E6b)." and "That the serving runtime uses that configuration: **UNRESOLVED** (E5b)."
- Note, section 6.3, row 2: "REJECTED ON MAIN in part; rest NOT BUILT and UNRESOLVED (E5b)"
- Note, section 7, schema example: `"not_covered": ["E5b", "E14"]`
- Note, section 9.2, row O-7: "covering dtype, quantization, adapters and settings | E5b, E14, counterexamples 5, 6 and 11"
- RESULTS, "Edges by status": "proposed code | 6 | E6a, E6b, E8c, E10, E12, E13" and "unsolved cryptographic obligation | 3 | E5b, E9, E14"
- RESULTS, counterexample 2 row: "runtime use UNRESOLVED" (kept; the edge it rests on is now named)
- RESULTS, deviation 8: "giving proposed 5 and unsolved 4"

Added, replacing nothing: a parts table and a reason under E6b, one sentence after the E10 paragraph, and one dependency line in section 9.1 of the note.

### 2. A missing rejection is not an observed acceptance (C, must-fix 2)

The note and this file said that a client running what is on main accepts the cases that have no rejecting check. Nothing was run, so no acceptance was observed, and main's envelope client is fail-closed on attestation: it refuses a claimed hardware attestation kind and refuses every envelope when TEE evidence is required (`research/envelope/client_verify.py:241-250`, `research/envelope/SPEC.md:169-170`, `:225-230`, `experiments/20261111-9-client-envelope/RESULTS.md:65-69`, all on main, read by the fix lane). The sentences now say only that no implemented end-to-end rejecting obligation for the specified bridge is established, and they keep three things apart: an unsupported input being refused, a relation with no coverage, and an attack observed to be accepted (none was). The refusal is not written up as a working identity bridge.

Replaced:

- Note, section 1, line 3: "Main rejects one of them today inside a stated scope (9), three in part at hash level (2, 3, 4) and seven not at all (1, 5, 6, 7, 8, 10, 11)."
- Note, section 6, before 6.1: "Today a client running only what is on main accepts every case not marked REJECTED ON MAIN."
- Note, section 6.1, counterexample 5: "On main: neither side."
- Note, section 6.3, summary table: the column heading "main today" and the cell "not rejected" in rows 1, 5, 6, 7, 8, 10 and 11 (now "rejecting check on main today" and "none", with one sentence above the table saying what "none" means)
- Note, section 10: "Where a row says NOT BUILT or UNRESOLVED, a client running what is on main accepts the counterexample today."
- RESULTS, under the counterexample table: "Main rejects one of the eleven inside a stated scope (9), three in part at hash level (2, 3, 4), and seven not at all. "Obligation, not built" is not a rejection: a client running what is on main accepts those cases today."

The same sentence stood in the pull request description ("A client running what is on main accepts those counterexamples today.") and is replaced there.

### 3. A new revision is not always a new checkpoint id (C, must-fix 3)

The checkpoint id hashes each tensor's name, dtype, shape and source-byte digest, and the number of tensors (`research/weight-binding/wb_manifest.py:36-38`, `:66-77`). It hashes neither the revision identifier nor the configuration. The configuration enters the conversion id separately, through the config pin (`research/weight-binding/wb_conv.py:365-378`). So two revisions that differ only in a configuration value share one checkpoint id. The update rules now give the change condition of each root, say that revisions can share a checkpoint id, and leave revision authorization and rollback to the client's policy. The common-revision recomputation proposal of E6a is unchanged. For the package root the note now says what the public page says and marks as unknown which files of a revision enter the packaged image.

Replaced:

- Note, section 5.2, E6a update row: "a new revision changes both; a new pack schema changes N3 only `[V1]`; a new leaf version changes N5 only"
- Note, section 5.2, E7 update row: "a new revision is a new id. Nothing links an old id to a new one"

### 4. Nonblocking items

- **Headline phrase (C, nonblocking 1).** Replaced in the note, section 1, line 2: "The edge that would make a proof say which weights ran, E9, has a research fixture on four tiny tensors and no security bound." Replaced in RESULTS, "The answer", item 2: "The edge that would make a proof say which weights ran (E9) has a four-tensor research fixture and no security bound." Both now say "bind the committed integers to the converted checkpoint" and add that a proof does not identify the physical run.
- **"No security bound" (A, nonblocking 2).** The same two sentences. The design on main states a fixed-pair bound and no bound for a hash-derived point (`research/weight-binding/DESIGN.md:86-93`). Both sentences now say "no bound that covers a derived point", which is what section 5.3 and O-1 of the note already said.
- **E9 "length-four" citation (A, nonblocking 1).** Note, section 5.3: the citation "(`experiments/20261111-36-keyfile-tensor-binding/RESULTS.md:5`, `:21-27`)" now also cites line 83 of that file, which is the line that says "Only four length-four public tensors".
- **"No checker is added" (A, nonblocking 3; also raised by C).** Clarified in PREREG A-2. A-1 itself is not edited.
- **Registration time 09:01Z against commit time 09:00:32Z (A, nonblocking 4; C, nonblocking 2).** Clarified in PREREG A-2. The header is not edited.
- **The producer's process slips (A, nonblocking 5).** They touch the audit trail only. Nothing was changed for them.
- **Review state.** Replaced in the note, header: "amendment A-1." (now names A-2 and says the corrected text is not reviewed). Replaced in the note, section 10: "Not replicated and not reviewed at the time of writing." Replaced in RESULTS, wall-stop row: "Anything done after the stop would be a deviation and is not in this file". Replaced in RESULTS, "Process": "Not reviewed and not replicated. This pull request is a draft." Each now says that a review happened at an earlier head and that the corrected text is not reviewed.

### 5. Lines extended, with no sentence removed

- Note, section 8, "How the citations were checked": one paragraph added for the citations of this round.
- Note, section 8.2, source map: four rows gained line numbers or uses (the conversion-id result now also lists E7's update rule and the same-tensor config cases; the key-file result gains line 83; the client-envelope result gains lines 65-69; the envelope specification gains section 6), and one row was added for `research/envelope/client_verify.py` (lines 241-250).
- RESULTS, first paragraph: the commit of amendment A-2 is named after that of A-1.
- RESULTS, "Verdict against the registration", first paragraph: one sentence added after "Not reviewed.", saying that a split round-1 review took place at an earlier head.
- RESULTS, under "Edges by status": one sentence added before "No edge is established on main for the full Qwen model under proof.", giving the total and the counts before review.
- RESULTS, "Process": one line added for the commits of this round.

### What this round did not do

- It ran nothing and measured nothing. It added no code, no checker in the repository and no results ledger row.
- It did not make any edge stronger. E7, E8a, E8b and E11 keep their stated scopes: hash level, rule text and not executable, 78 of 722 blocks, two synthetic stored examples. E9 and E14 stay unsolved, E10 stays proposed code with its disclosed judgement call, and counterexample 11 stays undetectable by proof alone.
- It fetched no vendor page. No corrected sentence rests on one beyond what the note already cited.
- It was made after the registered wall stop of 12:00:00Z. That is a deviation from the registration, recorded here and in PREREG A-2.
- **Citations.** Deviation 5 above gives 213 backticked citations for the note at the reviewed head. A second lane-side script, written by the fix lane and kept outside the repository, reproduces 213 at that head and counts 232 in the corrected note (152 with a line range, 47 follow-on line cites, 33 bare paths; 0 problems). Like the first, it checks only that the file exists on main and the range lies inside it. The lines added in this round were read by the fix lane at the cited ranges and their surroundings, not the files in full.
- The issue comment that summarises this pull request still carries the old counts. This round did not edit it.

## Corrections after review, second session (2026-11-17T19:17Z)

The session that wrote the section above made five commits (`af2dd653`, `d53d7ae2`, `0cab6383`, `28977ef5`, `b9f3d160`) and ended before it pushed them. A second session of the fix lane started at 19:00Z. It checked those commits itself, read the whole difference against the reviewed head and the corrected note in full, opened the cited lines on main, and re-ran the count, the citation range check and the quotation check. It kept the five commits unchanged and added the ones listed here on top. Nothing was run and nothing was measured in this session either. No status, edge or count changed. The round is recorded in PREREG amendment A-3. The section above is left as the first session wrote it, including its times and its citation count.

One of the first session's rows was narrowed (the E7 update rule) and one table row was extended (the guarantee table of section 3). Each sentence that was replaced or extended is quoted as it stood in commit `b9f3d160f8bcf9d61e90ae5f825d527769ac4b60`, which stays in the history. "Note" and "RESULTS" mean the same files as above; "C" is the [changes requested](https://github.com/wakesync/flashprove/pull/215#issuecomment-6948422134) comment and "A" the [approved](https://github.com/wakesync/flashprove/pull/215#issuecomment-6948402534) comment.

### 6. E7 update rule: the config pin shows a configuration change only for a pinned field (C, must-fix 3, taken one step further)

The first session's correction said that a revision changing only a configuration value keeps the checkpoint id "and the change shows in the config pin inside N6 instead". That overstates the pin. It covers 24 text fields and 3 top-level fields. A key on the listed known-unpinned set is allowed and is not hashed, so a change to it shows in neither id; a key outside both sets makes the build refuse (`experiments/20261111-91-conversion-id/RESULTS.md:68`; `research/weight-binding/wb_conv.py:131-147`, `:183-193`, on main, read by the second session). The row now says so, and says that neither id identifies a revision.

Replaced:

- Note, section 5.2, E7 update row: "a revision that changes only a configuration value keeps every tensor and keeps the id, and the change shows in the config pin inside N6 instead"
- Note, section 5.2, E7 update row: "So the id does not identify a revision and enforces no order between revisions."

### 7. Guarantee table of section 3 lists the runtime part of E6b (C, must-fix 1, surface agreement)

The table of section 5.5 puts the runtime side of E6b in group (a), and the recomputation row of section 3 already said that part rests on E5b. The group (a) row of section 3 did not list it.

Extended, with nothing removed:

- Note, section 3, guarantee table: "(a) hardware evidence | E2, E3, E4, E5a, E5b, E14" (kept; "and the runtime part of E6b" is added after it)

### 8. Lines that name the amendments, and lines extended

- Replaced in the note, header: "amendments A-1 and A-2." (now names A-3 too). One sentence was added to the line under it, saying that a second session finished the round.
- Replaced in the note, section 10: "asked for the corrections recorded in PREREG A-2." (now "A-2 and A-3").
- Replaced in the note, section 8.2, source map: "as cited in sections 4 to 6 | exact bytes of N5 and N6; counterexample 4" (the row now also names section 8 and the update rules of E6a and E7).
- Note, section 8, "How the citations were checked": one sentence added, saying which lines the second session read.
- RESULTS, first paragraph: the commit of amendment A-3 is named after that of A-2.
- RESULTS, "Process": one line added for this session.

### What the second session checked, and what it did not do

- **The five earlier commits.** Author and committer are the same no-reply identity on each, no commit message carries a trailer, each commit touches one of the three files of this pull request and nothing else, and the PREREG at the reviewed head is a byte prefix of the PREREG after A-2 and after A-3.
- **Counts.** Recounted from the edge headings, the table of section 5.5, the counts line, section 1 of the note and the table of this file: 18 edges, established on main 4, vendor only 5, proposed code 5, unsolved 4, the same on every one of those surfaces.
- **Citations at the final commit.** The lane-side range script of the first session, unchanged, counts 235 backticked citations in the note as it now stands (153 with a line range, 49 follow-on line cites, 33 bare paths; 0 problems). The 232 given in the section above was the count at commit `b9f3d160`. The script checks only that the file exists on main and the range lies inside it.
- **Reading.** The second session opened these ranges on main itself: `research/envelope/client_verify.py:241-250`, `research/envelope/SPEC.md:169-170` and `:225-230`, lines 65-69 of the client-envelope result, `research/weight-binding/wb_manifest.py:36-38` and `:66-77`, `research/weight-binding/wb_conv.py:365-378`, line 83 of the key-file result, `research/weight-binding/DESIGN.md:86-93` and `:198`, lines 23, 30-33 and 68 of the conversion-id result, and `docs/qwen-port.md:6-8` and `:56`. It read those lines and their surroundings, not the files in full.
- It ran nothing and measured nothing. It added no code, no checker in the repository and no results ledger row, fetched no vendor page, and made no edge stronger. E7, E8a, E8b and E11 keep their stated scopes: hash level, rule text and not executable, 78 of 722 blocks, two synthetic stored examples.
- It did not edit the issue comment that summarises this pull request. That comment still carries the counts and the wording from before review.
- The text as corrected is not reviewed. A fresh review pair is needed at the new head.
