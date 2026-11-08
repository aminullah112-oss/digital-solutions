# Stage 3 verification notes

Status of each Stage 3 result. "Verified" is used only where an independent technical basis exists. None exists yet for any engineering result.

| Result | Software verification | Engineering verification | What is needed |
|---|---|---|---|
| Loading percentages (transformer, UPS kW and kVA, generators) | Tests compare the package with hand calculations and a separately written reference model | NOT VERIFIED | Manufacturer ratings and derating at the site conditions; independent review of the scenarios |
| Policy statuses (target 90/80/80, maximum 100) | Boundary tests including exactly-at-limit | NOT VERIFIED | The policy is a preliminary Ohmetry decision, not an IEC limit |
| Derating | Factors are applied before loading and cannot raise a rating | NOT VERIFIED | Manufacturer derating data. The sample uses 1.00 placeholders |
| Generator PRP basis | Basis separation tests (PRP, ESP and COP are never mixed) | NOT VERIFIED | Manufacturer PRP rating, average load factor and hour restrictions |
| N+1 scenarios | Tests against hand-built essential-load references | NOT VERIFIED | Confirmation of the redundancy philosophy and of what each path serves |
| Load steps and transients | Upper-bound arithmetic only | NOT VERIFIED | Manufacturer step, dip, walk-in and harmonic data and a transient study |
| Battery | Energy arithmetic only | NOT VERIFIED | Manufacturer constant-power discharge data |
| Size suggestions | List lookup tests | NOT VERIFIED | The lists are illustrative |

## Independent reference calculations used by the tests
- Facility 2,865.595 kVA (load model, hand-built in `tests/conftest.py`): transformer 90.97 % of 3,150 kVA; UPS kW 80.0 % of 2,500 kW; UPS kVA 84.2 % of 2,500 kVA.
- Generators: essential load (everything except the small-power item) on 3 x 2,000 kVA in the path-out case.
- Battery: 2,000 kW x 10 min / 60 = 333.3 kWh at the UPS output.

## Outstanding manufacturer data
Listed by `validate-config` (check `manufacturer_data_pending`) and in the sizing summary: generator ESP and COP ratings, PRP average load factor and hour restriction, overload capability, maximum step load, frequency and voltage dip limits, UPS rectifier walk-in and input harmonics, battery data, and manufacturer values for the derating factors, UPS efficiency, transformer impedance and loss data.

## Required engineering review
Every assumption in `config/assumptions_register.yaml` and every NOT VERIFIED check above. The project is not construction-ready and not verified.
