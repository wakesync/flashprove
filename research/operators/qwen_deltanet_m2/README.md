# Qwen DeltaNet M2 design prototypes (research only)

These are prototypes for the M2 design. They do not prove M2. Design, PREREG and verdict: `experiments/20261105-32-qwen-deltanet-m2-design/` (DESIGN.md, RESULTS.md).

- `admit_proto.cpp` with `m1b_builder.h`: a verifier entry point `verify_from_words` that works on the M1b statement. It runs in this order:
  1. Decode every public word (it must be canonical and inside its integer class).
  2. Derive the relations from the decoded integers.
  3. Run the unchanged `lookup_verify`.

  The test suite covers huge field elements, class bounds, non-canonical words, header and length mismatches, and the #63 review's R9. `m1b_builder.h` is the #63 builder and prover, split out with a relation-only switch.
- `count_model.py`: counts columns, relations, terms, range cells and LKP keys for the lowering. It reproduces M1 and M1b exactly. It also has arm A (exact remainder bits) and arm B (lookup-exact remainders, direct LKP keys into a 2^12 table), with the M2 head added (private o, gated RMSNorm, T = 16).
- `head_reference.py`: an integer reference of one V head, from the in_proj outputs to the gated-norm output, with a float64 twin. Used for the range study.

Reproduce (CPU, about 12 min on 6 cores, about 4.5 GB RAM):

```
python3 research/operators/qwen_deltanet_m2/record.py build honest hostile model ranges
python3 research/operators/qwen_deltanet_m2/record.py ubsan   # hostile suite under UBSan, about 4 min
```

Post-review (#66): the statement words now include the conv history (3 x 384, class |H| < 2^31). The verifier's derivation is witness-free (`build(z, true)`), and every failure is a returned verdict, never exit(1). The hostile suite has 41 cases.

Research security settings only (target 10 bits).
