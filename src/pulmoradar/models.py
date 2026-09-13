from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Author:
    name: str
    affiliations: list[str] = field(default_factory=list)
    is_first: bool = False
    is_corresponding: bool = False
    email: str = ""


@dataclass
class Paper:
    paper_id: str
    source: str  # pubmed | biorxiv | medrxiv
    title: str
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    issn: str = ""
    date: str = ""
    url: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    preprint_id: str = ""
    publication_types: list[str] = field(default_factory=list)
    is_preprint: bool = False
    also_topics: list[str] = field(default_factory=list)
    subtopic: str = ""
    fulltext: str = ""
    evaluation_basis: str = "abstract_only"
    author_records: list[Author] = field(default_factory=list)
    first_affiliations: list[str] = field(default_factory=list)
    corresponding_affiliations: list[str] = field(default_factory=list)
    journal_metrics: dict[str, Any] = field(default_factory=dict)
    scores: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)
    slot: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Paper:
        payload = dict(data)
        records = []
        for item in payload.pop("author_records", []) or []:
            if isinstance(item, Author):
                records.append(item)
            elif isinstance(item, dict):
                records.append(Author(**{k: v for k, v in item.items() if k in Author.__dataclass_fields__}))
        payload["author_records"] = records
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in payload.items() if k in known})
