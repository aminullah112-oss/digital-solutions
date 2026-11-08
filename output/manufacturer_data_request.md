# Manufacturer data request

Reply with values, or attach the data sheets. Anything you leave out stays a placeholder and NOT VERIFIED. Quote the manufacturer, model and data sheet revision with each group.

Format of a reply: `parameter = value (unit), source: manufacturer model, data sheet rev`.

## 1. Transformers (TX-A1, TX-B1)

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `equipment.transformer_rating` Transformer rating | 3150 kVA | Transformer data sheet. Confirm the continuous rating on the applicable cooling stage at the site conditions. |
| `equipment.transformer_impedance` Transformer impedance | 6 % | Transformer data sheet. Enter the guaranteed impedance and tolerance. |
| `losses.distribution_loss_fraction` Distribution losses | 1.0 % | Transformer loss report and busduct and cable loss data. Replace the single percentage with calculated losses. |
| `derating.transformer_ambient_factor` Transformer ambient derating factor | 1.0 - | Manufacturer derating curve for ambient conditions (transformer). Enter the manufacturer's factor at the site conditions. |
| `derating.transformer_altitude_factor` Transformer altitude derating factor | 1.0 - | Manufacturer derating curve for altitude conditions (transformer). Enter the manufacturer's factor at the site conditions. |
| `derating.transformer_installation_factor` Transformer installation derating factor | 1.0 - | Manufacturer derating curve for installation conditions (transformer). Enter the manufacturer's factor at the site conditions. |
| `derating.transformer_contingency_factor` Transformer contingency derating factor | 1.0 - | Transformer data sheet. Confirm with the manufacturer's loading guide and the room design. |
| `short_circuit.transformer_x_r_ratio` Transformer X/R ratio | 8 - | Transformer test report (short-circuit impedance and load losses). Obtain from the transformer test report. |

## 10. Earthing and site

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `earthing_study.grid_area_m2` Earth grid area | 2500 m2 | Earthing grid layout drawing and design. Replace with the designed grid geometry. |
| `earthing_study.grid_conductor_length_m` Total buried grid conductor length | 1200 m | Earthing grid layout drawing and design. Replace with the designed grid geometry. |
| `earthing_study.grid_burial_depth_m` Grid burial depth | 0.5 m | Earthing grid layout drawing and design. Replace with the designed grid geometry. |
| `earthing.earthing_system_type` Earthing system type | TN-S - | Project earthing design basis. Confirm the system type (TN-S assumed). |
| `earthing.soil_resistivity` Soil resistivity | 100 ohm.m | Site soil resistivity survey (Wenner method) report. Commission the survey and enter the layered or apparent resistivity. |

## 11. Utility and general

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `short_circuit.utility_fault_level_mva` Utility initial short-circuit power at the MV connection | 500 MVA | Utility written statement of maximum and minimum fault levels and X/R at the point of connection. Obtain the utility's written fault levels (maximum and minimum). |
| `short_circuit.utility_x_r_ratio` Utility X/R ratio | 10 - | Utility written statement of maximum and minimum fault levels and X/R at the point of connection. Obtain from the utility. |

## 2. Generators (GEN-A1..B3)

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `equipment.generator_rating` Generator PRP rating (each) | 2000 kVA | Generator set data sheet. Obtain the data sheet stating the ISO 8528 basis, kVA, kW and site derating. |
| `equipment.generator_rating_power_factor` Generator rating power factor | 0.8 - | Generator set data sheet. Enter the rated power factor, engine kW and alternator kVA. |
| `equipment.generator_esp_rating` Generator ESP rating (each) | none | Generator set data sheet. Enter the ESP rating if that basis is selected. |
| `equipment.generator_cop_rating` Generator COP rating (each) | none | Generator set data sheet. Enter the COP rating if that basis is selected. |
| `derating.generator_ambient_factor` Generator ambient derating factor | 1.0 - | Manufacturer derating curve for ambient conditions (generator). Enter the manufacturer's factor at the site conditions. |
| `derating.generator_altitude_factor` Generator altitude derating factor | 1.0 - | Manufacturer derating curve for altitude conditions (generator). Enter the manufacturer's factor at the site conditions. |
| `derating.generator_installation_factor` Generator installation derating factor | 1.0 - | Manufacturer derating curve for installation conditions (generator). Enter the manufacturer's factor at the site conditions. |
| `generators.prp_max_average_load_factor_pct` PRP maximum average load factor | none | Generator set data sheet. Obtain the manufacturer's value and conditions. |
| `generators.operating_hours_restriction` PRP operating-hour restriction | none | Generator set data sheet. Obtain the manufacturer's value and conditions. |
| `generators.overload_capability` Manufacturer overload capability | none | Generator set data sheet. Obtain the manufacturer's value and conditions. |
| `generators.max_step_load_pct` Maximum single load step | none | Generator set data sheet. Obtain the manufacturer's value and conditions. |
| `generators.max_frequency_dip_pct` Maximum frequency dip allowed | none | Generator set data sheet. Obtain the manufacturer's value and conditions. |
| `generators.max_voltage_dip_pct` Maximum voltage dip allowed | none | Generator set data sheet. Obtain the manufacturer's value and conditions. |
| `generators.ups_rectifier_walk_in_s` UPS rectifier walk-in time | none | UPS data sheet. Obtain the manufacturer's value and conditions. |
| `generators.ups_input_current_thd_pct` UPS input current THD | none | UPS data sheet. Obtain the manufacturer's value and conditions. |
| `short_circuit.generator_subtransient_reactance_pct` Generator subtransient reactance x''d | 14 % | Generator set data sheet. Obtain from the generator data sheet. |
| `short_circuit.generator_x_r_ratio` Generator X/R ratio | 20 - | Generator set data sheet. Obtain from the generator data sheet. |

