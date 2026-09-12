from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from .models import Author, Paper

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_USE_API_KEY = True
_PREPRINT_JOURNALS = ("biorxiv", "medrxiv", "arxiv", "research square", "ssrn", "chemrxiv")


def _params(cfg: dict[str, Any], *, include_api_key: bool | None = None) -> dict[str, str]:
    pubmed = cfg.get("pubmed", {})
    params = {
        "tool": pubmed.get("tool", "pulmoradar"),
        "email": pubmed.get("contact_email", ""),
        "retmode": "xml",
    }
    if include_api_key is None:
        include_api_key = _USE_API_KEY
    key = os.environ.get(pubmed.get("api_key_env", "NCBI_API_KEY"), "").strip()
    if include_api_key and key:
        params["api_key"] = key
    return params


def _disable_api_key() -> None:
    global _USE_API_KEY
    if _USE_API_KEY:
        _USE_API_KEY = False
        print("NCBI_API_KEY 无效，已改为不带 key 访问 PubMed。", flush=True)


def _looks_like_bad_key(status: int, body: str) -> bool:
    text = body.lower()
    return status == 400 and ("api key" in text or "api-key" in text)


def _sleep(cfg: dict[str, Any]) -> None:
    key = os.environ.get(cfg.get("pubmed", {}).get("api_key_env", "NCBI_API_KEY"), "")
    time.sleep(0.12 if (key and _USE_API_KEY) else 0.35)


def scoped_query(query: str, preprint: bool | None) -> str:
    q = (query or "").strip()
    if preprint is True:
        return f"({q}) AND preprint[pt]"
    if preprint is False:
        return f"({q}) NOT preprint[pt]"
    return q


def is_preprint_record(paper: Paper) -> bool:
    types = " ".join(paper.publication_types).lower()
    if "preprint" in types:
        return True
    journal = (paper.journal or "").lower()
    return any(token in journal for token in _PREPRINT_JOURNALS)


def search_ids(
    query: str,
    cfg: dict[str, Any],
    client: httpx.Client | None = None,
    days: int | None = None,
) -> list[str]:
    pubmed = cfg.get("pubmed", {})
    days = int(days if days is not None else pubmed.get("days_back", 90))
    date_field = pubmed.get("date_field", "edat")
    mindate = (date.today() - timedelta(days=days)).strftime("%Y/%m/%d")
    maxdate = date.today().strftime("%Y/%m/%d")
    own = client is None
    client = client or httpx.Client(timeout=45.0)
    try:
        last_error = ""
        for include_key in (True, False):
            params = _params(cfg, include_api_key=include_key)
            params.update(
                {
                    "db": "pubmed",
                    "term": query,
                    "retmax": str(pubmed.get("retmax", 200)),
                    "datetype": date_field,
                    "mindate": mindate,
                    "maxdate": maxdate,
                    "usehistory": "n",
                }
            )
            r = client.get(f"{EUTILS}/esearch.fcgi", params=params)
            body = r.text[:400]
            if r.status_code >= 400:
                last_error = f"HTTP {r.status_code}"
                if "api key" in body.lower() or "api-key" in body.lower():
                    if include_key:
                        continue
                    raise RuntimeError("PubMed rejected NCBI_API_KEY; remove it from .env or create a new key.")
                raise RuntimeError(f"PubMed esearch {last_error}")
            root = ET.fromstring(r.text)
            err = root.findtext("ERROR") or root.findtext(".//error")
            if err:
                raise RuntimeError(f"PubMed esearch error: {err}")
            if include_key is False:
                _disable_api_key()
            return [el.text for el in root.findall(".//Id") if el.text]
        raise RuntimeError(f"PubMed esearch failed: {last_error}")
    finally:
        if own:
            client.close()


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _abstract(article: ET.Element) -> str:
    parts = []
    for abs_el in article.findall(".//Abstract/AbstractText"):
        label = abs_el.attrib.get("Label")
        body = "".join(abs_el.itertext()).strip()
        if not body:
            continue
        parts.append(f"{label}: {body}" if label else body)
    return "\n".join(parts)


