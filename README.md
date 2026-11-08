# ohmetry-data-center-engineering (OHM-DC-2000)

Educational and preliminary engineering reference package for a reference 2 MW data centre. **Stage 5 of 14 (status model, data override system, all 20 workbooks; build-package): configuration, validation, load model, power system sizing, distribution framework, manufacturer-data register, short-circuit and earthing framework.**

Nothing here is construction-ready, code-compliant, certified or independently approved. Every value in `config/` is a preliminary illustrative assumption (for the sample project, under ideal conditions) or a missing input. None is manufacturer data. Any real design must be reviewed and approved by suitably qualified engineers.

## What works now
- Load and validate the project configuration (provenance for every value).
- Run ten design-basis consistency checks with PASS, WARNING, FAIL, NOT VERIFIED and NOT APPLICABLE statuses.
- Generate the assumptions register from the configuration.
- Run the load model: itemised demand, UPS and distribution losses, facility load, design-point PUE and A/B path allocation.
- Generate `02_LOAD_ESTIMATION.xlsx` (live formulas, compared with the Python model) and the Electrical Load Estimation Report (PDF).
- Size transformers, UPS (kW and kVA) and generators against a configurable loading policy in the worst credible contingency, with derating applied first, PRP as the default generator basis, N+1 scenarios, load-step requirements and a battery interface.
- Record a design basis revision and show the equipment sizing changes (`revision-impact`).
- Run the automated tests.

## What does not exist yet
Distribution engineering, network studies, workbooks 01 and 03 to 20, the other reports, drawings, the training suite and the release package. Nothing here is construction-ready or verified. See `DEVELOPMENT_STATUS.md`.

## Use
```
pip install -r requirements.txt
PYTHONPATH=src python -m ohmetry_dc validate-config
PYTHONPATH=src python -m ohmetry_dc build-assumptions-register --check
PYTHONPATH=src python -m ohmetry_dc run-calculations
PYTHONPATH=src python -m ohmetry_dc generate-workbooks
PYTHONPATH=src python -m ohmetry_dc generate-reports
PYTHONPATH=src python -m ohmetry_dc sizing-summary
PYTHONPATH=src python -m ohmetry_dc build-manufacturer-register   # output/manufacturer_data_register.md and .csv
PYTHONPATH=src python -m ohmetry_dc qa-report                      # output/QA_RESULTS.md
PYTHONPATH=src python -m ohmetry_dc revision-impact --previous-config OLD_project_config.yaml --record "description"
PYTHONPATH=src python -m pytest -q
```
`validate-config` exits 1 when a FAIL is found, for example a required input for the current stage is missing. Inputs needed only in later stages are reported as NOT VERIFIED, not as failures. Workbook and report tests need LibreOffice and pdftotext, and are skipped if those are missing.

## Status flags
- **PASS**: the check ran and found no problem. Not an engineering approval.
- **WARNING**: a possible inconsistency to review.
- **FAIL**: a defect, such as a missing required input. Blocks release.
- **NOT VERIFIED**: the check cannot be judged without data or a limit that has not been supplied.
- **NOT APPLICABLE**: the check does not apply.
