#!/usr/bin/env bash
# Shared dependency-mode helpers.

use_system_deps() {
    case "${USE_SYSTEM_DEPS:-${SKIP_CONDA:-0}}" in
        1|true|TRUE|yes|YES) return 0 ;;
        *) return 1 ;;
    esac
}

source_relaxed_nounset() {
    local script_path="$1"
    local had_nounset=0

    if [[ $- == *u* ]]; then
        had_nounset=1
        set +u
    fi

    # shellcheck disable=SC1090
    source "$script_path"
    local rc=$?

    if (( had_nounset )); then
        set -u
    fi

    return "$rc"
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

activate_conda_env() {
    local root_dir="$1"
    local env_dir="$2"
    local had_nounset=0

    # Conda activation scripts, including gcc_linux-64 hooks, may reference
    # variables before defining them. That is incompatible with `set -u`.
    if [[ $- == *u* ]]; then
        had_nounset=1
        set +u
    fi

    local activated=1
    local try
    for try in "$env_dir" "$root_dir/miniconda" "$HOME/miniconda3" "$HOME/miniconda" "$HOME/anaconda3"; do
        if [[ -f "$try/etc/profile.d/conda.sh" ]]; then
            # shellcheck disable=SC1091
            if source "$try/etc/profile.d/conda.sh" && conda activate "$env_dir"; then
                activated=0
                break
            fi
        fi
    done

    if (( had_nounset )); then
        set -u
    fi

    return "$activated"
}
