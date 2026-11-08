# Load estimation: methodology (Stage 2)

Source: `src/ohmetry_dc/calculations/load.py` and `pue.py`. Inputs: `config/project_config.yaml`, `config/load_schedule.yaml`. Units: kW, kvar, kVA, percent as stated.

## Formulas
For each load item *i* in `load_schedule.yaml`:

- Connected load: `P_conn = quantity x unit rating` (kW)
- Demand: `P = P_conn x demand factor` (kW)
- Reactive demand: `Q = P x tan(acos(pf))` (kvar)
- Apparent demand: `S = sqrt(P^2 + Q^2)` (kVA)

Totals add real and reactive power separately. Apparent power is `sqrt(P_total^2 + Q_total^2)`. It is not the sum of the item kVA values, which would overstate the total whenever the power factors differ.

Losses are explicit lines, not left out:

- UPS losses: `P_ups = P_IT x (100 / eta - 1)` with `eta` the UPS efficiency in percent. All IT load is assumed to run through the UPS.
- Distribution losses: `P_dist = f x (P_items + P_ups)` with `f` the loss percentage divided by 100.
- Reactive power of both losses uses `tan(acos(design power factor))`.
- Facility demand: `P_fac = P_items + P_ups + P_dist`.
- Growth: design demand = facility demand x (1 + growth allowance / 100). The allowance does not enter the PUE.

## PUE
`PUE = P_fac / P_IT` at the design point. This is a power ratio, not the annual energy ratio the metric usually reports. The annual figure depends on IT utilisation, climate and operating modes that this model does not simulate.

## A/B allocation
Each item has a `path_a_fraction`. Path A carries `sum(P x fraction)` of the items, its share of the UPS losses (by the IT split), and distribution losses equal to the loss percentage of its own load. Path B is the facility load minus path A. In the path-out scenarios the surviving path carries the whole facility load. That is conservative, and it ignores load shedding and equipment limits.

## Assumptions (all illustrative, all in `config/assumptions_register.yaml`, all UNCONFIRMED)
Every load item (quantity, rating, power factor, demand factor, path fraction), UPS efficiency 96 %, distribution losses 1 %, growth allowance 0 %, design power factor 0.95, and the operating arrangements (chillers 3 of 4, pumps 4 of 6). None is manufacturer data or a measured value.

## Independent checks
- `tests/unit/test_load_calc.py` compares the package with a hand calculation and with `conftest.reference_model`, a separately written version of the model.
- Trend tests: higher UPS efficiency lowers losses and PUE, zero distribution losses give zero loss, a growth allowance scales the design demand but not the PUE, a higher IT load raises the facility load.
- The workbook carries the same calculation as Excel formulas. `tests/workbook/` recalculates it with LibreOffice and compares every result with Python.

## Limitations
Illustrative inputs. Single efficiency and single loss percentage. No harmonics, step loading or transients. No annual energy model. Path-out assumes full transfer. A passing test shows the code behaves as specified. It does not show the engineering is correct: that needs independent review.
