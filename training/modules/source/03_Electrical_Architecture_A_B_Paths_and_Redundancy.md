# Module 03: Electrical Architecture, A/B Paths and Redundancy

_Ohmetry engineering learning suite. Generated 2026-11-08 18:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Explain 2N, N+1 and dual-corded loads.
- List the credible contingencies for a dual-path design.
- Calculate loading of the surviving equipment after loss of a path or a unit.
- Say what a redundancy check does and does not prove.

## Technical explanation

In a 2N arrangement there are two complete, independent paths and each can carry the whole critical load. In N+1 there is one spare unit beyond what the load needs. A common data centre concept is 2N for the UPS and transformer path and N+1 for the generators inside each path. IT equipment with two power supplies (dual-corded) is fed from both paths, so losing one path moves its load to the other.

The sizing question is therefore always: what does the surviving equipment carry after the credible failure, and is that within its derated continuous rating and the project's loading limits. Loss of one path doubles the share on the other. Loss of a path and a unit at the same time is a double contingency: it is shown for information unless the project decides it is credible.

Redundancy arithmetic does not prove independence. Two paths fed from one upstream busbar, one fuel tank or one control system are not independent. That is a design review item, not a formula.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Loading | `loading = load / (units x rating x derating)` | same unit throughout |
| N+1 test | `load <= (n - 1) x rating` | n units per path |

## Worked example (reference project configuration)

- Reference project: path-out loads one transformer with 2,866 kVA against a derated 3,150 kVA: 91.0 % (preliminary).
- Normal operation loads each path at about half: 45.5 %.
- Generators: 3 units per path. Worst credible case (GEN-PATH-OUT-UNIT-OUT) 71.4 % of kVA; with one unit out in normal operation 35.7 %. Workbook 03_POWER_ARCHITECTURE shows all the scenarios.

## Common engineering mistakes

- Calling a design N+1 without checking the load is carried with one unit out.
- Assuming two paths are independent because there are two of everything.
- Ignoring the maintenance case.

## Practical design checklist

- [ ] Is each contingency named and its loading calculated?
- [ ] Is the double contingency decision recorded?
- [ ] Are common points of failure listed?

## Exercise

**3.1.** With the reference load (2,866 kVA on one path after loss of the other), the transformers are changed to 4,000 kVA each. What is the path-out loading, in percent of the derated rating?

**3.2.** A path has 3 generators of 2,000 kVA (derating 1.0). What is the largest load it can carry with one unit out at 80 % of the remaining capacity?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
