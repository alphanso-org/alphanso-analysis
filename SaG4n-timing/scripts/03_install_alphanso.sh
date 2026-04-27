#!/usr/bin/env bash
# 03_install_alphanso.sh — create ./venv/ and pip install ALPHANSO from PyPI
# (or from a local path if ALPHANSO_INSTALL is set). Idempotent.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
ENV_DIR="$ROOT_DIR/conda_env"
VENV_DIR="$ROOT_DIR/venv"

if [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -c "import alphanso" 2>/dev/null; then
    echo "[03] ALPHANSO already installed in $VENV_DIR — skipping."
    "$VENV_DIR/bin/pip" show alphanso | grep -E '^(Name|Version|Location):' || true
    exit 0
fi

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
    echo "[03] ERROR: conda env missing. Run scripts/00_install_conda_deps.sh first." >&2
    exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
    echo "[03] Creating venv at $VENV_DIR ..."
    "$ENV_DIR/bin/python" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --upgrade pip wheel setuptools

INSTALL_TARGET="${ALPHANSO_INSTALL:-alphanso}"
if [[ "$INSTALL_TARGET" != "alphanso" && -d "$INSTALL_TARGET" ]]; then
    echo "[03] Installing ALPHANSO from local path: $INSTALL_TARGET (editable)"
    "$VENV_DIR/bin/pip" install -e "$INSTALL_TARGET"
else
    echo "[03] Installing ALPHANSO from PyPI: $INSTALL_TARGET"
    "$VENV_DIR/bin/pip" install "$INSTALL_TARGET"
fi

# Sanity check.
"$VENV_DIR/bin/python" -c "from alphanso.transport import Transport; print('[03] alphanso import OK')"

mkdir -p "$ROOT_DIR/results"
"$VENV_DIR/bin/pip" freeze > "$ROOT_DIR/results/pip_freeze.txt"
"$VENV_DIR/bin/pip" show alphanso | grep -E '^(Name|Version|Location):' \
    > "$ROOT_DIR/results/alphanso_version.txt" || true

echo "[03] ALPHANSO installed. Frozen pkg list at results/pip_freeze.txt"
