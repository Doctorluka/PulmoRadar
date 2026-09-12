from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .models import Paper


class LLMError(RuntimeError):
    pass


def load_prompt(path, **kwargs: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text.format(**kwargs)


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    decoder = json.JSONDecoder()
    errors: list[Exception] = []
    for candidate in (text,):
        try:
            return decoder.decode(candidate)
        except json.JSONDecodeError as exc:
            errors.append(exc)
    for match in re.finditer(r"[\{\[]", text):
        try:
            obj, _ = decoder.raw_decode(text[match.start():])
            return obj
        except json.JSONDecodeError as exc:
            errors.append(exc)
            continue
    raise errors[-1] if errors else json.JSONDecodeError("No JSON object", text, 0)


def chat(cfg: dict[str, Any], messages: list[dict[str, str]], timeout: float = 90.0) -> str:
    llm = cfg.get("llm", {})
    api_key = os.environ.get(llm.get("api_key_env", "DEEPSEEK_API_KEY"), "")
    if not api_key:
        raise LLMError("DEEPSEEK_API_KEY is not set")
    base = llm.get("base_url", "https://api.deepseek.com").rstrip("/")
    model = llm.get("model", "deepseek-flash")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:400]}") from exc
        data = r.json()
    try:
        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        if not str(content).strip():
            content = message.get("reasoning_content") or ""
        return str(content)
    except (KeyError, IndexError) as exc:
        raise LLMError("Unexpected LLM response") from exc


def chat_json(cfg: dict[str, Any], system: str, user: str, retries: int = 1) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = chat(
                cfg,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user if attempt == 0 else user + "\n\nReturn a single valid JSON object only."},
                ],
            )
            data = _extract_json(raw)
            if not isinstance(data, dict):
                raise LLMError("LLM JSON was not an object")
            return data
        except (json.JSONDecodeError, LLMError) as exc:
            last_error = exc
            continue
    raise LLMError(f"Could not parse LLM JSON: {last_error}") from last_error


def paper_block(papers: list[Paper]) -> str:
    chunks = []
    for paper in papers:
        authors = ", ".join(paper.authors[:8])
        if len(paper.authors) > 8:
            authors += " et al."
        abstract = paper.abstract[:2500]
        chunks.append(
            "\n".join(
                [
                    f"id: {paper.paper_id}",
                    f"source: {paper.source}",
                    f"title: {paper.title}",
                    f"journal: {paper.journal}",
                    f"date: {paper.date}",
                    f"authors: {authors}",
                    f"abstract: {abstract}",
                ]
            )
        )
    return "\n\n---\n\n".join(chunks)
