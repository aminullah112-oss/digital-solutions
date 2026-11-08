# Independent reviewer checklist: OHMETRY 2 MW DATA CENTRE ELECTRICAL ENGINEERING PROJECT

**Document OHM-DC-2000-DOC-03  Issue P1. Package revision A5. Generated 2026-11-05 07:50 UTC.**

> FOR INDEPENDENT ENGINEERING REVIEW. THE PACKAGE IS PRELIMINARY. IT IS NOT CONSTRUCTION-READY AND NOT VERIFIED. NOTHING IN IT HAS BEEN APPROVED.

Mark each item PASS, FAIL, N/A or QUERY and record findings in REVIEW_FINDINGS_LOG.xlsx with the item reference. The checklist does not limit the review.

## A. Scope, independence and conduct of the review

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R01 | Confirm you are independent of the authors and have no stake in the package. | Reviewer declaration |  |  |
| R02 | Confirm the scope: educational and preliminary reference package, not a project design. Note anything claimed beyond that. | CUSTOMER_README sections 1, 13 to 16 |  |  |
| R03 | Confirm nothing is labelled approved, verified or construction-ready. | All documents; run the search listed in REVIEW_GUIDE |  |  |
| R04 | Reproduce the package from the review package: install, run the test suite, regenerate the deliverables (REVIEW_GUIDE, REPRODUCE). | REVIEW_GUIDE |  |  |

## B. Design basis

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R05 | Check each design-basis parameter, unit and source; confirm the data status is honest (preliminary vs placeholder vs reference). | 01_MASTER_DESIGN_BASIS.xlsx, config/project_config.yaml |  |  |
| R06 | Check the voltage and frequency basis (400/230 V, 60 Hz is flagged as unusual); decide whether it is acceptable for the reference project. | ER-001, lv_voltage_frequency check |  |  |
| R07 | Check the redundancy concept (2N paths, 2N UPS, N+1 generators) is internally consistent and what 'credible contingency' means here. | 03_POWER_ARCHITECTURE, config redundancy section |  |  |
| R08 | Check the loading policy (transformer 90/100 %, UPS 80/100 %, generator 80/100 %) is applied to the derated rating and no overload is used. | docs/calculation_methodology/power_system_sizing.md |  |  |
| R09 | Check the design-target exception EX-001 is recorded correctly and never converts a WARNING to PASS. | config/design_exceptions.yaml, validation/exceptions.py |  |  |

## C. Load estimate and PUE

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R10 | Check P and Q are added separately and S = sqrt(P^2+Q^2); check the UPS loss formula and distribution loss treatment. | docs/.../load_estimation.md, calculations/load.py, 02_LOAD_ESTIMATION |  |  |
| R11 | Check the load schedule items, demand and power factors are reasonable for the reference project. | config/load_schedule.yaml |  |  |
| R12 | Confirm the PUE is a design-point power ratio and not described as annual anywhere. | 02, 18, training module 02 |  |  |
| R13 | Check the A/B allocation and the path-out scenarios. | AB_ALLOCATION sheet, calculations/load.py |  |  |

## D. Equipment sizing

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R14 | Transformer: loading against the derated rating, contingency case, required rating for the target; confirm 3,150 kVA result. | 04_TRANSFORMER_SIZING, calculations/sizing.py |  |  |
| R15 | Generators: PRP basis stated as assumed; kW and kVA both checked; N+1 and the double-contingency treatment; step loads reported NOT VERIFIED. | 05_GENERATOR_SIZING, ER-010, ER-012 |  |  |
| R16 | UPS: kW and kVA both checked; 2N logic; kVA governs at 0.95 power factor. | 06_UPS_SIZING, ER-009 |  |  |
| R17 | Battery: energy only; confirm no battery selection is implied. | 07_BATTERY_SIZING |  |  |
| R18 | Derating: 1.00 placeholders are shown as placeholders everywhere and their effect is stated. | ER-011, derating_factors check |  |  |
| R19 | Check the size lists and suggested sizes are labelled illustrative. | config size lists |  |  |

## E. Distribution

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R20 | Design current bases for each feeder; busbar and busduct required current (about 4,136 A on path-out). | 08, 11, 12, 13; calculations/distribution.py |  |  |
| R21 | Conductor resistance constants and the three-phase voltage drop formula; reactance placeholders and their effect. | docs/.../distribution.md, 09_VOLTAGE_DROP |  |  |
| R22 | Confirm tabulated ratings, busduct and switchgear ratings are never assumed and read NOT VERIFIED. | 08, 11, 12, 13 |  |  |
| R23 | Check the cable selections are labelled illustrative and path B is assumed identical. | config/distribution.yaml |  |  |

