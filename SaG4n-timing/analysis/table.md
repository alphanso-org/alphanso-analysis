# SaG4n vs ALPHANSO Timing — Mendoza 2020 Table 2 Reproduction

Configuration: 10⁷ α at 10 MeV, F_B = 10³, S_max = 0.1 mm,
G4EmStandardPhysics_option4, JENDL/AN-2005.

| Nuclide | T_SaG4n median (s) | T_ALPHANSO calc median (s) | T_ALPHANSO wall median (s) | Speedup (kernel) | Speedup (wall) | Y_SaG4n | Y_ALPHANSO | Y faithful |
|---|---|---|---|---|---|---|---|---|
| Si-28 | 225.3 | 56.98 ms | 690.66 ms | 3954× (3917–4037) | 326× (323–333) | 0.1287 | 0.1444 | — |
| Li-6 | 223.1 | 16.70 ms | 648.97 ms | 13364× (13172–13504) | 344× (339–348) | 22.19 | 0.0000 | — |
| N-14 | 233.9 | 83.22 ms | 721.09 ms | 2811× (2770–2836) | 324× (320–327) | 23.48 | 26.54 | — |
| C-13 | 318.2 | 71.20 ms | 710.49 ms | 4470× (4455–4484) | 448× (446–449) | 107.82 | 106.13 | — |
| F-19 | 322.0 | 117.54 ms | 761.99 ms | 2739× (2697–2843) | 423× (416–439) | 116.60 | 110.43 | — |
| O-18 | 357.6 | 49.69 ms | 690.21 ms | 7196× (7145–7347) | 518× (513–530) | 212.07 | 183.08 | — |

Bootstrap CIs: 10000 resamples of the SaG4n and ALPHANSO trial vectors (median ratio, 95% CI). Y values are neutrons per 10^6 alpha particles.
