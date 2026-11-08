# Module 07: LV Distribution and Switchgear Selection

_Ohmetry engineering learning suite. Generated 2026-11-08 12:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Calculate the rated current a busbar or busduct must have.
- Explain verification evidence for assemblies.
- Link the short-circuit rating to the fault level.
- Describe the data a switchgear specification needs.

## Technical explanation

Low-voltage assemblies are specified by rated current, short-circuit withstand, form of separation, ingress protection and evidence that the design was verified (IEC 61439). Medium-voltage switchgear follows IEC 62271. The assembly's ratings come from the manufacturer's verification, not from the project. The designer states the requirement and checks the evidence.

The required rated current is the design current divided by the derating factors. The short-circuit rating must exceed the prospective fault level at the busbars, including the peak current, and the breaking capacity of each breaker must exceed the fault level at its location.

In the reference project the required busbar current is large, which is why busduct and a well-designed switchboard layout matter. Ratings are not assumed: the workbook reads NOT VERIFIED until a rating and its evidence are entered.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Required rated current | `I_rated = I_design / k` | A |
| Short-circuit test | `I_cw >= I_k''` | kA |

## Worked example (reference project configuration)

- LV main switchboard design current 4,136 A (path-out). Required rated current with derating 1.0: 4,136 A.
- The short-circuit rating needed is the LV fault level, which is NOT CALCULATED until utility data exists; the transformer-limited bound is the first available number.

## Common engineering mistakes

- Selecting a rating from a catalogue before the fault level is known.
- Accepting a rating without the verification evidence.
- Forgetting that derating applies to busbars as well as cables.

## Practical design checklist

- [ ] Are rated current, short-circuit rating, separation and IP rating all specified?
- [ ] Is the verification evidence listed?
- [ ] Is the peak withstand checked?

## Exercise

**7.1.** A switchboard carries a design current of 4,136 A with a combined derating factor of 0.9. What rated current is required?

**7.2.** A switchboard is rated 65 kA for 1 s and the fault level is 74 kA. Does it pass? Answer PASS or FAIL.

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
