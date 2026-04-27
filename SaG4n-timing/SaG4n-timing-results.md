# SaG4n Timing Results

Brief summary of the CELA timing run comparing ALPHANSO against SaG4n for the
Mendoza et al. Table 2 fastest-step configuration.

## Configuration

- Workstation: LLNL CELA.
- SaG4n: upstream `UIN-CIEMAT/SaG4n`, commit `9bd52c2ec6f9e3c9720bd982aadbc22b339a7539` (`v1.5`).
- Geant4: `geant4-11-02-patch-01` / Geant4 11.2.1.
- ALPHANSO: `alphanso 1.0.1`, installed in Python 3.11 virtual environment.
- Nuclear data: SaG4n pre-converted `JENDL_AN-2005` G4ParticleHP data.
- Physics setup: 10^7 alpha particles at 10 MeV, `F_B = 10^3`, `S_max = 0.1 mm`, `G4EmStandardPhysics_option4`.
- Targets: isotopically pure 5 cm cube at 1 g/cm^3.
- Timing protocol: 3 SaG4n trials per nuclide; 31 ALPHANSO subprocess trials per nuclide with trial 0 dropped as warmup.
- Threading: both engines run as single-process, single-thread jobs; benchmark wrapper sets `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMBA_NUM_THREADS=1`, `VECLIB_MAXIMUM_THREADS=1`, and `BLIS_NUM_THREADS=1`.
- CPU pinning: `taskset -c 0` was used where available.

Li-6 is excluded from the ALPHANSO comparison below because ALPHANSO returned
zero yield for Li-6 in this run, which is a known ALPHANSO issue. SaG4n's Li-6
yield did match the Mendoza reference.

## Results

ALPHANSO was faster than SaG4n by roughly 2,700x to 7,200x when comparing the
ALPHANSO calculation kernel against full SaG4n wall time. A more conservative
subprocess-wall comparison, including Python startup/import overhead for
ALPHANSO, gives roughly 324x to 518x speedup.

| Nuclide | SaG4n median wall (s) | ALPHANSO calc median (s) | ALPHANSO wall median (s) | Kernel speedup, 95% CI | Wall speedup, 95% CI | SaG4n Y | ALPHANSO Y | Mendoza Y | SaG4n-Mendoza error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Si-28 | 225.273 | 0.056976 | 0.690665 | 3,954x (3,917-4,037) | 326x (323-333) | 0.128712 | 0.144408 | 0.126800 | +1.508% |
| N-14 | 233.932 | 0.083217 | 0.721088 | 2,811x (2,770-2,836) | 324x (320-327) | 23.4814 | 26.5435 | 23.3700 | +0.477% |
| C-13 | 318.225 | 0.071196 | 0.710490 | 4,470x (4,455-4,484) | 448x (446-449) | 107.819 | 106.129 | 107.560 | +0.241% |
| F-19 | 321.968 | 0.117536 | 0.761988 | 2,739x (2,697-2,843) | 423x (416-439) | 116.598 | 110.433 | 116.550 | +0.041% |
| O-18 | 357.606 | 0.049694 | 0.690210 | 7,196x (7,145-7,347) | 518x (513-530) | 212.075 | 183.076 | 212.210 | -0.064% |

Summary excluding Li-6:

- Kernel speedup range: 2,739x to 7,196x.
- Kernel speedup median: 3,954x.
- Wall speedup range: 324x to 518x.
- Wall speedup median: 423x.
- SaG4n yield agreement with Mendoza: all retained nuclides within 1.6%.

Yields are reported as neutrons per 10^6 incident alpha particles.

## Interpretation

The kernel speedup is the comparison most directly tied to the numerical
transport calculation: `median(T_SaG4n wall) / median(T_ALPHANSO calc)`. This
is favorable to ALPHANSO because it excludes Python startup/import time, while
SaG4n's time includes Geant4 initialization and data loading.

The wall speedup is the more conservative user-facing comparison:
`median(T_SaG4n wall) / median(T_ALPHANSO subprocess wall)`. Even under this
more conservative definition, ALPHANSO is several hundred times faster for the
five retained nuclides.

The SaG4n yields reproduce the Mendoza Table 2 reference values well. This is
important because it indicates the SaG4n run configuration is close enough to
the Mendoza setup for timing comparison, despite using current upstream SaG4n
and Geant4 11.2.1 rather than Mendoza's modified Geant4 10.5.

## Caveats

- This is not a binary-identical reproduction of Mendoza et al.; Mendoza used a
  modified Geant4 10.5 build, while this run used upstream SaG4n `v1.5` with
  Geant4 11.2.1.
- The run was performed on a shared LLNL workstation, not an isolated HPC node.
  The final successful run printed a warning that the 1-minute load average was 7.31, so
  timing noise from other users may be present.
- Li-6 is excluded from the ALPHANSO yield/speedup interpretation because
  ALPHANSO returned zero yield for Li-6, a known ALPHANSO issue.
- The summary files `results/versions.json`, `results/timings.json`,
  `results/faithfulness.json`, and `analysis/table.md` were empty in the local
  checkout, even though the run log shows `06_analyze_results.py` wrote them on
  CELA. This appears to be a Git staging/transfer artifact, not a benchmark
  failure. The table above was reconstructed from `results/raw/*.json`.
- The committed `results/runlogs/latest.log` is a symlink whose target log file
  was not committed. The relevant log excerpt was supplied separately and
  confirms all benchmark and analysis steps completed.

## Missing System Fingerprint

I do not have the complete CELA system details locally. The committed
`SaG4n-timing/results/versions.json` is zero bytes, so the CPU model, kernel,
compiler version, CPU governor, and full package fingerprint were not preserved.
This does not affect the timing results above: those were reconstructed from
the complete raw trial records under `results/raw/*.json`.

The fingerprint can be regenerated on CELA without rerunning the benchmark.
This captures the system state at regeneration time rather than exactly at
timing time, but it should still be valid for stable fields such as CPU model,
kernel, compiler, Geant4 version, SaG4n commit, and ALPHANSO version. The run
log supplies the timing-time load warning: 1-minute load average was 7.31.

Recommended regeneration command:

```sh
cd /home/nelson254/alphanso-analysis/SaG4n-timing

venv/bin/python - <<'PY'
import importlib.util, json
from pathlib import Path

script = Path("scripts/05_run_benchmark.py").resolve()
spec = importlib.util.spec_from_file_location("bench", script)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

versions = bench.capture_versions()
Path("results/versions.json").write_text(json.dumps(versions, indent=2) + "\n")
print(json.dumps(versions, indent=2))
PY
```

Then commit the regenerated fingerprint:

```sh
git add -f results/versions.json
git commit -m "Add CELA timing system fingerprint"
git push
```

If the Python helper is not available for some reason, retrieve the main
details manually:

```sh
cd /home/nelson254/alphanso-analysis/SaG4n-timing

uname -a
lscpu | sed -n '1,25p'
g++ --version | head -1
cmake --version | head -1
./geant4_install/bin/geant4-config --version
git -C SaG4n_src rev-parse HEAD
git -C SaG4n_src describe --tags --always --dirty
venv/bin/pip show alphanso | grep -E '^(Name|Version|Location):'
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || true
```

If the original run log still exists on CELA, also retrieve:

```sh
ls -lh results/runlogs/
git add -f results/runlogs/run_*.log
git commit -m "Add complete CELA timing run log"
git push
```
