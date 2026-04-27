# Mendoza 2020 Table 2 — Reference Values

Source: Mendoza, Cano-Ott, Romojaro, Alcayne, García Abia, Pesudo, Romero,
Santorelli, "Neutron production induced by α-decay with Geant4," Nuclear
Inst. and Methods in Physics Research A 960 (2020) 163659.
DOI: 10.1016/j.nima.2020.163659. PDF in this directory's parent.

## Table 2 (transcribed verbatim)

Caption: "Computation times (using a 2.4 Ghz Intel Gold 6148 processor) and
Y/Yr ratios obtained from simulations of 10⁷ α particles of 10 MeV inside
different thick monoisotopic materials: ²⁸Si, ⁶Li, ¹⁴N, ¹³C, ¹⁹F and ¹⁸O,
for different maximum allowed step lengths S_max. All these calculations
were preformed [sic] with a biasing factor of F_B = 10³ and the JENDL/AN-2005
library."

(Cross-check: Table 2's Y/Yr at S_max=10⁻⁴ mm matches Table 1's Y/Yr at
F_B=10³ to the third decimal for all six nuclides, confirming the 10³.)

| S_max (mm) | ²⁸Si Time(s) | ²⁸Si Y/Yr | ⁶Li Time(s) | ⁶Li Y/Yr | ¹⁴N Time(s) | ¹⁴N Y/Yr | ¹³C Time(s) | ¹³C Y/Yr | ¹⁹F Time(s) | ¹⁹F Y/Yr | ¹⁸O Time(s) | ¹⁸O Y/Yr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10⁻¹ | 2.7×10² | 1.01(3)  | 2.6×10² | 1.002(2) | 2.6×10² | 0.883(2) | 3.5×10² | 0.981(1) | 4.4×10² | 1.001(1) | 3.8×10² | 0.9971(7) |
| 10⁻² | 7.9×10² | 1.02(3)  | 1.0×10³ | 1.002(2) | 1.0×10³ | 0.927(2) | 8.4×10² | 0.948(1) | 1.0×10³ | 0.999(1) | 8.9×10² | 0.9847(7) |
| 10⁻³ | 6.9×10³ | 0.97(3)  | 7.7×10³ | 1.001(2) | 6.3×10³ | 0.991(2) | 7.1×10³ | 0.981(1) | 7.6×10³ | 1.001(1) | 1.0×10⁴ | 0.9855(7) |
| 10⁻⁴ | 6.4×10⁴ | 1.01(3)  | 6.3×10⁴ | 1.002(2) | 5.6×10⁴ | 1.000(2) | 5.4×10⁴ | 0.996(1) | 6.7×10⁴ | 0.998(1) | 6.6×10⁴ | 0.9980(7) |

## Configuration we reproduce

The fastest row (S_max = 10⁻¹ mm = 0.1 mm):

| Parameter | Value |
|---|---|
| α primaries | 10⁷ |
| α kinetic energy | 10.0 MeV |
| Bias factor F_B | 10³ |
| Max step length S_max | 0.1 mm (= 0.01 cm in SaG4n's input units) |
| Physics list | G4EmStandardPhysics_option4 (compiled into upstream SaG4n) |
| Nuclear data | JENDL/AN-2005 |
| Neutron data | G4ParticleHP |
| Mendoza CPU | Intel Xeon Gold 6148 @ 2.4 GHz |

The generated SaG4n input uses a 5 cm cube of an isotopically pure material at
1 g/cm³. Density is not specified in Table 2; for a thick-target yield it
cancels analytically, and this avoids arbitrary physical phase choices for
N, F, and O.

## Reference Y values (from Table 1, F_B = 10³, S_max = 10⁻⁴ mm)

For the faithfulness gate. Y is "neutrons per 10⁶ α particles." Table 1
tabulates Y at S_max = 0.1 μm = 10⁻⁴ mm; we scale by Y/Yr at our S_max
(below) to reconstruct Y_expected at our configuration.

| Nuclide | Y_T1 (F_B=10³) | σ_(α,xn) at 10 MeV (barn) |
|---|---|---|
| ²⁸Si | 0.1268 | 0.0063 |
| ⁶Li  | 22.22  | 0.061  |
| ¹⁴N  | 26.47  | 0.12   |
| ¹³C  | 109.2  | 0.27   |
| ¹⁹F  | 116.2  | 0.47   |
| ¹⁸O  | 212.4  | 0.59   |

(¹⁸O is well-behaved at F_B = 10³ — the F_B = 10⁵ row with 26% uncertainty
that we previously noted does not apply here.)

## Reconstructed expected Y at our config (F_B = 10³, S_max = 10⁻¹ mm)

Y_expected = Y_T1 × (Y/Yr at 10⁻¹ mm) / (Y/Yr at 10⁻⁴ mm), per nuclide:

| Nuclide | Y_expected (per 10⁶ α) |
|---|---|
| ²⁸Si | 0.127 |
| ⁶Li  | 22.22 |
| ¹⁴N  | 23.37 |
| ¹³C  | 107.6 |
| ¹⁹F  | 116.5 |
| ¹⁸O  | 212.2 |

## Faithfulness gate

`|Y_us - Y_expected| / Y_expected < 0.05` per nuclide.

¹⁴N may drift further than 5% — Mendoza notes "deviations of up to 12% are
obtained" for ¹⁴N due to step-size sensitivity. The reference data widens
¹⁴N's tolerance to 15% (`y_tolerance_relative` in
`inputs/mendoza_table2.json`).

## Caveat on the "Mendoza reproduction" claim

Mendoza et al. ran a modified Geant4 10.5 (Dec 2018) tagged for inclusion
in 10.6. Current upstream SaG4n requires Geant4 ≥ 11.0 (tested on 11.2.1).
The benchmark therefore reproduces the *configuration* of Mendoza Table 2
(geometry, source, F_B, S_max, physics list selection, library), not the
exact 2020 binary. Yields agree at the few-percent level — sufficient for
the timing comparison; not sufficient to claim binary-identical
reproduction.
