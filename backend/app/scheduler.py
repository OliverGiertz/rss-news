"""Smart publishing scheduler.

Calculates suggested publish slots for new WordPress drafts.
Rules:
- Preferred slots: configurable hours (default 09:00, 12:00, 15:00, 18:00 CET/CEST)
- The preferred hours define the daily publishing grid
- Scheduling only happens between the configured start/end hours
- New articles queue up after the last already-scheduled article
- Checks both local DB AND WordPress future posts to avoid double-booking
"""
from __future__ import annotations

import base64
import json
import threading
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .config import get_settings
from .db import get_conn

# Ensures that concurrent pipeline runs (two threads) never assign the same slot.
_slot_lock = threading.Lock()

_BERLIN_TZ = ZoneInfo("Europe/Berlin")


def _today_cet() -> date:
    return datetime.now(_BERLIN_TZ).date()


def _schedule_bounds() -> tuple[int, int, int]:
    settings = get_settings()
    start_hour = max(0, min(23, int(settings.pipeline_publish_start_hour)))
    end_hour = max(start_hour, min(23, int(settings.pipeline_publish_end_hour)))
    min_gap = max(1, int(settings.pipeline_publish_min_gap_hours))
    return start_hour, end_hour, min_gap


def _preferred_hours() -> list[int]:
    settings = get_settings()
    start_hour, end_hour, min_gap = _schedule_bounds()
    max_per_day = max(1, int(settings.pipeline_max_drafts_per_day))

    try:
        preferred = [int(h.strip()) for h in settings.pipeline_publish_hours.split(",") if h.strip()]
    except Exception:
        preferred = [9, 12, 15, 18]

    anchors: list[int] = []
    seen: set[int] = set()
    for hour in preferred:
        if hour < start_hour or hour > end_hour or hour in seen:
            continue
        anchors.append(hour)
        seen.add(hour)

    if not anchors:
        anchors = [start_hour]

    candidates = anchors.copy()
    for hour in range(start_hour, end_hour + 1):
        if hour in seen:
            continue
        if all(abs(hour - existing) >= min_gap for existing in candidates):
            candidates.append(hour)
            seen.add(hour)
        if len(candidates) >= max_per_day:
            break

    return candidates[:max_per_day]


def _fetch_wp_occupied_slots() -> set[tuple[str, int]]:
    """Fetch all future-scheduled WordPress posts and return occupied (date_iso, hour) pairs.

    This prevents the scheduler from assigning a slot that is already taken
    by a WP post that was not created via this pipeline (e.g. manually or via recovery scripts).
    Returns an empty set on any error so the scheduler degrades gracefully.
    """
    settings = get_settings()
    try:
        auth = base64.b64encode(
            f"{settings.wordpress_username}:{settings.wordpress_app_password}".encode()
        ).decode()
        occupied: set[tuple[str, int]] = set()
        for page in range(1, 21):
            url = (
                f"{settings.wordpress_base_url}/wp-json/wp/v2/posts"
                f"?status=future&per_page=100&page={page}&orderby=date&order=asc&_fields=id,date"
            )
            req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                posts = json.loads(resp.read())
            if not isinstance(posts, list) or not posts:
                break
            for p in posts:
                try:
                    dt = datetime.fromisoformat(p["date"])
                    occupied.add((dt.date().isoformat(), dt.hour))
                except Exception:
                    pass
            if len(posts) < 100:
                break
        return occupied
    except Exception:
        return set()


