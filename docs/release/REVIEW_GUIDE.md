# Independent review guide: OHMETRY 2 MW DATA CENTRE ELECTRICAL ENGINEERING PROJECT

**Document OHM-DC-2000-DOC-04  Issue P2. Package revision A6. Generated 2026-11-08 12:00 UTC.**

> FOR INDEPENDENT ENGINEERING REVIEW. THE PACKAGE IS PRELIMINARY. IT IS NOT CONSTRUCTION-READY AND NOT VERIFIED. NOTHING IN IT HAS BEEN APPROVED.

## 1. What you are reviewing
The Ohmetry OHMETRY 2 MW DATA CENTRE ELECTRICAL ENGINEERING PROJECT (OHM-DC-2000): a preliminary educational and reference package for a 2 MW data centre electrical design. It contains a design basis, a Python calculation engine, twenty Excel workbooks, a report, a single-line diagram, ten specification templates, a twelve-module training suite, registers and documents. It is not a project design and makes no claim to be construction-ready or verified.

## 2. What the package claims, and what it does not
- It claims: transparent calculations; every input labelled with its data status; no calculation on unverified inputs reaches an overall PASS; missing data is reported, not substituted.
- It does not claim: that any rating is manufacturer-confirmed, that any result is verified, compliance with any standard or code, readiness for construction, or any approval by a regulator, utility, client or professional engineer.

## 3. What is in this review package
`00_START_HERE` (this guide, the checklist, the findings log, the outstanding items, the master index), `01_design_basis`, `02_calculation_methodology`, `03_workbooks`, `04_engine` (a complete runnable replica of the repository: source, tests, configuration and every generated deliverable; the other numbered folders are reading copies of parts of it), `05_reports`, `06_drawings`, `07_registers`, `08_specifications`, `09_training`, `10_customer_documents`, `11_qa`. A SHA-256 manifest (MANIFEST.json) covers every file.

## 4. Reproducing the package
1. Unzip the review package. Python 3.11 or later and LibreOffice are needed (LibreOffice is used by the workbook tests).
2. In `04_engine` (the repository root): install the dependencies in `requirements.txt` (pydantic, PyYAML, openpyxl, reportlab, python-docx, pytest).
3. Run `PYTHONPATH=src python -m pytest -q`. All tests should pass. Note any that do not.
4. Run `PYTHONPATH=src python -m ohmetry_dc validate-config` and compare with `11_qa/QA_RESULTS.md` and the CHECK_STATUS sheet of workbook 01.
5. Run `generate-workbooks`, `lint-workbooks`, `generate-reports`, `generate-drawings`, `generate-training`, `generate-documents` and compare the outputs with the supplied files (timestamps will differ).

## 5. Suggested order of review
Design basis, then the methodology documents, then the engine code for each calculation, then the workbooks against the engine, then registers, drawing, specifications, training and customer documents. Use the checklist; it does not limit your review.

## 6. Quick checks
- Search all documents for the words approved, verified, compliant and construction: every use should be a negation or a status label.
- In any workbook, enter a value in the blue datasheet column without a source: it must be rejected.
- Change `equipment.transformer_rating` in `config/project_config.yaml`, rerun, and confirm the workbook, report, drawing and training examples follow.

## 7. Recording findings
Use REVIEW_FINDINGS_LOG.xlsx (the columns match the engineering review log). Give each finding a severity (Critical, High, Medium, Low, Observation), the evidence (file, sheet, cell or line) and the corrective action you expect. Do not edit the package files; send findings back so changes are made and re-tested by the author.

## 8. Out of scope
Legal review of the licence, commercial terms, and the website. Those need a different professional.

## 9. Known gaps you should expect
See OUTSTANDING_VERIFICATION_ITEMS.md. The biggest: no independent review has happened yet; manufacturer, utility and site data are not supplied; the standards editions are NOT_VERIFIED; the workbooks were recalculated and tested in LibreOffice only: Microsoft Excel was not available, so they have never been opened in Excel (see WORKBOOK_LINT.md for the static lint, which does not replace that).
