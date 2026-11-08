# Corrective action report: OHMETRY 2 MW DATA CENTRE ELECTRICAL ENGINEERING PROJECT

**Document OHM-DC-2000-DOC-07  Issue P2. Package revision A6. Generated 2026-11-08 20:00 UTC. Package version 0.1.0.dev0.**

> FOR INDEPENDENT ENGINEERING REVIEW. THE PACKAGE IS PRELIMINARY. IT IS NOT CONSTRUCTION-READY AND NOT VERIFIED. NOTHING IN IT HAS BEEN APPROVED.

This report answers items 5 to 12 of the independent review of revision A5. **Implemented is not verified:** every change below is NOT REVIEWED until an independent engineer says otherwise.

## 1. What changed and what did not

Revision A6 changes how results are labelled, drawn and documented, and applies items 1 to 4 of the review. **No load, demand or rating input changed.** One judgement setting changed: the generator combined contingency (one utility path out and one engine out) is now judged, so the generator verification, the suggested generator size and the check summary change (one new WARNING, on generator kW). The table in section 3 shows the reviewed A5 values reproduce.

## 2. Items 1 to 4

The text of items 1 to 4 was supplied by the project owner on 2026-11-08 and is answered in the same way as items 5 to 12 below (items 1 to 4 first).

## 3. Key numbers: reviewed at A5, computed now

| Item | Reviewed at A5 | Computed now | Agreement | Status now |
|---|---|---|---|---|
| IT load (kW) | 2,000 | 2,000 | MATCH | - |
| Facility total (kW) | 2,697.3 | 2,697.3 | MATCH | - |
| Facility total (kVA) | 2,865.6 | 2,865.6 | MATCH | - |
| PUE (design point) | 1.349 | 1.349 | MATCH | - |
| Transformer 3,150 kVA, path out (% of derated kVA) | 90.97 | 90.97 | MATCH | WARNING |
| Transformer 4,000 kVA, same load (% kVA, arithmetic only) | 71.64 | 71.64 | MATCH | PASS |
| UPS, path out (% kW) | 80.0 | 80.0 | MATCH | PASS |
| UPS, path out (% kVA) | 84.2 | 84.2 | MATCH | WARNING |
| Generators, path out and one unit out (% of 4,000 kVA) | 71.36 | 71.36 | MATCH | PASS |
| Generators, path out and one unit out (% of 3,200 kW) | 83.98 | 83.98 | MATCH | WARNING |
| Transformer-limited LV figure (kA; utility contribution through one transformer only) | 82.64 | 82.64 | MATCH | - |
| Transformer full-load LV current (A) | 4,547 | 4,547 | MATCH | - |
| LV busduct required current (A) | 4,136 | 4,136 | MATCH | - |

Agreement: ALL MATCH. The transformer-limited figure is the utility contribution through one transformer only; it is not the bus fault level.

## 4. Check summary

| Status | A5 | A6 |
|---|---|---|
| PASS | 9 | 9 |
| WARNING | 2 | 3 |
| FAIL | 0 | 0 |
| NOT VERIFIED | 25 | 27 |
| NOT APPLICABLE | 0 | 2 |

WARNING rose from 2 to 3 because the generator kW check now judges the combined contingency (84.0 % of 3,200 kW, above the 80 % target, below the 100 % limit). NOT VERIFIED rose because checks were added (`cable_derating_basis`, `generator_contingency_basis`, `equipment_options`) and two scope checks read NOT APPLICABLE. Nothing was upgraded and no WARNING was converted to a PASS.

Tests: 282 passed, 0 failed, 0 skipped (2026-11-08 20:00 UTC; output/QA_RESULTS.md).

## Item 1. Generator N+1 (combined contingency)

**Asked:** Judge one utility path out plus one generator out (about 71.4 % kVA and 84.0 % kW: WARNING against the 80 % kW target, under the 100 % hard limit); document the redundancy philosophy (N+1 engine-out basis); flag that the engineer must select and document the contingency basis; do not convert the WARNING to PASS.

**Done:**

- The combined case is judged (`redundancy.double_contingency_credible` is true, source: the A5 review). Generator kVA 71.36 % of 4,000 kVA (under the 80 % target); kW 83.98 % of 3,200 kW: WARNING, never converted to PASS. Loss of a path only gives 47.6 % kVA / 56.0 % kW.
- New check `generator_contingency_basis` (NOT VERIFIED): states the basis used, shows the loading under each candidate basis, and says in capitals that the engineer must select and document it. New parameter `redundancy.generator_contingency_basis` records the assumption. The methodology document and the sizing summary state the philosophy.
- Note on the reviewed table: it lists the 71.36 % kVA row as WARNING; against the 80 % kVA target it reads PASS, and the WARNING is on kW. The item text says the same (WARNING against the 80 % kW target).

