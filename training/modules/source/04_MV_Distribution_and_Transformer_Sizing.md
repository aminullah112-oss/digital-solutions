# Module 04: MV Distribution and Transformer Sizing

_Ohmetry engineering learning suite. Generated 2026-11-05 07:48 UTC. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Learning objectives

- Size a transformer against the worst credible contingency with derating applied first.
- Explain the difference between a preferred loading target and a maximum.
- Describe what the impedance does to the fault level.
- State what must come from the transformer manufacturer.

## Technical explanation

Transformer loading is the load divided by the derated continuous rating. Derating comes first: ambient temperature, altitude and installation reduce what the transformer can carry continuously, and the factors come from the manufacturer's loading guide. Short-duration emergency overload may exist, but it is not used to justify continuous loading.

A project may set a preferred target (here 90 %) and a hard maximum (100 %). A result between them is a WARNING: it needs a decision, not necessarily a change. Such a decision is recorded as an exception with a ceiling and a verification action. An exception never turns a warning into a pass.

The impedance of the transformer sets the fault level downstream: a lower impedance passes more fault current. The LV fault level is limited by the transformer impedance whatever the utility's fault level, which gives a useful upper bound before any utility data exists.

## Key formulas

| Quantity | Formula | Units |
|---|---|---|
| Derated rating | `S_derated = S x k_amb x k_alt x k_inst` | kVA |
| Rating for a target | `S_needed = S_load / (units x target x k)` | kVA |
| Transformer-limited fault current | `I_k'' = c x U / (sqrt3 x K_T x z x U^2 / S_r)` | z per unit |

## Worked example (reference project configuration)

- Path-out: 2,866 kVA on one 3,150 kVA transformer (derating 1.00 placeholders) = 90.97 % against a 90 % target: WARNING.
- A rating of 3,184 kVA each would meet the 90 % target; the owner accepted the exception up to 91.0 % pending verification.
- With a 6 % impedance the transformer-limited LV fault level is 82.6 kA, valid for any utility fault level.

## Common engineering mistakes

- Applying the loading limit to the nameplate instead of the derated rating.
- Using overload capability to make a continuous load fit.
- Picking a larger transformer without checking what it does to the fault level.

## Practical design checklist

- [ ] Are the derating factors from the manufacturer's curve at the site conditions?
- [ ] Is the contingency case the one that governs?
- [ ] Is the exception, if any, recorded with a ceiling?

## Exercise

**4.1.** A path-out load of 2,866 kVA must be carried by one transformer at no more than 90 % of its derated rating, with a combined derating factor of 0.95. What nameplate rating is needed?

**4.2.** For a 2,500 kVA, 6 % transformer at 400 V with a voltage factor c = 1.05, what is the transformer-limited fault level in kA? Use the correction factor K_T = 0.95 c / (1 + 0.6 x 0.06).

_The answer key is a separate document._

## References

- IEC 60909 (short-circuit currents in three-phase AC systems), IEC 60076 (power transformers), IEC 61439 (LV switchgear and controlgear assemblies), IEC 62271 (HV switchgear and controlgear), IEC 62040 (UPS), ISO 8528 (generating sets), IEC 60364 (LV installations), IEEE 80 (substation grounding), IEEE 485 (sizing lead-acid batteries), IEC 62305 (lightning), IEEE 519 (harmonics), ASHRAE 90.4 (energy standard for data centres).
- Availability classification of data centres: Uptime Institute Tier standards and EN 50600 / ISO/IEC 22237. Use the current edition of each.

## Limitations and safety notes

- Educational content for working engineers. It is not accredited professional training and does not replace the standards, the manufacturer's data or the judgement of a qualified engineer.
- Worked examples use the preliminary Ohmetry reference configuration. Its values are assumptions, not manufacturer data. Exercise inputs are teaching values.
- Electrical work is hazardous. Nothing here is a procedure for working on live equipment; follow the site safety rules and applicable regulations.
