from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from .models import Paper
from .pubmed import fetch_pubmed


def _matches(query: str, title: str, abstract: str) -> bool:
    blob = f"{title} {abstract}".lower()
    raw = query.replace("(", " ").replace(")", " ")
    tokens = [part.replace('"', " ").strip().lower() for part in raw.split(" OR ")]
    return any(token and token in blob for token in tokens)


def _to_paper(row: dict[str, Any], server: str) -> Paper | None:
    """Used by tests and the bioRxiv details payload shape."""
    title = (row.get("title") or "").strip()
    abstract = (row.get("abstract") or "").strip()
    doi = (row.get("doi") or "").strip()
    if not title or not doi:
        return None
    version = str(row.get("version") or "1")
    date_str = (row.get("date") or "")[:10]
    url = f"https://www.{server}.org/content/{doi}v{version}"
    authors = [a.strip() for a in (row.get("authors") or "").split(";") if a.strip()]
    return Paper(
        paper_id=f"doi:{doi.lower()}",
        source=server,
        title=title,
        abstract=abstract,
        authors=authors,
        journal=f"{server} preprint",
        date=date_str,
        url=url,
        doi=doi,
        preprint_id=f"{server}:{doi}:v{version}",
        is_preprint=True,
    )


def fetch_preprints(
    topic_cfg: dict[str, Any],
    cfg: dict[str, Any],
    client=None,
    days: int | None = None,
) -> list[Paper]:
    """Preprints via NCBI PubMed (`preprint[pt]`), same E-utilities stack as published papers."""
    return fetch_pubmed(topic_cfg, cfg, days=days, client=client, preprint=True)


def europepmc_url(query: str, days: int = 90) -> str:
    # Kept for old tests / docs; NCBI is the live source.
    q = f"{query} AND preprint[pt]"
    return "https://pubmed.ncbi.nlm.nih.gov/?" + urlencode({"term": q})
