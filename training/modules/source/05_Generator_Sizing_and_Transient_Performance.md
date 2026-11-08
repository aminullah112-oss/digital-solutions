# Module 05: Generator Sizing and Transient Performance

_Ohmetry engineering learning suite. Generated 2026-11-05 07:48 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Distinguish prime power (PRP), emergency standby power (ESP) and continuous power (COP) ratings.
- Size N+1 generators in kVA and kW.
- Explain why load steps and the UPS rectifier matter.
- List the manufacturer data a generator study needs.

## Technical explanation

Generator ratings are defined in ISO 8528 and the three bases are not interchangeable. PRP allows unlimited running at variable load with a limit on the average load; ESP is for emergency standby with limited hours and is a poor basis for long outages; COP is for constant load. A rating quoted without its basis is not usable for sizing. The reference project assumes PRP and says that it is not confirmed.

A generator has two limits: the alternator in kVA and the engine in kW. The engine kW is the kVA rating times the rated power factor (0.8 here is a placeholder). Both are checked. N+1 means the load must be carried with the largest unit out.

Steady-state loading is not enough. A UPS rectifier or a large motor applies a step; the generator's frequency and voltage dip depend on the step size, the engine, the alternator and the controls. UPS rectifiers also draw harmonic current that loads the alternator. These need manufacturer data, so the engine reports an upper bound on the step and marks the result NOT VERIFIED.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Engine rating | `P_engine = S_rated x pf_rated` | kW |
| N+1 loading | `loading = load / ((n - 1) x rating x derating)` |  |

## Worked example (reference project configuration)

- 3 x 2,000 kVA per path. Worst credible case (loss of the other path, all units available): 47.6 % of kVA and 56.0 % of kW.
- With one unit out in normal operation: 35.7 % of kVA. Path out and one unit out together is beyond N+1 and is shown for information only: 71.4 % of kVA.
- The step-load check, prime-power load factor and hours restriction all read NOT VERIFIED because the manufacturer data is missing.

## Common engineering mistakes

- Using an ESP rating as if it were prime power.
- Checking kVA only and missing the engine kW limit.
- Reading a low loading percentage as good: light load needs the manufacturer's minimum-load guidance.

## Practical design checklist

- [ ] Is the rating basis stated and confirmed?
- [ ] Are kW and kVA both checked?
- [ ] Is the largest-unit-out case calculated?
- [ ] Are step loads and harmonics covered by manufacturer data?

## Exercise

**5.1.** A generator is rated 2,000 kVA at power factor 0.8. What is its engine kW rating?

**5.2.** A path must carry 2,687 kW. Each generator is rated 1,600 kW and the target is 80 % of the remaining capacity with one unit out. What is the smallest number of generators per path?

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
