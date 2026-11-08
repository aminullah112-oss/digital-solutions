# Power system sizing: methodology (Stage 3)

Source: `src/ohmetry_dc/calculations/derating.py` and `sizing.py`. Everything here is **preliminary**. It rests on illustrative inputs and on manufacturer data that has not been supplied.

## Loading policy (preliminary Ohmetry design policy, not an IEC acceptance limit)
| Equipment | Preferred target | Maximum continuous loading |
|---|---|---|
| Transformers | 90 % | 100 % of the derated continuous rating |
| UPS | 80 % | 100 % of the derated continuous kW and kVA capability |
| Generators | 80 % | 100 % of the derated PRP rating |

Set in `design_criteria.*_target_loading` and `*_max_loading`. Above the target is WARNING. Above the maximum is FAIL. Exactly at a limit is not above it. A missing limit gives NOT VERIFIED, never PASS. Short-duration overload capability is never used to justify continuous loading, and no code path uses it.

## Derating
Derated rating = rating x ambient factor x altitude factor x installation factor, from `derating.*`. The factors are manufacturer inputs. The code never derives one, and rejects a factor of 0 or above 1. Percentage loading is always taken against the derated rating. The sample uses 1.00 placeholders for ideal conditions (30 degC, 0 m), which is why the `derating_factors` check is NOT VERIFIED. For generators, enter the ratio of the manufacturer's site-derated PRP rating to the reference PRP rating, or 1.00 if the rating entered is already the site rating, so the derating is not counted twice. The transformer has an extra contingency factor for the loss-of-path case (elevated room temperature, reduced cooling).

## Scenarios and "worst credible"
For each equipment type with *n* units per path (two paths):

| Scenario | Load | Units |
|---|---|---|
| NORMAL | the more heavily loaded path | n |
| PATH-OUT | the whole load, on the surviving path | n |
| UNIT-OUT (generators and any equipment with n at least 2) | the path load | n - 1 |
| PATH-OUT-UNIT-OUT | the whole load | n - 1 |

The last case is beyond an N+1 and 2N design basis. It is shown as informational (NOT APPLICABLE) unless `redundancy.double_contingency_credible` is set to True. The status of each equipment check is that of the worst credible scenario, the one with the highest loading. Growth is applied to all loads.

## Per equipment
- **Transformers:** kVA from the load model. The surviving transformer carries the whole facility load when the other path is lost. Short-duration emergency overload (IEC 60076-7) is not used.
- **UPS:** kW and kVA are checked separately. The IT load kVA comes from the item power factors, so kVA can be the limiting figure when kW is not. Each UPS carries the whole critical load when the other path is lost (2N). Only the 2N topology is implemented.
- **Generators:** the rating basis is ISO 8528 Prime Power (PRP) by default, with ESP and COP selectable. PRP, ESP and COP are distinct ratings and the code never borrows one for another: a missing ESP rating gives "not assessed", not the PRP rating. The load is the items flagged `on_generator`, the UPS losses by the IT share on the generator, and distribution losses. N+1 loss-of-unit cases are included. The manufacturer's PRP average load factor and operating-hour restrictions are recorded as inputs; the checks cannot judge them without an outage profile and the manufacturer's values, so that check stays NOT VERIFIED.
- **Load steps and transients:** three load blocks (UPS input, mechanical, other) are applied at once at steady-state demand, as an upper bound, as a percentage of the running capacity. Soft starting, rectifier walk-in and sequencing are not modelled. The status stays NOT VERIFIED regardless, because transient performance needs the manufacturer's data and analysis. If the manufacturer's single-step limit is supplied and the largest block exceeds it, the status is WARNING.
- **Battery:** an interface only. Energy at the UPS output = critical load x autonomy. A battery is sized from the manufacturer's constant-power discharge table at end-of-life and design-temperature conditions, which is missing, so no battery is sized and the status is NOT VERIFIED. If correction factors are supplied, an indicative figure is shown with a warning that it must not be used to select a battery.

## Required rating and suggested size
For each equipment type the required rating per unit is the maximum over the credible scenarios of load / (units available x derating x loading limit), taken for both the target and the maximum. The suggested size is the next entry in a configurable size list. The lists are illustrative, a suggestion and not a selection. Ratings stay configurable and nothing is frozen.

## Demand data and revisions
New load figures go in `demand_data.*` only. Re-run `validate-config`, `run-calculations` and `sizing-summary`. `revision-impact --previous-config OLD.yaml --record "description"` lists the changed inputs, the load changes, **equipment sizing changes** and check status changes, and appends them to `config/design_basis_revisions.yaml` as NOT REVIEWED.

## Limitations
Illustrative inputs. No manufacturer data. No transient, harmonic, short-circuit or protection analysis. Single derating factor per type. Loads transfer fully in path-out cases. Generator light-load behaviour is not assessed. A passing check shows the code behaves as specified, not that the engineering is correct.

## Architecture functions that are not designed (revision A6)

The single-line diagram OHM-DC-2000-SLD-001 and the `FUNCTIONS` sheet of `03_POWER_ARCHITECTURE.xlsx` list twelve architecture functions. The list is held in `models/architecture.py`, so the drawing, the workbook and the outstanding-items register read the same source.

| Function | Status |
|---|---|
| Independence of utility A and utility B | **Not claimed.** Two supplies are drawn; separate feeders, substations and upstream network are not established. |
| Utility to generator transfer and interlocking (ACB-TX / ACB-GEN) | Concept symbol only. Not designed. |
| Generator paralleling and synchronising (a breaker per generator, GCB, onto a generator bus) | Concept symbol only. Not designed. |
| PMS: load sharing and load shedding | Concept symbol only. No shed feeders are selected. |
| UPS static bypass and maintenance bypass | Concept symbol only. Whether the bypass has its own feed is a design decision. |
| Battery isolator and DC protection | Concept symbol only. The battery is not sized, so no rating exists. |
| Protection and measurement boundaries | Not drawn. Relays, CTs, VTs, metering and settings are outside this revision. Arc-flash is out of scope. |
| Utility point of connection; UPS vendor-scope boundary | Boundary markers, to be agreed. |

The load and sizing results do **not** change because of these symbols. They model steady-state loading on the preliminary ratings; transfer times, synchronising behaviour, step loading and bypass operation are not modelled.
