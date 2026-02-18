from __future__ import annotations

from datetime import datetime, timezone


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def article_age_days(published_at: str | None, now: datetime | None = None) -> int | None:
    published = _parse_iso_datetime(published_at)
    if not published:
        return None
    ref = now or datetime.now(timezone.utc)
    delta = ref - published
    if delta.total_seconds() < 0:
        return 0
    return delta.days


def article_relevance(published_at: str | None, now: datetime | None = None) -> str:
    days = article_age_days(published_at, now=now)
    if days is None:
        return "unbekannt"
    if days <= 2:
        return "hoch"
    if days <= 7:
        return "mittel"
    if days <= 30:
        return "niedrig"
    return "alt"
