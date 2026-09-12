from __future__ import annotations

import re
from typing import Any

from .models import Paper

CLINICAL_HINTS = re.compile(
    r"\b(randomized|randomised|phase [123i]+|clinical trial|cohort study|"
    r"observational study|guideline|meta-analysis|systematic review|"
    r"case report|epidemiolog)\b",
    re.I,
)
REVIEWISH_TITLE = re.compile(
    r"\b(review|consensus statement|scientific statement|position paper|"
    r"workshop report|expert opinion|guidelines?)\b",
    re.I,
)
BASIC_HINTS = re.compile(
    r"\b(knockout|knock-in|crispr|sirna|shrna|mouse|mice|rat|zebrafish|"
    r"organoid|fibroblast|endothelial|smooth muscle|bleomycin|hypoxia|"
    r"scrna-seq|single-cell|lineage tracing|western blot|immunofluorescence|"
    r"in vitro|in vivo|rescue|conditional)\b",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def is_excluded_type(paper: Paper, exclude_types: list[str]) -> bool:
    types = {t.lower() for t in paper.publication_types}
    return any(ex.lower() in types for ex in exclude_types)


def looks_clinical_only(paper: Paper) -> bool:
    blob = f"{paper.title} {paper.abstract}"
    if BASIC_HINTS.search(blob):
        return False
    return bool(CLINICAL_HINTS.search(blob))


def looks_reviewish(paper: Paper) -> bool:
    return bool(REVIEWISH_TITLE.search(paper.title or ""))


def keyword_bonus(paper: Paper, boost: list[str], avoid: list[str]) -> float:
    blob = f"{paper.title} {paper.abstract}".lower()
    score = 0.0
    for kw in boost:
        if kw.lower() in blob:
            score += 1.0
    for kw in avoid:
        if kw.lower() in blob:
            score -= 1.5
    return score


def deterministic_filter(
    papers: list[Paper],
    cfg: dict[str, Any],
    seen: set[str],
) -> list[Paper]:
    from .history import is_seen

    exclude_types = cfg.get("exclude_publication_types", [])
    kept: list[Paper] = []
    seen_now: set[str] = set()
    for paper in papers:
        if not _norm(paper.title) or not _norm(paper.abstract):
            continue
        if is_seen(paper, seen) or is_seen(paper, seen_now):
            continue
        if is_excluded_type(paper, exclude_types):
            continue
        if looks_reviewish(paper):
            continue
        if looks_clinical_only(paper):
            continue
        from .journals import is_excluded_publisher

        publishers = ((cfg.get("selection") or {}).get("quality_gate") or {}).get("exclude_publishers") or []
        if is_excluded_publisher(paper, list(publishers)):
            continue
        kept.append(paper)
        seen_now |= {k.strip().lower() for k in (paper.paper_id, paper.pmid, paper.doi, paper.preprint_id) if k}
    return kept
