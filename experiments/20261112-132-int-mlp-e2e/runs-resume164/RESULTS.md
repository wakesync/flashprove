# Amendment A-2 (issue #164): regeneration of the abliterated state after layer 30. Results

**Outcome vs the amendment: REPRODUCED.** Every row the rerun wrote for abliterated layers 0 to 30 equals PR #138's committed row: 374 of 374 rows (31 `divergence-abl.jsonl`, 31 `ranges-abl.jsonl`, 312 `heads-abl.jsonl`), no differing row. Excluded by name, only: `seconds` and `mix_s` in the divergence rows (wall clock). Layer 30 equals PR #138's layer-30 row, which PR #138 labels post-cutoff descriptive evidence; equality there says only that the rerun reproduces that row, not that layer 30 was inside PR #138's registered run.

This is a regeneration of state, not a new measurement. It adds no token number, no range number and no bar verdict. Measured, unreplicated (one deterministic rerun; the comparison is the result).

## Plain-language summary
PR #138 stopped after layer 30 of 64 and its saved state was lost. We ran the same code (`1960ec5`) on the same pinned weights and prompts again up to layer 30, and every number it wrote matches PR #138's committed numbers to the last bit. The state after layer 30 now has a committed sha256, so #150 part B can resume from it.

## 1. Run record
- Code at the run: `1960ec5f81b4ad9fd092bed7bbaa7571a56fb4cf` (PR #138's run commit), executed unchanged from a checkout of that commit: `mlp_e2e.py run <state> <runs> full`. Launcher: `resume164_entry.py` writes the Python pid then execs `mlp_e2e.py` (same pid); watchdog `resume164_supervisor.py` polls every 2 s and signals that pid, never `/usr/bin/time` (planning repo, not committed here; behaviour as in PREREG A-2).
- Gate: `flock bigmem.lock fp-heavy.sh taskset -c 10-15 /usr/bin/time -v -o run.time python3 <entry> ...`. Slot granted 2026-11-13T05:50:00Z, MemAvailable 13.9 GB (>= 12 GB rule), cores 10 to 15.
- Stop: rule (1), layer 30 done. The `progress.log.jsonl` line for layer 30 appeared, the watchdog sent SIGTERM at 2026-11-13T07:02:00Z; `time -v`: "Command terminated by signal 15", elapsed 1:12:00. No row for layer 31 was written before the signal (none to report). No other stop rule fired (RSS, disk, 120 min budget, 07:45Z hard stop).
- Weights: fetched tensors' sha256 equal PR #138's committed manifests: stock 226 of 226 tensors and 319 of 319 embedding rows, abliterated 198 of 198 tensors; no tensor outside PR #138's manifests (descriptive, not part of the check).
- Peak RSS (`time -v`, largest single process): 8,493,992 kB (8.1 GiB). Watchdog sum of VmRSS over the process tree at layer ends: max 5,060,308 kB. Free disk on scratch: min 51.7 GB. User 7,399 s, system 3,126 s, 243% CPU.
- Per-layer seconds (`layer_s` in `rerun/progress.log.jsonl`, 31 layers): median 134.3, min 121.3, max 165.5. Descriptive: host shared and loaded.
- `run.stderr`: one multiprocessing resource_tracker warning (6 leaked semaphores at shutdown), a consequence of the SIGTERM stop.

## 2. The state after layer 30 (for #150 part B)
- `ckpt.npz`: sha256 `22dff8b92107511838e50e4b26d6e91a2b55d09064711c638042c4c18fb80009`, 183,551,075 B; meta `leg abl`, `next_layer 31`, `prompt_set full`; 33 arrays, per-array sha256 in `state-ckpt-l30-inventory.json`.
- `x16.npz` (state after layer 16): sha256 `67dde0e845de248c26838448b1df50bd1b6ed8eb2b1b03ddb40cd9feff3c53d5`, 183,551,023 B.
- Both files stay outside the repository, in the lane's scratch directory, and are registered as live for #150 part B. Their hashes are in `state-sha256.json`.

## 3. What this establishes, and what it does not
- Establishes: PR #138's code at `1960ec5` on these weights and prompts is bit-reproducible through abliterated layer 30 on this host (different core pinning, same thread counts), including the duplicate path XM18#2 rows; and a hashed state after layer 30 exists for a resume.
- Does not establish: anything about layers 31 to 63, the final norm, lm_head, logits, the token-agreement bar, the stock leg, or any proof. It does not move PR #138's cutoff: layer 30 remains post-cutoff evidence for PR #138. It is not an independent replication of PR #138's arithmetic (same code, same host class). Reproducibility on other hardware or BLAS builds is not tested.

## 4. Deviations
- None from amendment A-2. Disclosed: the comparator was tested on PR #138's committed files (self-equal, and a one-ulp change caught) and the watchdog on a dummy process before the run, as registered; neither touched the forward.

## 5. Files (this directory)
`compare.json` (row check, per file), `summary.json`, `watchdog.log`, `run.time` (`time -v` block), `progress.log` (slot grant), `run.log`, `run.stderr`, `state-sha256.json`, `state-ckpt-l30-inventory.json`, `ENV.json`, `rerun/` (the rerun's `divergence/ranges/heads-abl.jsonl`, `progress.log.jsonl`, `manifest-{stock,abl}.json`). Host paths replaced by placeholders. PR #138's `runs/` files are not modified.
