# Lab-Box Runbook

Self-bootstrapping benchmark for SaG4n vs. ALPHANSO. Designed to run on a
Linux workstation **without sudo** and **without Claude available**. Total
wall: roughly 3–5 hours of installs + ~2 hours of benchmarking.

## One-line detached run

```
git clone <this-repo> && cd <this-repo>/SaG4n-timing && ./run.sh
```

If CELA already has CMake, a C++ compiler, ROOT, and Python available, try the
no-conda path first:

```
USE_SYSTEM_DEPS=1 ./run.sh
```

To reuse an existing ALPHANSO venv:

```
USE_SYSTEM_DEPS=1 ALPHANSO_VENV=/path/to/venv ./run.sh
```

`./run.sh` starts the full benchmark with `nohup` in a new session and returns
immediately. It is safe to close the SSH connection. Check progress with:

```
./scripts/status.sh
tail -f results/runlogs/latest.log
```

For foreground debugging, run `./run.sh --foreground`.

Final outputs land in:

- `analysis/table.md`            — speedup table by nuclide
- `analysis/speedup.pdf`         — bar chart with bootstrap CIs
- `analysis/methods_section.md`  — pre-filled prose for the paper
- `results/versions.json`        — hardware/software fingerprint
- `results/timings.json`         — aggregated stats
- `results/faithfulness.json`    — Y vs Mendoza gate result

## Prerequisites on the lab box

- Linux x86_64.
- Internet access (for cloning SaG4n + downloading GEANT4 source + JENDL).
- ~10 GB free disk: ~3 GB GEANT4 data, ~3 GB GEANT4 build, optionally ~1 GB
  conda env, ~1 GB SaG4n build + nuclear data, headroom.
- Either an existing miniconda/anaconda install in `~`, or just internet
  access (the script bootstraps Miniconda into `./miniconda/` if absent).
- For `USE_SYSTEM_DEPS=1`: `cmake`, `make`, `g++`, `git`, `wget`, `tar`,
  `root-config`, and `python3 -m venv` must already work in your shell.
- **No sudo required.** If something asks for it, that's a bug — file it.
- Build parallelism is capped to 20% of visible CPUs by default
  (`floor(nproc/5)`, minimum 1). To be even more conservative, set
  `BUILD_JOBS=<lower-number>` before running `./run.sh`.

## Steps in order (each is independently re-runnable)

| # | Script | Purpose | Wall |
|---|---|---|---|
| 0 | `scripts/00_install_conda_deps.sh` | conda env @ `./conda_env/`, or system-dependency check when `USE_SYSTEM_DEPS=1` | ~10 min or <1 min |
| 1 | `scripts/01_install_geant4.sh` | GEANT4 11.2.1 source build to `./geant4_install/` using at most 20% of CPUs | 30–60 min |
| 2 | `scripts/02_build_sag4n.sh` | clone github.com/UIN-CIEMAT/SaG4n, build using at most 20% of CPUs, refuse if dirty | ~5 min |
| 3 | `scripts/03_install_alphanso.sh` | venv + `pip install alphanso` | ~2 min |
| 4 | `scripts/04_setup_nuclear_data.sh` | download converted JENDL/AN-2005, write `G4PARTICLEHPDATA` | ~1 min |
| 5 | `scripts/05_run_benchmark.py` | faithfulness + 3×SaG4n + 31×ALPHANSO per nuclide | ~2 hours |
| 6 | `scripts/06_analyze_results.py` | aggregate, plot, write methods | ~30 sec |

## Re-running individual steps

Each install script checks for its expected output and exits early if
present. To force a re-build, delete the relevant directory:

```
rm -rf conda_env/         # rebuild conda env
rm -rf geant4_install/    # rebuild GEANT4
rm -rf SaG4n_src/         # re-clone and rebuild SaG4n
rm -rf venv/              # re-create venv + reinstall ALPHANSO
rm -rf nuclear_data/      # re-fetch JENDL
rm -rf results/raw/       # discard timing data
```

## Troubleshooting

**Conda not found.** `00_install_conda_deps.sh` bootstraps Miniconda into
`./miniconda/`. If you'd rather use an existing env, point the script's
`CONDA` lookup at it (it checks `~/miniconda3`, `~/miniconda`, `~/anaconda3`).

**Conda Python fails with `No module named encodings`.** This is usually a
corrupt partial Miniconda install or inherited `PYTHONHOME`/`PYTHONPATH`.
The script now sanitizes those variables for conda creation, but if you
already have system build tools, prefer:
`USE_SYSTEM_DEPS=1 ./run.sh`.

**Using system dependencies instead of conda.** Run
`USE_SYSTEM_DEPS=1 ./run.sh`. Step 00 will check for `cmake`, `make`, `g++`,
`git`, `wget`, `tar`, `root-config`, and `python3 -m venv`. If it fails, load
the relevant CELA modules and rerun the same command.

