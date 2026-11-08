# Corrective action report: OHMETRY 2 MW DATA CENTRE ELECTRICAL ENGINEERING PROJECT

**Document OHM-DC-2000-DOC-07  Issue P2. Package revision A6. Generated 2026-11-08 12:00 UTC. Package version 0.1.0.dev0.**

> FOR INDEPENDENT ENGINEERING REVIEW. THE PACKAGE IS PRELIMINARY. IT IS NOT CONSTRUCTION-READY AND NOT VERIFIED. NOTHING IN IT HAS BEEN APPROVED.

This report answers items 5 to 12 of the independent review of revision A5. **Implemented is not verified:** every change below is NOT REVIEWED until an independent engineer says otherwise.

## 1. What changed and what did not

Revision A6 changes how results are labelled, drawn and documented. **No load, demand, rating or sizing value changed**: the revision log records no equipment sizing change, and the table in section 3 shows the reviewed A5 values reproduce.

## 2. Items 1 to 4

Items 1 to 4 of the A5 review are NOT covered by this report. They were implemented in an earlier working session whose repository was lost before it was ever pushed, and their text was not in the handover. This package was rebuilt from the A5 review package, so it is the A5 state plus corrective actions 5 to 12. Until the text of items 1 to 4 is supplied and checked, do not assume they are present. Signals in the handover suggest the reviewed values included a judged path-out-plus-one-unit generator case and a third WARNING; the engine currently reports that case as informational and still shows 2 WARNINGs. This is an inference, not a fact.

## 3. Key numbers: reviewed at A5, computed now

| Item | Reviewed at A5 | Computed now | Agreement |
|---|---|---|---|
| IT load (kW) | 2,000 | 2,000 | MATCH |
| Facility total (kW) | 2,697.3 | 2,697.3 | MATCH |
| Facility total (kVA) | 2,865.6 | 2,865.6 | MATCH |
| PUE (design point) | 1.349 | 1.349 | MATCH |
| Transformer 3,150 kVA, path out (% of derated kVA) | 90.97 | 90.97 | MATCH |
| Transformer 4,000 kVA, same load (% kVA, arithmetic only) | 71.64 | 71.64 | MATCH |
| UPS, path out (% kW) | 80.0 | 80.0 | MATCH |
| UPS, path out (% kVA) | 84.2 | 84.2 | MATCH |
| Generators, path out and one unit out (% of 4,000 kVA) | 71.36 | 71.36 | MATCH |
| Generators, path out and one unit out (% of 3,200 kW) | 83.98 | 83.98 | MATCH |
| Transformer-limited LV figure (kA; utility contribution through one transformer only) | 82.64 | 82.64 | MATCH |
| Transformer full-load LV current (A) | 4,547 | 4,547 | MATCH |
| LV busduct required current (A) | 4,136 | 4,136 | MATCH |

Agreement: ALL MATCH. The transformer-limited figure is the utility contribution through one transformer only; it is not the bus fault level.

## 4. Check summary

| Status | A5 | A6 |
|---|---|---|
| PASS | 9 | 9 |
| WARNING | 2 | 2 |
| FAIL | 0 | 0 |
| NOT VERIFIED | 25 | 26 |
| NOT APPLICABLE | 0 | 2 |

The NOT VERIFIED count rose because new checks were added (`cable_derating_basis`; arc-flash and lightning scope are NOT APPLICABLE). No check changed status and nothing was upgraded.

Tests: 270 passed, 0 failed, 0 skipped (2026-11-08 12:00 UTC; output/QA_RESULTS.md).

## Item 5. Single-line diagram and architecture

**Asked:** Utility A/B independence not claimed; generator transfer and interlocking; paralleling and synchronising; PMS and load sharing; load shedding; UPS static and maintenance bypass; battery isolation and protection; protection and measurement boundaries.

**Done:**

- SLD-001 redrawn at A6: a breaker per generator (GCB) onto a generator bus; a dashed interlock between ACB-TX and ACB-GEN; a PMS box (synchronising, load sharing, load shedding); UPS static bypass (STS) and maintenance bypass (MBB); a battery isolator (BAT-ISO); the utility point-of-connection boundary and the UPS vendor-scope boundary. Every one is labelled concept or not designed.
- The IT load is one dual-corded load fed from both IT distribution boards, replacing two boxes each labelled 2,000 kW (which could be read as 4 MW).
- Independence of utility A and B is stated as NOT claimed on the drawing, in the workbook and in the register.
- `models/architecture.py` lists twelve functions with status and what is needed; workbook 03 has a FUNCTIONS sheet; the sizing methodology document has a section on them.

