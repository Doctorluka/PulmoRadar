from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import yaml

from .config import project_root
from .models import Paper

MISSING = "未收录"


def _norm(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\bthe\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _issn_key(issn: str) -> str:
    return re.sub(r"[^0-9xX]", "", issn or "")


def _index_rows(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_name: dict[str, dict[str, Any]] = {}
    by_issn: dict[str, dict[str, Any]] = {}
    for row in rows:
        rec = dict(row)
        rec["in_catalog"] = True
        for name in rec.get("names", []):
            key = _norm(name)
            if key:
                by_name[key] = rec
        for issn in rec.get("issn", []):
            by_issn[_issn_key(str(issn))] = rec
    return by_name, by_issn


def catalog_years() -> tuple[int | None, int | None]:
    tables = _tables()
    return tables.get("if_year"), tables.get("cas_year")


@lru_cache(maxsize=1)
def _tables() -> dict[str, Any]:
    root = project_root() / "data"
    with (root / "jcr_if.yaml").open(encoding="utf-8") as f:
        jcr = yaml.safe_load(f) or {}
    with (root / "cas_zone.yaml").open(encoding="utf-8") as f:
        cas = yaml.safe_load(f) or {}
    jcr_name, jcr_issn = _index_rows(jcr.get("journals") or [])
    cas_name, cas_issn = _index_rows(cas.get("journals") or [])
    return {
        "if_year": jcr.get("year"),
        "cas_year": cas.get("year"),
        "if_source": jcr.get("source"),
        "cas_source": cas.get("source"),
        "jcr_name": jcr_name,
        "jcr_issn": jcr_issn,
        "cas_name": cas_name,
        "cas_issn": cas_issn,
    }


def lookup(journal: str, issn: str = "") -> dict[str, Any]:
    tables = _tables()
    issn_key = _issn_key(issn)
    jcr = tables["jcr_issn"].get(issn_key) if issn_key else None
    if jcr is None:
        jcr = tables["jcr_name"].get(_norm(journal))
    cas = tables["cas_issn"].get(issn_key) if issn_key else None
    if cas is None:
        cas = tables["cas_name"].get(_norm(journal))
    in_catalog = bool(jcr or cas)
    return {
        "impact_factor": None if jcr is None else jcr.get("impact_factor"),
        "jcr": (jcr or {}).get("jcr") or MISSING,
        "cas": (cas or {}).get("cas") or MISSING,
        "if_year": tables["if_year"],
        "cas_year": tables["cas_year"],
        "in_catalog": in_catalog,
    }


def format_metrics(paper: Paper) -> str:
    if paper.is_preprint:
        return ""
    meta = paper.journal_metrics or lookup(paper.journal, paper.issn)
    if_year = meta.get("if_year") or "最新"
    cas_year = meta.get("cas_year") or "2025"
    impact = meta.get("impact_factor")
    if_text = f"{impact}" if impact not in (None, "") else MISSING
    jcr = meta.get("jcr") or MISSING
    cas = meta.get("cas") or MISSING
    note = "" if meta.get("in_catalog", True) else "（本地期刊表未收录，非官方无IF）"
    return f"IF {if_year}：{if_text} · JCR：{jcr} · 中科院{cas_year}：{cas}{note}"


def metric_chips(paper: Paper) -> list[str]:
    if paper.is_preprint:
        return []
    meta = paper.journal_metrics or lookup(paper.journal, paper.issn)
    impact = meta.get("impact_factor")
    if_text = f"{impact}" if impact not in (None, "") else MISSING
    jcr = meta.get("jcr") or MISSING
    cas = meta.get("cas") or MISSING
    return [f"IF: {if_text}", f"JCR: {jcr}", cas]


def enrich(papers: list[Paper]) -> None:
    for paper in papers:
        if paper.is_preprint:
            paper.journal_metrics = {}
            continue
        paper.journal_metrics = lookup(paper.journal, paper.issn)


def cas_zone(cas: str) -> int | None:
    text = (cas or "").replace(" ", "")
    for n in (1, 2, 3, 4):
        if f"{n}区" in text:
            return n
    return None


_PUBLISHER_DOI_PREFIXES = {
    "frontiers": ("10.3389",),
    "mdpi": ("10.3390",),
    "hindawi": ("10.1155",),
}


def is_excluded_publisher(paper: Paper, names: list[str] | None) -> bool:
    if not names:
        return False
    blob = " ".join(
        [
            paper.journal or "",
            paper.url or "",
            paper.doi or "",
        ]
    ).lower()
    doi = (paper.doi or "").lower()
    for name in names:
        token = (name or "").strip().lower()
        if not token:
            continue
        if token in blob:
            return True
        for prefix in _PUBLISHER_DOI_PREFIXES.get(token, ()):
            if doi.startswith(prefix):
                return True
    if (paper.journal or "").lower().startswith("frontiers in"):
        return any(n.lower() == "frontiers" for n in names)
    return False


def passes_quality_gate(paper: Paper, gate: dict[str, Any] | None) -> bool:
    if not gate or paper.is_preprint:
        return True
    if is_excluded_publisher(paper, list(gate.get("exclude_publishers") or [])):
        return False
    meta = paper.journal_metrics or lookup(paper.journal, paper.issn)
    paper.journal_metrics = meta
    if not meta.get("in_catalog"):
        return (gate.get("unknown_journal") or "reject") != "reject"
    min_if = float(gate.get("min_impact_factor") or 0)
    impact = meta.get("impact_factor")
    if_ok = bool(min_if) and impact is not None and float(impact) >= min_if
    max_zone = int(gate.get("max_cas_zone") or 0)
    zone = cas_zone(str(meta.get("cas") or ""))
    cas_ok = bool(max_zone) and zone is not None and zone <= max_zone
    if min_if or max_zone:
        return if_ok or cas_ok
    return True


def journal_bonus(paper: Paper, preferred: list[str], extra: list[str] | None = None) -> float:
    name = _norm(paper.journal)
    for item in preferred:
        if _norm(item) and _norm(item) in name:
            return 2.0
    for item in extra or []:
        if _norm(item) and _norm(item) in name:
            return 1.2
    return 0.0
