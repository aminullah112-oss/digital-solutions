# OHM-DC-2000: power system sizing summary (Stage 3)

Revision A6. Generated 2026-11-08 18:00 UTC. Release state DEVELOPMENT.

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
| GEN-PATH-OUT-UNIT-OUT: Loss of the other path and one unit (combined contingency: N+1 engine-out on the surviving path) | yes | 2,854 kVA | 2 | 4,000 kVA | 71.4 % | PASS |

**Worst credible case: GEN-PATH-OUT-UNIT-OUT, 71.4 %, PASS.**

Rating each needed to meet the preferred target: 1,784 kVA (next size in the configured list: 2,000).
Rating each needed to stay at the maximum: 1,427 kVA (next size in the configured list: 1,500).

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
| GEN-PATH-OUT-UNIT-OUT: Loss of the other path and one unit (combined contingency: N+1 engine-out on the surviving path) | yes | 2,687 kW | 2 | 3,200 kW | 84.0 % | WARNING |

**Worst credible case: GEN-PATH-OUT-UNIT-OUT, 84.0 %, WARNING.**

Rating each needed to meet the preferred target: 1,680 kW.
Rating each needed to stay at the maximum: 1,344 kW.

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
| GEN-PATH-OUT-UNIT-OUT | 2 | 4,000 | 3,200 | 2,854 | 2,687 | 71.4 % | 84.0 % | yes |

Still to be verified from manufacturer documentation: actual PRP rating in kW and kVA, site derating for ambient temperature and altitude, load-step capability and transient response, UPS rectifier interaction and harmonic loading, continuous operating limits and manufacturer restrictions.

### Load steps and transient performance (generators)

Upper bound: each block applied at once at its steady-state demand. Soft starting, rectifier walk-in and sequencing are not modelled.

| Step | Block | Step size | Percent of running capacity |
|---|---|---|---|
| STEP-1 | UPS input (IT load and UPS losses) | 2,215 kVA | 55.4 % |
| STEP-2 | Mechanical and cooling plant | 601 kVA | 15.0 % |
| STEP-3 | Lighting, small power and auxiliary | 41 kVA | 1.0 % |

Status: **NOT VERIFIED**. Data required for the transient verification:

- Manufacturer maximum single load step (%) at the site conditions
- Frequency and voltage dip limits of the loads and the UPS during a step
- UPS rectifier walk-in time and input harmonic current on generator supply
- Generator transient response (frequency and voltage recovery) for the proposed step sequence
- Motor starting current and method for each mechanical load
- Harmonic voltage distortion with the UPS rectifier load, and the effect on the alternator rating

## Generator contingency basis

Judged against: N+1 engine-out on the surviving path combined with loss of the other utility path. **The engineer must select and document the contingency basis**; the generator verification table above shows the loading for each candidate basis. A WARNING is never converted to a PASS.

## Transformer and UPS options side by side

Both ratings are shown against the same worst credible contingency, derating (1.00 placeholders) and loading policy (target 90 / 100 % transformers, 80 / 100 % UPS). **The package does not select between them: the engineer does.**

| Equipment | Option | Rating | Loading, worst credible case | Status | Notes |
|---|---|---|---|---|---|
| transformer | Retained (preliminary) | 3,150 kVA | kVA 90.97 % (TX-PATH-OUT) | WARNING | full-load LV current 4,547 A; transformer-limited figure 82.6 kA (not a bus fault level) The transformer-limited figure scales with the rating at the same impedance. It is the utility contribution through one transformer only: not the bus fault level and not a design value. |
| transformer | Illustrative option | 4,000 kVA | kVA 71.64 % (TX-PATH-OUT) | PASS | full-load LV current 5,774 A; transformer-limited figure 104.9 kA (not a bus fault level) EXCEEDS the 100 kA practical limit (an Ohmetry preliminary policy, not a standard limit): a larger transformer at the same impedance raises the LV fault level, so a higher impedance, a split LV bus or a different arrangement would need to be considered with it. The transformer-limited figure scales with the rating at the same impedance. It is the utility contribution through one transformer only: not the bus fault level and not a design value. |
| ups | Retained (preliminary) | 2,500 kW, 2,500 kVA | kW 80.00 % (UPS-PATH-OUT); kVA 84.21 % (UPS-PATH-OUT) | WARNING |  |
| ups | Illustrative option | 3,000 kW, 3,000 kVA | kW 66.67 % (UPS-PATH-OUT); kVA 70.18 % (UPS-PATH-OUT) | PASS |  The kW rating is scaled by the retained kW/kVA ratio. Real UPS ratings and output power factor come from the manufacturer. |

## Sensitivity and load-model review

Illustrative variations chosen by the package. They are not forecasts. Equipment ratings and derating (1.00 placeholders) are as retained.

