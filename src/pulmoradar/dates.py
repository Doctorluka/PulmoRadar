from __future__ import annotations

from datetime import date

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_paper_date(date_str: str) -> date | None:
    raw = (date_str or "").strip()
    if not raw:
        return None
    iso = raw[:10]
    try:
        return date.fromisoformat(iso)
    except ValueError:
        pass
    parts = raw.replace(",", " ").split()
    if not parts:
        return None
    if parts[0].isdigit() and len(parts[0]) == 4:
        year = int(parts[0])
        month = 1
        day = 1
        if len(parts) >= 2:
            month = _MONTHS.get(parts[1][:3].lower(), 1)
        if len(parts) >= 3 and parts[2].isdigit():
            day = int(parts[2])
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def age_days(date_str: str, today: date | None = None) -> int | None:
    parsed = parse_paper_date(date_str)
    if parsed is None:
        return None
    today = today or date.today()
    return (today - parsed).days
