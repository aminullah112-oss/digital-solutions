"""Group issues into recommendations and score them transparently."""

from __future__ import annotations

from dataclasses import dataclass, field

from .audit.catalog import CATALOG
from .audit.checks import AuditResult

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
PCLASS_ORDER = ["P0", "P1", "P2", "P3"]
SITE_LEVEL = {"HOST_VARIANT_NOT_REDIRECTED", "ROBOTS_UNREACHABLE", "SITEMAP_MISSING", "SITEMAP_ERROR"}


@dataclass
class Recommendation:
    code: str
    title: str
    pclass: str
    severity: str
    affected_urls: list[str]
    evidence_samples: list[str]
    why: str
    action: str
    hypothesis: str
    validation: str
    rollback: str
    components: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    traffic_note: str = ""


def _reach(share: float, bands: list) -> int:
    for threshold, value in bands:
        if share >= float(threshold):
            return int(value)
    return 1


def build_recommendations(audit: AuditResult, scoring_cfg: dict, gsc_pages: dict[str, dict] | None = None) -> list[Recommendation]:
    weights = scoring_cfg.get("weights", {})
    sev_impact = scoring_cfg.get("severity_impact", {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1})
    bands = scoring_cfg.get("reach_bands", [[0.5, 5], [0.2, 4], [0.05, 3], [0.01, 2], [0, 1]])
    denom = max(len(audit.audited_pages), 1)
    recs = []
    for code, issues in audit.by_code().items():
        t = CATALOG[code]
        urls = sorted({i.url for i in issues})
        # Use the worst severity actually observed (checks can downgrade).
        severity = min((i.severity for i in issues), key=SEVERITY_ORDER.index)
        # Site-level issues affect every page regardless of how many URLs carry the issue.
        reach = 5 if code in SITE_LEVEL else _reach(len(urls) / denom, bands)
        comps = {
            "impact": sev_impact.get(severity, 1),
            "relevance": t.relevance,
            "confidence": t.confidence,
            "reach": reach,
            "effort": t.effort,
            "risk": t.risk,
        }
        score = (weights.get("impact", 3) * comps["impact"] + weights.get("relevance", 2) * comps["relevance"]
                 + weights.get("confidence", 2) * comps["confidence"] + weights.get("reach", 2) * comps["reach"]
                 + weights.get("effort", 1) * (6 - comps["effort"]) + weights.get("risk", 1) * (6 - comps["risk"]))
        traffic_note = ""
        if gsc_pages:
            hit = [(u, gsc_pages[u]) for u in urls if u in gsc_pages]
            if hit:
                clicks = sum(r.get("clicks") or 0 for _, r in hit)
                impr = sum(r.get("impressions") or 0 for _, r in hit)
                traffic_note = f"{len(hit)} affected URL(s) have GSC data: {clicks:,.0f} clicks / {impr:,.0f} impressions in the imported range"
        pclass = t.pclass
        if severity == "low" and pclass in ("P1", "P2"):
            pclass = "P3"
        recs.append(Recommendation(
            code, t.title, pclass, severity, urls, [i.evidence for i in issues[:5]], t.why, t.action,
            f"Hypothesis: fixing this removes a {t.category} obstacle on {len(urls)} URL(s); measured via: {t.validation}",
            t.validation, t.rollback, comps, round(score, 1), traffic_note))
    recs.sort(key=lambda r: (PCLASS_ORDER.index(r.pclass), -r.score, -len(r.affected_urls)))
    return recs
