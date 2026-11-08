"""Reviewer attestation: what the package records when a person says they checked a value or accepted an exception.

A reviewer name typed into the register, a workbook or the CLI is a SELF-DECLARED ATTESTATION. The package does not authenticate the person, check their
credentials or competence, or establish their independence from the authors. It records who said what, when, against which evidence and for which scope,
so that a later reader can ask that person and look at that evidence. A value is read as verified only when the whole record is present.
"""
from __future__ import annotations

import datetime as dt

ATTESTATION_FIELDS = ("verified_by", "verified_org", "verification_date", "evidence_ref", "verification_scope")
LABELS = {"verified_by": "reviewer name", "verified_org": "organisation", "verification_date": "date", "evidence_ref": "evidence reference", "verification_scope": "scope"}
NOTICE = ("The reviewer name is a self-declared attestation, not an authenticated identity. The package does not check who the person is, their credentials or their independence. "
          "It records the name, organisation, date, evidence reference and scope so the claim can be followed up.")
WORKBOOK_FORMAT = "name; organisation; date (YYYY-MM-DD); evidence reference; scope"


def missing_fields(rec: dict) -> list[str]:
    """Attestation fields that are absent, blank or invalid (a date must be ISO and not in the future)."""
    out = []
    for f in ATTESTATION_FIELDS:
        v = rec.get(f)
        if v is None or not str(v).strip():
            out.append(f)
    d = rec.get("verification_date")
    if d is not None and str(d).strip():
        try:
            if dt.date.fromisoformat(str(d).strip()) > dt.date.today():
                out.append("verification_date (in the future)")
        except ValueError:
            out.append("verification_date (not an ISO date)")
    return out


def is_complete(rec: dict) -> bool:
    return not missing_fields(rec)


def is_started(rec: dict) -> bool:
    """Any attestation field is filled in (complete or not)."""
    return any(str(rec.get(f) or "").strip() for f in ATTESTATION_FIELDS)


def describe(rec: dict) -> str:
    return (f"{rec['verified_by']}, {rec['verified_org']}, {rec['verification_date']}; evidence: {rec['evidence_ref']}; scope: {rec['verification_scope']} (self-declared attestation)")
