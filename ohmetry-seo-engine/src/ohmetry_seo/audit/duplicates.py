"""Exact and near-duplicate detection on main-content text."""

from __future__ import annotations

from collections import defaultdict

from ..crawler import PageRecord


def jaccard(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_exact_duplicates(pages: list[PageRecord]) -> list[list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for p in pages:
        if p.data and p.data.main_text_hash and p.data.word_count >= 20:
            groups[p.data.main_text_hash].append(p.url)
    return [sorted(urls) for urls in groups.values() if len(urls) > 1]


def find_near_duplicates(pages: list[PageRecord], threshold: float, exact_groups: list[list[str]],
                         min_words: int = 50, max_pages: int = 3000) -> list[tuple[str, str, float]]:
    """Pairwise shingle Jaccard. O(n²) — fine for a few thousand pages."""
    in_exact = {u for g in exact_groups for u in g}
    candidates = [p for p in pages if p.data and p.data.word_count >= min_words and p.url not in in_exact][:max_pages]
    pairs = []
    for i, a in enumerate(candidates):
        sa = a.data.shingles
        for b in candidates[i + 1:]:
            sb = b.data.shingles
            # Cheap bound: Jaccard <= min/max of set sizes.
            if min(len(sa), len(sb)) / max(len(sa), len(sb), 1) < threshold:
                continue
            score = jaccard(sa, sb)
            if score >= threshold:
                pairs.append((a.url, b.url, round(score, 3)))
    return sorted(pairs, key=lambda x: -x[2])
