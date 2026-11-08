# Module 08: Cable Sizing, Ampacity and Voltage Drop

_Ohmetry engineering learning suite. Generated 2026-11-08 12:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Calculate conductor resistance at an operating temperature.
- Calculate three-phase voltage drop.
- Explain why a tabulated current rating is never assumed.
- Check thermal withstand against a fault.

## Technical explanation

A cable must carry the design current within its tabulated rating (after grouping, ambient and installation derating), keep the voltage drop within the project limit, and survive the fault current for the clearing time. The tabulated rating comes from the standard for the installation method or from the manufacturer; it depends on the cable construction and layout and is not assumed.

Resistance rises with temperature: R = rho20 x (1 + alpha x (T - 20)) / A. Voltage drop in a three-phase circuit is sqrt3 x I x L x (R cos phi + X sin phi). Reactance depends on the layout (trefoil, flat, spacing) and is an input.

The adiabatic equation S >= I x sqrt(t) / k gives the smallest conductor that survives a fault of I for t seconds. With parallel cables the fault current divides between runs. The clearing time comes from the protection study.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Resistance | `R = rho20 (1 + alpha (T - 20)) / A` | ohm per m with A in mm2 |
| Voltage drop | `dV = sqrt3 I L (R cos phi + X sin phi)` | V |
| Thermal withstand | `S >= I sqrt(t) / k` | mm2 |

## Worked example (reference project configuration)

- 630 mm2 copper at 90 C: R = 34.90 micro-ohm per metre.
- Generator cables CAB-GEN-A: 2,887 A on 6 runs (481 A per run), voltage drop 0.474 % against a 3 % limit.
- The tabulated rating is missing, so the ampacity reads NOT VERIFIED while the required rating per run is shown.

## Common engineering mistakes

- Assuming a rating from memory instead of the table for the installation method.
- Using the 20 C resistance for a hot cable.
- Applying the whole fault current to one run of a parallel group.

## Practical design checklist

- [ ] Is the installation method stated and the table from the matching standard?
- [ ] Are grouping and ambient factors applied?
- [ ] Is the clearing time from the protection study?

## Exercise

**8.1.** A 120 mm2 copper conductor operates at 90 C (rho20 = 0.017241 ohm.mm2/m, alpha = 0.00393). What is its resistance in milliohm per metre?

**8.2.** A circuit carries 300 A per run over 40 m at 400 V, power factor 0.9, R = 0.07 mohm/m, X = 0.08 mohm/m. What is the three-phase voltage drop in percent?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
