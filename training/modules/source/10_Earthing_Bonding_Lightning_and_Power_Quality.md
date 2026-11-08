# Module 10: Earthing, Bonding, Lightning and Power Quality

_Ohmetry engineering learning suite. Generated 2026-11-08 12:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Estimate a grid resistance and ground potential rise.
- Explain touch and step voltage and why a screening is not a design.
- Say what a lightning risk assessment decides.
- Calculate voltage unbalance and THD from measurements.

## Technical explanation

Earthing serves safety (touch and step voltages), protection (a low-impedance path for fault current) and function. The grid resistance depends on the soil resistivity and the grid geometry. The ground potential rise is the earth-fault current into the grid times that resistance. If it is below the tolerable touch voltage, a screening passes; if not, a detailed mesh and step calculation is needed.

Lightning protection starts with a risk assessment (IEC 62305-2). The equivalent collection area and the flash density give the expected number of dangerous events, one input to the risk. Compliance cannot be claimed without a complete assessment.

Power quality is measured, not designed from a formula: voltage unbalance, harmonic distortion, flicker and frequency are compared with limits taken from the project requirements. The measurement instrument and conditions are part of the evidence.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Grid resistance (Sverak) | `Rg = rho [1/L + 1/sqrt(20 A) (1 + 1/(1 + h sqrt(20/A)))]` | ohm |
| Ground potential rise | `GPR = Ig x Rg` | V |
| THD | `THD = sqrt(sum Vh^2) / V1` | % |
| Unbalance | `max deviation from the mean / mean` | % |

## Worked example (reference project configuration)

- Soil resistivity, grid geometry and earth-fault current are pending site data in the reference project; the earthing workbook reads NOT CALCULATED.
- Teaching inputs only (not project data): 100 ohm.m soil, 2,500 m2, 1,200 m of conductor, 0.5 m depth give Rg = 0.959 ohm.
- Power quality and lightning workbooks are input registers: they calculate only from the measurements and site data you enter.

## Common engineering mistakes

- Assuming soil resistivity instead of surveying it.
- Treating a screening pass as an earthing design.
- Claiming lightning compliance from a collection area.

## Practical design checklist

- [ ] Is there a soil survey with the method stated?
- [ ] Is the clearing time from the protection study?
- [ ] Are the PQ limits taken from the project requirements, with the instrument stated?

## Exercise

**10.1.** Teaching inputs: soil 100 ohm.m, grid area 2,500 m2, buried conductor 1,200 m, depth 0.5 m. What is the grid resistance in ohm?

**10.2.** Line voltages measured 400, 404 and 396 V. What is the voltage unbalance (maximum deviation from the mean divided by the mean) in percent?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
