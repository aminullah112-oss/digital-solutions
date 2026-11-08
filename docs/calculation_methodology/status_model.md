# Status model: calculation validity is not design verification

Each engineering check reports four things separately, and the overall status combines them.

| Item | Values | Meaning |
|---|---|---|
| Calculation status | CALCULATED, PARTIAL, NOT CALCULATED | Did the arithmetic run on complete inputs |
| Calculation result | PASS, WARNING, FAIL, N/A | What the numbers show against the criterion. Preliminary when the inputs are |
| Input-data status | MISSING, UNVERIFIED_PLACEHOLDER, PRELIMINARY_ASSUMPTION, MANUFACTURER_SUPPLIED, SITE_DATA_SUPPLIED, REFERENCE_DATA, PROJECT_INPUT, MANUFACTURER_VERIFIED, SITE_DATA_VERIFIED | The worst status among the inputs the check uses |
| Verification status | VERIFIED, NOT VERIFIED, N/A | VERIFIED only if the result passes and every input is verified, reference data or an owner decision |
| **Overall design status** | PASS, WARNING, FAIL, NOT VERIFIED | PASS needs a passing calculation and verified inputs. A preliminary WARNING or FAIL is kept. A preliminary PASS becomes NOT VERIFIED |

`MANUFACTURER_VERIFIED` and `SITE_DATA_VERIFIED` are reachable only by importing a value with a source document and then recording a reviewer (`record-verification`). A preliminary value cannot be verified. Checks that test arithmetic or input completeness (for example PUE arithmetic) are N/A for verification: they prove the code, not the design.

Source: `models/data_status.py` (vocabulary), `validation/verification.py` (which inputs each check depends on, and the rule).

## Reviewer attestation (revision A6)

A reviewer name is a **self-declared attestation**. The package does not authenticate the person, check their credentials or competence, or establish that they are independent of the authors. What it does is refuse to read a value as verified unless the whole record is present:

| Field | Register / exception key | Workbook (one cell, separated by `;`) |
|---|---|---|
| Reviewer name | `verified_by` | 1st |
| Organisation | `verified_org` | 2nd |
| Date (ISO, not in the future) | `verification_date` | 3rd |
| Evidence reference (data sheet, document, revision) | `evidence_ref` | 4th |
| Scope (what was checked, and what was not) | `verification_scope` | 5th |

- `record-verification --parameter P --by NAME --org ORG --evidence REF --scope TEXT [--date YYYY-MM-DD]` rejects a record with a missing or invalid field, rejects a placeholder, writes the latest record to the register and appends every record to `config/verification_log.yaml` (append-only).
- A register or exception entry with some fields but not all is reported as a defect and is **not** treated as verified.
- In a workbook, a reviewer cell without four semicolons and some text reads `REJECTED: ATTESTATION INCOMPLETE`. That test only refuses an entry that lacks the record. It cannot tell whether the person exists.
- A verified value verifies the **value against its source document**, within the stated scope. It does not verify the design.
