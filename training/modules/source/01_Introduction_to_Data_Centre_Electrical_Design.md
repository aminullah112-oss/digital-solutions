# Module 01: Introduction to Data Centre Electrical Design

_Ohmetry engineering learning suite. Generated 2026-11-05 07:48 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Describe the power chain of a data centre from utility to IT load.
- List the design stages in order and say what each stage decides.
- Distinguish a preliminary assumption from manufacturer-confirmed data.
- Calculate a three-phase current from apparent power and line voltage.

## Technical explanation

A data centre converts utility power into clean, continuous power for IT equipment. The chain is: utility supply, medium-voltage switchgear, transformers, low-voltage switchgear, UPS with batteries, distribution to the IT rooms, with generators and fuel as the long-duration backup and mechanical plant (cooling) as the other large load. Availability is bought with redundancy: duplicate paths, spare units, and the ability to maintain one part while the rest runs.

Design proceeds in stages. The design basis fixes voltages, loads, redundancy and criteria. The load estimate gives real and reactive power. The architecture decides how many paths and units there are. Sizing checks each unit against its derated rating in the worst credible contingency. Distribution sizes cables, busducts and switchgear. The short-circuit study gives the fault levels the equipment must withstand. Protection and earthing follow. Documents, schedules and commissioning close the loop.

The most important habit is to keep three kinds of information apart: standard methods (equations), reference data (published constants), and project data. Project data is further divided into preliminary assumptions and values confirmed by a manufacturer or a survey. A calculation can be correct arithmetic and still say nothing about whether the design works, if its inputs are unconfirmed.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Apparent power | `S = sqrt(P^2 + Q^2)` | P in kW, Q in kvar, S in kVA |
| Three-phase current | `I = S / (sqrt(3) x V)` | S in VA, V line-to-line in V, I in A |

## Worked example (reference project configuration)

- Reference project: 2,000 kW of IT load, dual A/B paths, 2 x 3,150 kVA transformers at 400 V.
- Full-load secondary current of one transformer: I = 3,150,000 / (1.7321 x 400) = 4,546.6 A.
- That current is the reason LV switchgear, busduct and the fault level become demanding at this size. The project's check on it reads NOT VERIFIED: the arithmetic is right, but whether the equipment exists is a manufacturer question.

## Common engineering mistakes

- Mixing kW and kVA in one comparison.
- Sizing from the nameplate rating instead of the derated rating.
- Treating the first estimate as a result instead of a hypothesis to test.
- Quoting a calculated value without saying which inputs were assumed.

## Practical design checklist

- [ ] Is every input labelled assumption, reference, manufacturer or site data?
- [ ] Are voltages, frequency and redundancy written down before sizing starts?
- [ ] Is the worst credible contingency named for each unit?

## Exercise

**1.1.** A transformer is rated 2,500 kVA at 400 V line-to-line. What is its full-load secondary current?

**1.2.** A load draws P = 1,800 kW and Q = 600 kvar. What is the apparent power?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
