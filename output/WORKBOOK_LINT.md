# Workbook static lint (Excel compatibility)

Generated 2026-11-08 18:00 UTC. 20 workbooks, 1,697 formulas, 26 distinct functions.

**Microsoft Excel was not available when this package was built.** The workbook tests recalculate with LibreOffice only. This lint is a static read of the formulas for things Excel rejects (text literals over 255 characters, functions newer than Excel 2016, external links, unbalanced brackets, references to missing sheets). **It is not a substitute for opening the workbooks in Excel** and a clean result does not show that the formulas are right or that Excel and LibreOffice agree.

## Result

No finding. Every formula uses only allowlisted Excel 2007+ functions and stays within the Excel limits checked here.

## Constants typed into formulas (for the reviewer's formula audit)

Numbers other than counting, unit-conversion and tolerance values that appear inside formulas. Each should be a standard equation constant or an input cell reference; check each against its source.

| Workbook | Constants |
|---|---|
| 01_MASTER_DESIGN_BASIS.xlsx | 0.02 |
| 02_LOAD_ESTIMATION.xlsx | 0.02 |
| 03_POWER_ARCHITECTURE.xlsx | 4 |
| 04_TRANSFORMER_SIZING.xlsx | 4, 11 |
| 05_GENERATOR_SIZING.xlsx | 4, 13 |
| 06_UPS_SIZING.xlsx | 4, 13 |
| 07_BATTERY_SIZING.xlsx | 4, 60 |
| 08_CABLE_SIZING.xlsx | 4 |
| 09_VOLTAGE_DROP.xlsx | 8 |
| 10_SHORT_CIRCUIT.xlsx | 0.6, 0.95, 0.98, 1.02, 4, 5, 6, 7, 8, 9, 10, 11 |
| 11_LV_SWITCHGEAR.xlsx | 4 |
| 12_MV_SWITCHGEAR.xlsx | 4 |
| 13_BUSDUCT_SIZING.xlsx | 4 |
| 14_PROTECTION_COORDINATION.xlsx | 4 |
| 15_EARTHING_BONDING.xlsx | 0.09, 0.157, 1.5, 4, 6, 8 |
| 16_LIGHTNING_PROTECTION.xlsx | 4 |
| 17_POWER_QUALITY.xlsx | 4 |
| 18_ENERGY_EFFICIENCY.xlsx | 4 |
| 19_GENERATOR_FUEL.xlsx | 4, 9 |
| 20_MASTER_EQUIPMENT_SCHEDULE.xlsx | 4 |

Functions used: ABS, ACOS, AND, AVERAGE, COUNT, COUNTIF, EXP, IF, INDEX, INT, ISNUMBER, LEN, LN, MATCH, MAX, N, NOT, OR, PI, SQRT, SUBSTITUTE, SUM, SUMIF, SUMSQ, TAN, TRIM.
