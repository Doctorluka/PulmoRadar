from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import history, journals
from .config import project_root
from .emailer import send_email
from .filters import deterministic_filter
from .models import Paper
from .preprints import fetch_preprints
from .pubmed import fetch_pubmed
from .renderer import embed_logo_data_uri, logo_asset, render_email, render_markdown
from .slots import enrich_chosen, select_preprint_quota, select_published_slots, window_days
from .windows import expand_until, ladder_days, min_pool


def _tag_cross(papers: list[Paper], topic_key: str) -> None:
    if topic_key == "copd":
        hints, label = ("pulmonary fibrosis", "ipf", "fibroblast"), "fibrosis"
    elif topic_key == "fibrosis":
        hints, label = ("copd", "emphysema", "alveolar"), "COPD/emphysema"
    else:
        hints, label = ("copd", "emphysema", "pulmonary fibrosis", "ipf"), "COPD/fibrosis"
    for paper in papers:
        blob = f"{paper.title} {paper.abstract}".lower()
        if any(h in blob for h in hints):
            if label not in paper.also_topics:
                paper.also_topics.append(label)


def _quality_gate_for(cfg: dict[str, Any], topic_cfg: dict[str, Any] | None) -> dict[str, Any] | None:
    if not topic_cfg:
        return None
    return (cfg.get("selection") or {}).get("quality_gate")


def _prepare_pool(
    raw: list[Paper],
    cfg: dict[str, Any],
    seen: set[str],
    topic_key: str,
    topic_cfg: dict[str, Any] | None = None,
) -> list[Paper]:
    filtered = deterministic_filter(raw, cfg, seen)
    gate = _quality_gate_for(cfg, topic_cfg)
    if gate:
        journals.enrich(filtered)
        filtered = [p for p in filtered if journals.passes_quality_gate(p, gate)]
    _tag_cross(filtered, topic_key)
    for paper in filtered:
        paper.subtopic = topic_key
    return filtered


def _merge_unique(batches: list[list[Paper]]) -> list[Paper]:
    seen: set[str] = set()
    out: list[Paper] = []
    for batch in batches:
        for paper in batch:
            key = (paper.paper_id or paper.doi or paper.pmid).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(paper)
    return out


def _collect_track(
    topic_key: str,
    topic_cfg: dict[str, Any],
    cfg: dict[str, Any],
    seen: set[str],
    days_ladder: list[int],
    notes: list[str],
    injected: list[Paper] | None,
    kind: str,
) -> list[Paper]:
    label = f"{topic_cfg['name']} {kind}"
    use_gate = kind == "PubMed"
    gate_cfg = topic_cfg if use_gate else None
    if injected is not None:
        pool = _prepare_pool(injected, cfg, seen, topic_key, gate_cfg)
        notes.append(f"{label} 原始 {len(injected)} 篇，过滤后 {len(pool)} 篇。")
        return pool
    if kind == "PubMed":
        spans = window_days(cfg)
        year_raw = fetch_pubmed(topic_cfg, cfg, days=spans["flagship_year"])
        classic_raw = fetch_pubmed(topic_cfg, cfg, days=spans["classic"], sort="relevance")
        merged = _merge_unique([year_raw, classic_raw])
        pool = _prepare_pool(merged, cfg, seen, topic_key, gate_cfg)
        notes.append(
            f"{label} 年内 {len(year_raw)} 篇 + 经典窗 {len(classic_raw)} 篇，"
            f"合并 {len(merged)} 篇，过滤后 {len(pool)} 篇。"
        )
        return pool
    pool, _raw, used_days, step_notes = expand_until(
        fetch=lambda d, t=topic_cfg: fetch_preprints(t, cfg, days=d),
        prepare=lambda raw, k=topic_key, t=gate_cfg: _prepare_pool(raw, cfg, seen, k, t),
        windows=days_ladder,
        min_n=min_pool(cfg, "preprint"),
        label=label,
    )
    notes.extend(step_notes)
    notes.append(f"{label} 采用近 {used_days} 天窗口。")
    return pool


