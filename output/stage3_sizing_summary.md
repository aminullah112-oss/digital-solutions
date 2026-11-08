# OHM-DC-2000: power system sizing summary (Stage 3)

Revision A2. Generated 2026-11-05 05:31 UTC. Release state DEVELOPMENT.

**PRELIMINARY. Not construction-ready and not verified. Every rating, derating factor and efficiency here is an illustrative assumption for the sample project at ideal conditions, except the loading policy, which is a preliminary Ohmetry design policy and not an IEC acceptance limit. Manufacturer data is outstanding. Engineering verification is required.**

## Load basis

IT 2,000 kW. Facility 2,697.3 kW (2,865.6 kVA). Growth allowance 0 %. Source of the demand figures: Preliminary assumption. No external data yet. (2026-11-05).

## Transformers

Policy: preferred target 90 %, maximum 100 % of the derated continuous rating. Rating each 3,150 kVA; derating factors ambient 1, altitude 1, installation 1 (combined 1); derated 3,150 kVA.

| Scenario | Credible | Load | Units | Derated capacity | Loading | Status |
|---|---|---|---|---|---|---|
| TX-NORMAL: Normal operation: the more heavily loaded path on its own units | yes | 1,433 kVA | 1 | 3,150 kVA | 45.5 % | PASS |
| TX-PATH-OUT: Loss of the other path: the surviving path carries the whole load | yes | 2,866 kVA | 1 | 3,150 kVA | 91.0 % | WARNING |

**Worst credible case: TX-PATH-OUT, 91.0 %, WARNING.**

Rating each needed to meet the preferred target: 3,184 kVA (next size in the configured list: 4,000).
Rating each needed to stay at the maximum: 2,866 kVA (next size in the configured list: 3,150).

- Loading is taken against the derated continuous rating. Short-duration emergency overload (for example IEC 60076-7) is not used to justify continuous loading.
- The surviving transformer is evaluated under loss of the other supply path with the contingency derating factor.
- Transformer impedance, losses, cooling class and the manufacturer's loading guide are manufacturer data: present as an assumption.

## UPS: kW

Policy: preferred target 80 %, maximum 100 % of the derated continuous rating. Rating each 2,500 kW; derating factors ambient 1, altitude 1, installation 1 (combined 1); derated 2,500 kW.

| Scenario | Credible | Load | Units | Derated capacity | Loading | Status |
|---|---|---|---|---|---|---|
| UPS-NORMAL: Normal operation: the more heavily loaded path on its own units | yes | 1,000 kW | 1 | 2,500 kW | 40.0 % | PASS |
| UPS-PATH-OUT: Loss of the other path: the surviving path carries the whole load | yes | 2,000 kW | 1 | 2,500 kW | 80.0 % | PASS |

**Worst credible case: UPS-PATH-OUT, 80.0 %, PASS.**

Rating each needed to meet the preferred target: 2,500 kW (next size in the configured list: 2,500).
Rating each needed to stay at the maximum: 2,000 kW (next size in the configured list: 2,000).

- Both the kW and kVA limits are checked. Overload capability is not used. Each UPS is assumed to carry the whole critical load when the other path is lost (2N).

## UPS: kVA

Policy: preferred target 80 %, maximum 100 % of the derated continuous rating. Rating each 2,500 kVA; derating factors ambient 1, altitude 1, installation 1 (combined 1); derated 2,500 kVA.

| Scenario | Credible | Load | Units | Derated capacity | Loading | Status |
|---|---|---|---|---|---|---|
| UPS-NORMAL: Normal operation: the more heavily loaded path on its own units | yes | 1,053 kVA | 1 | 2,500 kVA | 42.1 % | PASS |
| UPS-PATH-OUT: Loss of the other path: the surviving path carries the whole load | yes | 2,105 kVA | 1 | 2,500 kVA | 84.2 % | WARNING |

**Worst credible case: UPS-PATH-OUT, 84.2 %, WARNING.**

Rating each needed to meet the preferred target: 2,632 kVA (next size in the configured list: 3,000).
Rating each needed to stay at the maximum: 2,105 kVA (next size in the configured list: 2,250).

- Both the kW and kVA limits are checked. Overload capability is not used. Each UPS is assumed to carry the whole critical load when the other path is lost (2N).

