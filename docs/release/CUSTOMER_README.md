# Customer README

**Document OHM-DC-2000-DOC-01  Revision A6, Issue P2.  Generated 2026-11-08 18:00 UTC.**

> PRELIMINARY EDUCATIONAL AND REFERENCE PACKAGE. NOT CONSTRUCTION-READY. NOT VERIFIED.

## 1. What this package is

The OHMETRY 2 MW DATA CENTRE ELECTRICAL ENGINEERING PROJECT (OHM-DC-2000) is a worked electrical engineering reference for a 2 MW (IT load) data centre. It contains calculation workbooks, a calculation engine, reports, a preliminary single-line diagram, specification templates and a training suite. This is package revision A6, version 0.1.0.dev0, generated 2026-11-08 18:00 UTC.

It shows how a data centre electrical design is built up: design basis, load estimate, redundancy architecture, equipment sizing, distribution, short-circuit levels, protection data, earthing and documentation. Every calculation states its inputs and their status.

Release state: DEVELOPMENT. PRELIMINARY EDUCATIONAL AND REFERENCE PACKAGE. NOT CONSTRUCTION-READY. NOT VERIFIED.

## 2. Intended users

- Working electrical engineers who want a structured, transparent starting point for data centre power design.
- Consulting engineers who want a calculation framework with traceable inputs and honest statuses.
- Engineers learning data centre design (see the training suite).
- Not intended for: construction, procurement, permit submissions or any use that relies on the results without independent engineering review.

## 3. What is included

| Item | Content |
|---|---|
| Workbooks | 20 Excel workbooks (01 to 20), listed in section 7 |
| Reports | Electrical load estimation report (PDF) |
| Drawings | OHM-DC-2000-SLD-001 preliminary single-line diagram (SVG and PDF) |
| Specification templates | Ten editable DOCX templates with PDF copies: transformers, generators, UPS, batteries, MV and LV switchgear, cables, busduct, protection, earthing |
| Training suite | Twelve modules (PDF and Markdown), exercise workbook, 48-question bank, answer key, completion certificate template |
| Registers | Assumptions register, standards register, manufacturer-data register and import template, outstanding verification items |
| Documents | Calculation methodology, user guides, engineering review log, development status, release checklist, QA results, master index, licence |
| Engine (optional) | The Python calculation engine and master configuration, only if included in your licence tier |

## 4. Design basis and key assumptions

The reference project is a 2,000 kW IT load with dual independent A and B power paths. The values below are the preliminary values in the master configuration. They are assumptions chosen for the reference project, not manufacturer data and not measurements. Each carries a data status (section 11).

| Item | Value | Data status |
|---|---|---|
| IT critical load | 2000 kW | PRELIMINARY_ASSUMPTION |
| Target PUE | 1.35 | PRELIMINARY_ASSUMPTION |
| LV line voltage | 400 V | PRELIMINARY_ASSUMPTION |
| Frequency | 60 Hz | PRELIMINARY_ASSUMPTION |
| MV supply | 13.8 kV | PRELIMINARY_ASSUMPTION |
| Architecture | Dual independent A and B power paths | PRELIMINARY_ASSUMPTION |
| UPS topology | 2N | PRELIMINARY_ASSUMPTION |
| Generator concept | N+1 per power path | PRELIMINARY_ASSUMPTION |
| Transformer rating | 3150 kVA | UNVERIFIED_PLACEHOLDER |
| Transformer impedance | 6 % | UNVERIFIED_PLACEHOLDER |
| Generator rating | 2000 kVA | UNVERIFIED_PLACEHOLDER |
| Generator power factor | 0.8 | UNVERIFIED_PLACEHOLDER |
| UPS rating (kW) | 2500 kW | UNVERIFIED_PLACEHOLDER |
| UPS rating (kVA) | 2500 kVA | UNVERIFIED_PLACEHOLDER |
| UPS efficiency | 96 % | UNVERIFIED_PLACEHOLDER |
| Distribution losses | 1.0 % | UNVERIFIED_PLACEHOLDER |
| Battery autonomy | 10 min | PRELIMINARY_ASSUMPTION |
| Transformer loading target | 90 % | PROJECT_INPUT |
| Transformer loading maximum | 100 % | PROJECT_INPUT |

The 400/230 V at 60 Hz pairing is the project owner's decision and was not independently verified. For a real project, the serving utility's written confirmation is required.

## 5. Supported software

