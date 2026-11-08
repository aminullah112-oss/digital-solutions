"""Roll check statuses up to a release gate. This code never grants approval on its own."""
from __future__ import annotations

from collections import Counter

from ohmetry_dc.models import ReleaseState

from .status import CheckResult, CheckStatus


def summarise(results: list[CheckResult]) -> dict[str, int]:
    c = Counter(r.status for r in results)
    return {s.value: c.get(s, 0) for s in CheckStatus}


def release_gate(results: list[CheckResult], declared: ReleaseState) -> ReleaseState:
    """The declared state is a ceiling that the checks can only lower.

    Any FAIL blocks release. Any WARNING or NOT VERIFIED prevents approval. Approval is also withheld in this stage because engineering review
    evidence is not tracked in the configuration yet.
    """
    s = summarise(results)
    if s["FAIL"]:
        return ReleaseState.RELEASE_BLOCKED
    if declared == ReleaseState.APPROVED_FOR_EDUCATIONAL_DISTRIBUTION:
        return ReleaseState.ENGINEERING_REVIEW_REQUIRED
    return declared
