#!/usr/bin/env bash
# Show detached benchmark status and the latest log tail.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
PID_FILE="$ROOT_DIR/results/run.pid"
LOG_FILE="$ROOT_DIR/results/runlogs/latest.log"

if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "RUNNING pid=$pid"
    else
        echo "NOT RUNNING (stale pid=${pid:-unknown})"
    fi
else
    echo "NOT RUNNING (no pid file)"
fi

if [[ -f "$LOG_FILE" || -L "$LOG_FILE" ]]; then
    echo
    echo "Log: $(readlink -f "$LOG_FILE" 2>/dev/null || echo "$LOG_FILE")"
    echo "---- tail -80 ----"
    tail -80 "$LOG_FILE"
else
    echo "No log yet at $LOG_FILE"
fi
