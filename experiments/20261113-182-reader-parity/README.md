# CPU parameter-reader parity: blocked proposal

Part of #182. Read [RESULTS.md](RESULTS.md) first: **PARTIAL, no compiled or executed tests**.

The proposed host-reader change admits dense table-line groups only when the sigmoid words
are zero. It leaves all parsing and other admission rules untouched. This is source intent;
no successful behavior is proved by this experiment. The unmodified verifier remains
responsible for public-table recomputation and standard-form checks. Dense producer execution,
proof validity and model support are outside scope and unestablished.

The first release build was refused by the unit harness's output-directory safety check.
No number here represents a performance or verification measurement. The receipt records only
that refusal. The registered matrix and UBSan checks were not run.

## Continuation commands, not run successfully here

From the repository root, after a separately authorized continuation has selected a safe
output directory (all ancestors must satisfy the harness's ownership/permissions checks):

```text
bash prover/tests/unit.sh build tests/parameter_file_tables_test.cpp <safe-output>
<safe-output>/parameter_file_tables_test <policy.txt>
bash prover/tests/unit.sh both tests/parameter_file_one_bits_test.cpp <safe-output> examples/target_small_f2/policy.txt
bash prover/tests/unit.sh both tests/parameter_file_one_place_test.cpp <safe-output> examples/target_small_f2/policy.txt
```

The probe emits parse and admission separately. Its exit codes are 0 (admitted), 1 (parse
rejection), 2 (limit rejection), and 3 (usage/read failure). A subsequent lane must implement
and retain the complete fixture suite, compare the pinned original reader against the patch,
build UBSan variants, and run unmodified cp_verify planning calls. These commands alone do not
reproduce the missing matrix and are not a complete regression runner.
