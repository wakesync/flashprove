#!/usr/bin/env bash
# Run count_params.py five times against the pinned revision and compare outputs by SHA-256.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p runs
for i in 1 2 3 4 5; do
  python3 count_params.py > "runs/run$i.json"
done
sha256sum runs/run*.json > runs/SHA256SUMS
n=$(cut -d' ' -f1 runs/SHA256SUMS | sort -u | wc -l)
echo "distinct outputs: $n of 5"
[ "$n" -eq 1 ]
