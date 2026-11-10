#!/usr/bin/env bash
# PREREG amendment A-4 runs (fix lane), in one heavy slot. Run via fp-heavy.sh.
#   prep: PR #68's in_proj outputs for stock, cached, under PR #68's own setting (taskset -c 0-5, thread variables unset)
#   arms: arms-r2.json (make_arms_r2.py), 6 single-thread processes on cores 0-5, as pipeline.sh
# Stop rule (A-4): the slot-grant time is logged first. If the grant is at or after 07:40Z nothing runs. Otherwise no new
# group of arms starts after grant + 45 minutes or 08:10Z, whichever is earlier; arms not started go to <out>.notrun.
# Usage: run_r2.sh <cache_dir> <scratch_dir>
set -euo pipefail
cd "$(dirname "$0")"
C="$1"; X="$2"; O=runs/r2
mkdir -p "$O"
prog() { echo "$1 $(date -u +%FT%TZ)" >> "$O/r2.progress"; }
prog "slot granted"
NOW=$(date -u +%H%M)
if [ "$NOW" \> "0739" ]; then prog "grant at or after 07:40Z: not running"; exit 3; fi
DL=$(date -u -d "+45 minutes" +%H%M)
if [ "$DL" \> "0810" ]; then DL=0810; fi
prog "arm cut-off $DL"
unset OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS || true
taskset -c 0-5 python3 scaled_head.py prep "$C" stock "$X/prep" > "$O/prep.log" 2>&1
prog "prep done"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NS_PREP="$X/prep"
taskset -c 0-5 python3 scaled_head.py run "$C" stock arms-r2.json "$O/r2-stock.jsonl" --jobs 6 --scratch "$X/fref" --deadline "$DL" > "$O/r2-stock.log" 2>&1 || prog "run failed"
prog "arms done"
python3 summarise_r2.py "$O/r2-stock.jsonl" > "$O/r2-stock.table.md" 2>&1 || prog "summary failed"
taskset -c 0 python3 reviewer_constructions.py "$C" "$O/reviewer-constructions.json" > "$O/reviewer-constructions.log" 2>&1 || prog "constructions failed"
prog "r2 done"
