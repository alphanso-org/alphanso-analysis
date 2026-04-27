#!/usr/bin/env bash
# 04_setup_nuclear_data.sh — fetch the SaG4n team's pre-converted (alpha,xn)
# data library for G4ParticleHP.
#
# The SaG4n upstream README directs users to download a pre-converted library
# (NOT raw ENDF). Mendoza Table 2 used JENDL/AN-2005, so that is the default.
# Set NUCLEAR_DATA_LIB=jendltendl01 if you deliberately want SaG4n's currently
# recommended hybrid library instead.
#
# CERNBox public-share download endpoint: append /download to the share URL.
# That returns a zipped tarball; if the unauth flow refuses, the user must
# log in via browser and place the archive at $DATA_ROOT/<lib>.tar.gz, then
# re-run this script — it'll pick up the local file.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
DATA_ROOT="$ROOT_DIR/nuclear_data"
ENV_FILE="$ROOT_DIR/results/nuclear_data.env"
# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/deps_mode.sh"

# Default to the Mendoza Table 2 library, not SaG4n's newer hybrid default.
LIB_KEY="${NUCLEAR_DATA_LIB:-jendl-an-2005}"

declare -A LIB_URL=(
    [jendltendl01]="https://cernbox.cern.ch/s/JBBzfqj4RVFjxL7/download"
    [jendl-an-2005]="https://cernbox.cern.ch/s/mD4gLPW5pRnHQWI/download"
    [jendl-an-2005-nosec01]="https://cernbox.cern.ch/s/4g1JQ7Ru9YE9QbE/download"
    [tendl-2017]="https://cernbox.cern.ch/s/oZXgc2TlBSEnObo/download"
)

declare -A LIB_DIRNAME=(
    [jendltendl01]="JENDLTENDL01"
    [jendl-an-2005]="JENDL_AN-2005"
    [jendl-an-2005-nosec01]="JENDL_AN-2005_noSec01"
    [tendl-2017]="TENDL-2017"
)

if [[ -z "${LIB_URL[$LIB_KEY]:-}" ]]; then
    echo "[04] ERROR: unknown NUCLEAR_DATA_LIB=$LIB_KEY" >&2
    echo "[04] Valid keys: ${!LIB_URL[@]}" >&2
    exit 1
fi

URL="${LIB_URL[$LIB_KEY]}"
DIRNAME="${LIB_DIRNAME[$LIB_KEY]}"
LIB_DIR="$DATA_ROOT/$DIRNAME"
TARBALL="$DATA_ROOT/${LIB_KEY}.tar.gz"

mkdir -p "$DATA_ROOT" "$ROOT_DIR/results"

if [[ -d "$LIB_DIR" ]] && [[ -n "$(ls -A "$LIB_DIR" 2>/dev/null)" ]]; then
    echo "[04] Library already present at $LIB_DIR — skipping download."
else
    if [[ ! -s "$TARBALL" ]]; then
        echo "[04] Downloading $LIB_KEY from $URL ..."
        # CERNBox returns either a tarball or a zip; -L follows redirects, -f errors on 4xx/5xx.
        if ! wget -q --tries=2 --content-disposition -O "$TARBALL" "$URL"; then
            echo "[04] ERROR: automated download failed." >&2
            echo "[04] Manual fallback:" >&2
            echo "[04]   1. Open $URL in a browser" >&2
            echo "[04]   2. Save the file as $TARBALL" >&2
            echo "[04]   3. Re-run this script" >&2
            rm -f "$TARBALL"
            exit 1
        fi
    fi

    echo "[04] Extracting $TARBALL ..."
    TMP_EXTRACT="$DATA_ROOT/.extract_${LIB_KEY}_$$"
    rm -rf "$TMP_EXTRACT" "$LIB_DIR"
    mkdir -p "$TMP_EXTRACT"

    magic="$(od -An -tx1 -N4 "$TARBALL" | tr -d ' \n')"
    if [[ "$magic" == 1f8b* ]]; then
        tar -xzf "$TARBALL" -C "$TMP_EXTRACT"
    elif [[ "$magic" == 504b* ]]; then
        if use_system_deps; then
            PY="$(benchmark_python "$ROOT_DIR")"
        else
            PY="$ROOT_DIR/conda_env/bin/python"
            [[ -x "$PY" ]] || PY="python3"
        fi
        "$PY" -m zipfile -e "$TARBALL" "$TMP_EXTRACT"
    else
        echo "[04] ERROR: unknown archive format for $TARBALL" >&2
        rm -rf "$TMP_EXTRACT"
        exit 1
    fi

    shopt -s dotglob nullglob
    entries=("$TMP_EXTRACT"/*)
    if [[ "${#entries[@]}" -eq 0 ]]; then
        echo "[04] ERROR: archive extracted no files" >&2
        rm -rf "$TMP_EXTRACT"
        exit 1
    elif [[ "${#entries[@]}" -eq 1 && -d "${entries[0]}" ]]; then
        mv "${entries[0]}" "$LIB_DIR"
        rmdir "$TMP_EXTRACT"
    else
        mkdir -p "$LIB_DIR"
        mv "$TMP_EXTRACT"/* "$LIB_DIR"/
        rmdir "$TMP_EXTRACT"
    fi
    shopt -u dotglob nullglob
fi

if [[ ! -d "$LIB_DIR" ]] || [[ -z "$(ls -A "$LIB_DIR" 2>/dev/null)" ]]; then
    echo "[04] ERROR: extraction did not produce $LIB_DIR" >&2
    exit 1
fi

cat > "$ENV_FILE" <<EOF
# Sourced by 05_run_benchmark.py.
export G4PARTICLEHPDATA="$LIB_DIR"
EOF

echo "[04] Wrote $ENV_FILE"
echo "[04] G4PARTICLEHPDATA=$LIB_DIR"
echo "[04] Library: $LIB_KEY"