- Workbooks: they use ordinary formulas (no macros) and are intended for Microsoft Excel 2016 or later or LibreOffice Calc 7 or later. IMPORTANT: they were recalculated and tested with LibreOffice only. Microsoft Excel was not available to the authors, so the workbooks have not been opened in Excel. A static lint checks Excel limits (see WORKBOOK_LINT.md) but cannot show that Excel gives the same results. Check results in Excel before relying on them.
- Reports, drawings and specifications are provided as PDF and DOCX; a PDF reader and a word processor are enough.
- Engine (if included): Python 3.11 or later with pydantic, PyYAML, openpyxl and reportlab. LibreOffice is used to recalculate workbooks in the test suite.

## 6. Installing and running the engine (if included)

From the folder containing the engine: install the dependencies listed in requirements.txt, then run the commands below with PYTHONPATH=src.

- validate-config: check the configuration and print every check with its statuses.
- generate-workbooks, generate-reports, generate-drawings, generate-training: rebuild the deliverables from the configuration.
- build-assumptions-register, build-manufacturer-register: refresh the registers.
- revision-impact --previous-config OLD --record "description": show and record what a configuration change did to the results.
- import-manufacturer-data, record-verification: import supplied data and record a reviewer (section 9).
- qa-report: run the tests and write the QA results.

Run: python -m ohmetry_dc <command>. Every command is safe to rerun.

## 7. The calculation workbooks

Every workbook has the same layout: README (what it does and its limits), INPUTS, CALCULATIONS, RESULTS and REVISION_LOG. The workbooks are live: change an input and the results update.

| Workbook | Purpose |
|---|---|
| 01_MASTER_DESIGN_BASIS | Every design-basis parameter with its data status and source; design criteria; assumptions and exclusions; standards links; check statuses; approval fields |
| 02_LOAD_ESTIMATION | Itemised load, UPS and distribution losses, facility load, design-point PUE, A/B allocation |
| 03_POWER_ARCHITECTURE | Operating modes, load transfer on loss of a path, UPS or generator, redundancy checks, dependency summary |
| 04_TRANSFORMER_SIZING | Transformer loading in normal and contingency cases against the derated rating; required rating |
| 05_GENERATOR_SIZING | Generator loading in kW and kVA with N+1 cases |
| 06_UPS_SIZING | UPS loading in kW and kVA with 2N cases |
| 07_BATTERY_SIZING | Energy at the UPS output and an indicative nominal energy (no battery selection) |
| 08_CABLE_SIZING | Design current, required rating, voltage drop and thermal withstand per feeder |
| 09_VOLTAGE_DROP | Voltage drop cases, three-phase and single-phase, operating and starting |
| 10_SHORT_CIRCUIT | IEC 60909 fault levels at the MV and LV busbars; equipment rating comparison |
| 11_LV_SWITCHGEAR | LV switchboard required rating, short-circuit rating and evidence |
| 12_MV_SWITCHGEAR | MV switchgear required rating, short-circuit rating and evidence |
| 13_BUSDUCT_SIZING | Busduct required rating, voltage drop and short-circuit withstand |
| 14_PROTECTION_COORDINATION | Protective device schedule, CT/VT and relay settings registers, selectivity evidence (never a coordination PASS) |
| 15_EARTHING_BONDING | Grid resistance, ground potential rise and touch voltage screening |
| 16_LIGHTNING_PROTECTION | Lightning protection input fields, collection area and expected events (no compliance claim) |
| 17_POWER_QUALITY | Voltage unbalance, THD and frequency deviation from measurements, against limits you enter |
| 18_ENERGY_EFFICIENCY | Annual energy and energy-based PUE (design-point upper bound unless you enter measured factors) |
| 19_GENERATOR_FUEL | Fuel consumption and runtime from the manufacturer's fuel curve (nothing without the curve) |
| 20_MASTER_EQUIPMENT_SCHEDULE | Equipment tags with ratings, datasheet fields, technical and procurement status |

Five workbooks (14 protection, 16 lightning, 17 power quality, 18 energy, 19 fuel) are structured input registers with only the calculations that the entered data supports. They produce no meaningful result until you enter data.

## 8. Entering your own and datasheet values in the workbooks

- On INPUTS, the yellow column holds the retained preliminary value. Do not overwrite it.
- Type the datasheet value in the blue column E, in the unit shown in column C.
- Type the datasheet source and revision in column H. A value without a source is rejected: the status reads REJECTED: SOURCE MISSING and the preliminary value stays in force.
- After you check the value against its source, type your name in column I. The status then changes from MANUFACTURER_SUPPLIED to MANUFACTURER_VERIFIED.
- Read RESULTS: the four statuses are shown separately (section 11).
- Load figures in the sizing workbooks are copied from the preliminary load estimate. Replace them with your project's loads.

## 9. Importing manufacturer data (engine)

The engine keeps the original design-basis values and records supplied data separately, so the original is never overwritten.

