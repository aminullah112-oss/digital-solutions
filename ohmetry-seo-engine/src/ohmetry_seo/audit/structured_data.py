"""Light JSON-LD validation: required/recommended properties per type.

This catches the common omissions. It is not a replacement for Google's Rich
Results Test, and the report says so.
"""

from __future__ import annotations

# type -> (required, recommended). Based on Google Search Central structured
# data docs; re-check against current docs when adding types.
RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Organization": (("name", "url"), ("logo", "sameAs")),
    "WebSite": (("name", "url"), ()),
    "BreadcrumbList": (("itemListElement",), ()),
    "Article": (("headline",), ("author", "datePublished", "dateModified", "image")),
    "TechArticle": (("headline",), ("author", "datePublished", "dateModified", "image")),
    "BlogPosting": (("headline",), ("author", "datePublished", "dateModified", "image")),
    # Google's software-app rich result requires offers plus aggregateRating or review.
    "SoftwareApplication": (("name",), ("offers", "aggregateRating", "applicationCategory", "operatingSystem")),
    "WebApplication": (("name",), ("offers", "aggregateRating", "applicationCategory")),
    "HowTo": (("name", "step"), ()),
    "FAQPage": (("mainEntity",), ()),
}

# Types whose rich-result eligibility is restricted or commonly abused.
RESTRICTED = {
    "FAQPage": "FAQ rich results are shown only for well-known government and health sites (Google, Aug 2023).",
    "HowTo": "HowTo rich results were deprecated by Google in Sept 2023.",
    "Review": "Review markup must reflect genuine, visible reviews; self-serving reviews are ineligible.",
    "AggregateRating": "Ratings must come from real users and be visible on the page.",
}


def _iter_nodes(node: object):
    if isinstance(node, dict):
        if "@graph" in node and isinstance(node["@graph"], list):
            for item in node["@graph"]:
                yield from _iter_nodes(item)
        if "@type" in node:
            yield node
        for key, value in node.items():
            if key != "@graph" and isinstance(value, (dict, list)):
                yield from _iter_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_nodes(item)


def validate_jsonld(data: object) -> list[dict]:
    """Return findings: {type, kind: missing_required|missing_recommended|restricted|breadcrumb, detail}."""
    findings: list[dict] = []
    for node in _iter_nodes(data):
        types = node["@type"] if isinstance(node["@type"], list) else [node["@type"]]
        for t in types:
            if not isinstance(t, str):
                continue
            if t in RESTRICTED:
                findings.append({"type": t, "kind": "restricted", "detail": RESTRICTED[t]})
            rule = RULES.get(t)
            if not rule:
                continue
            required, recommended = rule
            for prop in required:
                if node.get(prop) in (None, "", []):
                    findings.append({"type": t, "kind": "missing_required", "detail": prop})
            for prop in recommended:
                if node.get(prop) in (None, "", []):
                    findings.append({"type": t, "kind": "missing_recommended", "detail": prop})
            if t == "BreadcrumbList":
                findings.extend(_check_breadcrumb(node))
    return findings


def _check_breadcrumb(node: dict) -> list[dict]:
    out = []
    items = node.get("itemListElement") or []
    if not isinstance(items, list):
        return [{"type": "BreadcrumbList", "kind": "missing_required", "detail": "itemListElement must be a list"}]
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        if item.get("position") in (None, ""):
            out.append({"type": "BreadcrumbList", "kind": "missing_required", "detail": f"item {i}: position"})
        if not item.get("name") and not (isinstance(item.get("item"), dict) and item["item"].get("name")):
            out.append({"type": "BreadcrumbList", "kind": "missing_required", "detail": f"item {i}: name"})
        # 'item' (URL) is required for every element except the last one.
        if i < len(items) and not item.get("item"):
            out.append({"type": "BreadcrumbList", "kind": "missing_required", "detail": f"item {i}: item (URL)"})
    return out