| Case | IT kW | Facility kW | Facility kVA | PUE | Transformer 3,150 kVA, path out | UPS kW / kVA | Generators kVA / kW, combined contingency |
|---|---|---|---|---|---|---|---|
| IT -10 %, plant held as scheduled | 1,800 | 2,486.9 | 2,644.2 | 1.382 | 83.9 % PASS | 72.0 / 75.8 % PASS | 65.8 / 77.4 % PASS |
| IT +0 %, plant held as scheduled | 2,000 | 2,697.3 | 2,865.6 | 1.349 | 91.0 % WARNING (EX-001 covers) | 80.0 / 84.2 % WARNING | 71.4 / 84.0 % WARNING |
| IT +10 %, plant held as scheduled | 2,200 | 2,907.8 | 3,087.0 | 1.322 | 98.0 % WARNING (EX-001 does NOT cover) | 88.0 / 92.6 % WARNING | 76.9 / 90.6 % WARNING |
| IT -10 %, cooling plant scaled with IT load | 1,800 | 2,432.4 | 2,584.3 | 1.351 | 82.0 % PASS | 72.0 / 75.8 % PASS | 64.3 / 75.7 % PASS |
| IT +0 %, cooling plant scaled with IT load | 2,000 | 2,697.3 | 2,865.6 | 1.349 | 91.0 % WARNING (EX-001 covers) | 80.0 / 84.2 % WARNING | 71.4 / 84.0 % WARNING |
| IT +10 %, cooling plant scaled with IT load | 2,200 | 2,962.3 | 3,146.9 | 1.347 | 99.9 % WARNING (EX-001 does NOT cover) | 88.0 / 92.6 % WARNING | 78.4 / 92.3 % WARNING |

Losses:

| Case | IT kW | Facility kW | Facility kVA | PUE | Transformer 3,150 kVA, path out | UPS kW / kVA | Generators kVA / kW, combined contingency |
|---|---|---|---|---|---|---|---|
| As retained | 2,000 | 2,697.3 | 2,865.6 | 1.349 | 91.0 % WARNING (EX-001 covers) | 80.0 / 84.2 % WARNING | 71.4 / 84.0 % WARNING |
| UPS efficiency 94 % (lighter-load efficiency is usually lower) | 2,000 | 2,742.1 | 2,912.7 | 1.371 | 92.5 % WARNING (EX-001 does NOT cover) | 80.0 / 84.2 % WARNING | 72.5 / 85.4 % WARNING |
| UPS efficiency 98 % | 2,000 | 2,654.4 | 2,820.4 | 1.327 | 89.5 % PASS | 80.0 / 84.2 % WARNING | 70.2 / 82.6 % WARNING |
| Distribution loss 2 % | 2,000 | 2,724.0 | 2,893.7 | 1.362 | 91.9 % WARNING (EX-001 does NOT cover) | 80.0 / 84.2 % WARNING | 72.1 / 84.8 % WARNING |

PUE across all cases above: 1.322 to 1.382. PUE is an output of the model; no input was adjusted to reach a target.

### Allocation of the mechanical plant between paths (whole units)

| Item | Installed | Running | kW per unit | Model, worst path kW | Whole-unit worst path kW | Note |
|---|---|---|---|---|---|---|
| MC-1 | 4 | 3 | 120.0 | 180.0 | 240.0 | 3 running units cannot split evenly: one path carries 2, so the worst path is +60 kW against the 50 % model. |
| MC-2 | 20 | 20 | 6.0 | 60.0 | 60.0 | Running units split evenly between the paths. |
| MC-3 | 6 | 4 | 15.0 | 30.2 | 30.0 | Running units split evenly between the paths. |

### Review notes on the load model

- Chillers: 4 installed, 3 running (N+1). The load schedule counts only running units (demand factor 0.75), which is the right basis for the load; the spare is not in the load. With 3 running over 2 paths one path carries 2, so the 50 / 50 split understates the worst path (see the allocation table).
- Chilled-water and condenser pumps: 6 installed, 4 running (demand factor 0.67 gives 4.02, read as 4). Two spare pumps (N+2). Splits 2 + 2.
- CRAH fan units: 20 installed, all counted as running (demand factor 1.0). Whether the 20 include spare units is not stated. If some are spare the load is overstated; if none are, there is no CRAH redundancy. A design decision, not decided here.
- A/B path split: every item is split 50 / 50 by `path_a_fraction`. That is an assumption, not a design: real feeders are allocated by whole units and by hall. In the path-out cases all load transfers to the surviving path (ER-006); mechanical plant behaviour after a path loss is not modelled.
- UPS losses use one efficiency (96 %) at every load. In a 2N arrangement each UPS normally runs at about 40 % of its rating, where efficiency is usually lower than at full load. The loss table shows the effect of 2 points. The real curve is manufacturer data.
- Distribution losses use one flat 1 % of the load, an assumption. The loss table shows the effect of doubling it.
- PUE is a design-point power ratio and an OUTPUT of this model. The 1.35 target is context only: no input has been, or will be, adjusted to reach it (ER-005 records that the early inputs were chosen with the target in view, so the 1.349 result is not independent evidence).

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
- `short_circuit.transformer_x_r_ratio`: Transformer X/R ratio
- `short_circuit.generator_subtransient_reactance_pct`: Generator subtransient reactance x''d
- `short_circuit.generator_x_r_ratio`: Generator X/R ratio

## Verification required before any use

- Manufacturer sizing for each generator, UPS and transformer at the site conditions, including derating, load steps, UPS interaction, harmonics, altitude and ambient temperature.
- Battery sizing from the manufacturer's constant-power discharge data.
- Specialist studies where required: short-circuit, protection coordination, arc flash, harmonics, transients (Stages 4 and 5 and beyond).
- Independent engineering review of every assumption in `config/assumptions_register.yaml`.
