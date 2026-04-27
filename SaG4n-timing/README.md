# SaG4n vs ALPHANSO Timing Benchmark

Reproduces the Mendoza 2020 (NIM A 960, 163659) Table 2 fastest-step configuration
(10⁷ α at 10 MeV, F_B = 10³, S_max = 0.1 mm, JENDL/AN-2005, six monoisotopic
targets) on pinned upstream **SaG4n** and **ALPHANSO**, and reports the
speedup factor with bootstrap confidence intervals.

One-shot detached run on CELA:

```sh
./run.sh
./scripts/status.sh
```

GEANT4 and SaG4n compilation are capped to 20% of visible CPUs by default
(`floor(nproc/5)`, minimum 1). Set `BUILD_JOBS=<lower-number>` before
`./run.sh` if you need to be more conservative.

For the lab-box runbook (no Claude, no sudo), see [`timing_instructions.md`](timing_instructions.md).

For the source-of-truth Mendoza Table 2 values, see [`docs/mendoza_table2.md`](docs/mendoza_table2.md).
