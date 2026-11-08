# Release checklist: OHM-DC-2000

Release status: **DEVELOPMENT**. Nothing below is complete except where ticked.

## Required deliverables
- [ ] Working Python package (Stages 1 to 5: configuration, validation, load model, first workbook and report, power system sizing, distribution framework, manufacturer-data register, short-circuit and earthing framework)
- [x] Validated YAML project configuration (`config/project_config.yaml`)
- [x] Twenty Excel workbooks generated (five are input registers that need your data to produce results; see DEVELOPMENT_STATUS.md). Not independently reviewed
- [ ] Calculation methodology documentation
- [ ] Engineering reports
- [ ] Preliminary drawings and diagrams (single-line diagram done; others not started)
- [ ] Master equipment schedule
- [x] Technical specification templates (ten drafts; not reviewed)
- [ ] Standards register with verification status (names only, all NOT_VERIFIED)
- [x] Twelve training modules, exercises and answer keys (generated; not independently reviewed)
- [ ] QA test matrix, engineering review log, open issues register
- [x] Customer README and licence draft (the licence is NOT legally reviewed)
- [ ] Marketing assets
- [x] Versioned customer ZIP (preliminary, with manifest and master index) package
- [ ] Final release assessment

## Test status
Stage 1 to 5 and revision A6 automated tests (282). Workbooks are recalculated with LibreOffice only; Microsoft Excel was not available (see `output/WORKBOOK_LINT.md`). Results: `python -m ohmetry_dc qa-report` writes `output/QA_RESULTS.md`. A passing test proves code behaviour, not engineering correctness.

## Engineering review status
NOT PERFORMED. An independent review package has been prepared (`build-review-package`) with a reviewer checklist, a findings log and the consolidated outstanding items. No independent review of any calculation or assumption has taken place.

## Known limitations
All design values are preliminary illustrative assumptions. No manufacturer data (83 items in `config/manufacturer_data_register.yaml`, all NOT VERIFIED). Cable, busduct and switchgear ratings are not checked. ER-008 is a conditionally accepted exception pending verification. No specialist studies.

## Release approval
| Field | Value |
|---|---|
| Release state | DEVELOPMENT |
| Reviewer | not assigned |
| Review date | not assigned |
| Approved for educational distribution | NO |
