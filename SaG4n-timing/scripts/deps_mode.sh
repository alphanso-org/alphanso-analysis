#!/usr/bin/env bash
# Shared dependency-mode helpers.

use_system_deps() {
    case "${USE_SYSTEM_DEPS:-${SKIP_CONDA:-0}}" in
        1|true|TRUE|yes|YES) return 0 ;;
        *) return 1 ;;
    esac
}

benchmark_python() {
    local root_dir="$1"

    if [[ -n "${BENCH_PYTHON:-}" ]]; then
        printf '%s\n' "$BENCH_PYTHON"
        return 0
    fi

    if use_system_deps; then
        if [[ -n "${ALPHANSO_VENV:-}" && -x "$ALPHANSO_VENV/bin/python" ]]; then
            printf '%s\n' "$ALPHANSO_VENV/bin/python"
        elif [[ -x "$root_dir/venv/bin/python" ]]; then
            printf '%s\n' "$root_dir/venv/bin/python"
        else
            printf '%s\n' "python3"
        fi
    else
        if [[ -x "$root_dir/conda_env/bin/python" ]]; then
            printf '%s\n' "$root_dir/conda_env/bin/python"
        elif [[ -x "$root_dir/venv/bin/python" ]]; then
            printf '%s\n' "$root_dir/venv/bin/python"
        else
            printf '%s\n' "python3"
        fi
    fi
}