def _get_last_future_scheduled_date(wp_occupied: set[tuple[str, int]]) -> date | None:
    """Return the date of the latest already-scheduled slot (DB + WP)."""
    today = _today_cet()

    # Latest from local DB
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT MAX(scheduled_publish_at) AS last_slot
            FROM articles
            WHERE scheduled_publish_at IS NOT NULL
            AND scheduled_publish_at >= ?
            AND status NOT IN ('error', 'no_image')
            """,
            (today.isoformat() + "T00:00:00",),
        ).fetchone()
    db_last: date | None = None
    if row and row["last_slot"]:
        try:
            db_last = datetime.fromisoformat(row["last_slot"]).date()
        except Exception:
            pass

    # Latest from WP
    wp_last: date | None = None
    for d_str, _ in wp_occupied:
        try:
            d = date.fromisoformat(d_str)
            if d >= today and (wp_last is None or d > wp_last):
                wp_last = d
        except Exception:
            pass

    if db_last and wp_last:
        return max(db_last, wp_last)
    return db_last or wp_last


def _next_free_hour(target_date: date, wp_occupied: set[tuple[str, int]]) -> int | None:
    """Return first allowed hour with enough spacing to existing slots, or None if day is full."""
    hours = _preferred_hours()
    _, _, min_gap = _schedule_bounds()
    date_str = target_date.isoformat()

    # Hours used in local DB
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT scheduled_publish_at FROM articles
            WHERE scheduled_publish_at >= ? AND scheduled_publish_at < ?
            AND status NOT IN ('error', 'no_image')
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

    # Hours used in WordPress
    for d_str, h in wp_occupied:
        if d_str == date_str:
            used_hours.add(h)

    for h in hours:
        if all(abs(h - used_hour) >= min_gap for used_hour in used_hours):
            return h
    return None


def _format_slot(d: date, hour: int) -> str:
    weekday_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    wd = weekday_names[d.weekday()]
    return f"{wd}, {d.strftime('%d.%m.%Y')} um {hour:02d}:00 Uhr"


def _find_next_free_slot(
    wp_occupied: set[tuple[str, int]], lookahead_days: int = 60
) -> tuple[date, int] | None:
    """Find the next free (date, hour) slot.

    Starts from tomorrow and scans forward, filling any gaps in the schedule
    rather than always appending after the last existing post.
    """
    today = _today_cet()
    tomorrow = today + timedelta(days=1)

    for offset in range(0, lookahead_days + 1):
        candidate = tomorrow + timedelta(days=offset)
        hour = _next_free_hour(candidate, wp_occupied)
        if hour is not None:
            return candidate, hour

    hours = _preferred_hours()
    return tomorrow, hours[0] if hours else 9


def get_schedule_overview(lookahead_days: int = 60) -> list[dict]:
    """Return all booked scheduling slots (DB + WP) for the next N days, sorted by date."""
    today = _today_cet()
    hours = _preferred_hours()

    # Slots booked in local DB
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, status, wp_post_id, wp_post_url, scheduled_publish_at
            FROM articles
            WHERE scheduled_publish_at IS NOT NULL
              AND scheduled_publish_at >= ?
              AND status NOT IN ('error', 'no_image')
            ORDER BY scheduled_publish_at
            """,
            (today.isoformat() + "T00:00:00",),
        ).fetchall()

    db_slots: dict[tuple[str, int], dict] = {}
    for row in rows:
        try:
            dt = datetime.fromisoformat(row["scheduled_publish_at"])
            key = (dt.date().isoformat(), dt.hour)
            db_slots[key] = {
                "date": dt.date().isoformat(),
                "hour": dt.hour,
                "formatted": _format_slot(dt.date(), dt.hour),
                "source": "db",
                "article_id": row["id"],
                "article_title": row["title"],
                "article_status": row["status"],
                "wp_post_id": row["wp_post_id"],
                "wp_post_url": row["wp_post_url"],
            }
        except Exception:
            pass

    # Slots occupied in WordPress but not in local DB
    wp_occupied = _fetch_wp_occupied_slots()
    wp_only: list[dict] = []
    for d_str, h in sorted(wp_occupied):
        if (d_str, h) in db_slots:
            continue
        try:
            d = date.fromisoformat(d_str)
            if d >= today:
                wp_only.append({
                    "date": d_str,
                    "hour": h,
                    "formatted": _format_slot(d, h),
                    "source": "wordpress",
                    "article_id": None,
                    "article_title": "(WP-Beitrag außerhalb Pipeline)",
                    "article_status": None,
                    "wp_post_id": None,
                    "wp_post_url": None,
                })
        except Exception:
            pass

    all_slots = list(db_slots.values()) + wp_only
    all_slots.sort(key=lambda s: (s["date"], s["hour"]))
    return all_slots


def release_publish_slot(article_id: int) -> None:
    """Clear a previously reserved slot (e.g. when article is rejected after slot assignment)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET scheduled_publish_at = NULL WHERE id = ?",
            (article_id,),
        )


def suggest_publish_slot() -> str:
    """Return a suggested publish datetime string (CET) for the next free slot."""
    wp_occupied = _fetch_wp_occupied_slots()
    result = _find_next_free_slot(wp_occupied)
    if result:
        d, hour = result
        return _format_slot(d, hour)
    tomorrow = _today_cet() + timedelta(days=1)
    hours = _preferred_hours()
    return _format_slot(tomorrow, hours[0] if hours else 9)


def reserve_publish_slot(article_id: int) -> str:
    """Reserve a publish slot for an article and persist it in the DB.

    If the article already has a scheduled_publish_at, keep it unchanged.
    Returns the formatted publish datetime string.

    Uses a module-level lock so that concurrent pipeline runs (two threads)
    cannot read the same "free" slot and assign it twice.
    """
    # Fetch WP-occupied slots BEFORE acquiring the lock — the API call can be slow
    # and must not block other threads unnecessarily.
    wp_occupied = _fetch_wp_occupied_slots()

    with _slot_lock:
        # Single DB connection for the entire read-find-write cycle so the
        # slot we pick is still free when we write it.
        with get_conn() as conn:
            row = conn.execute(
                "SELECT scheduled_publish_at FROM articles WHERE id = ?",
                (article_id,),
            ).fetchone()
            existing_slot = row["scheduled_publish_at"] if row else None
            if existing_slot:
                try:
                    dt = datetime.fromisoformat(existing_slot)
                    return _format_slot(dt.date(), dt.hour)
                except Exception:
                    pass  # invalid — fall through and assign a fresh slot

            # Find the next free (date, hour) slot using THIS connection so we
            # see all slots written during this lock window.
            hours = _preferred_hours()
            today = _today_cet()
            tomorrow = today + timedelta(days=1)
            candidate: date | None = None
            chosen_hour: int | None = None

            for offset in range(0, 61):
                d = tomorrow + timedelta(days=offset)
                date_str = d.isoformat()

                rows = conn.execute(
                    """
                    SELECT scheduled_publish_at FROM articles
                    WHERE scheduled_publish_at >= ? AND scheduled_publish_at < ?
                    AND status NOT IN ('error', 'no_image')
                    """,
                    (date_str + "T00:00:00", date_str + "T23:59:59"),
                ).fetchall()

                used_hours: set[int] = set()
                for r in rows:
                    ts = r["scheduled_publish_at"] or ""
                    try:
                        used_hours.add(datetime.fromisoformat(ts).hour)
                    except Exception:
                        pass
                for d_str, h in wp_occupied:
                    if d_str == date_str:
                        used_hours.add(h)

                for h in hours:
                    if h not in used_hours:
                        candidate = d
                        chosen_hour = h
                        break
                if candidate is not None:
                    break

            if candidate is None:
                candidate = tomorrow
                chosen_hour = hours[0] if hours else 9

            iso_ts = f"{candidate.isoformat()}T{chosen_hour:02d}:00:00"
            conn.execute(
                "UPDATE articles SET scheduled_publish_at = ? WHERE id = ?",
                (iso_ts, article_id),
            )
            return _format_slot(candidate, chosen_hour)
