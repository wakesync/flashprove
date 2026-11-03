# Public-coordinate product proof, research v1

This is a small actual commitment/PSC/IOPP milestone, NOT a router proof. It is isolated from serving and model admission. All upstream headers are unchanged. `product.h` derives its composite sizing function from Apache-2.0 `blocks/toy/product.h`.

## Statement and composition

The verifier supplies the sized run and an ordered list of 1..64 `(row, column, value)` coordinates. Rows are 0=a, 1=b, 2=c; values are canonical Goldilocks base-field elements. Length is a power of two (log length 1..20). The witness satisfies `a[i]*b[i]=c[i]` everywhere and each specified entry equals its public value. Unspecified coordinates remain existential. Duplicate coordinates are allowed and separately counted; inconsistent duplicate values describe a false statement.

`coordinate_size` is the supported constructor. As with upstream toy APIs, C++ run/plan objects are trusted caller inputs, not a wire format. There is no parser or untrusted configuration interface. Do not mutate a run's shape, stages or coordinate count after sizing. This is not a production API.

The Binder uses a new label `0x46504331` and configuration run name `research-public-coordinate-product-v1`. The coordinate list length, row, column and value enter the first query via a statement handle. The verifier decision receives only bound handles. Each coordinate adds a unit-vector linear claim to the SAME oracle group returned by product PSC, before IOPP. It does not commit a detached witness or merely hash public values. Row bits are low and column bits high, as upstream specifies.

The derivative planner adds the exact number of coordinate claims to BOTH `GroupLoad.batched_rows` and the input row count to `plan_iopp`. Product PSC masks and samples are unchanged; linear coordinate claims consume no fresh masks or standalone transcript messages. Existing runtime plan checks remain enabled. This accounting is an implementation proposal requiring independent review, not a soundness/hiding theorem. Public coordinate disclosure intentionally narrows the relation; no new hiding claim is made.

## Test

From repository root:

```
g++ -std=c++17 -O2 -Wall -Wextra -fno-ipa-modref -DBLK_FIELD=2 -DBLK_HASH=1 -I blocks research/operators/public_binding/test.cpp -o research/operators/public_binding/test.bin
research/operators/public_binding/test.bin
```

`python3 research/operators/public_binding/record.py` runs both commands and records exact exits, elapsed times, output and source hashes in `evidence.json`.

CPU only, no external dependencies or network. The fixture uses 16 entries, 3 coordinates, deterministic test coins, target 10 and query work 6. These are test parameters, NOT a security level.

The dishonest prover in `test.cpp` binds the verifier's true statement and commits a valid-product table with a wrong bound coordinate. It then supplies truthful coordinate targets to its own IOPP, without changing the bound statement. The resulting complete malicious proof must be rejected by the unchanged verifier. This distinguishes enforcement of linear claims from public-input hashing alone. Three attacks cover a, b and c. Other checks cover honest acceptance, nine row/column/value input mutations, domain changes, sampled byte corruption and truncation, trailing bytes, integer-remainder field multiplication checks and exhaustive coordinate coefficient checks. The independent checks are arithmetic/layout checks, NOT an independent implementation of the cryptographic verifier.

## Remaining gaps

No router shared wires, Booleanity, range, permutation/order, selection or normalization proof. No full-model, GPU, security-level, hiding or publisher-equivalence claims. No independent verifier, Lean theorem or formal accounting proof. Tests are bounded synthetic evidence; malicious strategies are not exhaustive. Independent reviewer required before adoption. Do not merge this research milestone as support for a model.