**Using an existing ALPHANSO venv.** Run
`USE_SYSTEM_DEPS=1 ALPHANSO_VENV=/path/to/venv ./run.sh`. Step 03 will reuse
that venv and install any missing benchmark helper packages (`jinja2`, `numpy`,
`matplotlib`) if needed.

**GEANT4 build fails on missing xerces-c / expat.** Make sure the conda env
is active before re-running step 01. The script tries to source it, but
some shells require manual activation first:
`source ./conda_env/etc/profile.d/conda.sh && conda activate ./conda_env`.
When using `USE_SYSTEM_DEPS=1`, this means the system/module environment does
not expose the needed development headers/libraries; load the relevant module
or fall back to the conda path.

**GEANT4 download fails.** The script tries the CERN GitLab archive first
and falls back to GitHub releases. If both fail, manually download
`geant4-v11.2.1.tar.gz` to the repo root, then re-run step 01.

**SaG4n CMake can't find GEANT4.** Confirm `./geant4_install/bin/geant4.sh`
exists and is sourced by step 02. The script handles this, but if you're
running step 02 standalone, pre-source it:
`source ./geant4_install/bin/geant4.sh`.

**SaG4n won't build because tree is dirty.** This is intentional — the
benchmark requires unmodified SaG4n. Run `git -C SaG4n_src reset --hard`
to discard local changes, or delete `SaG4n_src/` and let step 02 re-clone.

**SaG4n input syntax mismatch.** The `inputs/template.inp.j2` is modeled on
the upstream `inputs/examples/beam/beam01.inp` and uses the actual flat-keyword
format (verified against `src/SaG4nInputManager.cc`: lengths in cm, single
`SEED` int, single trailing `END`, no `PHYSICSLIST` keyword). If SaG4n still
errors during parse, diff your generated `.inp` against
`SaG4n_src/inputs/examples/beam/beam01.inp` to find the regression.

**`G4PARTICLEHPDATA` complaint at runtime.** Step 04 downloads the SaG4n
team's pre-converted JENDL/AN-2005 library from CERNBox, not raw ENDF. Other
valid keys are `jendltendl01`, `jendl-an-2005-nosec01`, and `tendl-2017`;
set `NUCLEAR_DATA_LIB=<key>` before re-running step 04 if you deliberately
want a different library. If CERNBox blocks wget, the script tells you which
file to save under `nuclear_data/<lib>.tar.gz` from a browser before re-run.

**`pip install alphanso` fails with Python version mismatch.** The conda
path ships Python 3.11. With `USE_SYSTEM_DEPS=1`, step 03 uses
`${PYTHON_FOR_VENV:-python3}` to create the venv. Point `PYTHON_FOR_VENV` at a
different interpreter if your system default is wrong.

**Faithfulness fails for ¹⁴N.** Mendoza documents up to 12% step-size
deviation for ¹⁴N. The reference data widens that nuclide's tolerance to
15% (`y_tolerance_relative` in `inputs/mendoza_table2.json`). If it still
fails, double-check the `.inp` file actually used 0.1 mm step size and
F_B = 10³ — these were two of the most commonly miscoded values in the
draft plan.

**Faithfulness fails because yield isn't parseable.** The harness requests
SaG4n ASCII output (`OUTPUTTYPE 1 0 1`) and reads the first `NSpec_*` data row
from `results/raw/sag4n_<nuclide>_t<trial>.txt`. If that file is missing,
inspect the paired `.log` and generated `.inp`.

**CPU governor isn't `performance`.** The harness warns but proceeds.
Setting the governor usually requires sudo. Document the actual governor
from `results/versions.json` in the methods.

**Want to benchmark a non-PyPI ALPHANSO?**
`ALPHANSO_INSTALL=/path/to/alphanso ./scripts/03_install_alphanso.sh`

## What gets fingerprinted in `results/versions.json`

CPU model and flags, kernel + uname, gcc version, cmake version, GEANT4
version (from `geant4-config`), SaG4n commit SHA + `git describe`,
ALPHANSO version, scaling governor, full `pip freeze`. Paste the
relevant fields into the methods section.

## Configuration knobs (edit these if you need to)

| File | What to change |
|---|---|
| `scripts/geant4_version.txt` | GEANT4 version pin (default `11.2.1`) |
| `scripts/05_run_benchmark.py` (constants at top) | nuclide list, N primaries, F_B, S_max, trial counts |
| `inputs/mendoza_table2.json` | reference Y values + per-nuclide tolerances |
| `inputs/template.inp.j2` | SaG4n `.inp` syntax (verify against repo examples) |