## F. Short-circuit, protection and earthing

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R24 | Check the IEC 60909 equations (utility, K_T, K_G, peak factor, thermal factor) against the standard; check the transformer-limited bound. | calculations/short_circuit.py, docs/.../short_circuit_and_earthing.md |  |  |
| R25 | Confirm no utility, generator or site value is invented; cases that lack data read NOT CALCULATED. | 10_SHORT_CIRCUIT, ER-019, ER-024 |  |  |
| R26 | Check the adiabatic cable withstand constant and its flagged status. | 08_CABLE_SIZING |  |  |
| R27 | Check the IEEE 80 grid resistance and tolerable voltage equations against the standard; confirm the screening wording. | calculations/earthing.py, 15_EARTHING_BONDING |  |  |
| R28 | Confirm protection coordination, arc-flash and lightning compliance are never claimed. | 14, 16 workbooks |  |  |

## G. Status model and data override

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R29 | Confirm a calculation on unverified inputs can never reach overall PASS; confirm a preliminary WARNING or FAIL is kept. | validation/verification.py, docs/.../status_model.md |  |  |
| R30 | Confirm every engineering check depends on the right inputs (the CHECK_INPUTS map). | validation/verification.py |  |  |
| R31 | Import: confirm missing source, missing datasheet revision, unknown parameter, unsupported unit and implausible value reject the whole file; confirm unit conversion. | reporting/data_import.py |  |  |
| R32 | Confirm the master design basis is never edited by an import and the history is append-only. | config/loader.py, manufacturer_data_overrides.yaml |  |  |
| R33 | Confirm MANUFACTURER_VERIFIED is reachable only through an import plus a recorded reviewer. | models/data_status.py, cli record-verification |  |  |

## H. Workbooks

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R34 | Audit formulas in each workbook: no hard-coded critical values, correct references, correct units. | workbooks/ (all 20) |  |  |
| R35 | Enter a datasheet value without a source: confirm it is rejected. Enter with a source: confirm the calculation updates and the status becomes SUPPLIED. Add a reviewer: confirm VERIFIED. | INPUTS sheets |  |  |
| R36 | Confirm the overall status can only be PASS when the calculation passes and all inputs are verified (try it). | RESULTS sheets |  |  |
| R37 | Open in Microsoft Excel (the tests recalculated with LibreOffice only) and confirm results agree. | All workbooks |  |  |
| R38 | Check the five input-register workbooks (14, 16, 17, 18, 19) do not produce a result without data and do not claim compliance. | 14, 16, 17, 18, 19 |  |  |

## I. Python engine

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R39 | Review the code against the methodology documents; check units, boundary conditions and error handling. | engine/src/ohmetry_dc |  |  |
| R40 | Run the full test suite and confirm all tests pass; read the tests for the engineering-critical formulas (hand calculations). | engine/tests, QA_RESULTS.md |  |  |
| R41 | Check for hidden defaults: where an input is missing the engine must report it, not substitute a value. | calculations/*.py |  |  |
| R42 | Check configuration validation: required inputs, stage gating, value_ref resolution. | config/loader.py, models/ |  |  |

## J. Reports, drawings and registers

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R43 | Read the load estimation report; confirm statements, limitations and the agreement with the workbook. | reports/ |  |  |
| R44 | Review the single-line diagram: architecture, tags, no unverified value shown as fact; decide path independence and transfer scheme. | drawings/ |  |  |
| R45 | Check the assumptions register, standards register (all NOT_VERIFIED) and manufacturer-data register for completeness. | 07_registers |  |  |
| R46 | Verify the outstanding items list is complete; add anything missing. | OUTSTANDING_VERIFICATION_ITEMS |  |  |

## K. Specifications and training

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R47 | Review each specification template: standards named correctly, requirements sound, test lists complete, placeholders clear, no invented numbers. | 08_specifications |  |  |
| R48 | Review the training modules, worked examples, exercise answers and question bank for technical accuracy and fair wording. | 09_training |  |  |
| R49 | Confirm the certificate states it is not accredited. | Completion_Certificate_Template |  |  |

## L. Documentation and commercial

| Ref | Check | Where | Result | Notes |
|---|---|---|---|---|
| R50 | Check the customer README is accurate against the package and states limitations honestly. | CUSTOMER_README |  |  |
| R51 | Note that the licence draft is outside this review: it needs a legal professional. | LICENCE_COMMERCIAL |  |  |
| R52 | Check the master index and manifest: every file has an id, revision and hash; cross-references are right. | MASTER_INDEX, MANIFEST.json |  |  |

## Sign-off

| Field | Entry |
|---|---|
| Reviewer name and organisation |  |
| Qualification and registration (if any) |  |
| Independence declaration | I have no interest in the package or its sale and was not involved in producing it. [ ] Confirmed |
| Scope reviewed |  |
| Date of review |  |
| Overall conclusion (reviewer's own words) |  |
| Signature |  |
