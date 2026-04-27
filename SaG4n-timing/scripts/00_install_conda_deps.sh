#!/usr/bin/env bash
# 00_install_conda_deps.sh — bootstrap a conda env with build deps (no sudo).
#
# Creates ./conda_env/ with cmake, GCC 12 (conda-forge linux-64 toolchain),
# xerces-c, expat, zlib, ROOT, Python 3.11, git, wget. Idempotent.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
ENV_DIR="$ROOT_DIR/conda_env"

if [[ -x "$ENV_DIR/bin/cmake" ]]; then
    echo "[00] conda env already provisioned at $ENV_DIR — skipping."
    exit 0
fi

# Locate conda. Prefer ~/miniconda3, fall back to bootstrapping into ./miniconda/.
CONDA=""
for candidate in "$HOME/miniconda3/bin/conda" "$HOME/miniconda/bin/conda" \
                 "$HOME/anaconda3/bin/conda" "$ROOT_DIR/miniconda/bin/conda"; do
    if [[ -x "$candidate" ]]; then
        CONDA="$candidate"
        break
    fi
done

if [[ -z "$CONDA" ]]; then
    echo "[00] No conda found. Bootstrapping Miniconda into ./miniconda/ ..."
    INSTALLER="$ROOT_DIR/miniconda-installer.sh"
    wget -q -O "$INSTALLER" \
        https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash "$INSTALLER" -b -p "$ROOT_DIR/miniconda"
    rm -f "$INSTALLER"
    CONDA="$ROOT_DIR/miniconda/bin/conda"
fi

echo "[00] Using conda at: $CONDA"

# Create the env. -p puts it inline at ./conda_env/ (no global env name pollution).
"$CONDA" create -y -p "$ENV_DIR" -c conda-forge \
    cmake=3.27 \
    make \
    gcc_linux-64=12 \
    gxx_linux-64=12 \
    binutils_linux-64 \
    xerces-c \
    expat \
    zlib \
    root=6.30 \
    python=3.11 \
    pip \
    git \
    wget \
    jinja2 \
    numpy \
    matplotlib

echo "[00] Conda env ready at $ENV_DIR"
echo "[00] To activate manually: source \"$CONDA\"/../etc/profile.d/conda.sh && conda activate \"$ENV_DIR\""
