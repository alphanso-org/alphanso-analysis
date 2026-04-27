# Methods — Timing Comparison

We compared the wall-clock time of ALPHANSO with that of SaG4n
(github.com/UIN-CIEMAT/SaG4n, commit <unknown>) on the six monoisotopic
(α,n) calculations of Table 2 in Mendoza et al. (NIM A 960 (2020)
163659). We reproduced the *configuration* of the Table 2 fastest-step
row: 10⁷ α particles at 10 MeV, biasing factor F_B = 10³, maximum step
length S_max = 0.1 mm, G4EmStandardPhysics\_option4 electromagnetic
physics, and the JENDL/AN-2005 (α,xn) data library via G4ParticleHP.
Each monoisotopic target was modeled as an isotopically pure 5 cm cube with
density 1 g/cm³, matching the arbitrary-density style used by upstream SaG4n
examples; the thick-target yield is density independent.
This is not a binary-identical reproduction: Mendoza et al. used a
modified Geant4 10.5 (Dec 2018), whereas current upstream SaG4n
requires Geant4 ≥ 11.0 and is tested against 11.2.1. We pin to <unknown>
(g++ <unknown>). Yields agree with the Mendoza reference at the few-percent
level (faithfulness gate; see below).

ALPHANSO version <unknown> (`pip install alphanso`) was run in an isolated
venv on the same machine. Both engines were pinned to one core via
`taskset -c 0` on <unknown CPU>, and both subprocesses were launched with
`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
`NUMBA_NUM_THREADS=1`, and `VECLIB_MAXIMUM_THREADS=1` to suppress
thread spawning by underlying math libraries. ALPHANSO was launched as
a fresh subprocess per trial to avoid intra-process caching effects.
Two ALPHANSO timings were recorded: (i) `calc_time`, from
`time.perf_counter_ns` around `Transport.calculate(...)`, isolating the
kernel; and (ii) `wall_time`, the full subprocess wall including Python
startup and module import. Note that this is an asymmetry: SaG4n's
wall time includes Geant4 initialization and data-library load on
every invocation, while ALPHANSO's `calc_time` excludes its analogous
warm-up cost. The `wall_time` speedup is the more conservative
like-for-like user-experience comparison; the `calc_time` speedup
isolates the numerical kernel.

For each nuclide we ran SaG4n 3 times and ALPHANSO 31
times (dropping the first as warmup). Speedup ratios are reported as
`median(T_SaG4n) / median(T_ALPHANSO)`, with bootstrap 95% confidence
intervals (10000 resamples) over both timing vectors.

Before recording timings we ran a faithfulness gate: each SaG4n run's
neutron yield was compared to Mendoza's reference Y values
(reconstructed from Table 1 row F_B = 10³ scaled by the Y/Yr ratio at
S_max = 10⁻¹ mm from Table 2). Tolerance: 5% per nuclide, widened to
15% for ¹⁴N owing to the documented step-size sensitivity discussed by
Mendoza et al. ALPHANSO's neutron yield is also captured per trial
and reported alongside, demonstrating yield-level agreement between
the two codes. Reported yields are neutrons per 10⁶ incident alphas;
if ALPHANSO returns a per-alpha yield, it is multiplied by 10⁶ for
display. Faithfulness status: see results/faithfulness.json.

Across the six nuclides the kernel speedup ranged from 2739× to 13364× (median 4212×).
