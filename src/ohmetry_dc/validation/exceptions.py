"""Accepted design-target exceptions.

An exception is a recorded decision, not a pass. It never changes a check's status. It annotates the check, and it covers a result only up
to the accepted ceiling. A result above the ceiling is reported as not covered and needs re-review.
"""
from __future__ import annotations

from ohmetry_dc.models import ProjectConfig

from ohmetry_dc.models.attestation import describe, is_complete, is_started, missing_fields

from .status import CheckResult, CheckStatus


def apply_exceptions(cfg: ProjectConfig, results: list[CheckResult]) -> list[CheckResult]:
    by_id = {r.id: r for r in results}
    for ex in cfg.exceptions:
        r = by_id.get(ex.check_id)
        if r is None:
            continue
        loading = r.values.get("loading_pct")
        rec = ex.model_dump()
        done = is_complete(rec)
        pending = ("pending independent technical verification" if not is_started(rec) else
                   f"verification record INCOMPLETE ({', '.join(missing_fields(rec))}), treated as not verified") if not done else f"attested verified: {describe(rec)}"
        if r.status == CheckStatus.PASS:
            r.detail += f" Exception {ex.id} is not needed: the result is within the preferred target."
            r.values["exception"] = {"id": ex.id, "applies": False}
        elif loading is not None and r.status == CheckStatus.WARNING and loading <= ex.accepted_ceiling_pct + 1e-9:
            r.detail += (f" ACCEPTED DESIGN-TARGET EXCEPTION {ex.id} ({ex.status.lower()} by {ex.accepted_by}, {ex.accepted_date}): the exact result is {loading:.2f} % (shown as {loading:.1f} %), within the accepted ceiling of "
                         f"{ex.accepted_ceiling_pct:g} % by {ex.accepted_ceiling_pct - loading:.2f} percentage points, {pending}. The margin is small: any change that raises the loading above the ceiling (a derating factor below 1.00, +1 % load, a UPS or distribution loss "
                         "change) voids the exception, and the 4,000 kVA option needs none. The check stays a WARNING; the 90 % target and 100 % limit are unchanged.")
            r.values["exception"] = {"id": ex.id, "applies": True, "accepted_ceiling_pct": ex.accepted_ceiling_pct, "verified": done}
        else:
            r.detail += (f" EXCEPTION {ex.id} DOES NOT COVER THIS RESULT: it was accepted only up to {ex.accepted_ceiling_pct:g} % and a result above that, or a status other than WARNING, needs re-review.")
            r.values["exception"] = {"id": ex.id, "applies": False, "accepted_ceiling_pct": ex.accepted_ceiling_pct}
            r.next_action = f"Re-review exception {ex.id}."
    return results
