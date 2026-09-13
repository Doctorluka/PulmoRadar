from __future__ import annotations

import base64
import html
import re
from datetime import date, datetime
from pathlib import Path

from .config import project_root
from .journals import format_metrics, metric_chips
from .models import Author, Paper
from .slots import slot_label

LOGO_CID = "pulmoradar-logo"


def logo_asset(topic_name: str) -> Path:
    name = (topic_name or "").lower()
    filename = (
        "pah-icon-108.png"
        if "pah" in name or "肺动脉高压" in (topic_name or "")
        else "chronic-lung-icon-108.png"
    )
    return project_root() / "assets" / "logos" / filename


def embed_logo_data_uri(html_body: str, topic_name: str) -> str:
    path = logo_asset(topic_name)
    if not path.exists():
        return html_body
    b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return html_body.replace(f"cid:{LOGO_CID}", f"data:image/png;base64,{b64}")


def _esc(text) -> str:
    if text is None:
        return ""
    if isinstance(text, list):
        text = "；".join(str(x) for x in text if x)
    elif not isinstance(text, str):
        text = str(text)
    return html.escape(text)


def _authors(paper: Paper) -> str:
    names = paper.authors[:8]
    extra = " et al." if len(paper.authors) > 8 else ""
    return _esc(", ".join(names) + extra)


_WRAP = "text-align:left !important;"
_ABSTRACT_ALIGN = "text-align:justify !important;"
_DOI_WRAP = "overflow-wrap:break-word;word-break:break-all;"


def _list(items: list[str]) -> str:
    if not items:
        return "<p>（无）</p>"
    lis = "".join(f'<li style="margin:0 0 8px;{_WRAP}">{_esc(item)}</li>' for item in items)
    return f'<ul style="margin:0;padding-left:18px;{_WRAP}">{lis}</ul>'


def _links(paper: Paper) -> str:
    bits = []
    if paper.url:
        bits.append(f'<a href="{_esc(paper.url)}">原文</a>')
    if paper.pmid:
        bits.append(f'<a href="https://pubmed.ncbi.nlm.nih.gov/{_esc(paper.pmid)}/">PubMed</a>')
    if paper.doi:
        bits.append(f'<a href="https://doi.org/{_esc(paper.doi)}">DOI</a>')
    if paper.pmcid:
        pmc = paper.pmcid if paper.pmcid.upper().startswith("PMC") else f"PMC{paper.pmcid}"
        bits.append(f'<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/{_esc(pmc)}/">PMC</a>')
    return " · ".join(bits) if bits else "—"


def _also(paper: Paper) -> str:
    if not paper.also_topics:
        return ""
    return f'<p><em>交叉主题：{", ".join(_esc(t) for t in paper.also_topics)}</em></p>'


def _short_aff(text: str) -> str:
    text = (text or "").strip()
    if "@" in text:
        text = text.split("Electronic address:")[0].split("electronic address:")[0].strip(" ;,")
    return text


_ORG_RE = re.compile(
    r"([a-z][a-z .'-]{2,}(?:university|hospital|institute|college|academy|center|centre)|"
    r"[\u4e00-\u9fff]{2,}(?:大学|医院|研究所|学院|中心))",
    re.I,
)


def _org_tokens(text: str) -> set[str]:
    cleaned = _short_aff(text)
    found = {m.group(1).lower().strip() for m in _ORG_RE.finditer(cleaned)}
    if found:
        return found
    key = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", cleaned.lower())
    return {key.strip()} if key.strip() else set()


def _same_group(first_affs: list[str], corr_affs: list[str]) -> bool:
    first = set()
    corr = set()
    for item in first_affs:
        first |= _org_tokens(item)
    for item in corr_affs:
        corr |= _org_tokens(item)
    if not first or not corr:
        return False
    for a in first:
        for b in corr:
            if a == b or a in b or b in a:
                return True
    return False


