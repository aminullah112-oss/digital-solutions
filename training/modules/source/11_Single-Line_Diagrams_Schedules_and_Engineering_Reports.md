# Module 11: Single-Line Diagrams, Schedules and Engineering Reports

_Ohmetry engineering learning suite. Generated 2026-11-08 20:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Read a single-line diagram and trace a load back to its source.
- Keep tags consistent across drawings, schedules and calculations.
- Read the four-status result table.
- Write a limitation statement.

## Technical explanation

A single-line diagram shows how the power flows and where the protection sits. Every item has a tag, and the tag is the key that joins the drawing, the equipment schedule, the calculations and the specifications. A diagram that cannot be traced to a calculation is a sketch.

Results are reported with four separate statuses. The calculation status says whether the arithmetic ran on complete inputs. The calculation result says what the numbers show against the criterion. The input-data status says what the inputs are (assumption, placeholder, manufacturer data supplied, verified). The overall design status can be PASS only when the calculation passes and the inputs are verified. A preliminary pass reads NOT VERIFIED.

A report states its scope, its inputs and their status, its limitations, and what it does not cover. Approval fields are filled by the people who approve, never by the software.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Overall status rule | `PASS only if the calculation passes AND every input is verified, reference data or an owner decision` |  |

## Worked example (reference project configuration)

- Reference project at this revision: 9 checks PASS (all arithmetic or consistency checks), 3 WARNING, 0 FAIL, 27 NOT VERIFIED.
- The single-line diagram OHM-DC-2000-SLD-001 and the equipment schedule use the same tags as the workbooks.

## Common engineering mistakes

- Inventing tags in each document.
- Showing ratings on a diagram that were never calculated.
- Filling approval fields on behalf of reviewers.

## Practical design checklist

- [ ] Do all documents share one tag list?
- [ ] Does every rating on a diagram trace to a calculation or a datasheet?
- [ ] Is the status of each rating visible?

## Exercise

**11.1.** A check's calculation result is PASS and its input status is UNVERIFIED_PLACEHOLDER. What is the overall design status?

**11.2.** A check's calculation result is WARNING on preliminary inputs. What is the overall design status?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
