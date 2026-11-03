#!/bin/bash
# Copies the source patch and profiles into this folder and replaces the local checkout prefix and
# home directory with placeholders in every text artifact. Research harness only.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd -P)
top=$(cd "$here/../../.." && pwd -P)
cd "$top"
git diff HEAD -- blocks/numbers/real.h blocks/fence.h blocks/numbers/tests/planners_read_once_test.cpp > "$here/inline-limbs.patch"
rm -f "$here/real-h-inline-limbs.patch"
mkdir -p "$here/profiles"
for p in stock3:stock limbs:cand; do
  from=${p%%:*}; to=${p##*:}
  rm -rf "$here/profiles/$to"; mkdir -p "$here/profiles/$to"
  cp prof/$from/*.profile.txt prof/$from/run.stdout "$here/profiles/$to/"
done
home=$(cd ~ && pwd -P)
find "$here" -type f \( -name '*.txt' -o -name '*.json' -o -name '*.stdout' -o -name '*.stderr' -o -name '*.log' -o -name '*.time' \) -print0 |
  xargs -0 sed -i -e "s#$top#<REPO>#g" -e "s#${top%/*}#<PROJECTS>#g" -e "s#$home#<HOME>#g"
grep -rlI -e "$home" -e "$(id -un)" "$here" || echo "no host paths left"
