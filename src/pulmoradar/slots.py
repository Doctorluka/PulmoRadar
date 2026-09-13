from __future__ import annotations

from datetime import date
from typing import Any, Literal

from . import fulltext, journals, ranker
from .dates import age_days
from .filters import keyword_bonus
from .history import paper_keys
from .models import Paper

SlotKey = Literal["recent", "flagship_year", "classic", "preprint"]

SLOT_LABELS: dict[str, str] = {
    "recent": "近一月高质量",
    "flagship_year": "年内旗舰系统研究",
    "classic": "领域经典",
    "preprint": "预印本",
}


class QuotaError(RuntimeError):
    pass


def slot_label(key: str) -> str:
    if key == "recent":
        return SLOT_LABELS["recent"]
    if key == "flagship_year":
        return SLOT_LABELS["flagship_year"]
    if key == "classic":
        return SLOT_LABELS["classic"]
    if key == "preprint":
        return SLOT_LABELS["preprint"]
    unused: str = key
    return unused or "已发表"


def window_days(cfg: dict[str, Any]) -> dict[str, int]:
    windows = cfg.get("windows") or {}
    return {
        "recent": int(windows.get("recent_days", 30)),
        "flagship_year": int(windows.get("flagship_days", 365)),
        "classic": int(windows.get("classic_days", 7300)),
        "preprint": int((windows.get("days") or [90])[-1]),
    }


def _used_keys(chosen: list[Paper]) -> set[str]:
    keys: set[str] = set()
    for paper in chosen:
        keys |= paper_keys(paper)
    return keys


def _available(pool: list[Paper], chosen: list[Paper]) -> list[Paper]:
    used = _used_keys(chosen)
    return [p for p in pool if not (paper_keys(p) & used)]


def _in_window(paper: Paper, days: int | None, today: date) -> bool:
    if days is None:
        return True
    age = age_days(paper.date, today)
    if age is None:
        return False
    return 0 <= age <= days


def _quality_score(paper: Paper, cfg: dict[str, Any], topic_cfg: dict[str, Any]) -> float:
    profile = cfg.get("profile", {})
    boost = list(topic_cfg.get("boost_keywords", [])) + list(profile.get("boost_keywords", []))
    avoid = profile.get("avoid_keywords", [])
    extra = list(topic_cfg.get("preferred_journals", [])) + list(topic_cfg.get("extra_journals", []))
    kw = keyword_bonus(paper, boost, avoid)
    jbonus = journals.journal_bonus(paper, extra, [])
    tier = journals.journal_tier(paper, extra)
    tier_pts = {"cns": 4.0, "major": 3.0, "flagship": 2.0}.get(tier or "", 0.0)
    screen = float(paper.scores.get("screen") or 0)
    return screen + kw + jbonus + tier_pts


def _sort_quality(papers: list[Paper], cfg: dict[str, Any], topic_cfg: dict[str, Any]) -> list[Paper]:
    ranked = list(papers)
    ranked.sort(key=lambda p: _quality_score(p, cfg, topic_cfg), reverse=True)
    return ranked


def _pick_newest(papers: list[Paper], today: date) -> Paper | None:
    dated = [(age_days(p.date, today), p) for p in papers]
    dated = [(age, p) for age, p in dated if age is not None]
    if not dated:
        return papers[0] if papers else None
    dated.sort(key=lambda item: item[0])
    return dated[0][1]


def _pick_oldest_quality(papers: list[Paper], cfg: dict[str, Any], topic_cfg: dict[str, Any], today: date) -> Paper | None:
    if not papers:
        return None
    def key(paper: Paper) -> tuple[float, int]:
        age = age_days(paper.date, today)
        return (_quality_score(paper, cfg, topic_cfg), age if age is not None else 0)
    return max(papers, key=key)


def assign_slot(paper: Paper, key: SlotKey) -> Paper:
    paper.slot = key
    paper.scores["slot"] = key
    paper.scores["slot_label"] = slot_label(key)
    return paper


def _llm_or_heuristic(
    papers: list[Paper],
    topic_cfg: dict[str, Any],
    cfg: dict[str, Any],
    dry_run: bool,
    n: int,
) -> list[Paper]:
    if not papers or n <= 0:
        return []
    ranked = _sort_quality(papers, cfg, topic_cfg)
    if dry_run:
        return ranked[:n]
    screened = ranker.screen(ranked[: int(cfg.get("selection", {}).get("max_screen", 40))], topic_cfg, cfg)
    pool = screened or ranked
    shortlist = max(n, int(cfg.get("selection", {}).get("rank_shortlist", 10)))
    return ranker.rank(pool[:shortlist], topic_cfg, cfg)[:n]


