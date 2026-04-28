# SaG4n Timing Results

Brief summary of the CELA timing run comparing ALPHANSO against SaG4n for the
Mendoza et al. Table 2 fastest-step configuration.

## System And Software

- Workstation: LLNL CELA.
- Kernel: `Linux cela.llnl.gov 4.18.0-553.82.1.el8_10.x86_64 #1 SMP Thu Oct 23 16:05:55 EDT 2025 x86_64 x86_64`.
- CPU: Intel Xeon Platinum 8280 CPU @ 2.70 GHz.
- Python: 3.11.15.
- SaG4n: upstream `UIN-CIEMAT/SaG4n`, commit `9bd52c2ec6f9e3c9720bd982aadbc22b339a7539` (`v1.5`).
- Geant4: 11.2.1; SaG4n runtime banner reported `geant4-11-02-patch-01`.
- ALPHANSO: `alphanso 1.0.1`

## Methods

- Physics setup: 10^7 alpha particles at 10 MeV, `F_B = 10^3`, `S_max = 0.1 mm`, `G4EmStandardPhysics_option4`.
- Targets: isotopically pure 5 cm cube at 1 g/cm^3.
- Timing protocol: 3 SaG4n trials per nuclide; 31 ALPHANSO subprocess trials per nuclide with trial 0 dropped as warmup, leaving 30 timed ALPHANSO trials per nuclide.
- SaG4n faithfulness gate: the first SaG4n run for each nuclide was compared against Mendoza Table 2 reference yields before timing results were accepted. All six nuclides passed. This first successful faithfulness run was retained as SaG4n trial 0, followed by two additional SaG4n timing trials.
- Each SaG4n and ALPHANSO invocation was a separate process.
- Threading: both engines run as single-process, single-thread jobs
- Timing definitions: SaG4n timing is full subprocess wall time. ALPHANSO `calc` time is measured around `Transport.calculate(...)` inside the subprocess; ALPHANSO `wall` time includes subprocess startup, Python import, calculation, and shutdown.
- Summary statistic: medians are reported for each timing vector. Speedups are `median(T_SaG4n wall) / median(T_ALPHANSO)`.
- Confidence intervals: 95% bootstrap confidence intervals with 10,000 resamples over the SaG4n and ALPHANSO trial vectors.

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

Yields are reported as neutrons per 10^6 incident alpha particles. Don't worry about the yield values - it's just to confirm that we are running the same calcs as the Mendoza paper. Since yields agree, we have extra confidence that it's essentially the same.

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
    - Li-6 is excluded from the ALPHANSO yield/speedup interpretation because
      ALPHANSO returned zero yield for Li-6, a known ALPHANSO issue.
      