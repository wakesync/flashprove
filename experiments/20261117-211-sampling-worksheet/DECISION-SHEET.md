# Decision sheet for Shadow (empty on purpose)

This sheet is blank. The worksheet does not choose any of these values: they are policy decisions, not facts, and none has been approved. Filling one in does not make a policy feasible by itself; run the worksheet with the filled template and read its verdict (CONDITIONAL, INELIGIBLE or MISSING INPUTS).

Known unknowns that no blank below resolves: the Qwen full-request proof cost P and the per-request receipt cost C are not measured on main and stay unknown. Queue/batch effects and all-traffic trace cost are separate unknowns and do not scale with p.

| Decision | Fleet monitoring after release | Vendor-independent proof, irreversible decision | Hardware-trusting immediate service, later review |
|---|---|---|---|
| Customer risk being covered | | | |
| Acceptable proof relation (exact match, clipped gap with numbers, other) | | | |
| Population definition and epoch close rule | | | |
| Sampling scheme and p or m | | must be p=1 | |
| Desired miss probability | | n/a (p=1), unless a soundness epsilon is entered: then a desired miss probability is required (PREREG Amendment 1) | |
| Enforceable penalty or deposit, and in what unit | | | |
| Behavioral assumptions for deterrence | | | |
| Deadline / timeout policy | | verify before action: yes/no | |
| Hardware trust assumption | n/a | n/a | |
| Retention period for receipts and proof inputs | | | |
| Who enforces, and how | | | |
| Signed off by / date | | | |
