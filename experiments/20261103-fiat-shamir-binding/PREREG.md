# PREREG: 20261103-fiat-shamir-binding
Issue: none (assigned security research lane). Lane: fiat-shamir. Date (UTC): 2026-11-03. Base commit: 29907e5fbe648b9ec246cebf9d757511a751fca2.

## Hypothesis
For the shipped synthetic accepted-proof fixture, changing each semantically relevant configuration or request input either changes the earliest challenge of the affected transcript or causes rejection before that challenge; no altered configuration verifies against the original commitment ID.

## Metric
Count byte-identical versus different first challenge/digest outputs from CPU probes using production hash/transcript code, and accepted/rejected/error outcomes from the unmodified C++ verifier. Trace configuration, model/program description, commitment ID, request tokens and coverage, and next-token binding separately; identify offline versus request-chain challenges. Distinguish invalid parsing, identity mismatch and proof failure. A challenge difference is not a soundness proof.

## Acceptance threshold
Zero accepted semantically changed configurations at the fixed original ID. Every tested semantic public-input mutation must change its affected transcript's first challenge or reject before that challenge. Report any deferred binding explicitly, even if later verification rejects. Whitespace-only configuration variants are controls, not semantic mutations. Any identical challenge for a semantic mutation triggers source-level follow-up, not an automatic forgery claim.

## Kill criterion
CPU only, no model downloads, no GPU or paid API calls. Stop full verifier experiments after 45 minutes total build/run time or a confirmed false-claim accept. If a practical vulnerability is found, keep its reproducer and details local, publish only non-sensitive work in a draft PR, and notify the coordinator. Missing prerequisites or build failures are inconclusive, not rejections.

## Runs
Five paired repetitions per mutation/control on the shipped small synthetic fixture. Deterministic inputs and fixed proof randomness, no warmup needed; repeat measurements demonstrate determinism, not independent security trials. Order baseline then mutation on odd repetitions, mutation then baseline on even repetitions. No successful runs excluded. Summarize counts and binary indicators with n, median, population SD, min/max; time, if recorded, is diagnostic only. No random seeds required unless additional synthetic vectors are used (then enumerate seeds).

## Prior art
Khovratovich, Rothblum and Soukhanov, ePrint 2025/118, attacks concrete-hash Fiat-Shamir for GKR through specially constructed circuits. Fenzi, ePrint 2026/1838, attacks sufficiently expressive generated relations with late statement binding and formalizes generated-statement hashing as a mitigation. Both full papers will be read and mapped to this implementation rather than assumed applicable from keywords. FlashProve uses constrained-interleaved-code arguments, not automatically GKR or an arbitrary R1CS compiler. Existing verifier commitment-ID tests and hash vectors are starting points. The deliverable is limited to these two attacks and CPU binding probes, not an audit or a general security claim.

## Amendments
- 2026-11-03 (after code, before results were written): the Issue line read "none (assigned security research lane)". The lane's tracking issue is #37 (wakesync/flashprove); this amendment records "Issue: #37". No change to hypothesis, metric, threshold, kill criterion or runs.
- 2026-11-03 (after code): the first run of run.py recorded `first_challenge_changed` as null for every case, because cp_verify runs its stages in child processes and prints their output only on a pass. run.py now passes `-show-stages` to the diagnostic build only (the production verdict is still taken without it) and the whole study was re-run (5 reps, all cases). The first run's verdict columns were identical to the re-run's. Also added a wall-clock total to summary.json (diagnostic only, per the Runs section).
