#!/usr/bin/env bash
# Steps 2 to 5, called by repro_run2.sh inside its heavy slot and only after step 1 matched (PREREG amendment A-2).
# Cores 0-5, at most 6 single-thread processes.
#   engine check 2(a), 2(b) on the final engine code; stop if it fails
#   candidates (stock), summary, cost; pick the identity-rerun arm; C0 + that arm + X1..X3 on abliterated
#   localisation (stock), summary; mechanism numbers
# PREREG kill criterion as amended in A-3: no new arm starts after 03:55Z (scaled_head.py --deadline checks it before
# each group of 6 arms and lists the arms it did not start in <out>.notrun).
# Usage: pipeline.sh <cache_dir> <scratch_dir>
set -euo pipefail
cd "$(dirname "$0")"
C="$1"; X="$2"
P="$X/prep"; FR="$X/fref2"; DL=0355   # PREREG amendment A-3 (registered: 0340)
mkdir -p runs "$FR"
prog() { echo "$1 $(date -u +%FT%TZ)" >> runs/pipeline.progress; }
[ -e runs/repro.done ] || { prog "no repro.done: not running"; exit 3; }
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NS_PREP="$P"
if ! /usr/bin/time -v taskset -c 0 python3 scaled_head.py check "$C" stock runs/engine-check.json --scratch "$FR" > runs/engine-check.log 2> runs/engine-check.time; then
  prog "ENGINE CHECK FAILED"; echo "engine check failed" > runs/ENGINE-FAIL; exit 4
fi
prog "engine check ok"
rm -f runs/cand-stock.jsonl runs/cand-stock.jsonl.notrun
/usr/bin/time -v taskset -c 0-5 python3 scaled_head.py run "$C" stock arms-cand.json runs/cand-stock.jsonl --jobs 6 --scratch "$FR" --deadline $DL > runs/cand-stock.log 2> runs/cand-stock.time
python3 summarise.py runs/cand-stock.jsonl > runs/cand-stock.table.md
python3 count_cost.py > runs/cost.table.md
prog "cand done"
ARM=$(python3 pick_final.py)
rm -f runs/cand-abl.jsonl runs/cand-abl.jsonl.notrun
taskset -c 0-5 python3 scaled_head.py run "$C" abl arms-cand.json runs/cand-abl.jsonl --jobs 6 --scratch "$FR" --arms "C0,$ARM,X1,X2,X3" --deadline $DL > runs/cand-abl.log 2>&1
python3 cmp_ckpt.py > runs/cmp-ckpt.out || true
prog "abl identity done ($ARM)"
rm -f runs/local-stock.jsonl runs/local-stock.jsonl.notrun
/usr/bin/time -v taskset -c 0-5 python3 scaled_head.py run "$C" stock arms-local.json runs/local-stock.jsonl --jobs 6 --scratch "$FR" --deadline $DL > runs/local-stock.log 2> runs/local-stock.time
python3 summarise.py runs/local-stock.jsonl > runs/local-stock.table.md
prog "local done"
taskset -c 0 python3 diag_mech.py "$C" "$FR" runs/mech.json > runs/mech.log 2>&1 || prog "mech failed"
prog "pipeline done"
