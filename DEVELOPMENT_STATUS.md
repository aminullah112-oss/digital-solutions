# Development status: OHM-DC-2000

**Current milestone:** revision A6 = the A5 package plus corrective actions 1 to 12 of the independent A5 review (see `docs/release/CORRECTIVE_ACTION_REPORT.md`). Awaiting independent review.
**Declared release state:** DEVELOPMENT. The computed release gate is DEVELOPMENT. No check FAILs, 3 are WARNING (transformer kVA, UPS kVA, generator kW in the combined contingency), 27 are NOT VERIFIED and 2 are NOT APPLICABLE (arc-flash and lightning are out of scope). Approval is not possible. **Not construction-ready. Not verified.**

## Completed
| Item | Location | Stage | Status |
|---|---|---|---|
| Repository, configuration with provenance, models, loader, release gate, assumptions register, standards register | see README | 1 | Done |
| Itemised load schedule, load model, PUE, A/B allocation, `02_LOAD_ESTIMATION.xlsx`, load estimation report | `calculations/load.py`, `excel/`, `reporting/` | 2 | Done |
| Demand data section: the single place for new load figures, read by `general.*` | `config/project_config.yaml` | 3 | Done |
| Loading policy per equipment type (target and maximum), configurable | `design_criteria.*` | 3 | Done |
| Derating (ambient, altitude, installation) applied before loading, with a transformer contingency factor | `calculations/derating.py` | 3 | Done. Factors are 1.00 placeholders |
| Transformer sizing under loss of the other path | `calculations/sizing.py` | 3 | Done |
| UPS sizing, kW and kVA | `calculations/sizing.py` | 3 | Done |
| Generator sizing: PRP default, ESP and COP selectable, N+1 loss-of-unit scenarios | `calculations/sizing.py` | 3 | Done |
| Generator load-step and transient requirements (upper bound, always NOT VERIFIED) | `calculations/sizing.py` | 3 | Done as an interface |
| Battery sizing interface (arithmetic energy only, no battery sized) | `calculations/sizing.py` | 3 | Done as an interface |
| Required rating and suggested size per equipment (illustrative lists) | `calculations/sizing.py` | 3 | Done |
| Revision workflow: `revision-impact` compares revisions and records equipment sizing changes | `reporting/sizing_summary.py`, `config/design_basis_revisions.yaml` | 3 | Done |
| Sizing summary and verification notes | `sizing-summary`, `docs/engineering_review/stage3_verification_notes.md` | 3 | Done |
| Design-target exception mechanism (EX-001 transformer, ceiling 91.0 %); exceptions never turn WARNING into PASS | `validation/exceptions.py`, `config/design_exceptions.yaml` | 4 | Done |
| Generator kW check with rated power factor placeholder; PRP basis unconfirmed check | `validation/checks.py` | 4 | Done. NOT VERIFIED until manufacturer data |
| Distribution framework: cable resistance, three-phase voltage drop, design currents, required ratings for cables, busduct, LV and MV switchgear | `calculations/distribution.py`, `config/distribution.yaml` | 4 | Done. Ratings NOT VERIFIED |
| Manufacturer-data register (83 entries, live values, Markdown and CSV) with completeness check | `config/manufacturer_data_register.yaml`, `build-manufacturer-register` | 4 | Done |
| QA results report | `qa-report` | 4 | Done |
| Short-circuit method (IEC 60909): MV and LV, utility, generators, transformer-limited bound, peak and thermal | `calculations/short_circuit.py` | 5 | Method done and tested. NOT CALCULATED for the project: utility, transformer and generator data pending |
| Equipment short-circuit rating, cable thermal withstand and protection-device breaking capacity checks | `validation/checks.py` | 5 | Done. Ratings NOT VERIFIED |
| Earthing screening (IEEE 80 grid resistance, GPR, tolerable touch voltage) | `calculations/earthing.py` | 5 | Method done. NOT CALCULATED: soil survey and grid design pending |
| Four-status model (calculation, result, input data, overall); a preliminary PASS cannot reach PASS | `validation/verification.py`, `models/data_status.py` | 5 | Done |
| All 20 workbooks (01 to 20). Engine-backed: 02, 04 to 08, 10 to 13, 15 (agree with Python). Architecture, voltage drop, schedule and basis: 01, 03, 09, 20. Input registers with limited live calculation: 14, 16, 17, 18, 19. All with editable datasheet input cells, sources, reviewer and live statuses; agree with Python | `excel/sizing_workbooks.py`, `excel/distribution_workbooks.py` | 5 | Done |
| Preliminary single-line diagram OHM-DC-2000-SLD-001 (SVG and PDF) generated from the configuration; shows no unverified value as a fact | `drawings/single_line.py`, `generate-drawings` | 5 | Done |
| Training suite: 12 modules (Markdown and PDF), exercise workbook, 48-question bank, answer key, completion certificate template; worked examples use the engine | `training/`, `generate-training` | 5 | Done. Not accredited. Not independently reviewed |
| Ten specification templates (DOCX and PDF): ratings from the configuration with data status, standards named, manufacturer-data lists from the register, inspection, FAT and commissioning requirements | `documents/specs.py`, `specifications/` | 5 | Done. Templates, not issued specifications. Not reviewed |
| Customer README, commercial licence draft (not legally reviewed), master index, document register with revisions, issues and cross-references | `documents/`, `docs/release/` | 5 | Done. Licence needs a legal professional |
| Consolidated outstanding verification items, reviewer checklist and guide, findings log, independent review package (ZIP) | `documents/review.py`, `build-review-package` | 5 | Done. Review not performed |
| `build-package`: assembles the customer ZIP from what exists, with a manifest and a status file (no engine source unless requested) | `packaging.py` | 5 | Done |
| Data import from data sheets without changing code (overrides file, CSV template, data classification) | `import-manufacturer-data`, `config/manufacturer_data_overrides.yaml` | 5 | Done |
| Revision A6 corrective actions 1 to 4: generator combined contingency judged (kW WARNING, basis for the engineer to select); transformer 3,150 / 4,000 kVA and UPS 2,500 / 3,000 kVA side by side (nothing selected); EX-001 reconciled; load-model review and sensitivity (PUE an output) | `calculations/options.py`, `calculations/sensitivity.py` | A6 | Done. NOT REVIEWED |
| Revision A6 corrective actions 5 to 12: SLD architecture concept symbols (utility A/B independence not claimed); derating, installation, parallel arrangement and current-sharing status; short-circuit wording and arc-flash scope; earthing screening and lightning scope; reviewer attestation records; standards register (33) and specification schedules (vendor data, compliance, SAT); document control, ER log, static workbook lint; `regenerate-all` release gate | see CORRECTIVE_ACTION_REPORT | A6 | Done. NOT REVIEWED. Excel never available: workbooks tested in LibreOffice only |
| Tests: 282 | `tests/` | 1 to 5, A6 | Passing |

## Not started (do not treat as complete)
Drawings other than the preliminary single-line diagram, the other engineering reports (only the load report exists), marketing assets (LinkedIn post, FAQ, product page copy, sample previews), network studies and protection coordination (needs manufacturer curves and a validated study), independent engineering review, and any manufacturer data.


## Blockers for Stage 6
- Manufacturer data for ratings, derating, generator PRP limits, step loads, UPS and battery (see the sizing summary).
- ER-008 to ER-013: the concept ratings sit above or far below the policy targets in places, and rest on placeholder derating.
- Utility fault levels, generator and transformer data, soil survey, device curves. Protection coordination and arc-flash are not started.

## Next action
Review Stage 5, especially ER-019 (LV fault level). Obtain utility and manufacturer data (see the register). Then decide the next stage and the workbook plan for the ZIP.