def _institution_block(paper: Paper) -> str:
    a = paper.analysis or {}
    fields = a.get("author_fields") or {}
    first_names = [r.name for r in paper.author_records if r.is_first] or (paper.authors[:1] if paper.authors else [])
    corr_names = [r.name for r in paper.author_records if r.is_corresponding]
    first_aff = "；".join(_short_aff(x) for x in paper.first_affiliations[:2]) or "未提供"
    corr_aff = "；".join(_short_aff(x) for x in paper.corresponding_affiliations[:2]) or "未提供"
    first_field = fields.get("first") or "不详"
    corr_field = fields.get("corresponding") or "不详"
    first_label = "、".join(first_names) or "第一作者"
    corr_label = "、".join(corr_names) or "通讯作者"
    same = _same_group(paper.first_affiliations, paper.corresponding_affiliations) or (
        set(first_names) and set(first_names) == set(corr_names)
    )
    if same:
        names = "、".join(dict.fromkeys(first_names + corr_names)) or first_label
        field = first_field if first_field != "不详" else corr_field
        aff = first_aff if first_aff != "未提供" else corr_aff
        return f"""
  <p><strong>机构</strong></p>
  <p>第一作者/通讯作者（{_esc(names)}）同属：{_esc(aff)}<br>
  领域：{_esc(field)}</p>
"""
    return f"""
  <p><strong>机构</strong></p>
  <p>第一作者（{_esc(first_label)}）：{_esc(first_aff)}<br>
  领域：{_esc(first_field)}</p>
  <p>通讯作者（{_esc(corr_label)}）：{_esc(corr_aff)}<br>
  领域：{_esc(corr_field)}</p>
"""


def _first_institution(paper: Paper) -> str:
    return _short_aff(paper.first_affiliations[0]) if paper.first_affiliations else "未提供"


def _journal_meta(paper: Paper) -> str:
    name = _esc(paper.journal or "未提供")
    metrics = _esc(format_metrics(paper) or "期刊指标未收录")
    return (
        f'<span style="font-weight:600;">{name}</span>'
        f'<br><span style="color:#667575;font-size:13px;line-height:1.55;">{metrics}</span>'
    )


def _meta_line(label: str, value_html: str, theme: dict[str, str], *, last: bool = False) -> str:
    border = "none" if last else f"1px solid {theme['module_border']}"
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="table-layout:fixed;border-bottom:{border};">'
        f"<tr>"
        f'<td style="width:44px;padding:8px 8px 8px 0;vertical-align:top;'
        f'color:{theme["module_accent"]};font-size:12px;font-weight:700;line-height:1.5;">{_esc(label)}</td>'
        f'<td style="padding:8px 0;vertical-align:top;color:{theme["module_dark"]};'
        f'font-size:14px;line-height:1.55;{_WRAP}">{value_html}</td>'
        f"</tr></table>"
    )


_ABSTRACT_LABELS = (
    "BACKGROUND",
    "OBJECTIVE",
    "OBJECTIVES",
    "AIM",
    "AIMS",
    "PURPOSE",
    "RATIONALE",
    "INTRODUCTION",
    "METHODS",
    "METHOD",
    "MATERIALS AND METHODS",
    "PATIENTS AND METHODS",
    "STUDY DESIGN/METHODS",
    "STUDY DESIGN",
    "DESIGN",
    "RESULTS",
    "RESULT",
    "FINDINGS",
    "CONCLUSIONS",
    "CONCLUSION",
    "INTERPRETATION",
    "DISCUSSION",
    "SIGNIFICANCE",
    "LIMITATIONS",
    "CONTEXT",
    "SETTING",
    "PARTICIPANTS",
    "INTERVENTIONS",
    "MAIN OUTCOME MEASURES",
    "TRIAL REGISTRATION",
    "FUNDING",
    "UNASSIGNED",
    "目的",
    "方法",
    "结果",
    "结论",
    "背景",
    "材料与方法",
)
_ABSTRACT_LABEL_RE = re.compile(
    rf"(?m)^((?:{'|'.join(re.escape(item) for item in _ABSTRACT_LABELS)})\s*[:：])",
    re.I,
)


