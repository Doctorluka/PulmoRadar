from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Paper


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": []}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "items" not in data:
        return {"items": []}
    return data


def seen_keys(history: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for item in history.get("items", []):
        for field in ("paper_id", "pmid", "doi", "preprint_id"):
            value = (item.get(field) or "").strip().lower()
            if value:
                keys.add(value)
    return keys


def paper_keys(paper: Paper) -> set[str]:
    keys = set()
    for value in (paper.paper_id, paper.pmid, paper.doi, paper.preprint_id):
        if value:
            keys.add(value.strip().lower())
    return keys


def is_seen(paper: Paper, keys: set[str]) -> bool:
    return bool(paper_keys(paper) & keys)


def record(history: dict[str, Any], papers: list[Paper], topic: str, run_date: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    items = list(history.get("items", []))
    for paper in papers:
        items.append(
            {
                "paper_id": paper.paper_id,
                "pmid": paper.pmid,
                "doi": paper.doi,
                "preprint_id": paper.preprint_id,
                "title": paper.title,
                "topic": topic,
                "source": paper.source,
                "is_preprint": paper.is_preprint,
                "run_date": run_date,
                "recorded_at": now,
            }
        )
    history["items"] = items
    return history


def save_history(path: Path, history: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")
