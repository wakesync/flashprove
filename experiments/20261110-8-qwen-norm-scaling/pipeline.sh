#!/usr/bin/env bash
# Steps 2 to 5 in one heavy slot (run via fp-heavy.sh), only after step 1 matched (runs/repro.done).
# Cores 0-5, at most 6 single-thread processes. Arms are deterministic and independent, so their order does not
# change any number; the order below puts registered arms before post-registration ones (PREREG amendment A-3):
#   engine check 2(a), 2(b) on the final engine code; stop if it fails
#   G1 registered candidates C0..C5            G2 registered C1P..C4P, C3P-S14, and D-R15 (descriptive)
#   G3 localisation: upstream-of-o, o floor, norm (the six rows that separate them)
#   G4 post-registration X1..X3
#   summaries, cost, identity rerun on abliterated, then the remaining localisation arms, mechanism numbers
# Kill criterion (A-3): no new group of arms starts after 03:55Z; arms not started are appended to <out>.notrun.
# Usage: pipeline.sh <cache_dir> <scratch_dir>
set -euo pipefail
cd "$(dirname "$0")"
C="$1"; X="$2"
P="$X/prep"; FR="$X/fref2"; DL=0355
mkdir -p runs "$FR"
prog() { echo "$1 $(date -u +%FT%TZ)" >> runs/pipeline.progress; }
[ -e runs/repro.done ] || { prog "no repro.done: not running"; exit 3; }
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NS_PREP="$P"
prog "slot acquired"
if ! /usr/bin/time -v taskset -c 0 python3 scaled_head.py check "$C" stock runs/engine-check.json --scratch "$FR" > runs/engine-check.log 2> runs/engine-check.time; then
  prog "ENGINE CHECK FAILED"; echo "engine check failed" > runs/ENGINE-FAIL; exit 4
fi
prog "engine check ok"
rm -f runs/cand-stock.jsonl runs/cand-stock.jsonl.notrun runs/local-stock.jsonl runs/local-stock.jsonl.notrun runs/cand-abl.jsonl runs/cand-abl.jsonl.notrun
arms() {  # arms <ckpt> <arms.json> <out.jsonl> <log> [extra args...]
  local ck="$1" af="$2" out="$3" log="$4"; shift 4
  taskset -c 0-5 python3 scaled_head.py run "$C" "$ck" "$af" "$out" --jobs 6 --scratch "$FR" --deadline $DL "$@" >> "$log" 2>&1 || prog "run failed: $af $*"
}
arms stock arms-cand.json runs/cand-stock.jsonl runs/cand-stock.log --arms C0,C1,C2,C3,C4,C5;                prog "G1 done"
arms stock arms-cand.json runs/cand-stock.jsonl runs/cand-stock.log --arms C1P,C2P,C3P,C4P,C3P-S14,D-R15;    prog "G2 done"
arms stock arms-local.json runs/local-stock.jsonl runs/local-stock.log --arms roundG-upstream,exactG-upstream,round1-o,round1-o-rhu,roundG-norm,exactG-norm; prog "G3 done"
arms stock arms-cand.json runs/cand-stock.jsonl runs/cand-stock.log --arms X1,X2,X3;                         prog "G4 done"
python3 summarise.py runs/cand-stock.jsonl > runs/cand-stock.table.md || true
[ -s runs/local-stock.jsonl ] && python3 summarise.py runs/local-stock.jsonl > runs/local-stock.table.md || true
python3 count_cost.py > runs/cost.table.md || true
prog "summaries written"
ARM=$(python3 pick_final.py || echo C0)
arms abl arms-cand.json runs/cand-abl.jsonl runs/cand-abl.log --arms "C0,$ARM,X1,X2,X3"
python3 cmp_ckpt.py > runs/cmp-ckpt.out 2>&1 || true
prog "abl identity step done ($ARM)"
arms stock arms-local.json runs/local-stock.jsonl runs/local-stock.log --skip-done
[ -s runs/local-stock.jsonl ] && python3 summarise.py runs/local-stock.jsonl > runs/local-stock.table.md || true
prog "local step done"
taskset -c 0 python3 diag_mech.py "$C" "$FR" runs/mech.json > runs/mech.log 2>&1 || prog "mech failed"
prog "pipeline done"
