# Lean wrapper output-bound repair

Base: `604b259df77f85bb07f13739336e536e717e7157` (`research/integration-review`).
Scope: shell wrapper and fake-Lean harness only, not real Lean execution or a full CPU-suite rerun.

## Cause and repair

The child inherited `RLIMIT_FSIZE=1048576`, but its `timeout 0` supervisor did not.
Both wrote to `lean.err`. A supervisor diagnostic after SIGXFSZ/abort appended 43 bytes
past the cap. This was a bounded-output failure, not an observed false accept.

Keep timeout outside the limit so it remains able to supervise and forward signals.
A `bash -p -c` child redirects only the limited command's streams, then execs prlimit,
which execs Lake. The supervisor retains the wrapper's diagnostic stream instead of
opening `lean.err`. No pipeline, extra waiter, truncation or discarded diagnostic is
introduced. Shell startup files/functions are disabled by `-p`; paths and commands
are positional arguments, not interpolated shell text. `timeout 0`, its process group,
the trap, the cap, exact-bound rejection and status-plus-claim-plus-final-line verdict
checks are unchanged. Existing startup signal-race limitations remain unchanged.

Two new regressions fill exactly one MiB of stderr before aborting; one also fills
stdout. These reproduce the supervisor append without depending on a shell's
SIGXFSZ behavior. All existing assertions remain; expected call count rises by two.

## Observed results

- Fixed wrapper with expanded harness: **346 calls, all as expected, exit 0**.
- Original base wrapper with the same expanded harness: **346 calls, 3 discrepancies,
  exit 1**. `floods`, `bound-then-abort`, and `both-bounds-then-abort` each have
  stderr size 1048619. Each fixed stderr size is 1048576. All return NO VERDICT.
- Existing checks cover ignored SIGXFSZ, stdout flood, accept at the exact bound with
  lost following output, under-bound accept, abort after accept, INT/TERM/HUP,
  outer timeouts, process/descendant termination, and no core-file creation.
- Both runs report the core-limit holds were made and Program.lean was inspected.
  The latter is a text check, not a Lean theorem check.
- `bash -n` for both edited scripts and `git diff --check`: exit 0.

## Reproduction and evidence

From the isolated checkout (replace `<PLANNING>` with an absolute test-owned path):

```sh
bash -n tools/lean-verify/lean_verify.sh tools/lean-verify/lean_verify_test.sh
bash tools/lean-verify/lean_verify_test.sh <PLANNING>/wrapper-fixed-work > research/wrapper-output-bound/fixed.log 2>&1
# Immediately captured shell $? in fixed.exit.
```

For the negative control, copy `tools/lean-verify/` and
`lean/Johnson/PVR/Program.lean` to `<PLANNING>/wrapper-baseline-source/`, preserving
relative paths, then replace only its wrapper with:

```sh
git show 604b259:tools/lean-verify/lean_verify.sh > <PLANNING>/wrapper-baseline-source/tools/lean-verify/lean_verify.sh
bash <PLANNING>/wrapper-baseline-source/tools/lean-verify/lean_verify_test.sh <PLANNING>/wrapper-baseline-work > research/wrapper-output-bound/baseline.log 2>&1
# Immediately captured shell $? in baseline.exit.
python3 research/wrapper-output-bound/record.py <PLANNING>
```

Both work directories are retained locally, untouched by the recorder. The committed
console logs replace only the absolute planning prefix with `<PLANNING>`. `results.json`
records selected stdout, diagnostic excerpts and file sizes/hashes. The two call-hash
inventories cover every raw per-call file, including process records. The harness itself
checks individual exit statuses; they were not separately persisted per call, so these
receipts do not invent per-call exit records. Aggregate exits are durably captured.
`SHA256SUMS` covers changed test/source and portable evidence files (excluding itself).

No fixture-middleware changes, merge, rental, full CPU rerun, or claim that the original
CPU run is recovered/green. The existing merge hold and unrelated coverage gaps remain.
