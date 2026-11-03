# Verifier CPU speedup: inline limbs for the exact planning arithmetic

Issue #7, after the PR #18 baseline. **Result: complete stored-proof verification is 17.8% faster
(median wall 2.61 s to 2.145 s, single thread). Over 12 alternating runs per arm the min/max ranges
do not overlap. Nothing the verifier checks has changed. Verdicts and every printed line are
byte-identical on the honest example and all eight negative cases.**
The production change is in one header, `blocks/numbers/real.h`. A test-only switch is added to
`blocks/fence.h` and `planners_read_once_test.cpp` so that test keeps its full detection power (see
Correctness). Compiler-only changes (-O3, x86-64-v3, PGO) were measured separately and are noise.
A confirmatory 10-round run on the final source gave -18.0%, also with non-overlapping ranges.

## Where the time went (profile)

perf is unavailable (`kernel.perf_event_paranoid=4`, perf and valgrind not installed, no host
change requested). gprof's `-pg` gives call counts but no time. Its ITIMER_PROF does not survive
cp_verify's `fork()` of the three stage processes, so every stage reported "no time accumulated".
So this lane wrote a small unprivileged sampling profiler, `sampler.c`. It is LD_PRELOADed, re-arms
ITIMER_PROF at 1 kHz after every fork, and walks frame pointers. `symbolize.py` maps the samples to
functions with `nm`. It profiles a stock-flag build plus `-fno-omit-frame-pointer -g`; the sources
are unchanged. Run it with `profile_run.sh`.

Stock, one complete call, samples per stage process (1 sample = 1 ms CPU), from `profiles/stock/`:

| stage | CPU | stacks inside Big/Real/Bound | inside blk::configure | inside blk::sized | inside check_proof |
|---|---|---|---|---|---|
| key | 0.60 s | 71.5% | 55.8% | 43.6% | - |
| leaf | 0.53 s | 71.3% | 56.0% | 49.5% | - |
| request | 1.60 s | 27.6% | 18.4% | 14.3% | 66.0% |

What this shows:

- The exact arbitrary-precision arithmetic of planning and accounting (`Big`, `Real`, `Bound` in
  real.h) runs in **71% of the key and leaf stages' CPU time and 28% of the request's**. It comes
  from `blk::sized` and `configure` (lin_sized, group_holds, johnson_count, Real::sqrt/div,
  Big::divmod), from accounting, and from `whole_error`.
- Within that, much of the self time was not arithmetic. It was the heap traffic of
  `std::vector<u32>` limbs: `vector(const vector&)`, `_M_fill_assign`, `~vector`, `emplace_back`,
  and malloc/free under them. The flat profile with library time charged to the caller has
  `vector<u32>` copy+fill at about 16% of the key stage. gprof counts on the request stage alone:
  11.6 M `~vector<u32>`, 6.0 M copies, 4.6 M fill_assigns.
- The request's proof-checking core (`check_proof`, ~1.05 s) is spread out: `Tensor::folded_slice`
  12.6%, `Tensor::add_to` 5.5%, `eqTab` 4.3%, GL64 `dot3` 2.8%, Blake2b 1.1%... No single hashing or
  Merkle hot loop dominates. Hashing is under 2% in every stage.

## The change

`Big`'s limbs move from `std::vector<u32>` to `Limbs`, a small container in the same header with
the subset of the vector interface that `Big` uses: `size`, `empty`, `[]`, `back`, `pop_back`,
`push_back`, `assign`, `resize`. It holds up to 24 limbs (768 bits) inside the object and spills to
the heap beyond that. A Real is cut to REAL_BITS = 192 bits (6 limbs), and a product of two is 12
limbs, so planning arithmetic almost never allocates. In addition, `divmod` and `isqrt` move their
final temporaries instead of copying them (`q = std::move(t)`, `x = std::move(y)`).

What does not change:

- **No arithmetic changes.** Every Big/Real/Bound algorithm is the same text. Only where the limbs
  are stored has changed, and every value is the same.
- **Bounds checking is kept.** Every limb index is checked (`BLK_REQUIRE`, which aborts), as
  `-D_GLIBCXX_ASSERTIONS` checked `std::vector::operator[]` before. `pop_back` of an empty number
  and absurd sizes (>= 2^40 limbs) also abort.
- **No check is removed, reordered or cached.** The first sizing still validates the untrusted
  layout and mask shape before `configure`. Nothing is shared across stages or processes. No
  parameter, transcript, accounting or precision change.
- The build flags are unchanged: the stock `verifier/build.sh`, with every hardening flag and
  `-fno-ipa-modref`.

The source digest (`build=`) changes, because real.h (and fence.h) are hashed sources. That is
expected; it is the only difference in the full stdout apart from timing figures.

### The test switch BLK_BIG_ON_THE_HEAP_FOR_A_TEST