## 3. UPS (UPS-A1, UPS-B1)

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `equipment.ups_rating` UPS rating | 2500 kW | UPS data sheet. Confirm the continuous kW rating at the site conditions. |
| `equipment.ups_rating_kva` UPS rating (each), apparent power | 2500 kVA | UPS data sheet. Confirm the kVA rating and output power factor. |
| `equipment.ups_efficiency` UPS efficiency | 96 % | UPS data sheet. Enter the efficiency at the operating load points. |
| `equipment.ups_input_power_factor` UPS input power factor | 0.99 - | UPS data sheet. Enter the input power factor at the operating load. |
| `derating.ups_ambient_factor` UPS ambient derating factor | 1.0 - | Manufacturer derating curve for ambient conditions (ups). Enter the manufacturer's factor at the site conditions. |
| `derating.ups_altitude_factor` UPS altitude derating factor | 1.0 - | Manufacturer derating curve for altitude conditions (ups). Enter the manufacturer's factor at the site conditions. |
| `derating.ups_installation_factor` UPS installation derating factor | 1.0 - | Manufacturer derating curve for installation conditions (ups). Enter the manufacturer's factor at the site conditions. |

## 4. Batteries (BAT-A1, BAT-B1)

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `battery.dc_bus_voltage_v` DC bus voltage | none | Battery data sheet with the constant-power discharge table (W per cell to the end voltage at the autonomy time), temperature and ageing data. Obtain the battery manufacturer's data. |
| `battery.inverter_efficiency_pct` Inverter efficiency on battery | none | Battery data sheet with the constant-power discharge table (W per cell to the end voltage at the autonomy time), temperature and ageing data. Obtain the battery manufacturer's data. |
| `battery.end_of_life_capacity_factor` End-of-life capacity factor | none | Battery data sheet with the constant-power discharge table (W per cell to the end voltage at the autonomy time), temperature and ageing data. Obtain the battery manufacturer's data. |
| `battery.temperature_correction_factor` Temperature correction factor | none | Battery data sheet with the constant-power discharge table (W per cell to the end voltage at the autonomy time), temperature and ageing data. Obtain the battery manufacturer's data. |
| `battery.constant_power_discharge_data` Constant-power discharge data reference | none | Battery data sheet with the constant-power discharge table (W per cell to the end voltage at the autonomy time), temperature and ageing data. Obtain the battery manufacturer's data. |

## 5. Cables

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `cable_data.lv_reactance_ohm_per_km` LV cable reactance | 0.08 ohm/km | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the value from the cable data sheet for the chosen cable and layout. |
| `cable_data.mv_reactance_ohm_per_km` MV cable reactance | 0.1 ohm/km | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the value from the cable data sheet for the chosen cable and layout. |
| `cable_data.conductor_operating_temperature` Conductor temperature for resistance | 90.0 degC | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the value from the cable data sheet for the chosen cable and layout. |
| `distribution.CAB-MV-A.tabulated_rating_a` CAB-MV-A: tabulated_rating_a | none | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the table value per run for the installation method, with the real derating factors. |
| `distribution.CAB-GEN-A.tabulated_rating_a` CAB-GEN-A: tabulated_rating_a | none | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the table value per run for the installation method, with the real derating factors. |
| `distribution.CAB-UPS-IN-A.tabulated_rating_a` CAB-UPS-IN-A: tabulated_rating_a | none | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the table value per run for the installation method, with the real derating factors. |
| `distribution.CAB-UPS-OUT-A.tabulated_rating_a` CAB-UPS-OUT-A: tabulated_rating_a | none | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the table value per run for the installation method, with the real derating factors. |
| `distribution.CAB-MECH-A.tabulated_rating_a` CAB-MECH-A: tabulated_rating_a | none | Cable data sheet or the standard's current-rating table for the installation method, with grouping and ambient factors. Enter the table value per run for the installation method, with the real derating factors. |
| `short_circuit.assumed_clearing_time_s` Assumed fault clearing time for cable and busduct withstand | 0.5 s | Protection coordination study result and protective device time-current curves. Replace with the clearing time from the coordination study. |

