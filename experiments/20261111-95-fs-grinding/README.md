# Grinding the weakest Fiat-Shamir positions round (issue #95, research only)

What this is: a harness that grinds the repository's own Fiat-Shamir hash chain (`blocks/chain/chain.h`) at one planned round of the research convolution profile of PR #67 (`research/operators/qwen_ops/proof.cpp`, F = 12, target 10 bits, 6 bits of proof of work), and counts how often the drawn positions all land in an agreeing set whose size the plan's own bound allows. Pre-registration: `PREREG.md`. Numbers and verdict: `RESULTS.md`.

What it proves or verifies: nothing. It builds no proof and runs no verifier. It reuses the library's planner (to pick the round and read t, n, w and the error bound), and the library's chain query, work test and position draw (`Chain::message`, `Chain::prefix`, `Chain::step`, `Chain::draw_position`).

What the prover is allowed to vary: the nonce (arm A), its own message at the round, standing for a re-commitment with fresh private coins (arm B). Arm C is arm B without proof of work, a cost control.

What is not covered: a whole accepting proof, any other round, a constructed false witness, the production setting. No security level is claimed. See `RESULTS.md`, "What is NOT established".

Files: `grind.cpp` (harness; includes `proof.cpp` unchanged, with its `main` renamed), `run.py` (build, plan, registered runs, report with exact Clopper-Pearson intervals in the standard library), `env.py` (writes `ENV.json`), `runs/` (raw JSON lines per arm, the plan, the library's accounting print, the build record, the summary).

Reproduce: the commands at the end of `RESULTS.md`.