def _author_name(author: ET.Element) -> str:
    last = _text(author.find("LastName"))
    fore = _text(author.find("ForeName")) or _text(author.find("Initials"))
    collective = _text(author.find("CollectiveName"))
    if collective:
        return collective
    return f"{fore} {last}".strip()


def _affiliations(author: ET.Element) -> list[str]:
    found = []
    for aff in author.findall(".//Affiliation"):
        text = _text(aff)
        if text and text not in found:
            found.append(text)
    return found


_EQUAL_CONTRIB_RE = re.compile(
    r"contributed equally|equal(?:ly)? contribut|co-?first|joint first|"
    r"these authors.{0,40}equally|共同第一|同等贡献",
    re.I,
)


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", flags=re.I)


def _explicit_corresponding(affiliations: list[str]) -> bool:
    blob = " ".join(affiliations).lower()
    return "corresponding" in blob or "correspondence" in blob


def _has_email(affiliations: list[str]) -> bool:
    return bool(_EMAIL_RE.search(" ".join(affiliations)))


def _mark_corresponding(records: list[Author]) -> None:
    if not records:
        return
    for rec in records:
        rec.is_corresponding = False
    explicit = [rec for rec in records if _explicit_corresponding(rec.affiliations)]
    emailed = [rec for rec in records if _has_email(rec.affiliations)]
    chosen = explicit
    if not chosen:
        email_cap = max(2, len(records) // 4)
        if emailed and len(emailed) <= email_cap:
            chosen = emailed
    if not chosen:
        chosen = [records[-1]]
    if len(chosen) > max(1, len(records) // 2):
        chosen = [records[-1]]
    for rec in chosen:
        rec.is_corresponding = True


def _equal_contrib(author: ET.Element, affiliations: list[str]) -> bool:
    if str(author.attrib.get("EqualContrib", "")).upper() == "Y":
        return True
    return bool(_EQUAL_CONTRIB_RE.search(" ".join(affiliations)))


def _mark_co_first(records: list[Author], equal_flags: list[bool]) -> None:
    if not records:
        return
    records[0].is_first = True
    for idx in range(1, len(records)):
        if equal_flags[idx]:
            records[idx].is_first = True
            continue
        break
    if equal_flags[0] and len(records) > 1 and not records[1].is_first:
        records[1].is_first = True


def parse_authors(article: ET.Element) -> tuple[list[str], list[Author], list[str], list[str]]:
    records: list[Author] = []
    names: list[str] = []
    people = [el for el in article.findall(".//AuthorList/Author") if el.attrib.get("ValidYN", "Y") != "N"]
    equal_flags: list[bool] = []
    for idx, author in enumerate(people):
        name = _author_name(author)
        if not name:
            continue
        affs = _affiliations(author)
        emails = _EMAIL_RE.findall(" ".join(affs))
        rec = Author(
            name=name,
            affiliations=affs,
            is_first=idx == 0,
            is_corresponding=False,
            email=emails[0] if emails else "",
        )
        names.append(name)
        records.append(rec)
        equal_flags.append(_equal_contrib(author, affs))
    _mark_co_first(records, equal_flags)
    _mark_corresponding(records)
    first_aff = []
    corr_aff = []
    for rec in records:
        if rec.is_first:
            for aff in rec.affiliations:
                if aff not in first_aff:
                    first_aff.append(aff)
        if rec.is_corresponding:
            for aff in rec.affiliations:
                if aff not in corr_aff:
                    corr_aff.append(aff)
    return names, records, first_aff, corr_aff


def parse_pubmed_xml(xml_text: str) -> list[Paper]:
    root = ET.fromstring(xml_text)
    papers: list[Paper] = []
    for rec in root.findall(".//PubmedArticle"):
        medline = rec.find("MedlineCitation")
        article = rec.find(".//Article")
        if medline is None or article is None:
            continue
        pmid = _text(medline.find("PMID"))
        title = _text(article.find("ArticleTitle"))
        journal = _text(article.find("Journal/Title")) or _text(article.find("Journal/ISOAbbreviation"))
        year = _text(article.find("Journal/JournalIssue/PubDate/Year"))
        month = _text(article.find("Journal/JournalIssue/PubDate/Month"))
        day = _text(article.find("Journal/JournalIssue/PubDate/Day"))
        medline_date = _text(article.find("Journal/JournalIssue/PubDate/MedlineDate"))
        date_str = " ".join(p for p in (year, month, day) if p) or medline_date
        doi = ""
        for aid in rec.findall(".//ArticleId"):
            if aid.attrib.get("IdType") == "doi" and aid.text:
                doi = aid.text.strip()
        pmcid = ""
        for aid in rec.findall(".//ArticleId"):
            if aid.attrib.get("IdType") == "pmc" and aid.text:
                pmcid = aid.text.strip()
        pub_types = [_text(t) for t in article.findall("PublicationTypeList/PublicationType") if _text(t)]
        issn = _text(article.find("Journal/ISSN"))
        names, records, first_aff, corr_aff = parse_authors(article)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else "")
        preprint = "preprint" in " ".join(pub_types).lower() or any(token in journal.lower() for token in _PREPRINT_JOURNALS)
        source = "pubmed"
        if preprint:
            low = journal.lower()
            if "medrxiv" in low:
                source = "medrxiv"
            elif "biorxiv" in low:
                source = "biorxiv"
            else:
                source = "preprint"
        papers.append(
            Paper(
                paper_id=f"pmid:{pmid}" if pmid else f"doi:{doi}",
                source=source,
                title=title,
                abstract=_abstract(article),
                authors=names,
                journal=journal,
                issn=issn,
                date=date_str,
                url=url,
                doi=doi,
                pmid=pmid,
                pmcid=pmcid,
                publication_types=pub_types,
                is_preprint=preprint,
                author_records=records,
                first_affiliations=first_aff,
                corresponding_affiliations=corr_aff,
            )
        )
    return papers


def fetch_details(ids: list[str], cfg: dict[str, Any], client: httpx.Client | None = None) -> list[Paper]:
    if not ids:
        return []
    own = client is None
    client = client or httpx.Client(timeout=60.0)
    papers: list[Paper] = []
    try:
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            params = _params(cfg)
            params.update({"db": "pubmed", "id": ",".join(chunk), "retmode": "xml"})
            r = client.get(f"{EUTILS}/efetch.fcgi", params=params)
            if _looks_like_bad_key(r.status_code, r.text):
                _disable_api_key()
                params = _params(cfg)
                params.update({"db": "pubmed", "id": ",".join(chunk), "retmode": "xml"})
                r = client.get(f"{EUTILS}/efetch.fcgi", params=params)
            if r.status_code >= 400:
                raise RuntimeError(f"PubMed efetch HTTP {r.status_code}")
            papers.extend(parse_pubmed_xml(r.text))
            if i + 50 < len(ids):
                _sleep(cfg)
    finally:
        if own:
            client.close()
    return papers


def fetch_pubmed(
    topic_cfg: dict[str, Any],
    cfg: dict[str, Any],
    days: int | None = None,
    client: httpx.Client | None = None,
    preprint: bool = False,
) -> list[Paper]:
    query = scoped_query(topic_cfg["pubmed_query"], preprint)
    ids = search_ids(query, cfg, client=client, days=days)
    papers = fetch_details(ids, cfg, client=client)
    if preprint:
        kept = []
        for paper in papers:
            if not paper.is_preprint:
                paper.is_preprint = True
            kept.append(paper)
        return kept
    return [p for p in papers if not p.is_preprint]


def pubmed_search_url(query: str, days: int = 90) -> str:
    mindate = (date.today() - timedelta(days=days)).strftime("%Y/%m/%d")
    q = f"{query} AND ({mindate}[edat] : 3000[edat])"
    return "https://pubmed.ncbi.nlm.nih.gov/?" + urlencode({"term": q})