## 6. Busduct (BD-TX-A)

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `distribution.BD-TX-A.rated_current_a` BD-TX-A: rated_current_a | none | Busduct data sheet with the manufacturer's type-test evidence. Obtain the busduct data sheet. |
| `distribution.BD-TX-A.resistance_ohm_per_km` BD-TX-A: resistance_ohm_per_km | none | Busduct data sheet with the manufacturer's type-test evidence. Obtain the busduct data sheet. |
| `distribution.BD-TX-A.reactance_ohm_per_km` BD-TX-A: reactance_ohm_per_km | none | Busduct data sheet with the manufacturer's type-test evidence. Obtain the busduct data sheet. |
| `distribution.BD-TX-A.short_circuit_withstand_ka` BD-TX-A: short_circuit_withstand_ka | none | Busduct data sheet with the manufacturer's type-test evidence. Obtain the busduct data sheet. |

## 7. LV switchboard (LV-MSB-A)

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `distribution.LV-MSB-A.rated_current_a` LV-MSB-A: rated_current_a | none | LV switchgear data sheet and IEC 61439 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.LV-MSB-A.short_circuit_rating_ka` LV-MSB-A: short_circuit_rating_ka | none | LV switchgear data sheet and IEC 61439 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.LV-MSB-A.form_of_separation` LV-MSB-A: form_of_separation | none | LV switchgear data sheet and IEC 61439 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.LV-MSB-A.ip_rating` LV-MSB-A: ip_rating | none | LV switchgear data sheet and IEC 61439 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.LV-MSB-A.verification_evidence` LV-MSB-A: verification_evidence | none | LV switchgear data sheet and IEC 61439 verification evidence. Obtain the manufacturer's data and evidence. |

## 8. MV switchgear (MV-SWG-A)

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `distribution.MV-SWG-A.rated_current_a` MV-SWG-A: rated_current_a | none | MV switchgear data sheet and IEC 62271 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.MV-SWG-A.short_circuit_rating_ka` MV-SWG-A: short_circuit_rating_ka | none | MV switchgear data sheet and IEC 62271 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.MV-SWG-A.form_of_separation` MV-SWG-A: form_of_separation | none | MV switchgear data sheet and IEC 62271 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.MV-SWG-A.ip_rating` MV-SWG-A: ip_rating | none | MV switchgear data sheet and IEC 62271 verification evidence. Obtain the manufacturer's data and evidence. |
| `distribution.MV-SWG-A.verification_evidence` MV-SWG-A: verification_evidence | none | MV switchgear data sheet and IEC 62271 verification evidence. Obtain the manufacturer's data and evidence. |

## 9. Protection devices

| Parameter | Current placeholder | What to read from the data sheet |
|---|---|---|
| `distribution.MV-CB-A.breaking_capacity_ka` MV-CB-A: breaking_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.MV-CB-A.making_capacity_ka` MV-CB-A: making_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.MV-CB-A.time_current_curve_ref` MV-CB-A: time_current_curve_ref | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.MV-CB-A.settings` MV-CB-A: settings | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-TX-A.breaking_capacity_ka` ACB-TX-A: breaking_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-TX-A.making_capacity_ka` ACB-TX-A: making_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-TX-A.time_current_curve_ref` ACB-TX-A: time_current_curve_ref | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-TX-A.settings` ACB-TX-A: settings | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-GEN-A.breaking_capacity_ka` ACB-GEN-A: breaking_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-GEN-A.making_capacity_ka` ACB-GEN-A: making_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-GEN-A.time_current_curve_ref` ACB-GEN-A: time_current_curve_ref | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-GEN-A.settings` ACB-GEN-A: settings | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-UPS-IN-A.breaking_capacity_ka` ACB-UPS-IN-A: breaking_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-UPS-IN-A.making_capacity_ka` ACB-UPS-IN-A: making_capacity_ka | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-UPS-IN-A.time_current_curve_ref` ACB-UPS-IN-A: time_current_curve_ref | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
| `distribution.ACB-UPS-IN-A.settings` ACB-UPS-IN-A: settings | none | Circuit breaker or relay data sheet with time-current curves and test certificates. Obtain the manufacturer's data. |
