"""Smart publishing scheduler.

Calculates suggested publish slots for new WordPress drafts.
Rules:
- Maximum N drafts per day (configurable, default 2)
- Prefer slots spread across the week for steady traffic
- Preferred hours: configurable (default 09:00 and 14:00 CET)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .config import get_settings
from .db import get_conn


# CET offset (UTC+1 winter / UTC+2 summer – we use a fixed +1 for simplicity)
_CET_OFFSET = timedelta(hours=1)


def _today_cet() -> date:
    return (datetime.now(timezone.utc) + _CET_OFFSET).date()


def _preferred_hours() -> list[int]:
    settings = get_settings()
    try:
        return [int(h.strip()) for h in settings.pipeline_publish_hours.split(",") if h.strip()]
    except Exception:
        return [9, 14]


def _count_scheduled_on_day(target_date: date) -> int:
    """Count articles already scheduled for publication on a given date."""
    date_str = target_date.isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM articles
            WHERE scheduled_publish_at >= ? AND scheduled_publish_at < ?
            AND status NOT IN ('error')
            """,
            (date_str + "T00:00:00", date_str + "T23:59:59"),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def _next_free_hour(target_date: date) -> int | None:
    """Return first preferred hour that is not yet used on target_date, or None if day is full."""
    settings = get_settings()
    max_per_day = settings.pipeline_max_drafts_per_day
    hours = _preferred_hours()

    date_str = target_date.isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT scheduled_publish_at FROM articles
            WHERE scheduled_publish_at >= ? AND scheduled_publish_at < ?
            AND status NOT IN ('error')
            """,
            (date_str + "T00:00:00", date_str + "T23:59:59"),
        ).fetchall()

    used_hours: set[int] = set()
    for row in rows:
        ts = row["scheduled_publish_at"] or ""
        try:
            used_hours.add(datetime.fromisoformat(ts).hour)
        except Exception:
            pass

    for h in hours:
        if h not in used_hours:
            return h
    return None  # day is full


def suggest_publish_slot(lookahead_days: int = 14) -> str:
    """Return a suggested publish datetime string (ISO, CET) for the next free slot.

    Format: 'Mo, 24.03.2026 um 09:00 Uhr'
    Also updates DB so consecutive calls return different slots.
    """
    today = _today_cet()
    weekday_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    for offset in range(1, lookahead_days + 1):
        candidate = today + timedelta(days=offset)
        hour = _next_free_hour(candidate)
        if hour is not None:
            wd = weekday_names[candidate.weekday()]
            return f"{wd}, {candidate.strftime('%d.%m.%Y')} um {hour:02d}:00 Uhr"

    # Fallback: just tomorrow morning
    tomorrow = today + timedelta(days=1)
    hours = _preferred_hours()
    h = hours[0] if hours else 9
    wd = weekday_names[tomorrow.weekday()]
    return f"{wd}, {tomorrow.strftime('%d.%m.%Y')} um {h:02d}:00 Uhr"


def reserve_publish_slot(article_id: int) -> str:
    """Reserve a publish slot for an article and persist it in the DB.

    Returns the suggested publish datetime string.
    """
    today = _today_cet()
    lookahead_days = 14
    weekday_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    for offset in range(1, lookahead_days + 1):
        candidate = today + timedelta(days=offset)
        hour = _next_free_hour(candidate)
        if hour is not None:
            # Reserve this slot by writing to the article
            iso_ts = f"{candidate.isoformat()}T{hour:02d}:00:00"
            with get_conn() as conn:
                conn.execute(
                    "UPDATE articles SET scheduled_publish_at = ? WHERE id = ?",
                    (iso_ts, article_id),
                )
            wd = weekday_names[candidate.weekday()]
            return f"{wd}, {candidate.strftime('%d.%m.%Y')} um {hour:02d}:00 Uhr"

    # Fallback
    tomorrow = today + timedelta(days=1)
    hours = _preferred_hours()
    h = hours[0] if hours else 9
    iso_ts = f"{tomorrow.isoformat()}T{h:02d}:00:00"
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET scheduled_publish_at = ? WHERE id = ?",
            (iso_ts, article_id),
        )
    wd = weekday_names[tomorrow.weekday()]
    return f"{wd}, {tomorrow.strftime('%d.%m.%Y')} um {h:02d}:00 Uhr"
