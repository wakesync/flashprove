# Targeted test receipt

Candidate: base 6851f4221fd29f3184853f9a160c837552b4b2df plus cpu-account-reuse.patch, no profiling modifications. Exact candidate source committed locally after measurement as `09533e579b96c7a04829060315067efd1f777dc1` (same patch, research/cpu-account-reuse-experiment); the source is reproducible from the published patch even without that experimental branch. Stock verifier binary SHA256: 7656dfb61c9f8c104b655b535b53a930d4d302aa884ebf2f199bf154571df829.

Focused existing unit test, not the full suite:

```
g++ -O2 -fno-ipa-modref -std=c++17 -DBLK_FIELD=2 -D_GLIBCXX_ASSERTIONS -Iblocks blocks/numbers/tests/numbers_test.cpp -o /path/to/cpu-numbers-test
/path/to/cpu-numbers-test
```

Compile exit 0, test exit 0, complete final line `ok, 58510 checks`. This existing test includes exact arithmetic, planning, accounting and negative cases. Test-specific by-hand plan macros are intentionally not compiled with SERVING_BUILD. These are not production verifier build flags; the timing binary uses the unchanged stock hardened verifier/build.sh.

Retained failed first attempt: the same compile was initially attempted without `-DBLK_FIELD=2`, and exited 1 at blocks/base.h:34 with `#error "compile with -DBLK_FIELD=2 (p = 2^64 - 2^32 + 1): there is no other field"`. No binary ran from that failure. Corrected compile above completed successfully. No assertions or protections were disabled to obtain the pass.

The adversarial runner additionally performed 18 complete invocations (nine cases x two arms), with equal semantic accounting/result records and expected verdicts. See README and cpu-account-adversarial/results.json. All builds/tests were serial with timings; no compiler ran during measured comparisons.
