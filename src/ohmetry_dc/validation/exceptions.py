"""Accepted design-target exceptions.

An exception is a recorded decision, not a pass. It never changes a check's status. It annotates the check, and it covers a result only up
to the accepted ceiling. A result above the ceiling is reported as not covered and needs re-review.
"""
from __future__ import annotations

from ohmetry_dc.models import ProjectConfig

from .status import CheckResult, CheckStatus


def apply_exceptions(cfg: ProjectConfig, results: list[CheckResult]) -> list[CheckResult]:
    by_id = {r.id: r for r in results}
    for ex in cfg.exceptions:
        r = by_id.get(ex.check_id)
        if r is None:
            continue
        loading = r.values.get("loading_pct")
        pending = "pending independent technical verification" if not ex.verified_by else f"verified by {ex.verified_by} on {ex.verification_date}"
        if r.status == CheckStatus.PASS:
            r.detail += f" Exception {ex.id} is not needed: the result is within the preferred target."
            r.values["exception"] = {"id": ex.id, "applies": False}
        elif loading is not None and r.status == CheckStatus.WARNING and loading <= ex.accepted_ceiling_pct + 1e-9:
            r.detail += (f" ACCEPTED DESIGN-TARGET EXCEPTION {ex.id} ({ex.status.lower()} by {ex.accepted_by}, {ex.accepted_date}): the result is within the accepted ceiling of {ex.accepted_ceiling_pct:g} %, {pending}. "
                         "The check stays a WARNING.")
            r.values["exception"] = {"id": ex.id, "applies": True, "accepted_ceiling_pct": ex.accepted_ceiling_pct, "verified": bool(ex.verified_by)}
        else:
            r.detail += (f" EXCEPTION {ex.id} DOES NOT COVER THIS RESULT: it was accepted only up to {ex.accepted_ceiling_pct:g} % and a result above that, or a status other than WARNING, needs re-review.")
            r.values["exception"] = {"id": ex.id, "applies": False, "accepted_ceiling_pct": ex.accepted_ceiling_pct}
            r.next_action = f"Re-review exception {ex.id}."
    return results
