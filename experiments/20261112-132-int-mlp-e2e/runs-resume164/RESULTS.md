# Amendment A-2 (issue #164): regeneration of the abliterated state after layer 30. Results

**Outcome vs the amendment: REPRODUCED.** Every row the rerun wrote for abliterated layers 0 to 30 equals PR #138's committed row: 374 of 374 rows (31 `divergence-abl.jsonl`, 31 `ranges-abl.jsonl`, 312 `heads-abl.jsonl`), no differing row. Excluded by name, only: `seconds` and `mix_s` in the divergence rows (wall clock). Layer 30 equals PR #138's layer-30 row, which PR #138 labels post-cutoff descriptive evidence; equality there says only that the rerun reproduces that row, not that layer 30 was inside PR #138's registered run.

This is a regeneration of state, not a new measurement. It adds no token number, no range number and no bar verdict. Measured, unreplicated (one deterministic rerun; the comparison is the result).

## Plain-language summary
PR #138 stopped after layer 30 of 64 and its saved state was lost. We ran the same code (`1960ec5`) on the same pinned weights and prompts again up to layer 30, and every number it wrote matches PR #138's committed numbers to the last bit. The state after layer 30 now has a committed sha256, so #150 part B can resume from it.

## 1. Run record
- Code at the run: `1960ec5f81b4ad9fd092bed7bbaa7571a56fb4cf` (PR #138's run commit), executed unchanged from a checkout of that commit: `mlp_e2e.py run <state> <runs> full`. Launcher: `resume164_entry.py` writes the Python pid then execs `mlp_e2e.py` (same pid); watchdog `resume164_supervisor.py` polls every 2 s and signals that pid, never `/usr/bin/time` (planning repo, not committed here; behaviour as in PREREG A-2).
- Gate: `flock bigmem.lock fp-heavy.sh taskset -c 10-15 /usr/bin/time -v -o run.time python3 <entry> ...`. Slot granted 2026-11-13T05:50:00Z, cores 10 to 15. MemAvailable at the grant, as recorded in `progress.log`: 13,866,352 kB; `/proc/meminfo` kB are KiB, so this is 13.224 GiB (13,866,352 / 1,048,576 = 13.22398, rounding corrected in round 2; 14.199 GB). The launcher's admission check compares the value with 12 x 1024 x 1024 kB, so the floor as implemented is 12 GiB (the PREREG text says "12 GB"); the value was above it. The same reading applies to two stop rules of A-2: the supervisor implements "RSS over 14 GB" as 14 x 1024 x 1024 kB (14 GiB) and "free disk under 21 GB" as 21 x 1024^3 bytes (21 GiB), as the round-2 review notes (https://github.com/wakesync/flashprove/pull/167#issuecomment-6849329507); neither came near firing (RSS max 5,060,308 kB, disk min 51.7 GiB, see the RSS and disk line below).
- Stop: rule (1), layer 30 done. The `progress.log.jsonl` line for layer 30 appeared, the watchdog sent SIGTERM at 2026-11-13T07:02:00Z; `time -v`: "Command terminated by signal 15", elapsed 1:12:00. No row for layer 31 was written before the signal (none to report). No other stop rule fired (RSS, disk, 120 min budget, 07:45Z hard stop).
- Weights: fetched tensors' sha256 equal PR #138's committed manifests: stock 226 of 226 tensors and 319 of 319 embedding rows, abliterated 198 of 198 tensors; no tensor outside PR #138's manifests (descriptive, not part of the check).
- Peak RSS (`time -v`, largest single process): 8,493,992 kB (8.1 GiB). Watchdog sum of VmRSS over the process tree, recorded at the 31 layer ends: max 5,060,308 kB (KiB). Free disk on the scratch filesystem: 51.7 GiB, the minimum over the 31 samples the watchdog recorded at layer ends (`disk_free_gb` in `watchdog.log` is free bytes / 1024^3, so GiB despite the field name). The watchdog checked disk at every 2 s poll but logged only these 31 samples, so this is not a minimum over every poll. User 7,399 s, system 3,126 s, 243% CPU.
- Per-layer seconds (`layer_s` in `rerun/progress.log.jsonl`, 31 layers): median 134.3, min 121.3, max 165.5. Descriptive: host shared and loaded.
- Units and record notes (added after review, no measured value changed): Linux `kB` in `progress.log`, `watchdog.log` (`rss_kb`) and `run.time` are KiB. In `summary.json` (a generated run output, left unchanged) the key `watchdog_disk_free_gb_min` holds GiB, and `time_v` has null for the signal and elapsed lines, a quirk of the summary script's line parsing; `run.time` records "Command terminated by signal 15" and elapsed 1:12:00. `ENV.json`'s copy of `time_v` now carries those two values from `run.time` verbatim, with a `units_note`.
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
