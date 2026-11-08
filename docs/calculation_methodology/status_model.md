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
