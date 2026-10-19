from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .filters import deterministic_filter
from .history import paper_keys
from .journals import enrich, passes_quality_gate
from .models import Paper
from .pubmed import fetch_details, search_ids
from .slots import _available, _sort_quality, assign_slot, window_days


def _people(cfg: dict[str, Any], topic_key: str) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    for person in cfg.get("follow") or []:
        if not isinstance(person, dict) or not person.get("name") or not person.get("query"):
            continue
        topics = [str(item) for item in person.get("topics") or []]
        if topics and topic_key not in topics:
            continue
        people.append(person)
    return people


def person_on_paper(paper: Paper, person: dict[str, Any]) -> bool:
    tokens = [part.lower() for part in str(person.get("name") or "").split() if part]
    if not tokens:
        return False
    for rec in paper.author_records:
        if not (rec.is_first or rec.is_corresponding):
            continue
        blob = rec.name.lower()
        if all(token in blob for token in tokens):
            return True
    return False


def _fetch(query: str, days: int, cfg: dict[str, Any]) -> list[Paper]:
    return fetch_details(search_ids(query, cfg, days=days, retmax=40), cfg)


def _eligible(
    papers: list[Paper],
    person: dict[str, Any],
    cfg: dict[str, Any],
    seen: set[str],
    topic_key: str,
    topic_cfg: dict[str, Any],
) -> list[Paper]:
    filtered = deterministic_filter(papers, cfg, seen)
    gate = (cfg.get("selection") or {}).get("quality_gate")
    enrich(filtered)
    kept = [
        paper
        for paper in filtered
        if not paper.is_preprint and person_on_paper(paper, person) and passes_quality_gate(paper, gate)
    ]
    for paper in kept:
        paper.subtopic = topic_key
    return _sort_quality(kept, cfg, topic_cfg)


def backfill_follow(
    chosen: list[Paper],
    *,
    need: int,
    topic_key: str,
    topic_cfg: dict[str, Any],
    cfg: dict[str, Any],
    seen: set[str],
    notes: list[str],
    fetch: Callable[[str, int], list[Paper]] | None = None,
) -> list[Paper]:
    """One representative paper per followed author, until `need` is filled."""
    if need <= 0:
        return []
    people = _people(cfg, topic_key)
    if not people:
        return []
    days = window_days(cfg)["flagship_year"]
    loader = fetch or (lambda query, span: _fetch(query, span, cfg))
    blocked = set(seen)
    for paper in chosen:
        blocked |= paper_keys(paper)
    buckets: list[tuple[dict[str, Any], list[Paper]]] = []
    for person in people:
        try:
            found = loader(str(person["query"]), days)
        except Exception as exc:
            notes.append(f"关注作者 {person.get('name')} 检索失败：{exc}")
            found = []
        buckets.append((person, _eligible(found, person, cfg, blocked, topic_key, topic_cfg)))

    picked: list[Paper] = []
    while len(picked) < need:
        progressed = False
        for person, bucket in buckets:
            if len(picked) >= need:
                break
            rest = _available(bucket, chosen + picked)
            if not rest:
                continue
            paper = assign_slot(rest[0], "follow")
            paper.scores["follow_author"] = person.get("name") or ""
            picked.append(paper)
            progressed = True
        if not progressed:
            break
    return picked
