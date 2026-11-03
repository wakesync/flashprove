#!/usr/bin/env bash
# Fail if tracked files publish local host paths or agent-workspace names.
# Evidence logs must use neutral placeholders such as <REPO>, <HOME>,
# <WORKSPACE> or <PLANNING> instead of absolute paths of the machine that ran them.
#
# Usage: scripts/check-no-host-paths.sh [<rev>]
#   no argument: scan tracked files in the working tree
#   <rev>:       scan the tree of that commit (e.g. origin/some-branch)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

rev=()
[ $# -ge 1 ] && rev=("$1")
self=':(exclude)scripts/check-no-host-paths.sh'

# 1. Workspace / host identifiers, anywhere in the repository.
#    (Bracketed characters keep this file from matching its own patterns.)
ident='sha[d]0w|[.]mol[t]bot|ocpl[a]tform'

# 2. Absolute home-like paths in research evidence, docs and scripts.
#    /home/user is the conventional placeholder and is allowed; URLs are skipped.
abs='(^|[^A-Za-z0-9_.:/<>-])/(home/[A-Za-z0-9_.-]+|Users/[A-Za-z0-9_.-]+|root)/'

fail=0
if out=$(git grep -nIiE "$ident" "${rev[@]}" -- . "$self"); then
  printf 'host/workspace identifiers found:\n%s\n' "$out" >&2
  fail=1
fi
if out=$(git grep -nIE "$abs" "${rev[@]}" -- research docs scripts "$self" | grep -vE '/home/user([^A-Za-z0-9_.-]|$)'); then
  printf 'absolute host paths found:\n%s\n' "$out" >&2
  fail=1
fi
if [ "$fail" -ne 0 ]; then
  echo "check-no-host-paths: FAILED (use <REPO>/<HOME>/<WORKSPACE>/<PLANNING> placeholders)" >&2
  exit 1
fi
echo "check-no-host-paths: ok"