**Evidence:** tests/unit/test_options_sensitivity.py; tests/unit/test_sizing.py; check generator_contingency_basis; ER-035.

**Still open:**

- No engineer has selected or documented the contingency basis, the outage duration, fuel autonomy or load-shedding assumptions it implies.
- The PRP rating basis and 1,600 kW engine rating are still assumptions.

## Item 2. Transformer: EX-001 and the 3,150 / 4,000 kVA options

**Asked:** Reconcile design exception EX-001 with the 91.0 % kVA loading on 3,150 kVA; keep the 90 % target / 100 % limit (WARNING); show 3,150 kVA and 4,000 kVA side by side so the engineer can select.

**Done:**

- The exact loading is 90.97 % (shown as 91.0 %). EX-001's ceiling is 91.0 %: the check now states the exact value, the 0.03 percentage point margin and that any small increase voids the exception (at +10 % IT the loading is 98 % and EX-001 does not cover it). Target 90 % and limit 100 % unchanged; the result stays WARNING.
- 3,150 kVA (90.97 %, WARNING) and an illustrative 4,000 kVA (71.64 %, PASS) are shown side by side in the check `equipment_options`, workbook 04 sheet OPTIONS (live formulas, option rating editable) and the sizing summary. The 4,000 kVA option raises the transformer-limited figure to 104.9 kA at the same impedance, above the 100 kA practical limit, and the full-load LV current to 5,774 A: the table flags both. Nothing is selected.

**Evidence:** tests/unit/test_options_sensitivity.py (4 tests); tests/workbook/test_calc_workbooks.py (OPTIONS sheets); ER-008, ER-036.

**Still open:**

- The 4,000 kVA option assumes the same impedance percentage and derating, which a real unit would not have to share.
- Transformer selection, impedance and the fault-level consequence are for the engineer, from manufacturer data.

## Item 3. UPS: separate kW and kVA, 3,000 kVA option

**Asked:** Separate kW and kVA checks; kVA 84.2 % at 2,500 kVA is a WARNING; keep kW at 80.0 % (PASS); include an illustrative 3,000 kVA option in the sizing table.

**Done:**

- kW (80.0 %, PASS) and kVA (84.2 %, WARNING) remain separate checks (`ups_loading_kw`, `ups_loading_kva`). The 3,000 kVA option (kW scaled by the same ratio) reads 66.7 % kW and 70.2 % kVA (PASS) in the options table, workbook 06 sheet OPTIONS and the sizing summary.

**Evidence:** tests/unit/test_options_sensitivity.py; workbook 06_UPS_SIZING sheet OPTIONS; ER-009, ER-036.

**Still open:**

- Real UPS kW and kVA ratings and the output power factor are manufacturer data; the 3,000 kVA option is illustrative.

## Item 4. Load model review and sensitivity

**Asked:** Review cooling load (chiller and pump redundancy, CRAH), the A/B split, UPS and distribution losses; add a sensitivity table (+/-10 % IT load, PUE range); do not force a PUE target.

**Done:**

- Review recorded (sizing summary, methodology document, ER-037): chillers 4 installed / 3 running (N+1), pumps 6 / 4, CRAH 20 all counted as running with spares not stated; the 50 / 50 path split is an assumption and 3 running chillers cannot split evenly (worst path 240 kW against 180 kW in the model); UPS efficiency (flat 96 %) and distribution loss (flat 1 %) are assumptions.
- Sensitivity table: IT load -10 / 0 / +10 % with the cooling plant held as scheduled and scaled with the load, plus UPS efficiency +/-2 points and doubled distribution losses. PUE ranges from 1.322 to 1.382. At +10 % IT the transformer reads 98.0 to 99.9 % and EX-001 does not cover it. Workbook 02 sheet SENSITIVITY (a Python snapshot, labelled as such).
- PUE is documented and tested as an output: the check `load_pue_vs_target` no longer suggests retuning inputs, and the sensitivity code varies copies of the configuration, never the configuration itself.

**Evidence:** tests/unit/test_options_sensitivity.py (5 tests); calculations/sensitivity.py; docs/calculation_methodology/power_system_sizing.md; ER-005, ER-037.

**Still open:**

- CRAH redundancy, the real UPS efficiency curve, the A/B allocation by whole units and mechanical behaviour after a path loss need design decisions and manufacturer data.
- The sensitivity table is a snapshot, not live formulas, and its cases are the package's own choices.

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
