# Manufacturer-data register

`config/manufacturer_data_register.yaml` holds, per required parameter: equipment tags, required data sheet, engineering impact and the verification action. The current value, source and status are read live from the master configuration, so the register never holds a second copy.

Columns in the generated register: required parameter, equipment tag, required datasheet, current assumed value, source and status, engineering impact, outstanding verification action, data state.

Data states: PENDING (no value), PLACEHOLDER, NOT VERIFIED (an assumed value flagged for manufacturer verification), DATA SUPPLIED, REVIEW REQUIRED (a value with status MANUFACTURER_DATA awaiting a reviewer).

Importing data without touching the engine:
1. `python -m ohmetry_dc build-manufacturer-register` writes `output/manufacturer_data_import_template.csv` (parameter, value, unit, source, datasheet_reference).
2. Fill value, source and datasheet_reference from the data sheet. Keep the unit of the master configuration.
3. `python -m ohmetry_dc import-manufacturer-data --file <filled csv>` writes `config/manufacturer_data_overrides.yaml`. A row without a source, or for an unknown parameter, rejects the whole import.
4. Run `validate-config`. Every dependent calculation reruns. Supplied values show as DATA SUPPLIED, REVIEW REQUIRED until a reviewer fills `verified_by` in the register.

Equivalent manual procedure when a data sheet arrives:
1. Enter the value in the master configuration with source, status MANUFACTURER_DATA and revision.
2. Run `validate-config`. Dependent calculations rerun.
3. Fill `datasheet_reference`, `verified_by` and `verification_date` in the register only after review. The QA check fails if `verified_by` is set while the value is still a placeholder.
4. Run `revision-impact` to record the equipment sizing changes.

A placeholder is never treated as validated equipment data.
