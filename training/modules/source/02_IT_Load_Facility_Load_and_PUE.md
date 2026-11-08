# Module 02: IT Load, Facility Load and PUE

_Ohmetry engineering learning suite. Generated 2026-11-08 20:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Build a facility load from IT, cooling, lighting and losses.
- Explain why real and reactive power are added separately.
- Calculate UPS losses from efficiency and the PUE of a design point.
- State why a design-point PUE is not an annual PUE.

## Technical explanation

The IT load is the reason the facility exists. Everything else supports it: mechanical cooling, lighting and small power, auxiliaries, and the losses in the UPS and the distribution. Each item has a quantity, a unit rating, a demand factor and a power factor. Demand is connected load times demand factor. Real power adds directly. Reactive power also adds directly. Apparent power is then the square root of the sum of squares, never the sum of the apparent powers.

UPS losses follow from efficiency: if the UPS delivers P_IT at efficiency eta, it draws P_IT / eta, so the loss is P_IT x (100/eta - 1) with eta in percent. Distribution losses are taken here as a single percentage of the load supplied, which is a placeholder for the transformer and cable loss data.

PUE is facility energy over IT energy. The workbook value is a design-point power ratio: facility kW over IT kW at the design point. An annual PUE needs annual load profiles and ambient conditions and is a different number.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Demand | `P = N x P_unit x DF` | kW |
| UPS loss | `P_loss = P_IT x (100 / eta - 1)` | eta in % |
| PUE (design point) | `PUE = P_facility / P_IT` | - |

## Worked example (reference project configuration)

- IT load 2,000 kW; UPS efficiency 96 % gives UPS losses 83.3 kW; distribution losses 26.7 kW.
- Facility load 2,697.3 kW, 967.5 kvar, 2,865.6 kVA; power factor 0.941.
- Design-point PUE = 2,697.3 / 2,000 = 1.349 against a target of 1.35.

## Common engineering mistakes

- Adding kVA figures arithmetically.
- Forgetting the UPS losses, which understates the load and the PUE.
- Quoting a design-point PUE as an annual figure.

## Practical design checklist

- [ ] Is every load item flagged with its basis (estimated or measured)?
- [ ] Are losses included in the facility load?
- [ ] Is the PUE labelled design point or annual?

## Exercise

**2.1.** A UPS delivers 2,000 kW and its efficiency is 94 %. What are its losses?

**2.2.** Using the reference project with the UPS efficiency changed to 94 % (everything else unchanged), what is the design-point PUE? Answer to 3 decimals.

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
