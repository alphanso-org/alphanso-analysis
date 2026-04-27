#!/usr/bin/env bash
# run_all.sh — orchestrate the full benchmark from a clean lab box.
#
# Stops on the first failure and prints how to re-run that step (each
# script is independently re-runnable / idempotent). Total wall: ~3-5h.

set -euo pipefail
cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
mkdir -p "$ROOT_DIR/results"
trap 'rm -f "$ROOT_DIR/results/run.pid"' EXIT
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/deps_mode.sh"

STEPS=(
    "00_install_conda_deps.sh"
    "01_install_geant4.sh"
    "02_build_sag4n.sh"
    "03_install_alphanso.sh"
    "04_setup_nuclear_data.sh"
)

run_step() {
    local step="$1"
    echo
    echo "============================================================"
    echo "== STEP $step"
    echo "============================================================"
    if ! "$ROOT_DIR/scripts/$step"; then
        echo
        echo "ERROR: $step failed."
        echo "Re-run just this step with:"
        if use_system_deps; then
            echo "  USE_SYSTEM_DEPS=1 $ROOT_DIR/scripts/$step"
        else
            echo "  $ROOT_DIR/scripts/$step"
        fi
        echo "Steps are idempotent — partial state is preserved."
        exit 1
    fi
}

for s in "${STEPS[@]}"; do
    run_step "$s"
done

echo
echo "============================================================"
echo "== STEP 05_run_benchmark.py"
echo "============================================================"
PY="$(benchmark_python "$ROOT_DIR")"
"$PY" "$ROOT_DIR/scripts/05_run_benchmark.py" "$@"

echo
echo "============================================================"
echo "== STEP 06_analyze_results.py"
echo "============================================================"
"$PY" "$ROOT_DIR/scripts/06_analyze_results.py"

echo
echo "Done."
echo "Outputs:"
echo "  $ROOT_DIR/analysis/table.md"
echo "  $ROOT_DIR/analysis/speedup.pdf"
echo "  $ROOT_DIR/analysis/methods_section.md"
echo "  $ROOT_DIR/results/versions.json"
echo "  $ROOT_DIR/results/timings.json"
echo "  $ROOT_DIR/results/faithfulness.json"
