#!/bin/bash
# fetch_bounded.sh: run one result fetch so that it is over before the restore cut-off, or not at all.
# Used by RUNBOOK.md step 5 for both fetch paths (`tinfoil http get` and the `curl` through the
# verified proxy). Untested against Tinfoil; tested on CPU by fetch_bounded_test.py.
#
#   fetch_bounded.sh <cutoff> <grace s> <margin s> -- <command...>
#
#   <cutoff>  the restore cut-off, anything `date -u -d` accepts (e.g. 2026-12-01T14:30:00Z). It must
#             be at most MAX_AHEAD (6 h) after the clock reading, so that a typo far in the future
#             is refused instead of leaving the fetch effectively unbounded.
#   <grace>   seconds between TERM and KILL for a fetch that does not stop on TERM
#   <margin>  seconds kept free before the cut-off for starting the fetch and for the KILL to take
#             effect
#   grace and margin: canonical decimal integers from 1 to 3600 (digits only, no sign, no leading
#   zero, no spaces). `08`, `010`, `-0`, `+5`, ` 5` are refused (bash arithmetic would read a leading
#   zero as octal).
#
# All inputs are validated BEFORE any arithmetic: grace and margin as above; the cut-off and the
# clock reading (`date -u +%s`) as canonical 10-digit epoch seconds between EPOCH_MIN and EPOCH_MAX.
# Any other value (empty, negative, a sign, a leading zero, too many digits, 2^63 or 2^64-1, a year
# before 2001 or after 2099) is refused with exit 2 and nothing is started. With these bounds every
# intermediate value below is far inside 64-bit range, so nothing can wrap.
#
# It reads the clock ONCE, computes
#   left   = cutoff - now                       (refused, exit 2, if left > MAX_AHEAD)
#   budget = left - grace - margin
# and only if budget is strictly positive runs
#   timeout -k <grace> <budget> <command...>
# so the command, including a KILL after the grace, ends no later than cutoff - margin. The grace
# and the margin come out of the fetch budget, never out of the restore reserve after the cut-off.
# If budget is zero or negative the command is not started: go straight to restore. A duration of
# zero is never passed to timeout (for GNU timeout, 0 means no timeout at all).
#
# Assumptions (no hard real-time claim): the bound holds against the host clock as read once, so
# that clock must be synchronised (RUNBOOK.md window sheet: NTP check before the window) and must
# not step during the fetch; the delay between the clock read and the start of the command, plus
# the time the KILL takes, must fit in the margin; `timeout` signals the command's process group,
# so a descendant that leaves it (e.g. via `setsid`) is not stopped by this helper.
#
# Exit status: the command's own status if it finished in time; 124 if it was stopped by TERM at the
# end of the budget; 137 if it ignored TERM and was killed after the grace; 121 if it was not started
# because the budget was not positive (no fetch: restore now); 2 for bad arguments, an unreadable or
# out-of-range cut-off or clock, or a cut-off more than MAX_AHEAD ahead. Anything a stopped fetch
# wrote is partial.
set -u
export LC_ALL=C

SKIPPED=121
MAX_SECONDS=3600            # upper bound for grace and for margin
EPOCH_MIN=1000000000        # 2001-09-09T01:46:40Z, the smallest 10-digit epoch value
EPOCH_MAX=4102444800        # 2100-01-01T00:00:00Z
MAX_AHEAD=21600             # 6 h: the largest accepted distance from now to the cut-off

usage() {
  echo "usage: fetch_bounded.sh <cutoff> <grace s> <margin s> -- <command...>  (grace, margin: 1..$MAX_SECONDS, canonical decimal)" >&2
  exit 2
}

# Canonical decimal 1..9999 (no sign, no leading zero, no spaces), then the explicit bound. String
# checks only before the bound is known to hold, so no arithmetic sees an unvalidated value.
small_ok() {
  case "$1" in
    [1-9] | [1-9][0-9] | [1-9][0-9][0-9] | [1-9][0-9][0-9][0-9]) ;;
    *) return 1 ;;
  esac
  [ "$((10#$1))" -le "$MAX_SECONDS" ]
}

# Canonical 10-digit epoch seconds within [EPOCH_MIN, EPOCH_MAX].
epoch_ok() {
  case "$1" in
    [1-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) return 1 ;;
  esac
  [ "$((10#$1))" -ge "$EPOCH_MIN" ] && [ "$((10#$1))" -le "$EPOCH_MAX" ]
}

[ "$#" -ge 5 ] || usage
cutoff=$1
grace=$2
margin=$3
[ "$4" = "--" ] || usage
shift 4

small_ok "$grace" || usage
small_ok "$margin" || usage

cut=$(date -u -d "$cutoff" +%s) || {
  echo "fetch_bounded: cannot read the cut-off '$cutoff'" >&2
  exit 2
}
now=$(date -u +%s) || {
  echo "fetch_bounded: cannot read the clock" >&2
  exit 2
}
epoch_ok "$cut" || { echo "fetch_bounded: cut-off value '$cut' is not epoch seconds in $EPOCH_MIN..$EPOCH_MAX" >&2; exit 2; }
epoch_ok "$now" || { echo "fetch_bounded: clock value '$now' is not epoch seconds in $EPOCH_MIN..$EPOCH_MAX" >&2; exit 2; }

# All four values are now bounded (grace, margin <= 3600; cut, now <= 4102444800): no overflow.
left=$((10#$cut - 10#$now))
if [ "$left" -gt "$MAX_AHEAD" ]; then
  echo "fetch_bounded: the cut-off is $left s ahead, more than $MAX_AHEAD s: refusing (typo in the cut-off?)" >&2
  exit 2
fi
budget=$((left - 10#$grace - 10#$margin))
if [ "$budget" -le 0 ]; then
  echo "fetch_bounded: $left s to the cut-off, less than grace $grace s + margin $margin s + 1 s: not fetching; restore now" >&2
  exit "$SKIPPED"
fi
echo "fetch_bounded: fetch budget $budget s (+ $grace s kill grace), ends by cut-off - $margin s" >&2
exec timeout -k "${grace}s" "${budget}s" "$@"
