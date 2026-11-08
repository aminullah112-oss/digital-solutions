# Module 09: Short-Circuit Fundamentals and Protection Coordination

_Ohmetry engineering learning suite. Generated 2026-11-08 12:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Describe the IEC 60909 steps for a maximum fault level.
- Explain peak and thermal equivalent currents.
- Say what selectivity is and what it needs.
- List the data a coordination study cannot do without.

## Technical explanation

The initial symmetrical short-circuit current is Ik'' = c x U / (sqrt3 x |Z|), where Z is the total impedance from the sources to the fault and c is a voltage factor. Sources are the utility, the transformer and the generators, each converted to an impedance at the fault voltage. The peak current is kappa x sqrt2 x Ik'', and the thermal effect of a fault of duration t is the thermal equivalent current. Equipment must withstand all three.

The utility's fault level and X/R ratio are written statements from the utility. Transformer impedance and generator reactance are manufacturer data. Until they exist the engine reports NOT CALCULATED and does not substitute defaults. The transformer-limited bound, which needs only the transformer data, is a legitimate first number.

Selectivity (discrimination) means only the device nearest the fault trips. It needs the time-current curves of every device and a study at the relevant fault levels. Without curves it cannot be asserted, so the protection workbook never reports a coordination pass.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Initial fault current | `Ik'' = c U / (sqrt3 |Z|)` | kA |
| Peak current | `ip = kappa sqrt2 Ik''` | kA |
| Peak factor | `kappa = 1.02 + 0.98 exp(-3 R/X)` | - |

## Worked example (reference project configuration)

- Reference project: transformer-limited LV bound 82.6 kA with the 6 % preliminary impedance.
- Utility, generator and parallel cases read NOT CALCULATED: the utility fault level and generator reactance are not supplied.
- Protection coordination reads NOT VERIFIED: no device curves, no network study.

## Common engineering mistakes

- Selecting equipment ratings before the fault level exists.
- Adding the generator and utility contributions when they never run in parallel (or forgetting to when they do).
- Calling a coordination chart a study without the manufacturers' curves.

## Practical design checklist

- [ ] Is the maximum and the minimum fault level calculated?
- [ ] Is the operating arrangement (open or closed transition) decided?
- [ ] Are device curves and a study reference recorded?

## Exercise

**9.1.** A source has R/X = 0.1 (X/R = 10) and Ik'' = 40 kA. What is the peak current?

**9.2.** A utility has S''kQ = 250 MVA at 13.8 kV with c = 1.10. What is the initial fault current at the MV bus in kA?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
