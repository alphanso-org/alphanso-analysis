#!/usr/bin/env bash
# Detached one-shot entry point for LLNL workstation runs.
#
# Default:
#   ./run.sh
# starts scripts/run_all.sh under nohup, writes results/run.pid, and returns.
#
# Foreground/debug:
#   ./run.sh --foreground

set -euo pipefail

cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"
LOG_DIR="$ROOT_DIR/results/runlogs"
PID_FILE="$ROOT_DIR/results/run.pid"
mkdir -p "$LOG_DIR" "$ROOT_DIR/results"

if [[ "${1:-}" == "--foreground" ]]; then
    shift
    exec "$ROOT_DIR/scripts/run_all.sh" "$@"
fi

if [[ -f "$PID_FILE" ]]; then
    old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
        echo "A benchmark appears to already be running: PID $old_pid"
        echo "Log: $(readlink -f "$LOG_DIR/latest.log" 2>/dev/null || true)"
        exit 1
    fi
fi

stamp="$(date +%Y%m%d_%H%M%S)"
log="$LOG_DIR/run_${stamp}.log"
ln -sfn "$(basename "$log")" "$LOG_DIR/latest.log"

launcher=(bash "$ROOT_DIR/scripts/run_all.sh" "$@")
if command -v setsid >/dev/null 2>&1; then
    nohup setsid "${launcher[@]}" > "$log" 2>&1 < /dev/null &
else
    nohup "${launcher[@]}" > "$log" 2>&1 < /dev/null &
fi
pid="$!"
printf '%s\n' "$pid" > "$PID_FILE"

echo "Started SaG4n timing benchmark in the background."
echo "PID: $pid"
echo "Log: $log"
echo "Status: ./scripts/status.sh"
