#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
# Own-process PID check avoids an accidental duplicate on an ordinary restart.
if [[ -f data/dashboard.pid ]] && kill -0 "$(cat data/dashboard.pid)" 2>/dev/null; then
  echo "JobHunter is already running. Open the private forwarded port 8765."
  exit 0
fi
nohup python run_local.py serve --port 8765 > data/dashboard.log 2>&1 &
printf '%s\n' "$!" > data/dashboard.pid
sleep 1
if ! kill -0 "$(cat data/dashboard.pid)" 2>/dev/null; then
  echo "JobHunter failed to start. Inspect the ignored data/dashboard.log locally."
  exit 1
fi
echo "JobHunter started. Open port 8765 and keep its visibility PRIVATE."
