#!/bin/bash
# fetch_bounded.sh: run one result fetch so that it is over before the restore cut-off, or not at all.
# Used by RUNBOOK.md step 5 for both fetch paths (`tinfoil http get` and the `curl` through the
# verified proxy). Untested against Tinfoil; tested on CPU by fetch_bounded_test.py.
#
#   fetch_bounded.sh <cutoff> <grace s> <margin s> -- <command...>
#
#   <cutoff>  the restore cut-off, anything `date -u -d` accepts (e.g. 2026-12-01T14:30:00Z)
#   <grace>   seconds between TERM and KILL for a fetch that does not stop on TERM (integer >= 1)
#   <margin>  seconds kept free before the cut-off for starting the fetch and for the KILL to take
#             effect (integer >= 1)
#
# It reads the clock ONCE, computes
#   budget = cutoff - now - grace - margin
# and only if budget is strictly positive runs
#   timeout -k <grace> <budget> <command...>
# so the command, including a KILL after the grace, ends no later than cutoff - margin. The grace
# and the margin come out of the fetch budget, never out of the restore reserve after the cut-off.
# If budget is zero or negative the command is not started: go straight to restore. A duration of
# zero is never passed to timeout (for GNU timeout, 0 means no timeout at all).
#
# Exit status: the command's own status if it finished in time; 124 if it was stopped by TERM at the
# end of the budget; 137 if it ignored TERM and was killed after the grace; 121 if it was not started
# because the budget was not positive (no fetch: restore now); 2 for bad arguments or an unreadable
# cut-off or clock. Anything a stopped fetch wrote is partial.
set -u

SKIPPED=121

usage() {
  echo "usage: fetch_bounded.sh <cutoff> <grace s> <margin s> -- <command...>" >&2
  exit 2
}

[ "$#" -ge 5 ] || usage
cutoff=$1
grace=$2
margin=$3
[ "$4" = "--" ] || usage
shift 4

case "$grace" in '' | *[!0-9]*) usage ;; esac
case "$margin" in '' | *[!0-9]*) usage ;; esac
[ "$grace" -ge 1 ] || usage
[ "$margin" -ge 1 ] || usage

cut=$(date -u -d "$cutoff" +%s) || {
  echo "fetch_bounded: cannot read the cut-off '$cutoff'" >&2
  exit 2
}
now=$(date -u +%s) || {
  echo "fetch_bounded: cannot read the clock" >&2
  exit 2
}
case "$cut" in '' | *[!0-9]*) echo "fetch_bounded: bad cut-off value '$cut'" >&2; exit 2 ;; esac
case "$now" in '' | *[!0-9]*) echo "fetch_bounded: bad clock value '$now'" >&2; exit 2 ;; esac

budget=$((cut - now - grace - margin))
if [ "$budget" -le 0 ]; then
  echo "fetch_bounded: $((cut - now)) s to the cut-off, less than grace $grace s + margin $margin s + 1 s: not fetching; restore now" >&2
  exit "$SKIPPED"
fi
echo "fetch_bounded: fetch budget $budget s (+ $grace s kill grace), ends by cut-off - $margin s" >&2
exec timeout -k "${grace}s" "${budget}s" "$@"
