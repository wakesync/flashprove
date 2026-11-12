#!/bin/bash
# stamp.sh <window file> <command...>: runs the command and appends one line to <window file>:
#   <program name> <start> <end> <exit status>
# with start and end as epoch seconds with nanoseconds (date +%s.%N), read just before the command
# starts and just after it ends. run_job.sh puts it in front of /usr/bin/time in GPU_RUN, so that each
# cp_commit and cp_prove has a wall-clock window against which the 100 ms GPU samples are cut. The
# command's exit status is passed on unchanged. A failure to write the line is reported on stderr and
# does not change the exit status (the window is then missing, and the run is reported without it).
set -u
w=$1
shift
name=unknown
for a in "$@"; do # the first argument that names a cp_ program, else the last word of the command
  case ${a##*/} in cp_*) name=${a##*/} && break ;; esac
done
start=$(date +%s.%N)
"$@"
rc=$?
end=$(date +%s.%N)
printf '%s %s %s %s\n' "$name" "$start" "$end" "$rc" >>"$w" || echo "stamp.sh: could not write $w" >&2
exit "$rc"
