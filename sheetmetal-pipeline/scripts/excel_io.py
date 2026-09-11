"""Stage 4: read part specs from an Excel workbook.

One row per part. Header row (row 1) gives column names; this module does
no type coercion or validation -- it just turns each data row into a dict
of {header: cell_value}. Coercing to float and validating happens per-row
in run_batch.py, inside that row's own try/except, so a single bad cell
(wrong type, missing value) is a normal caught-and-logged failure for that
one job, not a reason to abort the whole file.

Expected columns (case-sensitive, any order):
    JobID, PlateLength, PlateWidth, Thickness, FlangeLength, BendAngle,
    BendRadius, KFactor, HoleDia, HoleX, HoleY
"""

import openpyxl


def read_rows(path, sheet_name=None):
    """Yield one dict per data row: {column_header: cell_value}.

    Stops at the first row where every cell is empty (trailing blank rows
    in the sheet are common and not an error). Raises if the file can't be
    opened or has no header row -- those are file-level problems, not a
    single bad row, so they're not swallowed here.
    """
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        raise ValueError(f"{path}: sheet '{ws.title}' has no header row")

    headers = [str(h).strip() if h is not None else None for h in header]
    if not any(headers):
        raise ValueError(f"{path}: header row is empty")

    for row in rows:
        if all(cell is None for cell in row):
            continue
        yield {h: v for h, v in zip(headers, row) if h is not None}

    wb.close()
