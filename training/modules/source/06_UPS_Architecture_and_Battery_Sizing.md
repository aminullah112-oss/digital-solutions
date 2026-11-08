# Module 06: UPS Architecture and Battery Sizing

_Ohmetry engineering learning suite. Generated 2026-11-08 18:00 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Check a UPS in both kW and kVA.
- Explain why a battery cannot be sized from energy alone.
- Calculate the energy a battery must deliver.
- List the manufacturer data a battery calculation needs.

## Technical explanation

A UPS has an active power rating in kW and an apparent power rating in kVA. A load with power factor below unity can reach the kVA limit before the kW limit. The reference UPS is 2,500 kW and 2,500 kVA, so a 0.95 power factor load is kVA-limited.

In a 2N design each UPS must carry the whole critical load when the other path is lost. The battery bridges the time until the generators accept load. The energy at the UPS output is the critical load times the autonomy. That is arithmetic, not a battery selection: batteries are sized from the manufacturer's constant-power discharge table at end of life and the room temperature, because capacity falls as the discharge rate rises.

Ageing, temperature and design margin factors convert the energy into a nameplate energy. They are battery-specific and are never assumed in the Ohmetry package.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Energy at the UPS output | `E = P x t / 60` | P in kW, t in min, E in kWh |
| Indicative nominal energy | `E_nom = E / eta_inv / (k_EOL x k_temp) x k_margin` | kWh |

## Worked example (reference project configuration)

- Critical load 2,000 kW for 10 min = 333.3 kWh at the UPS output.
- UPS kW loading 80.0 % and kVA loading 84.2 %: the kVA limit governs (check WARNING).
- No battery is selected: the discharge data and correction factors are pending.

## Common engineering mistakes

- Sizing a battery from nameplate ampere-hours without the discharge table.
- Checking the UPS in kW only.
- Forgetting the inverter efficiency between the battery and the load.

## Practical design checklist

- [ ] Is the autonomy time tied to the generator start and transfer time?
- [ ] Are end-of-life and temperature factors from the manufacturer?
- [ ] Are kW and kVA both within limits?

## Exercise

**6.1.** A UPS must supply 1,800 kW for 12 minutes. What energy must the battery deliver at the UPS output?

**6.2.** Teaching values (not data): the energy is 360 kWh, inverter efficiency 96 %, end-of-life factor 0.8, temperature factor 0.95, margin 1.1. What is the indicative nominal energy?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