- build-manufacturer-register writes the register and a blank import template (parameter, value, unit, source, datasheet revision, datasheet reference).
- Fill the template from the datasheets. Use the unit of the master configuration or a convertible unit (for example MVA for kVA).
- import-manufacturer-data --file <csv> validates every row: a missing source or datasheet revision, an unknown parameter, an unsupported unit or an implausible value rejects the whole file and nothing is imported.
- Accepted values are written to config/manufacturer_data_overrides.yaml with an append-only history (date, previous value, source, revision). Every dependent calculation reruns and the changes are printed.
- record-verification --parameter <id> --by <name> records that a reviewer checked the value against its source. A placeholder cannot be verified.

## 10. Calculation outputs

- Workbook RESULTS sheets: calculated values with the four statuses and the Python agreement column.
- The load estimation report (PDF): inputs, load schedule, results, checks and limitations.
- The single-line diagram: architecture and preliminary ratings read from the configuration.
- The registers: assumptions, manufacturer data (with the engineering impact of each missing item), standards, outstanding verification items.
- The revision log: what changed between revisions and its effect on the results.

## 11. Verification statuses

Every check reports four separate things. A calculation can be correct arithmetic and still say nothing about whether the design works, if its inputs are unconfirmed.

| Status | Meaning |
|---|---|
| Calculation status | CALCULATED, PARTIAL or NOT CALCULATED: did the arithmetic run on complete inputs |
| Calculation result | PASS, WARNING or FAIL against the criterion. Preliminary when the inputs are |
| Input-data status | The worst status among the inputs (below) |
| Overall design status | PASS only if the calculation passes AND every input is verified, reference data or an owner decision. A preliminary pass reads NOT VERIFIED. A preliminary WARNING or FAIL is kept |

| Input-data status | Meaning |
|---|---|
| MISSING | No value supplied. Nothing is assumed |
| UNVERIFIED_PLACEHOLDER | A preliminary value standing in for manufacturer data |
| PRELIMINARY_ASSUMPTION | A value chosen for the reference project |
| REFERENCE_DATA | A published constant (verify the edition) |
| PROJECT_INPUT | A decision or policy value from the project owner |
| MANUFACTURER_SUPPLIED / SITE_DATA_SUPPLIED | Imported from a document, not yet reviewed |
| MANUFACTURER_VERIFIED / SITE_DATA_VERIFIED | Imported and reviewed by a named person |

NOT CALCULATED means the inputs are missing and the result is not shown. In the shipped package no engineering check reaches PASS.

## 12. Editing the configuration (engine)

config/project_config.yaml is the single source of project values; each parameter has a value, unit, source, status and revision. Change a value there (for example the IT load in the demand-data section), rerun the commands, and every workbook, report, drawing and training example follows. Use revision-impact to record the effect. Do not edit the overrides file by hand except to correct a source reference.

## 13. What is preliminary

- Every value in section 4 and every equipment rating.
- The load schedule, derating factors (1.00 placeholders), cable selections and lengths, and the illustrative device list.
- The generator rating basis (assumed PRP) and rated power factor.
- All results derived from them.

## 14. What requires manufacturer data

- Transformer impedance, X/R, losses and derating; generator PRP and ESP ratings, reactance, step-load and transient data; UPS efficiency curve, input harmonics and walk-in; battery constant-power discharge data.
- Cable tabulated ratings; busduct and switchgear ratings, impedance, short-circuit ratings and verification evidence; circuit-breaker and relay curves and settings.

The manufacturer-data register lists every item, the datasheet needed, and the engineering impact of its absence.

## 15. What requires specialist software or studies

- Network short-circuit, load-flow and protection coordination studies with validated models (for example in a power systems analysis package).
- Detailed grounding analysis (mesh and step voltage, layered soil).
- Arc-flash assessment.
- Harmonic analysis.
- Cooling and airflow design.
- Lightning protection risk assessment and design.
- Utility studies and the utility's written fault-level data.

This package provides the framework and the data requirements for these. It does not replace them.

## 16. What requires independent engineering approval

Every result, drawing and specification here requires review and approval by a suitably qualified engineer before any use beyond education. Approval fields in the documents are empty: a name written in a field is a record, not a verification performed by this package. Local code, utility and authority requirements are not stated here and must be added by the project team.

## 17. Reporting issues

Report an issue with: the document or workbook name and revision, the input values, what you expected and what you saw. Contact details: [support contact to be confirmed by the owner before distribution]. Support scope and update rights depend on the licence tier (see the licence).

## 18. Licence and disclaimer

Use of this package is governed by the commercial licence in this package (draft, not legally reviewed). The package is provided as is for education and reference. It is not engineering advice and not a design. Ohmetry does not accept responsibility for any use of the results without independent engineering verification.
