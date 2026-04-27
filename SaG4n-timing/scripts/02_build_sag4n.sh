#!/usr/bin/env bash
# 02_build_sag4n.sh — clone github.com/UIN-CIEMAT/SaG4n and build against the
# local GEANT4. Refuses to proceed with a dirty working tree to enforce the
# "base, unmodified SaG4n" claim. Idempotent.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
ENV_DIR="$ROOT_DIR/conda_env"
G4_INSTALL="$ROOT_DIR/geant4_install"
SRC_DIR="$ROOT_DIR/SaG4n_src"
BUILD_DIR="$SRC_DIR/build"
SAG4N_REPO="${SAG4N_REPO:-https://github.com/UIN-CIEMAT/SaG4n.git}"
SAG4N_REF="${SAG4N_REF:-9bd52c2ec6f9e3c9720bd982aadbc22b339a7539}"
BUILD_STAMP="$BUILD_DIR/.sag4n_commit"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/build_jobs.sh"

if [[ -x "$BUILD_DIR/SaG4n" ]]; then
    echo "[02] SaG4n already built at $BUILD_DIR/SaG4n — verifying clean tree."
else
    if [[ ! -d "$SRC_DIR/.git" ]]; then
        echo "[02] Cloning SaG4n from upstream ..."
        git clone "$SAG4N_REPO" "$SRC_DIR"
    fi
fi

echo "[02] Checking out SaG4n ref: $SAG4N_REF"
git -C "$SRC_DIR" fetch --tags --quiet origin || true
git -C "$SRC_DIR" checkout --detach "$SAG4N_REF"

# Verify clean working tree. Refuse to build if the tree was modified.
DIRTY_FILES="$(git -C "$SRC_DIR" status --porcelain --untracked-files=no | head -5 || true)"
if [[ -n "$DIRTY_FILES" ]]; then
    echo "[02] ERROR: SaG4n_src has local modifications. The benchmark requires" >&2
    echo "[02] base, unmodified SaG4n. Reset the tree or delete SaG4n_src/ and re-run:" >&2
    echo "$DIRTY_FILES" >&2
    exit 1
fi

COMMIT_SHA="$(git -C "$SRC_DIR" rev-parse HEAD)"
DESCRIBE="$(git -C "$SRC_DIR" describe --tags --always --dirty 2>/dev/null || echo "unknown")"
echo "[02] SaG4n commit: $COMMIT_SHA ($DESCRIBE)"

if [[ ! -x "$G4_INSTALL/bin/geant4-config" ]]; then
    echo "[02] ERROR: GEANT4 not installed. Run scripts/01_install_geant4.sh first." >&2
    exit 1
fi

# Activate conda env (compiler) and source GEANT4 env.
for try in "$ROOT_DIR/miniconda" "$HOME/miniconda3" "$HOME/anaconda3"; do
    if [[ -f "$try/etc/profile.d/conda.sh" ]]; then
        # shellcheck disable=SC1091
        source "$try/etc/profile.d/conda.sh"
        conda activate "$ENV_DIR"
        break
    fi
done
# shellcheck disable=SC1091
source "$G4_INSTALL/bin/geant4.sh"

if [[ -x "$BUILD_DIR/SaG4n" && -f "$BUILD_STAMP" ]] && [[ "$(cat "$BUILD_STAMP")" != "$COMMIT_SHA" ]]; then
    echo "[02] Existing build was for a different SaG4n commit; rebuilding."
    rm -rf "$BUILD_DIR"
fi

if [[ ! -x "$BUILD_DIR/SaG4n" ]]; then
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
    echo "[02] Configuring SaG4n with cmake ..."
    cmake ..
    BUILD_JOBS_RESOLVED="$(resolve_build_jobs)"
    CPU_COUNT="$(detect_cpu_count)"
    echo "[02] Building SaG4n with $BUILD_JOBS_RESOLVED parallel jobs (20% cap of $CPU_COUNT visible CPUs) ..."
    make -j"$BUILD_JOBS_RESOLVED"
    printf '%s\n' "$COMMIT_SHA" > "$BUILD_STAMP"
fi

if [[ ! -x "$BUILD_DIR/SaG4n" ]]; then
    echo "[02] ERROR: SaG4n binary not produced after build." >&2
    exit 1
fi

# Smoke test: invoke the binary to confirm it loads and prints something sane.
"$BUILD_DIR/SaG4n" --help 2>&1 | head -20 || \
    "$BUILD_DIR/SaG4n" 2>&1 | head -20 || true

# Record commit info for results/versions.json. The benchmark harness will
# also re-capture this, but stamping it here lets re-runs keep history.
mkdir -p "$ROOT_DIR/results"
cat > "$ROOT_DIR/results/sag4n_build.json" <<EOF
{
  "commit_sha": "$COMMIT_SHA",
  "describe": "$DESCRIBE",
  "binary": "$BUILD_DIR/SaG4n",
  "geant4_install": "$G4_INSTALL"
}
EOF

echo "[02] SaG4n built. Binary: $BUILD_DIR/SaG4n"
