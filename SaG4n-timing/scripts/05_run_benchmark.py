#!/usr/bin/env python3
"""
05_run_benchmark.py — SaG4n vs ALPHANSO timing harness.

Reproduces the Mendoza 2020 Table 2 fastest row:
  10^7 alpha at 10 MeV, F_B = 10^3, S_max = 0.1 mm,
  G4EmStandardPhysics_option4 (compiled into SaG4n upstream),
  JENDL/AN-2005 via G4ParticleHP.

For each of 6 nuclides (Si-28, Li-6, N-14, C-13, F-19, O-18):
  * SAG4N_TRIALS SaG4n runs (default 3).
  * ALPHANSO_TRIALS ALPHANSO runs in fresh subprocesses (drop trial 0
    as warmup).

Each invocation pinned to one core via taskset and run with single-thread
math-library env vars (OMP/OPENBLAS/MKL/NUMBA = 1) so that taskset is the
only relevant resource lever.

Two ALPHANSO timings recorded: calc_time (perf_counter around
Transport.calculate) and wall_time (full subprocess wall, includes
Python startup + import). ALPHANSO yield is also captured for
cross-validation against SaG4n.

Outputs:
  results/versions.json
  results/faithfulness.json
  results/raw/<engine>_<nuclide>_<trial>.json
  results/raw/sag4n_<nuclide>_t<trial>.{log,txt,root}
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---- Mendoza Table 2 fastest row ---------------------------------------- #
NUCLIDES = [
    # Use the same arbitrary 1 g/cm^3 density style as the SaG4n examples.
    # Thick-target yield is density independent; this avoids encoding a
    # physical phase choice for gases such as N, F, and O.
    {"label": "Si-28", "Z": 14, "A": 28, "density": 1.0},
    {"label": "Li-6",  "Z":  3, "A":  6, "density": 1.0},
    {"label": "N-14",  "Z":  7, "A": 14, "density": 1.0},
    {"label": "C-13",  "Z":  6, "A": 13, "density": 1.0},
    {"label": "F-19",  "Z":  9, "A": 19, "density": 1.0},
    {"label": "O-18",  "Z":  8, "A": 18, "density": 1.0},
]

N_PRIMARIES   = 10**7
F_B           = 10**3      # corrected from 10^5; verified against Mendoza Table 2 caption
SMAX_CM       = 0.01       # 0.1 mm in SaG4n's cm units
E_ALPHA_MEV   = 10.0
SEED_BASE     = 1234567

ALPHANSO_TRIALS = 31    # drop trial 0 as warmup → 30 timed
SAG4N_TRIALS    = 3     # bumped from 1 to give the speedup CI a real denom for SaG4n too

# Single-thread env for both engines so taskset pins are meaningful.
SINGLE_THREAD_ENV = {
    "OMP_NUM_THREADS":      "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS":      "1",
    "NUMBA_NUM_THREADS":    "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "BLIS_NUM_THREADS":     "1",
}


# --------------------------------------------------------------------------- #
# Setup helpers
# --------------------------------------------------------------------------- #

def render_inp(nuc: dict, out_path: Path, output_stem: Path, seed: int) -> None:
    try:
        from jinja2 import Template
    except ImportError as e:
        raise RuntimeError(
            "jinja2 not available. Activate the conda env or install jinja2."
        ) from e
    tpl_text = (ROOT / "inputs" / "template.inp.j2").read_text()
    tpl = Template(tpl_text)
    rendered = tpl.render(
        label          = nuc["label"],
        Z              = nuc["Z"],
        A              = nuc["A"],
        density_g_cm3  = nuc["density"],
        E_alpha_MeV    = E_ALPHA_MEV,
        smax_cm        = SMAX_CM,
        F_B            = F_B,
        n_events       = N_PRIMARIES,
        output_stem    = str(output_stem),    # without extension
        seed           = seed,
    )
    if not rendered.endswith("\n"):
        rendered += "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered)


def find_sag4n_binary() -> Path:
    candidates = [
        ROOT / "SaG4n_src" / "build" / "SaG4n",
        ROOT / "SaG4n_src" / "build" / "bin" / "SaG4n",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    raise FileNotFoundError(
        f"SaG4n binary not found. Searched: {[str(c) for c in candidates]}. "
        f"Run scripts/02_build_sag4n.sh first."
    )


def find_venv_python() -> Path:
    explicit = os.environ.get("ALPHANSO_PYTHON")
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        raise FileNotFoundError(f"ALPHANSO_PYTHON points to missing file: {p}")

    venv_dir = os.environ.get("ALPHANSO_VENV")
    p = Path(venv_dir) / "bin" / "python" if venv_dir else ROOT / "venv" / "bin" / "python"
    if not p.is_file():
        raise FileNotFoundError(
            f"ALPHANSO venv python not found at {p}. Run scripts/03_install_alphanso.sh first."
        )
    return p


def sag4n_env() -> dict[str, str]:
    """Compose env for SaG4n: GEANT4 vars + G4PARTICLEHPDATA + single-thread."""
    env = os.environ.copy()

    g4_setup = ROOT / "geant4_install" / "bin" / "geant4.sh"
    if not g4_setup.is_file():
        raise FileNotFoundError(
            f"GEANT4 setup script not found at {g4_setup}. "
            f"Run scripts/01_install_geant4.sh first."
        )
    proc = subprocess.run(
        ["bash", "-c", f"source {shlex.quote(str(g4_setup))} && env"],
        capture_output=True, text=True, check=True,
    )
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k] = v

    nd_env = ROOT / "results" / "nuclear_data.env"
    if nd_env.is_file():
        for line in nd_env.read_text().splitlines():
            m = re.match(r'\s*export\s+(\w+)="?(.*?)"?\s*$', line)
            if m:
                env[m.group(1)] = m.group(2)

    env.update(SINGLE_THREAD_ENV)
    return env


def alphanso_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(SINGLE_THREAD_ENV)
    return env


# --------------------------------------------------------------------------- #
# Versions / pre-flight
# --------------------------------------------------------------------------- #

def capture_versions() -> dict:
    info: dict = {
        "timestamp": datetime.now().isoformat(),
        "uname": " ".join(platform.uname()),
        "python_version": platform.python_version(),
        "nproc": os.cpu_count(),
    }
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info["cpu_model"] = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    try:
        gov_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
        if os.path.exists(gov_path):
            info["cpu_governor"] = Path(gov_path).read_text().strip()
    except Exception:
        pass
    for cmd, key in [
        (["g++", "--version"],   "gxx_version"),
        (["cmake", "--version"], "cmake_version"),
    ]:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info[key] = out.stdout.splitlines()[0].strip()
        except Exception:
            info[key] = None

    g4cfg = ROOT / "geant4_install" / "bin" / "geant4-config"
    if g4cfg.is_file():
        try:
            out = subprocess.run([str(g4cfg), "--version"],
                                 capture_output=True, text=True, check=True)
            info["geant4_version"] = out.stdout.strip()
        except Exception:
            info["geant4_version"] = None

    sag4n_dir = ROOT / "SaG4n_src"
    if (sag4n_dir / ".git").exists():
        try:
            info["sag4n_commit"] = subprocess.run(
                ["git", "-C", str(sag4n_dir), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True).stdout.strip()
            info["sag4n_describe"] = subprocess.run(
                ["git", "-C", str(sag4n_dir), "describe", "--tags", "--always", "--dirty"],
                capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            info["sag4n_commit"] = None

    venv_pip = ROOT / "venv" / "bin" / "pip"
    if venv_pip.is_file():
        try:
            out = subprocess.run([str(venv_pip), "show", "alphanso"],
                                 capture_output=True, text=True, check=True)
            for line in out.stdout.splitlines():
                if line.startswith("Version:"):
                    info["alphanso_version"] = line.split(":", 1)[1].strip()
                if line.startswith("Location:"):
                    info["alphanso_location"] = line.split(":", 1)[1].strip()
        except Exception:
            info["alphanso_version"] = None

        try:
            out = subprocess.run([str(venv_pip), "freeze"],
                                 capture_output=True, text=True, check=True)
            (ROOT / "results" / "pip_freeze.txt").write_text(out.stdout)
        except Exception:
            pass

    return info


def pre_flight_warnings(info: dict) -> list[str]:
    warns: list[str] = []
    gov = info.get("cpu_governor")
    if gov and gov != "performance":
        warns.append(f"CPU governor is {gov!r}, not 'performance' — timings may be noisy.")
    try:
        load1, _, _ = os.getloadavg()
        if load1 > 1.0:
            warns.append(f"1-min load average is {load1:.2f} (>1.0) — system is busy.")
    except Exception:
        pass
    if shutil.which("taskset") is None:
        warns.append("taskset not on PATH — runs will not be pinned to a core.")
    return warns


# --------------------------------------------------------------------------- #
# SaG4n: runner + yield parser
# --------------------------------------------------------------------------- #

def parse_sag4n_yield_txt(txt_path: Path) -> float | None:
    """Read total yield from SaG4n's ASCII output.

    Format (per src/SaG4nEventAction.cc):
      NSpec_<volname>  <nbins>  <Emax_MeV>
      <Ebin_lo>  <Y_per_alpha_per_bin>  <err>
      ...
      (blank line, then AlphaFlux histogram, then SourceEnergy histogram)

    SaG4n's first NSpec data row (Ebin_lo=0) is already the total neutron
    yield per source alpha. The remaining NSpec rows are the binned spectrum;
    summing them would double-count the total. This function returns Mendoza's
    units: neutrons per 1e6 alpha particles.
    """
    if not txt_path.is_file():
        return None
    text = txt_path.read_text(errors="replace")
    need_total_row = False
    total_per_alpha = 0.0
    saw_total = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            need_total_row = False
            continue
        if s.startswith("NSpec_"):
            need_total_row = True
            continue
        if s.startswith(("AFlux_", "SourceE_", "AlphaFlux_")):
            need_total_row = False
            continue
        if need_total_row:
            parts = s.split()
            if len(parts) >= 2:
                try:
                    total_per_alpha += float(parts[1])
                    saw_total = True
                except ValueError:
                    pass
            need_total_row = False
    return total_per_alpha * 1e6 if saw_total else None


def run_sag4n(nuc: dict, env: dict, log_dir: Path, trial: int) -> dict:
    bin_path = find_sag4n_binary()
    inp_path = ROOT / "inputs" / "generated" / f"{nuc['label']}_t{trial}.inp"
    out_stem = log_dir / f"sag4n_{nuc['label']}_t{trial}"
    seed = SEED_BASE + nuc["Z"] * 1000 + nuc["A"] + trial * 7919
    render_inp(nuc, inp_path, output_stem=out_stem, seed=seed)

    log_path = log_dir / f"sag4n_{nuc['label']}_t{trial}.log"

    cmd: list[str] = []
    if shutil.which("taskset"):
        cmd += ["taskset", "-c", "0"]
    cmd += [str(bin_path), str(inp_path)]

    print(f"  [SaG4n] {nuc['label']} t{trial}: {' '.join(cmd)}")
    t0 = time.perf_counter_ns()
    proc = subprocess.run(
        cmd, env=env, capture_output=True, text=True, cwd=str(ROOT),
    )
    t1 = time.perf_counter_ns()

    log_path.write_text(
        f"# cmd: {' '.join(cmd)}\n"
        f"# returncode: {proc.returncode}\n"
        f"# wall_ns: {t1 - t0}\n"
        f"# === STDOUT (last 80 lines) ===\n"
        + "\n".join(proc.stdout.splitlines()[-80:])
        + f"\n# === STDERR ===\n{proc.stderr}\n"
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"SaG4n failed for {nuc['label']} trial {trial} "
            f"(exit {proc.returncode}). See {log_path}"
        )

    txt_path = Path(str(out_stem) + ".txt")
    y_us = parse_sag4n_yield_txt(txt_path)

    return {
        "engine":     "sag4n",
        "nuclide":    nuc["label"],
        "trial":      trial,
        "wall_ns":    t1 - t0,
        "wall_s":     (t1 - t0) / 1e9,
        "y_us":       y_us,
        "log_path":   str(log_path),
        "txt_path":   str(txt_path),
        "input_path": str(inp_path),
        "binary":     str(bin_path),
    }


# --------------------------------------------------------------------------- #
# ALPHANSO runner
# --------------------------------------------------------------------------- #

ALPHANSO_RUNNER = """\
import json, time, logging
logging.disable(logging.CRITICAL)
from alphanso.transport import Transport