## Generators (PRP basis): alternator kVA

Policy: preferred target 80 %, maximum 100 % of the derated continuous rating. Rating each 2,000 kVA; derating factors ambient 1, altitude 1, installation 1 (combined 1); derated 2,000 kVA.

| Scenario | Credible | Load | Units | Derated capacity | Loading | Status |
|---|---|---|---|---|---|---|
| GEN-NORMAL: Normal operation: the more heavily loaded path on its own units | yes | 1,427 kVA | 3 | 6,000 kVA | 23.8 % | PASS |
| GEN-PATH-OUT: Loss of the other path: the surviving path carries the whole load | yes | 2,854 kVA | 3 | 6,000 kVA | 47.6 % | PASS |
| GEN-UNIT-OUT: Loss of one unit (N+1): the path load on the remaining units | yes | 1,427 kVA | 2 | 4,000 kVA | 35.7 % | PASS |
| GEN-PATH-OUT-UNIT-OUT: Loss of the other path and one unit: beyond an N+1 design basis | no (informational) | 2,854 kVA | 2 | 4,000 kVA | 71.4 % | NOT APPLICABLE |

**Worst credible case: GEN-PATH-OUT, 47.6 %, PASS.**

Rating each needed to meet the preferred target: 1,189 kVA (next size in the configured list: 1,250).
Rating each needed to stay at the maximum: 951 kVA (next size in the configured list: 1,000).

- Rating basis: PRP, ASSUMED and NOT confirmed by manufacturer documentation. PRP (Prime Power), ESP (Emergency Standby Power) and COP (Continuous Power) are different ISO 8528 ratings and are not interchangeable.
- PRP is the default basis. ESP is selectable but should not be relied on for prolonged outages.
- No overload capability is used. Final selection must be verified against manufacturer data for load steps, UPS interaction, harmonics, altitude and ambient temperature.
- Lightly loaded generators need the manufacturer's minimum-load guidance. A low loading percentage is not automatically better.

## Generators: engine kW (kVA rating x rated power factor, a placeholder)

Policy: preferred target 80 %, maximum 100 % of the derated continuous rating. Rating each 1,600 kW; derating factors ambient 1, altitude 1, installation 1 (combined 1); derated 1,600 kW.

| Scenario | Credible | Load | Units | Derated capacity | Loading | Status |
|---|---|---|---|---|---|---|
| GEN-NORMAL: Normal operation: the more heavily loaded path on its own units | yes | 1,344 kW | 3 | 4,800 kW | 28.0 % | PASS |
| GEN-PATH-OUT: Loss of the other path: the surviving path carries the whole load | yes | 2,687 kW | 3 | 4,800 kW | 56.0 % | PASS |
| GEN-UNIT-OUT: Loss of one unit (N+1): the path load on the remaining units | yes | 1,344 kW | 2 | 3,200 kW | 42.0 % | PASS |
| GEN-PATH-OUT-UNIT-OUT: Loss of the other path and one unit: beyond an N+1 design basis | no (informational) | 2,687 kW | 2 | 3,200 kW | 84.0 % | NOT APPLICABLE |

**Worst credible case: GEN-PATH-OUT, 56.0 %, PASS.**

Rating each needed to meet the preferred target: 1,120 kW.
Rating each needed to stay at the maximum: 896 kW.

- Rating basis: PRP, ASSUMED and NOT confirmed by manufacturer documentation. PRP (Prime Power), ESP (Emergency Standby Power) and COP (Continuous Power) are different ISO 8528 ratings and are not interchangeable.
- PRP is the default basis. ESP is selectable but should not be relied on for prolonged outages.
- No overload capability is used. Final selection must be verified against manufacturer data for load steps, UPS interaction, harmonics, altitude and ambient temperature.
- Lightly loaded generators need the manufacturer's minimum-load guidance. A low loading percentage is not automatically better.

### Loss of the largest generator and remaining capacity

Rating basis PRP: **ASSUMED, NOT confirmed. The 2,000 kVA rating must not be treated as PRP until the manufacturer confirms it**. Derating: ambient, altitude and installation factors are placeholders unless the manufacturer's values are entered.

