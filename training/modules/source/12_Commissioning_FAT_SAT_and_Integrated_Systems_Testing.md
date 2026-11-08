# Module 12: Commissioning, FAT, SAT and Integrated Systems Testing

_Ohmetry engineering learning suite. Generated 2026-11-08 20:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Distinguish factory acceptance, site acceptance and integrated systems testing.
- Plan a failure test sequence.
- Calculate load bank sizes and test energy.
- Describe what records a test must leave.

## Technical explanation

Factory acceptance tests (FAT) prove a unit against its specification at the factory. Site acceptance tests (SAT) prove installation and function on site. Integrated systems testing (IST) proves the whole chain under failure: utility loss, generator start and transfer, UPS and battery behaviour, loss of a path, and return to normal. The acceptance criteria come from the specification and the manufacturer data, not from this course.

Tests are planned with prerequisites, a step sequence, expected results and abort criteria. A load bank supplies a known load so that the generator and UPS can be loaded without the IT load. Records must name the instrument, the calibration, the date and the person.

Commissioning is where a design's assumptions are tested. Every NOT VERIFIED item in the design record should either be closed by a test or carried forward as a stated risk.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Load bank size | `P_bank = target % x P_rated - P_existing` | kW |
| Autonomy test energy | `E = P x t / 60` | kWh |

## Worked example (reference project configuration)

- Generator engine rating 1,600 kW (placeholder). To test one unit at 80 % with no other load needs a 1,280 kW load bank.
- A battery autonomy test at the critical load (2,000 kW) for 10 min removes 333 kWh from the batteries.
- Typical IST steps: simulate utility loss; confirm generator start, transfer and UPS behaviour; lose a path; restore. Each step has an expected result written beforehand.

## Common engineering mistakes

- Testing before the prerequisites (protection settings, interlocks) are verified.
- Not recording instrument calibration.
- Treating a test passed on a load bank as proof of behaviour under the real, non-linear IT load.

## Practical design checklist

- [ ] Is there a written test procedure with expected results?
- [ ] Are safety isolations and abort criteria defined?
- [ ] Does every open NOT VERIFIED item map to a test or a stated risk?

## Exercise

**12.1.** A generator has an engine rating of 1,600 kW. Its existing load is 400 kW. What load bank is needed to test it at 75 % of its rating?

**12.2.** An autonomy test runs a 1,500 kW load for 9 minutes. How much energy leaves the batteries at the UPS output?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