def run_topic(
    topic_key: str,
    cfg: dict[str, Any],
    *,
    send: bool = False,
    dry_run: bool = False,
    run_date: date | None = None,
    history_path: Path | None = None,
    archive_dir: Path | None = None,
    published: list[Paper] | None = None,
    preprints: list[Paper] | None = None,
    published_by_track: dict[str, list[Paper]] | None = None,
    preprints_by_track: dict[str, list[Paper]] | None = None,
) -> dict[str, Any]:
    groups = cfg.get("digest_groups", {})
    topics = cfg.get("topics", {})
    if topic_key in groups:
        group = groups[topic_key]
        track_keys = list(group.get("tracks") or [])
        group_name = group["name"]
    elif topic_key in topics:
        group = {"name": topics[topic_key]["name"], "preprint_n": cfg.get("selection", {}).get("preprint_n", 3)}
        track_keys = [topic_key]
        group_name = topics[topic_key]["name"]
    else:
        raise SystemExit(f"Unknown topic {topic_key!r}. Choose from: {', '.join(list(groups) + list(topics))}")

    run_date = run_date or date.today()
    root = project_root()
    history_path = history_path or root / "data" / "history.json"
    archive_dir = archive_dir or root / "archive"
    hist = history.load_history(history_path)
    seen = history.seen_keys(hist)
    notes: list[str] = []
    days_ladder = ladder_days(cfg)

    chosen_sections: list[tuple[str, list[Paper]]] = []
    preprint_pool: list[Paper] = []
    for key in track_keys:
        topic_cfg = topics[key]
        pub_injected = None
        if published_by_track and key in published_by_track:
            pub_injected = published_by_track[key]
        elif published is not None and len(track_keys) == 1:
            pub_injected = published
        pub_pool = _collect_track(key, topic_cfg, cfg, seen, days_ladder, notes, pub_injected, "PubMed")
        n_pub = int(topic_cfg.get("published_n", cfg.get("selection", {}).get("published_n", 3)))
        if n_pub != 3:
            notes.append(f"{topic_cfg['name']} published_n={n_pub} 已按硬配额 3 执行。")
        chosen = select_published_slots(
            pub_pool,
            topic_cfg,
            cfg,
            today=run_date,
            dry_run=dry_run,
            label=topic_cfg["name"],
        )
        enrich_chosen(chosen, cfg, dry_run)
        chosen_sections.append((topic_cfg["name"], chosen))

        pre_injected = None
        if preprints_by_track and key in preprints_by_track:
            pre_injected = preprints_by_track[key]
        elif preprints is not None and len(track_keys) == 1:
            pre_injected = preprints
        pre_pool = _collect_track(key, topic_cfg, cfg, seen, days_ladder, notes, pre_injected, "预印本")
        preprint_pool.extend(pre_pool)

    # Dedup preprint pool across Monday tracks, keep first occurrence.
    pre_seen: set[str] = set()
    unique_pre: list[Paper] = []
    for paper in preprint_pool:
        key = (paper.paper_id or paper.doi).lower()
        if key in pre_seen:
            continue
        pre_seen.add(key)
        unique_pre.append(paper)
    n_pre = int(group.get("preprint_n", cfg.get("selection", {}).get("preprint_n", 3)))
    pre_cfg = topics[track_keys[0]]
    if len(track_keys) > 1:
        pre_cfg = {
            **pre_cfg,
            "name": group_name + " 预印本",
            "focus": " ; ".join(topics[k].get("focus", "") for k in track_keys),
            "boost_keywords": [kw for k in track_keys for kw in topics[k].get("boost_keywords", [])],
        }
    chosen_pre = select_preprint_quota(
        unique_pre,
        pre_cfg,
        cfg,
        n=n_pre,
        dry_run=dry_run,
        label=group_name,
    )
    enrich_chosen(chosen_pre, cfg, dry_run)

    chosen_pub = [p for _, papers in chosen_sections for p in papers]
    subject, html = render_email(
        topic_name=group_name,
        run_date=run_date,
        published_sections=chosen_sections,
        preprints=chosen_pre,
        notes=notes,
    )
    md = render_markdown(
        topic_key=topic_key,
        topic_name=group_name,
        run_date=run_date,
        published_sections=chosen_sections,
        preprints=chosen_pre,
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    out_md = archive_dir / f"{run_date.isoformat()}-{topic_key}.md"
    out_md.write_text(md, encoding="utf-8")
    out_html = archive_dir / f"{run_date.isoformat()}-{topic_key}.html"
    out_html.write_text(embed_logo_data_uri(html, group_name), encoding="utf-8")

    if send and not dry_run:
        send_email(cfg, subject, html, logo_path=logo_asset(group_name))
        history.save_history(history_path, history.record(hist, chosen_pub + chosen_pre, topic_key, run_date.isoformat()))
    elif send and dry_run:
        notes.append("dry-run 不发送邮件、不写入 history。")

    return {
        "topic": topic_key,
        "subject": subject,
        "published": chosen_pub,
        "published_sections": chosen_sections,
        "preprints": chosen_pre,
        "archive_md": str(out_md),
        "archive_html": str(out_html),
        "notes": notes,
        "sent": bool(send and not dry_run),
    }
