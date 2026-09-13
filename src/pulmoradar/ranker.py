from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import llm
from .config import project_root
from .dates import age_days
from .filters import keyword_bonus
from .models import Paper


def recency_bonus(date_str: str, today: date | None = None) -> float:
    """Small tie-break only. Quality / slot rules decide selection."""
    age = age_days(date_str, today)
    if age is None:
        return 0.0
    if age <= 14:
        return 0.15
    if age <= 45:
        return 0.05
    return 0.0


def _prompt(name: str) -> Path:
    return project_root() / "prompts" / name


def screen(papers: list[Paper], topic_cfg: dict[str, Any], cfg: dict[str, Any]) -> list[Paper]:
    profile = cfg.get("profile", {})
    boost = ", ".join(topic_cfg.get("boost_keywords") or profile.get("boost_keywords", []))
    avoid = ", ".join(profile.get("avoid_keywords", []))
    batch_n = int(cfg.get("selection", {}).get("screen_batch", 8))
    kept: list[Paper] = []
    template = _prompt("screening.txt").read_text(encoding="utf-8")
    for i in range(0, len(papers), batch_n):
        batch = papers[i : i + batch_n]
        user = template.format(
            topic_name=topic_cfg.get("name", ""),
            focus=topic_cfg.get("focus", ""),
            boost_keywords=boost,
            avoid_keywords=avoid,
            papers_block=llm.paper_block(batch),
        )
        data = llm.chat_json(
            cfg,
            "You return only JSON for literature screening.",
            user,
        )
        by_id = {p.paper_id: p for p in batch}
        for row in data.get("papers", []):
            paper = by_id.get(row.get("id"))
            if paper is None:
                continue
            if not row.get("is_on_topic") or not row.get("is_basic_research"):
                continue
            rel = float(row.get("relevance") or 0)
            paper.scores["screen"] = rel
            paper.scores["screen_reason"] = row.get("reason", "")
            kept.append(paper)
    kept.sort(key=lambda p: p.scores.get("screen", 0), reverse=True)
    return kept


def rank(papers: list[Paper], topic_cfg: dict[str, Any], cfg: dict[str, Any]) -> list[Paper]:
    if not papers:
        return []
    from . import journals as journal_mod

    profile = cfg.get("profile", {})
    boost = list(topic_cfg.get("boost_keywords") or profile.get("boost_keywords", []))
    avoid = profile.get("avoid_keywords", [])
    preferred = topic_cfg.get("preferred_journals") or []
    extra = topic_cfg.get("extra_journals") or []
    if preferred:
        journal_note = (
            "For this topic, prefer flagship journals "
            + ", ".join(preferred)
            + " and also strongly consider "
            + ", ".join(extra)
            + ". Journal is a prior, not a substitute for mechanism."
        )
    else:
        journal_note = "Do NOT let journal name dominate over mechanistic quality."
    template = _prompt("ranking.txt").read_text(encoding="utf-8")
    user = template.format(
        topic_name=topic_cfg.get("name", ""),
        focus=topic_cfg.get("focus", ""),
        journal_note=journal_note,
        papers_block=llm.paper_block(papers),
    )
    data = llm.chat_json(cfg, "You return only JSON for literature ranking.", user)
    by_id = {p.paper_id: p for p in papers}
    for row in data.get("papers", []):
        paper = by_id.get(row.get("id"))
        if paper is None:
            continue
        mech = float(row.get("mechanism") or 0)
        methods = float(row.get("methods") or 0)
        novelty = float(row.get("novelty") or 0)
        fit = float(row.get("fit") or row.get("personal") or 0)
        bonus = keyword_bonus(paper, boost, avoid)
        jbonus = journal_mod.journal_bonus(paper, preferred, extra)
        total = 0.34 * mech + 0.24 * methods + 0.2 * novelty + 0.16 * fit + 0.06 * bonus + jbonus
        recency = recency_bonus(paper.date)
        paper.scores.update(
            {
                "mechanism": mech,
                "methods": methods,
                "novelty": novelty,
                "fit": fit,
                "keyword_bonus": bonus,
                "journal_bonus": jbonus,
                "total": total + recency,
                "rank_why": row.get("why", ""),
            }
        )
    papers.sort(key=lambda p: float(p.scores.get("total") or 0), reverse=True)
    return papers


def analyze_one(paper: Paper, cfg: dict[str, Any]) -> dict[str, Any]:
    template = _prompt("analysis.txt").read_text(encoding="utf-8")
    user = template.format(
        title=paper.title,
        journal=paper.journal,
        date=paper.date,
        source=paper.source,
        first_aff="; ".join(paper.first_affiliations) or "未知",
        corr_aff="; ".join(paper.corresponding_affiliations) or "未知",
        abstract=paper.abstract[:4000],
        fulltext=(paper.fulltext or "（无 OA 全文）")[:6000],
    )
    try:
        data = llm.chat_json(cfg, "You return only JSON for a paper briefing.", user)
    except Exception:
        data = {
            "one_liner": "模型未能生成规范解读，请直接阅读摘要与原文。",
            "what_is_new": [],
            "implications": [],
            "design": [],
            "findings": [],
            "why_selected": paper.scores.get("rank_why") or "",
            "limitations": ["AI 解读解析失败"],
            "author_fields": {"first": "不详", "corresponding": "不详"},
            "evaluation_basis": paper.evaluation_basis or "abstract_only",
        }
    paper.analysis = data
    if data.get("evaluation_basis"):
        paper.evaluation_basis = data["evaluation_basis"]
    return data