| Scenario | Units running | Remaining capacity (kVA) | Remaining capacity (kW) | Load (kVA) | Load (kW) | kVA loading | kW loading | Credible |
|---|---|---|---|---|---|---|---|---|
| GEN-NORMAL | 3 | 6,000 | 4,800 | 1,427 | 1,344 | 23.8 % | 28.0 % | yes |
| GEN-PATH-OUT | 3 | 6,000 | 4,800 | 2,854 | 2,687 | 47.6 % | 56.0 % | yes |
| GEN-UNIT-OUT | 2 | 4,000 | 3,200 | 1,427 | 1,344 | 35.7 % | 42.0 % | yes |
| GEN-PATH-OUT-UNIT-OUT | 2 | 4,000 | 3,200 | 2,854 | 2,687 | 71.4 % | 84.0 % | no (informational) |

Still to be verified from manufacturer documentation: actual PRP rating in kW and kVA, site derating for ambient temperature and altitude, load-step capability and transient response, UPS rectifier interaction and harmonic loading, continuous operating limits and manufacturer restrictions.

### Load steps and transient performance (generators)

Upper bound: each block applied at once at its steady-state demand. Soft starting, rectifier walk-in and sequencing are not modelled.

| Step | Block | Step size | Percent of running capacity |
|---|---|---|---|
| STEP-1 | UPS input (IT load and UPS losses) | 2,215 kVA | 36.9 % |
| STEP-2 | Mechanical and cooling plant | 601 kVA | 10.0 % |
| STEP-3 | Lighting, small power and auxiliary | 41 kVA | 0.7 % |

Status: **NOT VERIFIED**. Data required for the transient verification:

- Manufacturer maximum single load step (%) at the site conditions
- Frequency and voltage dip limits of the loads and the UPS during a step
- UPS rectifier walk-in time and input harmonic current on generator supply
- Generator transient response (frequency and voltage recovery) for the proposed step sequence
- Motor starting current and method for each mechanical load
- Harmonic voltage distortion with the UPS rectifier load, and the effect on the alternator rating

## Battery (interface only)

Critical load 2,000 kW for 10 min is 333 kWh at the UPS output. Status: **NOT VERIFIED**.

- Energy at the UPS output = critical load x autonomy. It is arithmetic, not a battery size.
- A battery is sized from the manufacturer's constant-power discharge table (W per cell to the end-of-discharge voltage at the autonomy time), at the end-of-life and temperature conditions. That data is missing, so no battery is sized.
- String configuration, DC bus voltage and cell count cannot be determined without it.

Missing: battery.dc_bus_voltage_v, battery.inverter_efficiency_pct, battery.end_of_life_capacity_factor, battery.temperature_correction_factor, battery.design_margin_factor, battery.constant_power_discharge_data

## Outstanding manufacturer data

- `equipment.generator_esp_rating`: Generator ESP rating (each)
- `equipment.generator_cop_rating`: Generator COP rating (each)
- `generators.prp_max_average_load_factor_pct`: PRP maximum average load factor
- `generators.operating_hours_restriction`: PRP operating-hour restriction
- `generators.overload_capability`: Manufacturer overload capability
- `generators.max_step_load_pct`: Maximum single load step
- `generators.max_frequency_dip_pct`: Maximum frequency dip allowed
- `generators.max_voltage_dip_pct`: Maximum voltage dip allowed
- `generators.ups_rectifier_walk_in_s`: UPS rectifier walk-in time
- `generators.ups_input_current_thd_pct`: UPS input current THD
- `battery.dc_bus_voltage_v`: DC bus voltage
- `battery.inverter_efficiency_pct`: Inverter efficiency on battery
- `battery.end_of_life_capacity_factor`: End-of-life capacity factor
- `battery.temperature_correction_factor`: Temperature correction factor
- `battery.constant_power_discharge_data`: Constant-power discharge data reference

## Verification required before any use

- Manufacturer sizing for each generator, UPS and transformer at the site conditions, including derating, load steps, UPS interaction, harmonics, altitude and ambient temperature.
- Battery sizing from the manufacturer's constant-power discharge data.
- Specialist studies where required: short-circuit, protection coordination, arc flash, harmonics, transients (Stages 4 and 5 and beyond).
- Independent engineering review of every assumption in `config/assumptions_register.yaml`.
