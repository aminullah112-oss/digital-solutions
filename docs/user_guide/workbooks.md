# Using the calculation workbooks

Workbooks: `04_TRANSFORMER_SIZING`, `05_GENERATOR_SIZING`, `06_UPS_SIZING`, `08_CABLE_SIZING` (current rating, voltage drop, thermal withstand), `10_SHORT_CIRCUIT`, and `02_LOAD_ESTIMATION`.

On every INPUTS sheet each row has: the **preliminary value** (retained from the master configuration, yellow), a **datasheet / confirmed value** cell (blue, yours), the **effective value used**, its source, the **datasheet source and revision** (blue, required with a value), a **reviewer** cell (blue), the live **input status** and the preliminary status.

1. Type the datasheet value in column E in the unit shown in column C.
2. Type the datasheet source and revision in column H. Without it the value is rejected (status REJECTED: SOURCE MISSING) and the preliminary value stays in force.
3. Everything recalculates. The input status reads MANUFACTURER_SUPPLIED (or SITE_DATA_SUPPLIED).
4. After checking the value against its source, type your name in column I. The status becomes ..._VERIFIED.
5. RESULTS shows the four statuses separately. An overall PASS needs a passing calculation and every input verified, reference data or an owner decision.

The column "Python engine at generation" on RESULTS holds the value the Python engine produced when the file was generated. After you change inputs it shows DIFFERENT, which is expected. Cases that lack data read NOT CALCULATED and nothing is substituted.
