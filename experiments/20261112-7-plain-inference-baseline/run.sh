#!/usr/bin/env bash
# Runs one route_bench.py mode under the shared route lock.
# Required env (supplied privately, never committed): BRIDGE_URL, BRIDGE_KEY_FILE, BRIDGE_MODEL, ROUTE_LOCK.
set -euo pipefail
cd "$(dirname "$0")"
if [ "$1" = analyze ]; then exec python3 route_bench.py analyze; fi
: "${BRIDGE_URL:?}" "${BRIDGE_KEY_FILE:?}" "${BRIDGE_MODEL:?}" "${ROUTE_LOCK:?}"
exec flock "$ROUTE_LOCK" python3 route_bench.py "$1"
