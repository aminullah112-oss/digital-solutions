"""Stage 5: material x thickness -> K-factor lookup.

Bend allowance was hardcoded (K_FACTOR = 0.38) through Stages 2-4. This
module replaces that with a lookup against an external JSON table
(config/kfactor_table.json), keyed by material name and thickness band --
so a batch run looks up the K-factor per row instead of assuming one value
for every part regardless of material or gauge.
"""

import json
import os

PIPELINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TABLE_PATH = os.path.join(PIPELINE_ROOT, "config", "kfactor_table.json")


def load_table(path=None):
    path = path or DEFAULT_TABLE_PATH
    with open(path) as f:
        return json.load(f)


def lookup_k_factor(table, material, thickness):
    """Return (k_factor, extrapolated). Raises KeyError if `material` isn't
    in the table -- an unknown material is a data problem the caller should
    treat like any other bad-row failure, not silently default away.
    """
    materials = table["materials"]
    if material not in materials:
        known = ", ".join(sorted(materials))
        raise KeyError(f"unknown material '{material}' (known materials: {known})")

    bands = materials[material]
    for band in bands:
        if thickness <= band["thickness_max"]:
            return band["k_factor"], False

    # Thickness exceeds every band -- extrapolate from the largest band
    # rather than fail outright, but tell the caller so it can warn.
    return bands[-1]["k_factor"], True