cfg = {cfg!r}

def scalar_or_none(value):
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

t0 = time.perf_counter_ns()
result = Transport.calculate(cfg)
t1 = time.perf_counter_ns()

an_yield = None
if isinstance(result, dict):
    for key in ("an_yield", "neutron_yield", "yield"):
        if key in result:
            an_yield = scalar_or_none(result[key])
            break

print(json.dumps({{
    "calc_ns": t1 - t0,
    "an_yield": an_yield,
}}))
"""


def alphanso_config(nuc: dict) -> dict:
    return {
        "calc_type": "beam",
        "matdef": {nuc["label"]: 1.0},
        "beam_energy": E_ALPHA_MEV,
        "calculate_gammas": False,
        "neutron_energy_bins": [12.0, 0.0, 101],
    }


def run_alphanso(nuc: dict, trial: int, env: dict) -> dict:
    py = find_venv_python()
    cfg = alphanso_config(nuc)
    script = ALPHANSO_RUNNER.format(cfg=cfg)

    cmd: list[str] = []
    if shutil.which("taskset"):
        cmd += ["taskset", "-c", "0"]
    cmd += [str(py), "-c", script]

    t0 = time.perf_counter_ns()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    t1 = time.perf_counter_ns()

    if proc.returncode != 0:
        raise RuntimeError(
            f"ALPHANSO failed for {nuc['label']} trial {trial} "
            f"(exit {proc.returncode}). stderr:\n{proc.stderr}"
        )

    last = proc.stdout.strip().splitlines()[-1]
    parsed = json.loads(last)
    return {
        "engine":   "alphanso",
        "nuclide":  nuc["label"],
        "trial":    trial,
        "calc_ns":  parsed["calc_ns"],
        "calc_s":   parsed["calc_ns"] / 1e9,
        "wall_ns":  t1 - t0,
        "wall_s":   (t1 - t0) / 1e9,
        "an_yield": parsed.get("an_yield"),
    }


# --------------------------------------------------------------------------- #
# Faithfulness gate
# --------------------------------------------------------------------------- #

def run_faithfulness_check(env: dict) -> dict:
    """One SaG4n run per nuclide, parse yield, compare to Mendoza."""
    ref = json.loads((ROOT / "inputs" / "mendoza_table2.json").read_text())
    ref_by_label = {n["label"]: n for n in ref["nuclides"]}

    log_dir = ROOT / "results" / "raw"
    log_dir.mkdir(parents=True, exist_ok=True)

    out: dict = {"timestamp": datetime.now().isoformat(), "results": []}
    for nuc in NUCLIDES:
        print(f"\n[faithfulness] {nuc['label']}")
        timing = run_sag4n(nuc, env, log_dir, trial=0)
        save_raw(timing)

        y_us  = timing["y_us"]
        ref_n = ref_by_label.get(nuc["label"], {})
        y_exp = ref_n.get("y_expected_per_million_alpha")
        tol   = ref_n.get("y_tolerance_relative", 0.05)

        if y_us is None or y_exp is None:
            passed  = False
            rel_err = None
            note    = "yield not parseable from .txt; check OUTPUTTYPE / output stem"
        else:
            rel_err = abs(y_us - y_exp) / y_exp
            passed  = rel_err < tol
            note    = "ok" if passed else f"deviation {rel_err:.3%} exceeds tolerance {tol:.1%}"

        out["results"].append({
            "nuclide":            nuc["label"],
            "y_us":               y_us,
            "y_expected":         y_exp,
            "tolerance_relative": tol,
            "rel_err":            rel_err,
            "passed":             passed,
            "note":               note,
            "wall_s":             timing["wall_s"],
            "log_path":           timing["log_path"],
        })
        print(f"  Y_us={y_us}  Y_exp={y_exp}  pass={passed}  ({note})")

    out["all_passed"] = all(r["passed"] for r in out["results"])
    return out


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #

def save_raw(record: dict) -> None:
    raw_dir = ROOT / "results" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    engine = record["engine"]
    label  = record["nuclide"]
    trial  = record.get("trial", 0)
    fname  = f"{engine}_{label}_{trial:03d}.json"
    (raw_dir / fname).write_text(json.dumps(record, indent=2))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-faithfulness", action="store_true",
                    help="Skip the faithfulness gate. For debugging only.")
    ap.add_argument("--skip-sag4n", action="store_true",
                    help="Skip SaG4n timing runs.")
    ap.add_argument("--skip-alphanso", action="store_true",
                    help="Skip ALPHANSO timing runs.")
    ap.add_argument("--sag4n-trials", type=int, default=SAG4N_TRIALS,
                    help=f"SaG4n trials per nuclide (default {SAG4N_TRIALS}).")
    ap.add_argument("--alphanso-trials", type=int, default=ALPHANSO_TRIALS,
                    help=f"ALPHANSO trials per nuclide, including warmup "
                         f"(default {ALPHANSO_TRIALS}).")
    args = ap.parse_args()

    (ROOT / "results").mkdir(parents=True, exist_ok=True)

    print("[run] capturing versions ...")
    versions = capture_versions()
    (ROOT / "results" / "versions.json").write_text(json.dumps(versions, indent=2))
    for w in pre_flight_warnings(versions):
        print(f"[run] WARNING: {w}")

    needs_g4_env = not (args.skip_sag4n and args.skip_faithfulness)
    env_g4 = sag4n_env() if needs_g4_env else os.environ.copy()
    env_an = alphanso_subprocess_env()

    # Faithfulness gate (counts as the first SaG4n trial per nuclide).
    faith = None
    if not args.skip_faithfulness:
        print("\n[run] === Faithfulness check (one SaG4n run per nuclide) ===")
        faith = run_faithfulness_check(env_g4)
        (ROOT / "results" / "faithfulness.json").write_text(json.dumps(faith, indent=2))
        if not faith["all_passed"]:
            print("\n[run] FAITHFULNESS FAILED. See results/faithfulness.json.")
            print("[run] Refusing to record timing data with mismatched yields.")
            return 2

    # Additional SaG4n trials for variance estimation.
    if not args.skip_sag4n:
        first_trial = 1 if not args.skip_faithfulness else 0
        log_dir = ROOT / "results" / "raw"
        for nuc in NUCLIDES:
            for trial in range(first_trial, args.sag4n_trials):
                t = run_sag4n(nuc, env_g4, log_dir, trial=trial)
                save_raw(t)

    # ALPHANSO timings.
    if not args.skip_alphanso:
        print(f"\n[run] === ALPHANSO timing ({args.alphanso_trials} trials/nuclide) ===")
        for nuc in NUCLIDES:
            print(f"\n  [ALPHANSO] {nuc['label']}", end=" ", flush=True)
            for trial in range(args.alphanso_trials):
                rec = run_alphanso(nuc, trial, env_an)
                save_raw(rec)
                print(".", end="", flush=True)
            print()

    print("\n[run] Done. Aggregate by running scripts/06_analyze_results.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