def select_published_slots(
    pool: list[Paper],
    topic_cfg: dict[str, Any],
    cfg: dict[str, Any],
    *,
    today: date,
    dry_run: bool,
    label: str,
) -> list[Paper]:
    """Pick exactly 3 published papers: recent / year-flagship / classic."""
    gate = (cfg.get("selection") or {}).get("quality_gate")
    extra = list(topic_cfg.get("preferred_journals", [])) + list(topic_cfg.get("extra_journals", []))
    days = window_days(cfg)
    quality = [p for p in pool if journals.passes_quality_gate(p, gate)]
    chosen: list[Paper] = []
    notes: list[str] = []

    recent_pool = [p for p in _available(quality, chosen) if _in_window(p, days["recent"], today)]
    recent = _pick_newest(_sort_quality(recent_pool, cfg, topic_cfg), today)
    if recent is None:
        wider = [p for p in _available(quality, chosen) if _in_window(p, 90, today)]
        recent = _pick_newest(_sort_quality(wider, cfg, topic_cfg), today)
        if recent is not None:
            notes.append(f"{label} 近一月槽回退到 90 天。")
    if recent is None:
        recent = _sort_quality(_available(quality, chosen), cfg, topic_cfg)[:1]
        recent = recent[0] if recent else None
        if recent is not None:
            notes.append(f"{label} 近一月槽回退到质量最高的已发表。")
    if recent is None:
        raise QuotaError(f"{label} 无法凑满近一月高质量槽。")
    chosen.append(assign_slot(recent, "recent"))

    year_pool = [
        p
        for p in _available(quality, chosen)
        if _in_window(p, days["flagship_year"], today) and journals.is_flagship_tier(p, extra)
    ]
    year_pick = _llm_or_heuristic(year_pool, topic_cfg, cfg, dry_run, 1)
    flagship = year_pick[0] if year_pick else None
    if flagship is None:
        fallback = [p for p in _available(quality, chosen) if _in_window(p, days["flagship_year"], today)]
        year_pick = _llm_or_heuristic(fallback, topic_cfg, cfg, dry_run, 1)
        flagship = year_pick[0] if year_pick else None
        if flagship is not None:
            notes.append(f"{label} 年内旗舰槽回退到一年内高质量（不限档）。")
    if flagship is None:
        raise QuotaError(f"{label} 无法凑满年内旗舰系统研究槽。")
    chosen.append(assign_slot(flagship, "flagship_year"))

    classic_pool = _available(quality, chosen)
    classic_cfg = {
        **topic_cfg,
        "focus": (
            f"{topic_cfg.get('focus', '')} "
            "Prefer landmark or foundational papers for this disease area or a major sub-direction, "
            "even if they are older than the usual recency window."
        ).strip(),
    }
    classic_pool = sorted(
        classic_pool,
        key=lambda p: (_quality_score(p, cfg, topic_cfg), age_days(p.date, today) or 0),
        reverse=True,
    )
    classic_pick = _llm_or_heuristic(classic_pool, classic_cfg, cfg, dry_run, 1)
    classic = classic_pick[0] if classic_pick else None
    if classic is None:
        classic = _pick_oldest_quality(classic_pool, cfg, topic_cfg, today)
        if classic is not None:
            notes.append(f"{label} 经典槽回退到质量最高的剩余论文。")
    if classic is None:
        raise QuotaError(f"{label} 无法凑满领域经典槽。")
    chosen.append(assign_slot(classic, "classic"))

    if len(chosen) != 3:
        raise QuotaError(f"{label} 已发表未凑满 3 篇（当前 {len(chosen)}）。")
    for paper in chosen:
        paper.scores["selection_notes"] = notes
    return chosen


def select_preprint_quota(
    pool: list[Paper],
    topic_cfg: dict[str, Any],
    cfg: dict[str, Any],
    *,
    n: int,
    dry_run: bool,
    label: str,
) -> list[Paper]:
    if n <= 0:
        return []
    ranked = _llm_or_heuristic(pool, topic_cfg, cfg, dry_run, n)
    if len(ranked) < n:
        used = _used_keys(ranked)
        extra = [p for p in _sort_quality(pool, cfg, topic_cfg) if not (paper_keys(p) & used)]
        ranked.extend(extra[: n - len(ranked)])
    if len(ranked) < n:
        raise QuotaError(f"{label} 预印本必须 {n} 篇，过滤后只有 {len(ranked)} 篇。")
    chosen = ranked[:n]
    for paper in chosen:
        assign_slot(paper, "preprint")
    return chosen


def enrich_chosen(papers: list[Paper], cfg: dict[str, Any], dry_run: bool) -> None:
    journals.enrich(papers)
    if dry_run:
        return
    fulltext.enrich(papers)
    for paper in papers:
        ranker.analyze_one(paper, cfg)
    journals.enrich(papers)
