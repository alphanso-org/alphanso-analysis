#!/usr/bin/env bash
# 01_install_geant4.sh — download and build GEANT4 against the conda toolchain.
# Single-threaded build flag (GEANT4_BUILD_MULTITHREADED=OFF) for deterministic
# timing. Idempotent: skips if geant4_install/bin/geant4-config already exists.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
ENV_DIR="$ROOT_DIR/conda_env"
INSTALL_DIR="$ROOT_DIR/geant4_install"
SRC_DIR="$ROOT_DIR/geant4_src"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/build_jobs.sh"

if [[ -x "$INSTALL_DIR/bin/geant4-config" ]]; then
    echo "[01] GEANT4 already installed at $INSTALL_DIR — skipping."
    exit 0
fi

if [[ ! -x "$ENV_DIR/bin/cmake" ]]; then
    echo "[01] ERROR: conda env missing. Run scripts/00_install_conda_deps.sh first." >&2
    exit 1
fi

VERSION="$(cat "$ROOT_DIR/scripts/geant4_version.txt" | tr -d '[:space:]')"
echo "[01] Installing GEANT4 v$VERSION"

# Activate conda env to get the gcc_linux-64 toolchain wrappers (CC, CXX) and
# pick up xerces-c / expat / zlib headers from the env.
# shellcheck disable=SC1091
source "$(dirname "$(readlink -f "$ENV_DIR/bin/conda" 2>/dev/null || echo "$ENV_DIR/bin/python")")/../etc/profile.d/conda.sh" 2>/dev/null || true
# Robust activation: locate the conda installation that owns this env.
CONDA_ROOT="$(dirname "$(dirname "$(readlink -f "$ENV_DIR/bin/python")")")"
# If that didn't yield a sane root with a profile.d/conda.sh, walk back.
for try in "$ENV_DIR" "$ROOT_DIR/miniconda" "$HOME/miniconda3" "$HOME/anaconda3"; do
    if [[ -f "$try/etc/profile.d/conda.sh" ]]; then
        # shellcheck disable=SC1091
        source "$try/etc/profile.d/conda.sh"
        conda activate "$ENV_DIR"
        break
    fi
done

# Sanity: cmake and a C++ compiler must now be on PATH from the conda env.
command -v cmake >/dev/null || { echo "[01] ERROR: cmake not on PATH after activation." >&2; exit 1; }
command -v "${CXX:-x86_64-conda-linux-gnu-g++}" >/dev/null || \
    command -v g++ >/dev/null || \
    { echo "[01] ERROR: no C++ compiler on PATH." >&2; exit 1; }

# Download source. Try the canonical CERN URL first, fall back to GitHub.
TARBALL="$ROOT_DIR/geant4-v${VERSION}.tar.gz"
mkdir -p "$SRC_DIR"

if [[ ! -f "$TARBALL" ]]; then
    echo "[01] Downloading GEANT4 source ..."
    URL_PRIMARY="https://gitlab.cern.ch/geant4/geant4/-/archive/v${VERSION}/geant4-v${VERSION}.tar.gz"
    URL_FALLBACK="https://github.com/Geant4/geant4/archive/refs/tags/v${VERSION}.tar.gz"
    wget -q -O "$TARBALL" "$URL_PRIMARY" || \
        wget -q -O "$TARBALL" "$URL_FALLBACK" || \
        { echo "[01] ERROR: could not download GEANT4 source from either URL." >&2; exit 1; }
fi

# Extract.
if [[ ! -d "$SRC_DIR/geant4-v${VERSION}" ]]; then
    echo "[01] Extracting source ..."
    tar -xzf "$TARBALL" -C "$SRC_DIR"
    # Some archives extract as geant4-vX.Y.Z, others as geant4-X.Y.Z. Normalize.
    if [[ ! -d "$SRC_DIR/geant4-v${VERSION}" && -d "$SRC_DIR/geant4-${VERSION}" ]]; then
        mv "$SRC_DIR/geant4-${VERSION}" "$SRC_DIR/geant4-v${VERSION}"
    fi
fi

# Configure & build.
BUILD_DIR="$SRC_DIR/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "[01] Running cmake ..."
cmake -DCMAKE_INSTALL_PREFIX="$INSTALL_DIR" \
      -DCMAKE_PREFIX_PATH="$ENV_DIR" \
      -DGEANT4_INSTALL_DATA=ON \
      -DGEANT4_USE_SYSTEM_EXPAT=ON \
      -DGEANT4_USE_GDML=ON \
      -DGEANT4_BUILD_MULTITHREADED=OFF \
      -DCMAKE_BUILD_TYPE=Release \
      "$SRC_DIR/geant4-v${VERSION}"

BUILD_JOBS_RESOLVED="$(resolve_build_jobs)"
CPU_COUNT="$(detect_cpu_count)"
echo "[01] Building with $BUILD_JOBS_RESOLVED parallel jobs (20% cap of $CPU_COUNT visible CPUs) ..."
make -j"$BUILD_JOBS_RESOLVED"
make install

echo "[01] GEANT4 installed at $INSTALL_DIR"
echo "[01] To use: source \"$INSTALL_DIR/bin/geant4.sh\""