`planners_read_once_test` checks the READ ONCE rule of blocks/numbers/plan.h. It replaces global
`operator new` and changes a planner's size argument at each heap allocation in turn. Big's limbs
were a large share of those allocations. With inline limbs the test still passed, but it probed
4,618 plans instead of 119,156. A mutation check showed that this cost it detection power: each of
the 11 `READ ONCE` copies that can be mutated was turned into a reference, one at a time. Base
detected all 11; the candidate missed 3 (blocks.h lines 532, 547, 755). The 3 remaining
`READ ONCE` sites, lines 1061/1111/1142, take `const TableSize T` in a form the sed did not
rewrite. They were not mutated on either side, and the test's own header lists four sites it cannot
detect.

So `real.h` now has a test-only switch, `BLK_BIG_ON_THE_HEAP_FOR_A_TEST`, which sets the inline
capacity to 0, so every limb is heap-allocated as with std::vector. The read-once test defines it.
The switch is listed in `blocks/fence.h`: it does not compile next to `SERVING_BUILD` (checked:
`#error`), and a test build carries the BLK-NOT-FOR-SERVING marker (checked). With the switch the
candidate's test probes 114,705 plans and detects all 11 mutants, the same set as base
(`results/unit/round4-switch-fence-mutants.txt`; before the switch:
`results/unit/read-once-mutants-before-switch.txt`). The production binary built after this
addition differs from the first candidate build only in the embedded source digest. Its
disassembly differs only in immediate operands that encode string lengths and offsets of the
digest-bearing messages, and no instruction changes. It was re-run through the differential and
a confirmatory timing (below).

## Measurements

AMD EPYC-Rome KVM VM, 16 vCPUs, Ubuntu g++ 13.3.0, kernel 6.8. Shared host: other lanes and
services run, and load average was about 1.9 to 4.1 during the runs (recorded around every call in
`results.json`). No compiler of this lane ran during timing. The fixture is
`examples/accepted-proof`: the full key + leaf + request verification of a stored synthetic proof
(4,145,300-byte proof), `-id` given, exit 0 `YES` required on every timed call.

### Single thread (`-j 1`, all three stages pinned to CPU 15), 12 alternating rounds, rotating order

`results/single/`. Each round runs all six arms once, and the starting arm rotates every round.
"cand" here is the first candidate (inline limbs, before the test switch, whose production code is
identical: see above).

| arm | what | median s | mean | SD | min | max | vs stock | ranges overlap stock? |
|---|---|---|---|---|---|---|---|---|
| stock | unchanged sources, verifier/build.sh flags | 2.610 | 2.646 | 0.107 | 2.55 | 2.94 | - | - |
| stock-o3 | unchanged, -O3 | 2.555 | 2.548 | 0.071 | 2.46 | 2.68 | -2.1% | yes: noise |
| stock-v3 | unchanged, -march=x86-64-v3 | 2.620 | 2.645 | 0.083 | 2.55 | 2.83 | +0.4% | yes: noise |
| stock-pgo | unchanged, PGO (trained on 2 honest runs) | 2.655 | 2.638 | 0.055 | 2.56 | 2.70 | +1.7% | yes: noise |
| **cand** | **this change, stock flags** | **2.145** | 2.158 | 0.058 | **2.09** | **2.28** | **-17.8%** | **no** |
| cand-pgo | this change + PGO | 2.100 | 2.108 | 0.045 | 2.03 | 2.19 | -19.5% | no (vs cand: yes, so PGO adds nothing demonstrable) |

CPU time (user+sys) moves with wall time: stock median 2.60 s, cand 2.14 s. Max RSS per process is
unchanged (157.7-158.3 MiB both).

`-march=native` was built and given a 3-run pilot (2.67-2.75 s): no better than stock, so it was
not given a full comparison. A 3-round pilot over five arms (`results/pilot/`) agreed with the
main run.

### Confirmation on the final source (`results/single-final/`, `results/differential-final/`)

This is the final source (inline limbs + test switch), stock flags. 10 alternating rounds, CPU 15,
load average 2.7 to 4.7:

| arm | median s | SD | min | max |
|---|---|---|---|---|
| stock | 2.700 | 0.089 | 2.59 | 2.89 |
| cand-final | 2.215 | 0.080 | 2.12 | 2.38 |

That is -18.0% median, non-overlapping. The differential is ALL OK: the same 9 verdicts and
identical public and full output.

### Four threads (`-j 4`, CPUs 12-15), 12 alternating rounds: parallelism, reported separately

`results/threads4/`. The verifier already parallelizes the request stage (`parFor`), and its key
and leaf stages run as concurrent processes. These are this lane's numbers, not a new threading
change:

| arm | median wall s | SD | min | max | median CPU s |
|---|---|---|---|---|---|
| stock -j 4 | 1.535 | 0.037 | 1.49 | 1.61 | 2.71 |
| cand -j 4 | 1.380 | 0.030 | 1.33 | 1.41 | 2.235 |

That is -10.1% wall, non-overlapping. Compared with stock -j 1 (2.61 s), the existing threading
alone gives -41%. The two together give 2.61 s to 1.38 s (-47%). The wall gain is smaller than the
single-thread one because at -j 4 the planning sits partly off the critical path. The CPU time
still falls by 17.5%.

