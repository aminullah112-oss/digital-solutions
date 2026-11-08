"""Input-data status vocabulary, derived from a parameter's provenance. It is never stored, so it cannot drift from the facts.

PRELIMINARY_ASSUMPTION   a value chosen for the sample project (owner decision or master prompt), not tied to a data sheet
UNVERIFIED_PLACEHOLDER   a preliminary value that stands in for manufacturer-specific data and is flagged for verification
REFERENCE_DATA           a published constant or factor (edition to be verified); never manufacturer-confirmed
PROJECT_INPUT            a decision or policy value supplied by the project owner
MANUFACTURER_SUPPLIED    imported from a manufacturer document, not yet reviewed
SITE_DATA_SUPPLIED       imported from a utility, survey or design document, not yet reviewed
MANUFACTURER_VERIFIED    imported and reviewed (a reviewer is recorded in the register). The only way to reach this status.
SITE_DATA_VERIFIED       the same for utility and site data
MISSING                  no value
"""
from __future__ import annotations

from .parameter import Parameter

MISSING = "MISSING"
UNVERIFIED_PLACEHOLDER = "UNVERIFIED_PLACEHOLDER"
PRELIMINARY_ASSUMPTION = "PRELIMINARY_ASSUMPTION"
MANUFACTURER_SUPPLIED = "MANUFACTURER_SUPPLIED"
SITE_DATA_SUPPLIED = "SITE_DATA_SUPPLIED"
REFERENCE_DATA = "REFERENCE_DATA"
PROJECT_INPUT = "PROJECT_INPUT"
MANUFACTURER_VERIFIED = "MANUFACTURER_VERIFIED"
SITE_DATA_VERIFIED = "SITE_DATA_VERIFIED"

# worst first. A check reports the worst status among its inputs.
RANK = {MISSING: 0, UNVERIFIED_PLACEHOLDER: 1, PRELIMINARY_ASSUMPTION: 2, MANUFACTURER_SUPPLIED: 3, SITE_DATA_SUPPLIED: 3, REFERENCE_DATA: 5, PROJECT_INPUT: 5,
        MANUFACTURER_VERIFIED: 6, SITE_DATA_VERIFIED: 6}
ACCEPTABLE = 5       # statuses at or above this rank do not by themselves block engineering verification


def data_status(p: Parameter, verified: bool = False) -> str:
    if p.value is None:
        return MISSING
    overridden = p.revision == "OVERRIDE"
    s = p.status.value
    if s == "MANUFACTURER_DATA":
        return MANUFACTURER_VERIFIED if (verified and overridden) else MANUFACTURER_SUPPLIED
    if s == "USER_INPUT":
        if overridden:
            return SITE_DATA_VERIFIED if verified else SITE_DATA_SUPPLIED
        return PROJECT_INPUT
    if s == "REFERENCE":
        return REFERENCE_DATA
    return UNVERIFIED_PLACEHOLDER if p.requires_manufacturer_verification else PRELIMINARY_ASSUMPTION


def worst(statuses: list[str]) -> str:
    return min(statuses, key=lambda s: RANK[s]) if statuses else "N/A"
