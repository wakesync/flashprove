# Combined integration V2 review

Decision: **HOLD merge**. Focused combined gates pass; full CPU gate remains blocked by disk capacity, not established as passing. No GPU work or spend, no merge. Source licenses, LICENSE, NOTICE and third-party notices retained.

## Changes reviewed

Base `604b259df77f85bb07f13739336e536e717e7157`. Independently read fixture commit `da80d122fbe63ac409394e5cb2482a7831863ac6` and wrapper commit `9cc05efc571da66934253abc982fe4be800c016e`, integrated as `ac2dbcd3` and `8c5d6d62`. Fixture normalization affects newly copied test-owned files only. Production trust checks unchanged; three explicit source-mode regressions preserve original bytes/modes. copytree dereferences trusted fixture symlinks by default, so normalization does not chmod the original target. This helper is not an untrusted filesystem copier.

Wrapper launcher passes arguments positionally and quoted, uses bash privileged mode to avoid startup environment evaluation, and execs prlimit then Lake without an extra waiter. Timeout retains its own stderr outside bounded Lean files. Existing status/claim/exact-bound/signal/core checks remain. This is a bounded-output repair, not a new sandbox or soundness proof.

**Additional integration defect caught:** both lane commits changed test counts without updating SUITE.md. The combined suite would reject successful outputs. Commit `79c07616` changes exact 344 to 346 and 65/64/63 to 68/67/66. No wildcard replacement or assertion relaxation. Four non-research files differ from upstream: SUITE.md, fixture test, wrapper, wrapper test. Verifier and middleware production code unchanged.

Independently reread baseline adapter and regression source: canonical equality rejects unapproved profiles/types, fixed config hashes anchor local bytes, snapshot checked configuration goes to unchanged check_proof.py, numeric interior next-token expectations are rejected rather than silently dropped, and terminal expectations require vocabulary integers. These claims rely on trusted local runtime; manifest digest is not proof-transcript binding. Baseline README correctly distinguishes clipped sentinel from generated token and parser rejection from cryptographic rejection.

## Executed combined checks

Fresh verifier build through normal confined suite, not a reused binary. Exact commands and aggregate exits in evidence/results.json. Raw full suite row stdout preserved in evidence/*.txt, runner stdout in focused.log; focused-rows.json derives observed per-row exit values from runner output, not from retrospective guesses.

- Focused suite: **3 passed, 0 partial, 0 failed, 0 not run, 0 status-3, 0 alarm lines; exit 0**, 287.3 s.
- build.verifier: exit 0, 82.9 s.
- integrations.cp_verify: **68 passed**, row exit 0, 142.1 s. Both real proof fixtures and negative paths exercised.
- tools.lean_verify.script: **346 calls all as expected**, row exit 0, 145.1 s. Fake Lean harness, not real Lean.
- Adapter: **9 tests**, exit 0.
- Framework baseline: verified outcome, exit 0.
- Independent mutation audit: **41 calls, no failures**, exit 0; individual verifier exits and asserted final lines in audit/.
- Prior baseline evidence integrity: exit 0.

No focused selected skips. Internal wrapper exits are checked by its harness, not individually persisted as standalone process receipts. Kernel confines files but not ordinary signals. Source checkout ancestor remains group-writable with the runner's explicit warning. No guard bypass or permissions alteration.

## Remaining full-suite gate

The full run was **not launched**: free disk fell from 952 MiB to 64 MiB while bounded validation ran, whereas prior full CPU artifacts occupy 1.7 GiB. `/dev/shm` is explicitly forbidden by the unchanged runner for confined work and was not used as a workaround. Original artifacts remain untouched. See full-suite-blocked.json. This is a preflight limitation, not a fabricated test exit or a passing full result.

Recommendation: do not merge this PR or separately merge stacked PRs 1/2/3. Provide several GiB of stable disk headroom, then execute exactly one fresh confined full CPU run with stdout redirected to a durable file and aggregate exit persisted even for nonzero status. Existing runner prints per-row exit statuses; preserve those plus screens. Investigate every unexpected failure/status 3 and explicitly accept or close dependency/kernel skips before merge. Prior clang, gguf/numpy, root-only and kernel gaps remain unclosed. GPU/real Lean/TEE/full production inference remain outside this CPU gate.
