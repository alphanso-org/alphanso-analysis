#!/usr/bin/env bash
# Shared build parallelism policy for the lab workstation.
#
# Default to at most 20% of visible CPUs so the one-shot run does not
# monopolize a shared machine during GEANT4/SaG4n compilation. BUILD_JOBS may
# be set lower, but values above the 20% cap are rejected.

detect_cpu_count() {
    local cpus
    if command -v nproc >/dev/null 2>&1; then
        cpus="$(nproc)"
    elif command -v getconf >/dev/null 2>&1; then
        cpus="$(getconf _NPROCESSORS_ONLN 2>/dev/null || true)"
    else
        cpus="1"
    fi

    if [[ ! "$cpus" =~ ^[0-9]+$ ]] || (( cpus < 1 )); then
        cpus="1"
    fi
    printf '%s\n' "$cpus"
}

max_build_jobs() {
    local cpus jobs
    cpus="$(detect_cpu_count)"
    jobs=$(( cpus / 5 ))
    if (( jobs < 1 )); then
        jobs=1
    fi
    printf '%s\n' "$jobs"
}

resolve_build_jobs() {
    local max_jobs
    max_jobs="$(max_build_jobs)"

    if [[ -n "${BUILD_JOBS:-}" ]]; then
        if [[ ! "$BUILD_JOBS" =~ ^[1-9][0-9]*$ ]]; then
            echo "ERROR: BUILD_JOBS must be a positive integer, got '$BUILD_JOBS'." >&2
            return 2
        fi
        if (( BUILD_JOBS > max_jobs )); then
            echo "ERROR: BUILD_JOBS=$BUILD_JOBS exceeds the 20% cap of $max_jobs jobs." >&2
            echo "Set BUILD_JOBS to $max_jobs or lower." >&2
            return 2
        fi
        printf '%s\n' "$BUILD_JOBS"
        return 0
    fi

    printf '%s\n' "$max_jobs"
}
