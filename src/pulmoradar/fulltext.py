from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from .models import Paper

EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def _clean(text: str, limit: int = 8000) -> str:
    text = " ".join(text.split())
    return text[:limit]


def _parse_fulltext(root: ET.Element) -> str:
    texts = [t.strip() for t in root.itertext() if t.strip()]
    return _clean(" ".join(texts))


def fetch_oa_fulltext(paper: Paper, client: httpx.Client | None = None) -> str:
    query = paper.pmcid or paper.doi or paper.pmid
    if not query:
        return ""
    own = client is None
    client = client or httpx.Client(timeout=45.0)
    try:
        if paper.pmcid:
            xml_id = paper.pmcid.replace("PMC", "")
            r = client.get(f"{EUROPE_PMC}/PMC{xml_id}/fullTextXML")
            if r.status_code == 200 and "<" in r.text:
                return _parse_fulltext(ET.fromstring(r.text))
        params = {"query": f"DOI:{paper.doi}" if paper.doi else f"EXT_ID:{paper.pmid}", "format": "json", "pageSize": 1}
        r = client.get(f"{EUROPE_PMC}/search", params=params)
        r.raise_for_status()
        hits = (r.json().get("resultList") or {}).get("result") or []
        if not hits:
            return ""
        hit = hits[0]
        pmcid = hit.get("pmcid")
        if not pmcid:
            return ""
        paper.pmcid = pmcid
        r = client.get(f"{EUROPE_PMC}/{pmcid}/fullTextXML")
        if r.status_code != 200:
            return ""
        return _parse_fulltext(ET.fromstring(r.text))
    except Exception:
        return ""
    finally:
        if own:
            client.close()


def enrich(papers: list[Paper]) -> None:
    with httpx.Client(timeout=45.0) as client:
        for paper in papers:
            text = fetch_oa_fulltext(paper, client=client)
            if text:
                paper.fulltext = text
                paper.evaluation_basis = "full_text_oa"