**Evidence:** tests/drawing/test_single_line.py (5 new tests); tests/workbook/test_calc_workbooks.py (FUNCTIONS sheet); drawings/svg/OHM-DC-2000-SLD-001.svg; ER-028.

**Still open:**

- None of the twelve functions is designed. No transfer scheme, synchronising method, PMS, bypass arrangement or battery protection exists.
- Protection and measurement are not drawn at all (no relays, CTs, VTs or metering).
- Utility independence needs the utility's written confirmation.

## Item 6. Distribution and cables

**Asked:** Parallel arrangement; grouping factors (never 1.00 as verified); installation method; ambient derating; conductor temperature; current sharing; busduct rating; voltage drop.

**Done:**

- A derating factor counts as verified only when the entry names its source (`derating_evidence`). A 1.00 is a placeholder. Required ratings for every cable, busduct and switchgear item are labelled MINIMUMS while any factor is a placeholder.
- A grouping factor of 1.00 with parallel runs is called out (CAB-GEN-A: 6 runs).
- Installation method, parallel arrangement and current-sharing allowance are recorded; unsupplied ones are listed as missing data and no allowance is invented.
- New check `cable_derating_basis`; workbook 08 splits the derating into grouping, ambient and installation placeholders and takes a sharing allowance; busduct and switchgear workbooks label their factor a placeholder.
- Voltage drop is stated as per segment, operating current only, not cumulative, excluding starting. Conductor temperature is stated as used for resistance only.

**Evidence:** tests/unit/test_checks.py (7 new tests); check cable_derating_basis; docs/calculation_methodology/distribution.md; ER-029.

**Still open:**

- No cable table, grouping, ambient or installation factor, parallel layout or sharing allowance is supplied, so every required rating is a minimum.
- Busduct and switchgear ratings and impedances are manufacturer data and absent.

## Item 7. Short-circuit and protection

**Asked:** Keep NOT CALCULATED where data is absent; never select ratings from an invented fault level; keep arc-flash out of scope.

**Done:**

- The 82.6 kA figure is reworded everywhere: it limits only the utility contribution through one transformer. It excludes generators and motors, so it is not the bus fault level and not a design value. (The earlier wording called it an upper bound valid for any utility fault level and the check said 'LV bus calculated': both overstated it.)
- Tests show no required rating, withstand, cable section or breaking capacity is derived from it.
- Check `arc_flash_scope` records arc-flash as OUT OF SCOPE (IEEE 1584 named, not applied).

**Evidence:** tests/unit/test_stage5.py (4 new tests); docs/calculation_methodology/short_circuit_and_earthing.md; ER-024 (corrected), ER-030.

**Still open:**

- The design fault level is NOT CALCULATED: utility fault level and X/R, transformer X/R and generator reactance and X/R are not supplied.
- No protection coordination, minimum fault current, device settings or arc-flash study.

## Item 8. Earthing and lightning

**Asked:** Preliminary screening only; distinguish GPR screening from a full mesh and step study; no IEC 62305 compliance claim.

**Done:**

- The earthing check states, in every state, that it is PRELIMINARY SCREENING ONLY and not a mesh and step voltage study or an earthing design; the NOT CALCULATED message says so too.
- Check `lightning_scope` records lightning as OUT OF SCOPE with compliance NOT claimed.

**Evidence:** tests/unit/test_stage5.py (2 new tests); ER-031.

**Still open:**

- Soil survey, grid design, earth-fault current and clearing time are not supplied, so grid resistance and GPR are NOT CALCULATED for the project.
- No lightning risk assessment.

## Item 9. Data verification

**Asked:** The reviewer name is an attestation, not authenticated; record name, organisation, date, evidence reference and scope.

**Done:**

- `models/attestation.py`: a value reads verified only when all five fields are present, the date is ISO and not in the future. A bare name is reported as an incomplete record and is not treated as verified.
- `record-verification` requires all five, rejects incomplete or invalid records and placeholders, and appends every record to `config/verification_log.yaml`.
- Design exceptions use the same rule. Workbook reviewer cells need `name; organisation; date; evidence; scope` or read REJECTED: ATTESTATION INCOMPLETE.
- The register, CLI output and documents say the name is a self-declared attestation and not authenticated.

