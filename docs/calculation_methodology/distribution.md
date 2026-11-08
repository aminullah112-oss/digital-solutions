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