def _abstract_html(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""
    parts = [part.strip() for part in re.split(r"\n+", raw) if part.strip()]
    blocks: list[str] = []
    for i, part in enumerate(parts):
        body = _ABSTRACT_LABEL_RE.sub(r"<strong>\1</strong>", _esc(part))
        bottom = "0" if i == len(parts) - 1 else "8px"
        blocks.append(f'<p style="margin:0 0 {bottom};{_ABSTRACT_ALIGN}">{body}</p>')
    return "".join(blocks)


def _author_entries(paper: Paper) -> list[Author]:
    if paper.author_records:
        return [rec for rec in paper.author_records if rec.name]
    return [Author(name=name) for name in paper.authors if name]


def _featured_authors(entries: list[Author]) -> list[Author]:
    featured = [rec for rec in entries if rec.is_first or rec.is_corresponding]
    if featured:
        return featured
    if not entries:
        return []
    if len(entries) == 1:
        return entries
    return [entries[0], entries[-1]]


def _authors_html(paper: Paper, theme: dict[str, str] | None = None) -> str:
    _ = theme
    entries = _author_entries(paper)
    if not entries:
        return "未提供"
    n_first = sum(1 for rec in entries if rec.is_first)
    n_corr = sum(1 for rec in entries if rec.is_corresponding)
    mark_first = n_first >= 2
    mark_corr = n_corr >= 2
    names = []
    for rec in _featured_authors(entries):
        label = _esc(rec.name)
        if mark_first and rec.is_first:
            label += "*"
        if mark_corr and rec.is_corresponding:
            label += "<sup>#</sup>"
        names.append(label)
    return " · ".join(names)


def _featured_author_line(paper: Paper) -> str:
    entries = _author_entries(paper)
    if not entries:
        return "未提供"
    n_first = sum(1 for rec in entries if rec.is_first)
    n_corr = sum(1 for rec in entries if rec.is_corresponding)
    parts = []
    for rec in _featured_authors(entries):
        name = rec.name
        if n_first >= 2 and rec.is_first:
            name += "*"
        if n_corr >= 2 and rec.is_corresponding:
            name += "#"
        parts.append(name)
    return ", ".join(parts)


def _doi_html(paper: Paper, theme: dict[str, str]) -> str:
    if not paper.doi:
        return "未提供"
    href = f"https://doi.org/{_esc(paper.doi)}"
    return (
        f'<a href="{href}" style="color:{theme["module_accent"]};text-decoration:underline;{_DOI_WRAP}">'
        f"{_esc(paper.doi)}</a>"
    )


def _paper_meta_html(paper: Paper, theme: dict[str, str]) -> str:
    journal = _esc(paper.journal or "未提供")
    chips = " · ".join(_esc(chip) for chip in metric_chips(paper))
    if chips:
        journal = f'{journal}<br><span style="color:#667575;font-size:13px;">{chips}</span>'
    date = _esc(paper.date or "未提供")
    article = f"{date}<br>{_doi_html(paper, theme)}" if paper.doi else date
    return (
        f'<div style="margin:0 0 16px;padding:4px 10px;background:rgba(255,255,255,.58);'
        f'border-left:3px solid {theme["module_accent"]};">'
        f'{_meta_line("杂志", journal, theme)}'
        f'{_meta_line("文章", article, theme)}'
        f'{_meta_line("作者", _authors_html(paper, theme), theme)}'
        f'{_meta_line("机构", _esc(_first_institution(paper)), theme, last=True)}'
        f"</div>"
    )


def _days_since_publication(paper: Paper, today: date) -> int | None:
    if not paper.date:
        return None
    for fmt in ("%Y-%m-%d", "%Y %b %d", "%Y %b", "%Y"):
        try:
            published = datetime.strptime(paper.date.strip(), fmt).date()
            return max(0, (today - published).days)
        except ValueError:
            continue
    return None


def _abstract_highlight(paper: Paper) -> str:
    """Derive a traceable one-sentence highlight from analysis or abstract text."""
    analysis = paper.analysis or {}
    news = analysis.get("what_is_new") or []
    if isinstance(news, list) and news and str(news[0]).strip():
        return str(news[0]).strip().rstrip("。")
    for value in (analysis.get("one_liner"), analysis.get("why_selected")):
        if isinstance(value, str) and value.strip():
            return value.strip().rstrip("。")
    findings = analysis.get("findings") or []
    if isinstance(findings, list) and findings and str(findings[0]).strip():
        return str(findings[0]).strip().rstrip("。")
    abstract = " ".join((paper.abstract or "").split())
    if not abstract:
        return f"《{paper.title}》摘要信息不足，暂无法生成可靠的一句话概括"
    # Prefer an explicit conclusion/results block. Split only at sentence
    # punctuation followed by a new sentence, so abbreviations such as "i.p."
    # do not produce the unusable fragment "Res i.p".
    section = re.search(
        r"(?:CONCLUSION|CONCLUSIONS|RESULTS|目的|结论|结果)\s*:\s*(.*?)(?=\s+(?:BACKGROUND|PURPOSE|OBJECTIVE|METHODS|RESULTS|CONCLUSION|CONCLUSIONS|目的|方法|结果|结论)\s*:|$)",
        abstract,
        re.I,
    )
    source = section.group(1).strip() if section else abstract
    sentence = re.split(r"(?<=[.!?。])\s+(?=[A-Z\u4e00-\u9fff])", source, maxsplit=1)[0].strip()
    return sentence.rstrip("。") or f"《{paper.title}》摘要信息不足，暂无法生成可靠的一句话概括"


def _overview_section(
    title: str,
    items: list[str],
    theme: dict[str, str],
    *,
    escaped: bool = False,
    first: bool = False,
) -> str:
    top = "0" if first else "16px"
    heading = (
        f'<p style="margin:{top} 0 8px;color:{theme["accent"]};font-size:13px;'
        f'font-weight:700;letter-spacing:.02em;">{_esc(title)}</p>'
    )
    if not items:
        return heading + f'<p style="margin:0;color:#111111;font-size:14px;line-height:1.7;{_WRAP}">（无）</p>'
    lis = "".join(
        f'<li style="margin:0 0 10px;{_WRAP}">{item if escaped else _esc(item)}</li>'
        for item in items
    )
    return (
        heading
        + f'<ul style="margin:0;padding-left:18px;color:#111111;font-size:14px;'
        f'line-height:1.7;{_WRAP}">{lis}</ul>'
    )


def _digest_overview(
    sections: list[tuple[str, list[Paper]]],
    preprints: list[Paper],
    run_date: date,
    theme: dict[str, str],
) -> str:
    published_papers = [paper for _, items in sections for paper in items]
    journals: list[str] = []
    for paper in published_papers:
        label = _journal_meta(paper)
        if label not in journals:
            journals.append(label)
    days = [_days_since_publication(paper, run_date) for paper in published_papers]
    days = [n for n in days if n is not None]
    age_text = f"已发表论文距发表平均 {sum(days) / len(days):.1f} 天。" if days else "已发表论文的发表时间不可完整计算。"
    highlights = [_abstract_highlight(paper) for paper in published_papers]
    journal_items = journals or [_esc("暂无可用期刊信息")]
    highlight_items = highlights or ["本期暂无可用的研究亮点摘要"]
    return (
        _overview_section("本期期刊", journal_items, theme, escaped=True, first=True)
        + _overview_section("研究亮点", highlight_items, theme)
        + _overview_section("时间概览", [age_text], theme)
    )


def _theme(topic_name: str) -> dict[str, str]:
    name = (topic_name or "").lower()
    if "pah" in name or "肺动脉高压" in topic_name:
        # A Thursday digest may contain both PAH and influenza sections.
        # Keep the digest-level palette blue; section palettes are selected in _module_theme.
        return {
            "accent": "#2367a6",
            "accent_dark": "#173f68",
            "accent_soft": "#e4eff8",
            "source_bg": "#f2f7fc",
            "source_border": "#bfd6ea",
            "ai_bg": "#f3f0fa",
            "ai_border": "#d6caeb",
            "ai_text": "#493b6d",
            "warm": "#7a5b2e",
            "logo_label": "PAH · 肺动脉高压",
            "logo_alt": "PulmoRadar PAH",
        }
    return {
        "accent": "#087c78",
        "accent_dark": "#173b3a",
        "accent_soft": "#dce9e7",
        "source_bg": "#f2f8f7",
        "source_border": "#c7dfdc",
        "ai_bg": "#fff8f1",
        "ai_border": "#efd8c7",
        "ai_text": "#5a4034",
        "warm": "#a9472c",
        "logo_label": "CHRONIC LUNG · 慢性肺病",
        "logo_alt": "PulmoRadar Chronic Lung",
    }


def _module_theme(theme: dict[str, str], section_title: str, is_preprint: bool = False) -> dict[str, str]:
    if is_preprint or "预印本" in section_title:
        return {**theme, "module_accent": "#9a4f32", "module_dark": "#6f3424", "module_bg": "#fbf1eb", "module_border": "#e7c9bb", "module_label": "预印本精选"}
    if "流感" in section_title or "influenza" in section_title.lower() or "h1n1" in section_title.lower():
        return {**theme, "module_accent": "#8b4b72", "module_dark": "#5e304d", "module_bg": "#fbf3f7", "module_border": "#dfc3d2", "module_label": "INFLUENZA · 流感肺损伤"}
    if "纤维化" in section_title:
        return {**theme, "module_accent": "#76558a", "module_dark": "#503765", "module_bg": "#f5f0f8", "module_border": "#d8c9e0", "module_label": "肺纤维化"}
    if "COPD" in section_title or "肺气肿" in section_title:
        return {**theme, "module_accent": "#176b68", "module_dark": "#104b49", "module_bg": "#eef7f5", "module_border": "#c5dfdc", "module_label": "COPD · 肺气肿"}
    return {**theme, "module_accent": theme["accent"], "module_dark": theme["accent_dark"], "module_bg": theme["source_bg"], "module_border": theme["source_border"], "module_label": section_title or theme["logo_label"]}


def _as_items(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _editor_take_html(paper: Paper, theme: dict[str, str]) -> str:
    analysis = paper.analysis or {}
    what_is_new = _as_items(analysis.get("what_is_new"))
    one = str(analysis.get("one_liner") or "").strip()
    if not what_is_new and one:
        what_is_new = [one]
    body = (
        _list(what_is_new)
        if what_is_new
        else f'<p style="margin:0;color:#111111;font-size:14px;line-height:1.7;{_WRAP}">（本次未生成）</p>'
    )
    return (
        f'<div style="margin:0 0 16px;padding:12px 14px;background:{theme["module_bg"]};border:1px solid {theme["module_border"]};border-radius:8px;">'
        f'<p style="margin:0 0 8px;color:{theme["warm"]};font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;">AI 解读 · WHAT IS NEW?</p>'
        f'<div style="color:#111111;font-size:14px;line-height:1.7;{_WRAP}">{body}</div></div>'
    )


def render_paper_html(paper: Paper, index: int, theme: dict[str, str] | None = None, section_title: str = "") -> str:
    theme = _module_theme(theme or _theme(""), section_title, paper.is_preprint)
    a = paper.analysis or {}
    basis = paper.evaluation_basis or a.get("evaluation_basis") or "abstract_only"
    basis_label = "OA 全文" if basis == "full_text_oa" else "仅摘要"
    design = a.get("design") or []
    findings = a.get("findings") or []
    limits = a.get("limitations") or []
    implications = _as_items(a.get("implications")) or _as_items(a.get("takeaways"))
    source_label = slot_label(paper.slot) if paper.slot else ("预印本" if paper.is_preprint else "已发表")
    section = (
        f'<p style="margin:18px 0 8px;color:{theme["module_accent"]};font-size:13px;'
        f'font-weight:700;letter-spacing:.02em;border-bottom:1px solid {theme["module_border"]};'
        f'padding-bottom:7px;">'
    )
    return f"""
<article class="paper-card" style="margin:0 0 20px;padding:0;background:{theme['module_bg']};border:1px solid {theme['module_border']};border-radius:12px;overflow:hidden;">
  <div style="padding:14px 16px 16px;background:{theme['module_dark']};color:#ffffff;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed;"><tr>
      <td style="vertical-align:top;{_WRAP}"><span style="display:inline-block;padding:4px 9px;background:rgba(255,255,255,.16);color:#ffffff;border:1px solid rgba(255,255,255,.28);border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.04em;">{index:02d} · {_esc(source_label.upper())}</span></td>
      <td align="right" style="vertical-align:top;color:#ffffff;font-size:12px;opacity:.82;width:72px;">{_esc(basis_label)}</td>
    </tr></table>
    <h3 style="margin:12px 0 0;color:#ffffff;font-size:18px;line-height:1.4;font-weight:700;{_WRAP}">{_esc(paper.title)}</h3>
  </div>
  <div style="padding:16px;">
    {_paper_meta_html(paper, theme)}
    {_editor_take_html(paper, theme)}
    {section}原文摘要 · ABSTRACT</p>
    <div style="margin:0 0 16px;padding:12px 14px;background:{theme['module_bg']};border:1px solid {theme['module_border']};border-radius:8px;color:#111111;font-size:14px;line-height:1.7;">{_abstract_html(paper.abstract)}</div>
    {section}AI 解读 · 研究设计</p>
    <div style="color:#111111;font-size:14px;line-height:1.7;{_WRAP}">{_list(design if isinstance(design, list) else [str(design)])}</div>
    {section}AI 解读 · 主要发现</p>
    <div style="color:#111111;font-size:14px;line-height:1.7;{_WRAP}">{_list(findings if isinstance(findings, list) else [str(findings)])}</div>
    {section}AI 解读 · 为什么入选</p>
    <p style="margin:0;color:#111111;font-size:14px;line-height:1.7;{_WRAP}">{_esc(a.get("why_selected") or paper.scores.get("rank_why") or "")}</p>
    {section}AI 解读 · 局限</p>
    <div style="color:#111111;font-size:14px;line-height:1.7;{_WRAP}">{_list(limits if isinstance(limits, list) else [str(limits)])}</div>
    {section}AI 解读 · 可借鉴之处</p>
    <div style="color:#111111;font-size:14px;line-height:1.7;{_WRAP}">{_list(implications)}</div>
  </div>
</article>
"""


def render_email(
    *,
    topic_name: str,
    run_date: date,
    published: list[Paper] | None = None,
    published_sections: list[tuple[str, list[Paper]]] | None = None,
    preprints: list[Paper],
    notes: list[str] | None = None,
) -> tuple[str, str]:
    if published_sections is None:
        published_sections = [("已发表", published or [])]
    theme = _theme(topic_name)
    n_pub = sum(len(items) for _, items in published_sections)
    subject = f"PulmoRadar · {topic_name} · {run_date.isoformat()} · 发表{n_pub}+预印本{len(preprints)}"
    overview_html = _digest_overview(published_sections, preprints, run_date, theme)
    # Screening-window notes are operational logs for the terminal/CI output,
    # not reader-facing content for the email digest.
    note_html = ""
    pub_html = ""
    for title, items in published_sections:
        module = _module_theme(theme, title)
        body = "".join(render_paper_html(p, i, theme, title) for i, p in enumerate(items, 1)) or "<p>本周无新的已发表入选论文。</p>"
        pub_html += (
            f'<h2 style="margin:22px 0 12px;padding:12px 16px;background:{module["module_dark"]};'
            f'color:#ffffff;font-size:18px;line-height:1.35;{_WRAP}">{_esc(title)}</h2>{body}'
        )
    pre_module = _module_theme(theme, "预印本", True)
    pre_html = "".join(render_paper_html(p, i, theme, "预印本") for i, p in enumerate(preprints, 1)) or "<p>本周无新的预印本入选。</p>"
    body = f"""<!DOCTYPE html>
<html><head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="format-detection" content="telephone=no">
  <style>
    @media only screen and (max-width: 620px) {{
      .email-h1 {{ font-size: 24px !important; }}
      .email-pad {{ padding-left: 16px !important; padding-right: 16px !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background:#f8f7f0;-webkit-text-size-adjust:100%;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Helvetica,Arial,sans-serif;color:#173b3a;line-height:1.6;{_WRAP}">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">PulmoRadar · {_esc(topic_name)} · {_esc(run_date.isoformat())} · 每周发现值得阅读的肺部基础研究</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f8f7f0;"><tr><td align="center" style="padding:0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:680px;width:100%;table-layout:fixed;background:#ffffff;border:1px solid #e1e9e6;"><tr><td style="padding:0;">
      <div style="height:9px;background:{theme['accent']};font-size:0;line-height:0;">&nbsp;</div>
      <div class="email-pad" style="padding:22px 16px 18px;background:#f8f7f0;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed;"><tr>
          <td style="width:54px;height:54px;vertical-align:top;"><img src="cid:{LOGO_CID}" width="54" height="54" alt="{_esc(theme['logo_alt'])}" style="display:block;width:54px;height:54px;border:0;"/></td>
          <td style="padding-left:12px;vertical-align:top;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
              <td style="font-size:13px;font-weight:700;letter-spacing:.12em;color:{theme['accent']};">PULMORADAR</td>
              <td align="right" style="color:#667575;font-size:12px;line-height:1.4;white-space:nowrap;">第 01 期<br>{_esc(run_date.isoformat())}</td>
            </tr></table>
            <h1 class="email-h1" style="margin:8px 0 4px;color:{theme['accent_dark']};font-size:26px;line-height:1.25;{_WRAP}">肺部基础研究周报</h1>
            <div style="color:#667575;font-size:13px;line-height:1.45;{_WRAP}">Weekly Digest of Pulmonary Basic Research</div>
          </td>
        </tr></table>
        <div style="height:2px;background:{theme['accent']};margin-top:18px;font-size:0;line-height:0;">&nbsp;</div>
        <div style="margin-top:12px;color:#315452;font-size:14px;line-height:1.55;{_WRAP}"><span style="display:inline-block;padding:3px 8px;background:{theme['accent_soft']};color:{theme['accent']};border-radius:999px;font-size:11px;font-weight:700;">{theme['logo_label']}</span><br><span style="display:inline-block;margin-top:8px;">{_esc(topic_name)} · 本期精选研究</span></div>
      </div>
      <div class="email-pad" style="padding:18px 16px 8px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="table-layout:fixed;"><tr>
          <td width="33%" style="padding:0 4px 12px 0;"><div style="padding:12px 6px;background:{theme['accent_soft']};border-radius:8px;text-align:center;"><div style="color:{theme['accent']};font-size:22px;font-weight:700;line-height:1;">{n_pub + len(preprints)}</div><div style="margin-top:6px;color:#315452;font-size:12px;">本期精选</div></div></td>
          <td width="33%" style="padding:0 4px 12px;"><div style="padding:12px 6px;background:{theme['source_bg']};border:1px solid {theme['source_border']};border-radius:8px;text-align:center;"><div style="color:{theme['accent']};font-size:22px;font-weight:700;line-height:1;">{n_pub}</div><div style="margin-top:6px;color:#315452;font-size:12px;">已发表</div></div></td>
          <td width="33%" style="padding:0 0 12px 4px;"><div style="padding:12px 6px;background:#fffaf5;border:1px solid #f0dfd2;border-radius:8px;text-align:center;"><div style="color:#a9472c;font-size:22px;font-weight:700;line-height:1;">{len(preprints)}</div><div style="margin-top:6px;color:#493b36;font-size:12px;">预印本</div></div></td>
        </tr></table>
        <div style="margin:4px 0 20px;padding:14px;background:{theme['source_bg']};border-left:4px solid {theme['accent']};color:#315452;font-size:14px;line-height:1.7;{_WRAP}">{overview_html}</div>
        {note_html}
      </div>
      <div class="email-pad" style="padding:0 16px 20px;">
        {pub_html}
        <div style="margin:22px 0 12px;padding:12px 16px;background:{pre_module['module_dark']};color:#ffffff;"><span style="font-size:12px;color:#ffffff;opacity:.78;">PREPRINTS</span><h2 style="margin:5px 0 0;color:#ffffff;font-size:18px;">预印本精选</h2></div>
        {pre_html}
      </div>
      <div class="email-pad" style="padding:18px 16px 24px;background:#f8f7f0;border-top:1px solid {theme['source_border']};color:#667575;font-size:12px;line-height:1.7;{_WRAP}">PulmoRadar · 每周发现值得阅读的肺部研究<br>本邮件用于科研信息整理，不构成医疗建议。解读与作者领域可能有误，请以原文为准。IF / JCR / 中科院 / 新锐分区来自仓库内固定表，运行时不联网查询。已发表门槛：IF&gt;5 <em>或</em> 中科院 2025 / 新锐 2026 大类 2 区及以上；并排除 Frontiers / MDPI 等。每栏硬配额 3 篇（近一月 / 年内旗舰 / 经典）。预印本不套用 IF/分区门槛，但必须 3 篇。</div>
    </td></tr></table>
  </td></tr></table>
</body></html>"""
    return subject, body


def render_markdown(
    *,
    topic_key: str,
    topic_name: str,
    run_date: date,
    published: list[Paper] | None = None,
    published_sections: list[tuple[str, list[Paper]]] | None = None,
    preprints: list[Paper],
) -> str:
    if published_sections is None:
        published_sections = [("已发表", published or [])]

    def block(paper: Paper, i: int) -> str:
        a = paper.analysis or {}
        authors = _featured_author_line(paper)
        findings = a.get("findings") or []
        design = a.get("design") or []
        limits = a.get("limitations") or []
        what_is_new = _as_items(a.get("what_is_new"))
        implications = _as_items(a.get("implications")) or _as_items(a.get("takeaways"))
        metrics = format_metrics(paper)
        fields = a.get("author_fields") or {}
        return "\n".join(
            [
                f"### {i}. {paper.title}",
                "",
                f"{paper.journal} | {paper.date} | {authors}",
                f"{metrics}" if metrics else "",
                "",
                f"- 来源：{paper.source}",
                f"- 槽位：{slot_label(paper.slot) if paper.slot else ('预印本' if paper.is_preprint else '已发表')}",
                f"- 依据：{paper.evaluation_basis}",
                *(() if False else (
                    [
                        f"- 第一作者/通讯作者单位：{'; '.join(paper.first_affiliations) or '未提供'}",
                        f"- 领域：{fields.get('first') or fields.get('corresponding', '不详')}",
                    ]
                    if _same_group(paper.first_affiliations, paper.corresponding_affiliations)
                    else [
                        f"- 第一作者单位：{'; '.join(paper.first_affiliations) or '未提供'}",
                        f"- 通讯作者单位：{'; '.join(paper.corresponding_affiliations) or '未提供'}",
                        f"- 第一作者领域：{fields.get('first', '不详')}",
                        f"- 通讯作者领域：{fields.get('corresponding', '不详')}",
                    ]
                )),
                f"- 链接：{paper.url}",
                f"- DOI：{paper.doi or '—'}",
                "",
                "**Abstract**",
                "",
                paper.abstract,
                "",
                "**What Is New?**",
                *[f"- {x}" for x in what_is_new],
                "",
                "**研究设计**",
                *[f"- {x}" for x in design],
                "",
                "**主要发现**",
                *[f"- {x}" for x in findings],
                "",
                f"**为什么入选** {a.get('why_selected', '')}",
                "",
                "**局限**",
                *[f"- {x}" for x in limits],
                "",
                "**可借鉴之处**",
                *[f"- {x}" for x in implications],
                "",
            ]
        )

    lines = [
        f"# PulmoRadar {topic_name} {run_date.isoformat()}",
        "",
        f"topic: `{topic_key}`",
        "",
    ]
    for title, items in published_sections:
        lines += [f"## {title}", ""]
        if items:
            for i, paper in enumerate(items, 1):
                lines.append(block(paper, i))
        else:
            lines.append("（无）")
        lines.append("")
    lines += ["## 预印本", ""]
    if preprints:
        for i, paper in enumerate(preprints, 1):
            lines.append(block(paper, i))
    else:
        lines.append("（无）")
    return "\n".join(lines)