**Evidence:** tests/integration/test_cli.py (3 new tests); tests/unit/test_stage4.py (3 new tests); tests/workbook/test_calc_workbooks.py (1 new test); docs/calculation_methodology/status_model.md; ER-032.

**Still open:**

- Identity, credentials and independence are still not checked by anything. A workbook cell is a text pattern, not a signature.

## Item 10. Standards and specifications

**Asked:** Review the standards register (no invented clause numbers); expand the specifications with vendor data schedules, compliance schedules, FAT, SAT and commissioning.

**Done:**

- Register reconciled: 33 entries (was 18). Every standard named in a specification is now in it (tested). Each entry has `relevant_modules` and `package_use`, including where a standard is named only to say compliance is not claimed or the topic is out of scope. No edition or clause is given.
- Specifications now carry a vendor data schedule, a compliance schedule (per standard and per requirement), FAT, SAT, commissioning with integrated systems testing, and a submittals table. Acceptance criteria are left to the project.

**Evidence:** tests/documents/test_documents.py (6 new tests); config/standards_register.yaml; specifications/; ER-033.

**Still open:**

- Titles and relevance of the 33 standards are from the authors' general knowledge and have not been checked against the standards; editions and applicability are all NOT_VERIFIED.
- Local codes, utility and authority requirements are not stated.

## Item 11. Document control and QA

**Asked:** Revision A6; remove or regenerate the stale Stage 3 sizing summary; reconcile the ER log; note that Excel was unavailable (LibreOffice only plus static lint).

**Done:**

- Revision A6 in the configuration, the revision log (no load, demand or sizing change) and every generated document at issue P2.
- The Stage 3 sizing summary (A2) and results.json (A1) are regenerated; a test fails if any generated file carries another revision.
- ER log reconciled: ER-016, ER-018, ER-024, ER-025, ER-027 amended; ER-028 to ER-034 added; a test checks the IDs, columns, references and closure evidence.
- Two defects found while reconciling and fixed: the register check reported 0 placeholders (the real split is 59 missing, 24 placeholders); distribution tags GEN-SWG-A, CRIT-DIST-A, MCC-A differed from the drawing (GENBUS-A, IT-DIST-A, MECH-A).
- Excel limitation stated in the customer README, review guide, checklist, outstanding items, QA results and ER-027. `lint-workbooks` statically checks all 20 workbooks for Excel limits (text literal length, post-2016 functions, external links, brackets, missing sheets) and lists typed-in constants for the formula audit.

**Evidence:** tests/package/test_repository_files.py (5 new tests); tests/workbook/test_workbook_lint.py (9 tests); output/WORKBOOK_LINT.md; ER-034.

**Still open:**

- The workbooks have never been opened in Microsoft Excel. The lint cannot show Excel and LibreOffice agree.
- The lint found no problem; that does not mean the formulas are right (R34 is still a person's job).

## Item 12. Release gate

**Asked:** Regenerate the full package, manifest, master index, outstanding items register, corrective-action report, revised reviewer checklist and review package.

**Done:**

- `regenerate-all` rebuilds everything in one deterministic sequence: assumptions and manufacturer registers, results, sizing summary, workbooks and lint, report, drawing, training, documents (index, outstanding items, checklist with new section M, guide, findings log), QA results, review package and customer package.
- This report, the revised checklist (section M, R-numbers continue from the A5 checklist so existing findings references still resolve) and the review package are part of that run.

**Evidence:** dist/OHM-DC-2000_A6_REVIEW_PACKAGE.zip (MANIFEST.json with hashes); docs/release/MASTER_INDEX.md; output/OUTSTANDING_VERIFICATION_ITEMS.md.

**Still open:**

- The release state stays DEVELOPMENT. Nothing is pushed or approved by this work.

## Limits of this report

- Microsoft Excel was not available: the workbooks have never been opened in Excel.
- The tests show the code does what it was written to do. They do not show the engineering is right.
- Nothing here has been independently reviewed, approved, or checked against the standards named.

## Sign-off

| Field | Entry |
|---|---|
| Independent reviewer | not assigned |
| Review date | not assigned |
| Release state | DEVELOPMENT |
