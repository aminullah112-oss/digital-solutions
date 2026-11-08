# Distribution framework (Stage 4)

Preliminary and educational. Not a design. Every cable, busduct and switchgear entry in `config/distribution.yaml` is an illustrative placeholder, and path B is assumed identical to path A.

## Design current
Each feeder names a design-current basis: `transformer_path_out_load`, `generator_rated`, `ups_input_path_out`, `ups_output_path_out`, `mechanical_path_out`. The current is I = S / (sqrt(3) x V), with S taken from the load model and the sizing results.

## Conductor resistance
R(T) = rho20 x (1 + alpha x (T - 20)) / A, with copper rho20 = 0.017241 ohm.mm2/m, alpha = 0.00393, aluminium 0.028264 and 0.00403. Worked check: 630 mm2 copper at 90 C gives 0.017241 x 1.2751 / 630 = 3.4895e-5 ohm/m.

## Voltage drop
Three-phase: dV = sqrt(3) x I x L x (R cos(phi) + X sin(phi)) per run, with the current divided over the parallel runs. Reactance is a placeholder (LV 0.08 ohm/km, MV 0.10 ohm/km) until cable data is entered. The limit is `design_criteria.voltage_drop_limit_pct` (3 %, project owner configurable).

## What is not checked
- Ampacity: tabulated ratings are never assumed. The check reports the required rating per run after derating and is NOT VERIFIED until `tabulated_rating_a` is entered from the cable standard or data sheet.
- Busduct and switchgear ratings, short-circuit ratings, form of separation, IP rating and verification evidence (IEC 61439 for LV assemblies, IEC 62271 for MV) are manufacturer data and NOT VERIFIED.
- Short-circuit withstand cannot be judged before the Stage 5 fault study.

## Updating
Enter manufacturer data in `config/project_config.yaml` or `config/distribution.yaml`, then run `validate-config`, `build-manufacturer-register` and `revision-impact --previous-config OLD --record "description"`. All dependent results rerun; nothing is frozen.

## Derating, installation, parallel arrangement and current sharing (revision A6)

- **A derating factor of 1.00 is a placeholder, never a verified value.** Each cable, busduct and switchgear entry in `config/distribution.yaml` carries `derating.grouping`, `ambient` and `installation`. A factor counts as verified only when the same entry names its source in `derating_evidence.<factor>` (a cable table or data sheet reference). Without that, the factor is reported as NOT VERIFIED and the required rating is called a **minimum**.
- **Grouping.** With several parallel runs, and with neighbouring circuits on the same tray or duct, grouped cables always carry less than a single cable. A grouping factor of 1.00 with parallel runs is called out in the check text and in the workbook.
- **Installation method.** Taken from `installation.cable_installation_method` unless the feeder sets its own `installation_method`. It fixes the tabulated rating and the grouping factor, and is a placeholder for the sample project.
- **Ambient and conductor temperature.** The design ambient (`environment.design_ambient_temperature`) is an assumption. The conductor temperature (`cable_data.conductor_operating_temperature`) is used only to derive resistance for the voltage drop. It does not set the current rating, which comes from the table.
- **Parallel arrangement and current sharing.** `parallel_arrangement` describes the layout of the runs (null until supplied, and then listed as missing data). `current_sharing_allowance_pct` is the allowance for unequal sharing between runs. When it is null, **no allowance is included** and the required rating per run is a minimum: equal sharing needs matched lengths, the same cross-section and a layout that equalises impedance. The engine does not calculate the sharing.
- **Busduct rating.** The required rated current (for example 4,136 A on the LV busduct from the 3,150 kVA transformer with the other path lost) is the design current divided by the derating factors, which are placeholders: it is a minimum, and the rating itself is manufacturer data.
- **Voltage drop.** Per segment, at the operating current, three-phase, resistance at the stated conductor temperature, placeholder reactance. It is not cumulative from the source to the load, excludes motor starting, and cannot be calculated for a busduct without the manufacturer's impedance.

The check `cable_derating_basis` reports all of this for every feeder, busduct and switchgear item and is always NOT VERIFIED while any factor is a placeholder.
