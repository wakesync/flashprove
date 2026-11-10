# Qwen Gated DeltaNet head with the RNG/LKP range check (M1b, research only)

This is the M1 head (`../qwen_deltanet/`, PR #47): one 128 x 128 state, T = 4, F = 12 staged floor. Here it is proved with the approximate range check of `blocks/iop/rng.h` (RNG, with its LKP digit lookup) instead of 19-bit decomposition of each quotient cell. Experiment and verdict: `experiments/20261105-32-qwen-deltanet-m1b-lookup/`.

- `lookup.h` composes RNG with the wide product oracle in one proximity-test group (sizing, plan, bind, verifier). It also holds `rng_prove_research`, a copy of `rng_prove` used only by hostile provers.
- `test.cpp` is derived from `../qwen_deltanet/test.cpp`. Its range cells are S', M, delta_lo and delta_hi, laid directly on product row a. Remainders are exact bits. Modes are `honest` and `hostile`.
- `record.py` builds fixtures (M1 `reference.py`), compiles, and runs H1, H2 and H3b. It writes `evidence.json` and the experiment's `runs/`.

Reproduce (CPU, about 30 min on 6 cores, about 4.5 GB RAM):

```
python3 research/operators/qwen_deltanet_lookup/record.py build honest hostile h3b
```

Not a serving protocol. These are research security settings (target 10 bits). See RESULTS.md for the soundness note and open risks.