No new threading was added. The remaining proof-checking time is spread over many functions (see
profile), and each stage's configure/sizing must run in its own process (isolated globals, input
binding). So there is no bounded independent-check split that would be both safe and worth it.

## Correctness

### Differential, honest + eight negative cases (`results/differential/`)

`differential.py` copies the example and applies each case. Every arm (stock as reference, cand,
cand-pgo, stock-o3, stock-v3, stock-pgo) verifies it pinned to one CPU.

| case | verdict (all arms) | exit | public lines equal | full stdout equal (timings and build= masked) |
|---|---|---|---|---|
| honest | YES | 0 | yes | yes |
| proof middle byte flipped | NO: proof-refused | 1 | yes | yes |
| proof truncated by 1 byte | NO: proof-refused | 1 | yes | yes |
| key middle byte flipped | NO: key-refused | 1 | yes | yes |
| leaf entry middle byte flipped | NO: entry-refused | 1 | yes | yes |
| request middle byte flipped | NO: proof-refused | 1 | yes | yes |
| reply flipped | NO: token-range | 1 | yes | yes |
| wrong commitment ID | NO: model-statement | 1 | yes | yes |
| parameter file with an unknown line | NO: policy-call-line | 1 | yes | yes |

"Public lines" are every `accounting:`, `commitment:`, `proof of work:`, `covered:`, `result-v1`,
`YES` and `NO:` line. These include the full soundness accounting, computed by the very Real/Big
arithmetic this change touches, down to the last printed digit. The full-stdout comparison also
covers every plan line (`plan-sums`, `plan-round` with 6-decimal bits, `work:`, `link N:`,
`read: ...` counts).

### Unit tests (`results/unit/`)

- `numbers_test` (blocks/numbers, which covers real.h's identities, codes, planning and accounting),
  built as in the earlier receipt (`-O2 -fno-ipa-modref -D_GLIBCXX_ASSERTIONS -DBLK_FIELD=2`):
  **ok, 58510 checks**, exit 0, on the first candidate and on the final source. The count is the
  same as on unchanged sources.
- The same test under **AddressSanitizer + UndefinedBehaviorSanitizer** (`-fsanitize=address,undefined
  -fno-sanitize-recover=all`, -O1, _GLIBCXX_ASSERTIONS): **ok, 58510 checks**, exit 0, with no
  report (`numbers_test_asan_ubsan.log`).
- The library's honest test list (`blocks/tests/TESTS`, 89 sources, the list of SUITE.md row
  `blocks.tests`) ran through `blocks/Makefile` `test`, setting f2h1, on the first candidate and the
  unchanged base side by side. Both gave make exit 0 and 89/89 `.ran`. The 89 result lines are
  identical except one: the read-once test's probe count, explained above.
  `blocks-tests-cand-first-round.txt`, `blocks-tests-base.txt`. The same list on the final source:
  `blocks-tests-final.txt` (see SUMMARY.txt).

## Limits

- One fixture: the stored synthetic example, 64 positions. Real-model proofs have larger shapes;
  the planning share, and so the gain, may differ. GPU proving is untouched.
- Shared KVM host with no exclusive core. The claim rests on non-overlapping ranges with a gap
  (cand max 2.28 s < stock min 2.55 s), not on small ratios.
- The `-O3`/`-march`/PGO arms keep every hardening flag. They differ from stock in code
  generation only, and all of them gave identical outputs; none is a win.
- No full `run_suite.py` rerun (PR #4's coverage gate is unchanged); the differential suite plus
  the unit tests above are the evidence.

## Files

- `bench.py`: the alternating multi-arm timer (taskset, GNU time, load recorded per call; refuses
  any honest call that does not end YES).
- `differential.py`: the nine-case differential.
- `build_variant.sh`: verifier/build.sh's exact compile line plus extra flags. With no extra flags it
  reproduces the stock binary byte for byte (SHA-256 7f9efc1e...e7604394, same as PR #18).
- `build_round2.sh`, `build_round3.sh`, `build_stock_pgo.sh`: the candidate, PGO, and stock-PGO
  builds. `run_pilot.sh`, `run_main.sh`, `run_differential.sh`, `run_unit_tests.sh`: the runs, in
  that order.
- `sampler.c`, `symbolize.py`, `profile_run.sh`: the unprivileged profiler.
- `results/`: raw stdout/stderr/time per call and `results.json` per run. `profiles/`: per-stage
  flat + inclusive profiles, stock and candidate.
- `inline-limbs.patch`: the source change alone (real.h, fence.h, the read-once test).
- `read_once_mutants.sh`, `run_round4.sh`, `run_final.sh`, `run_blocks_tests_final.sh`: the
  mutation check, the switch/fence checks, and the confirmation runs on the final source.
- `stage_artifacts.sh`: copies patch and profiles here and replaces local paths.

Local paths in the logs are replaced with `<REPO>`.
