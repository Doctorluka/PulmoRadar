from __future__ import annotations

from typing import Any, Callable, Iterable

from .models import Paper

DEFAULT_DAYS = [10, 30, 60, 90]


def ladder_days(cfg: dict[str, Any]) -> list[int]:
    windows = cfg.get("windows", {})
    days = windows.get("days") or DEFAULT_DAYS
    out = []
    for item in days:
        n = int(item)
        if n > 0 and n not in out:
            out.append(n)
    return out or list(DEFAULT_DAYS)


def min_pool(cfg: dict[str, Any], kind: str) -> int:
    windows = cfg.get("windows", {})
    sel = cfg.get("selection", {})
    if kind == "preprint":
        default = max(int(sel.get("preprint_n", 3)) * 2, 5)
        return int(windows.get("min_preprint_pool", default))
    default = int(windows.get("min_published_pool", 6))
    return default


def expand_until(
    *,
    fetch: Callable[[int], list[Paper]],
    prepare: Callable[[list[Paper]], list[Paper]],
    windows: Iterable[int],
    min_n: int,
    label: str,
) -> tuple[list[Paper], list[Paper], int, list[str]]:
    """Widen the date window until the filtered pool is large enough.

    Each step re-queries `days` (10 → 30 → 60 → 90) and merges by paper_id so
    earlier hits are kept. Stops as soon as filtered count >= min_n.
    """
    notes: list[str] = []
    merged: list[Paper] = []
    seen: set[str] = set()
    used_days = 0
    filtered: list[Paper] = []
    for days in windows:
        used_days = days
        for paper in fetch(days):
            key = (paper.paper_id or paper.doi or paper.pmid).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(paper)
        filtered = prepare(merged)
        notes.append(f"{label} 近{days}天：原始 {len(merged)} 篇，过滤后 {len(filtered)} 篇。")
        if len(filtered) >= min_n:
            break
    if len(filtered) < min_n:
        notes.append(f"{label} 扩到 {used_days} 天仍不足 {min_n} 篇，按现有候选继续。")
    return filtered, merged, used_days, notes
