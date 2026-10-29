#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--restart" ) ]]; then
  echo "Usage: bash .devcontainer/start.sh [--restart]"; exit 2
fi
# Never kill an unrelated process if a PID file was left behind.
running() {
  kill -0 "$1" 2>/dev/null && [[ "$(awk '{print $3}' "/proc/$1/stat" 2>/dev/null)" != "Z" ]]
}
if [[ -f data/dashboard.pid ]]; then
  pid=$(cat data/dashboard.pid)
  if [[ "$pid" =~ ^[0-9]+$ ]] && running "$pid"; then
    if [[ ! -r "/proc/$pid/cmdline" ]] || ! tr '\0' ' ' < "/proc/$pid/cmdline" | grep -Eq 'python[^ ]* .*run_local.py serve --port 8765( |$)'; then
      echo "PID file belongs to another process. Nothing was stopped. Inspect data/dashboard.pid locally."; exit 1
    fi
    if [[ "${1:-}" != "--restart" ]]; then
      echo "JobHunter is already running. Open the private forwarded port 8765."; exit 0
    fi
    kill -TERM "$pid"
    for _ in {1..30}; do
      if ! running "$pid"; then break; fi
      sleep 1
    done
    if running "$pid"; then
      echo "The previous process has not stopped yet. No second server was started."; exit 1
    fi
  fi
fi
nohup python run_local.py serve --port 8765 > data/dashboard.log 2>&1 &
printf '%s\n' "$!" > data/dashboard.pid
sleep 1
if ! running "$(cat data/dashboard.pid)"; then
  echo "JobHunter failed to start. Inspect the ignored data/dashboard.log locally."; exit 1
fi
echo "JobHunter started with automatic discovery. Open port 8765 and keep its visibility PRIVATE."
