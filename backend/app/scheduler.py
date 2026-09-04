"""Smart publishing scheduler.

Calculates suggested publish slots for new WordPress drafts.
Rules:
- Preferred slots: configurable hours (default 09:00, 12:00, 15:00, 18:00 CET/CEST)
- The preferred hours define the daily publishing grid
- Scheduling only happens between the configured start/end hours
- New articles queue up after the last already-scheduled article
- Checks both local DB AND WordPress future posts to avoid double-booking

Ein freigegebener Artikel muss aber manchmal sofort raus - ein Messebericht ist
in acht Wochen wertlos. Dafuer gibt es Sondertermine: sie liegen zwischen den
Rasterzeiten (10:30 statt 09:00 oder 12:00) und lassen den Plan unangetastet.
Nichts wird verschoben; der frei werdende Rastertermin faellt beim naechsten
Lauf ohnehin dem Lueckenfueller in `_find_next_free_slot` zu.
"""
from __future__ import annotations

import base64
import json
import threading
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import get_settings
from .db import get_conn

# Ensures that concurrent pipeline runs (two threads) never assign the same slot.
_slot_lock = threading.Lock()

_BERLIN_TZ = ZoneInfo("Europe/Berlin")


def _today_cet() -> date:
    return datetime.now(_BERLIN_TZ).date()


def _now_cet() -> datetime:
    """Local wall clock without tzinfo - the form `scheduled_publish_at` uses."""
    return datetime.now(_BERLIN_TZ).replace(tzinfo=None, second=0, microsecond=0)


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


def _fetch_wp_future_datetimes() -> list[datetime]:
    """Fetch the publish datetimes of all future-scheduled WordPress posts.

    Minutes matter here: a Sondertermin at 10:30 is a real booking, and rounding
    it to a full hour would either hide it or block the wrong raster slot.
    Returns an empty list on any error so the scheduler degrades gracefully.
    """
    settings = get_settings()
    try:
        auth = base64.b64encode(
            f"{settings.wordpress_username}:{settings.wordpress_app_password}".encode()
        ).decode()
        found: list[datetime] = []
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
            for post in posts:
                try:
                    found.append(datetime.fromisoformat(post["date"]).replace(tzinfo=None))
                except Exception:
                    pass
            if len(posts) < 100:
                break
        return found
    except Exception:
        return []


def _fetch_wp_occupied_slots() -> set[tuple[str, int]]:
    """Occupied (date_iso, hour) pairs from WordPress, for the hour-based callers.

    This prevents the scheduler from assigning a slot that is already taken
    by a WP post that was not created via this pipeline (e.g. manually or via recovery scripts).
    """
    return {(dt.date().isoformat(), dt.hour) for dt in _fetch_wp_future_datetimes()}


def _format_slot(d: date, hour: int, minute: int = 0) -> str:
    weekday_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    wd = weekday_names[d.weekday()]
    return f"{wd}, {d.strftime('%d.%m.%Y')} um {hour:02d}:{minute:02d} Uhr"


def get_schedule_overview(lookahead_days: int = 60) -> list[dict]:
    """Return all booked scheduling slots (DB + WP) for the next N days, sorted by date.

    Keyed by the full minute, not by the hour: a Sondertermin at 10:30 and the
    raster slot at 09:00 are two different bookings and both have to show up.
    """
    today = _today_cet()

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

    db_slots: dict[tuple[str, int, int], dict] = {}
    for row in rows:
        try:
            dt = datetime.fromisoformat(row["scheduled_publish_at"])
        except Exception:
            continue
        db_slots[(dt.date().isoformat(), dt.hour, dt.minute)] = {
            "date": dt.date().isoformat(),
            "hour": dt.hour,
            "minute": dt.minute,
            "kind": _slot_kind(dt),
            "formatted": _format_slot(dt.date(), dt.hour, dt.minute),
            "source": "db",
            "article_id": row["id"],
            "article_title": row["title"],
            "article_status": row["status"],
            "wp_post_id": row["wp_post_id"],
            "wp_post_url": row["wp_post_url"],
        }

    # Slots occupied in WordPress but not in local DB
    wp_only: list[dict] = []
    for dt in sorted(_fetch_wp_future_datetimes()):
        if (dt.date().isoformat(), dt.hour, dt.minute) in db_slots or dt.date() < today:
            continue
        wp_only.append({
            "date": dt.date().isoformat(),
            "hour": dt.hour,
            "minute": dt.minute,
            "kind": _slot_kind(dt),
            "formatted": _format_slot(dt.date(), dt.hour, dt.minute),
            "source": "wordpress",
            "article_id": None,
            "article_title": "(WP-Beitrag außerhalb Pipeline)",
            "article_status": None,
            "wp_post_id": None,
            "wp_post_url": None,
        })

    all_slots = list(db_slots.values()) + wp_only
    all_slots.sort(key=lambda slot: (slot["date"], slot["hour"], slot["minute"]))
    return all_slots


# ---------------------------------------------------------------------------
# Terminwahl bei der Freigabe
# ---------------------------------------------------------------------------

SLOT_MODES = ("auto", "now", "today", "tomorrow", "custom")

SLOT_MODE_LABELS: dict[str, str] = {
    "auto": "Nächster freier Termin",
    "now": "Sofort veröffentlichen",
    "today": "Heute",
    "tomorrow": "Morgen",
    "custom": "Datum und Uhrzeit wählen",
}

# Abstand, den ein Sondertermin zu jedem anderen Beitrag haelt. 45 Minuten sind
# so gewaehlt, dass zwischen zwei Rasterzeiten (3 h) nur die Mitte uebrig
# bleibt: 10:30 geht, 09:30 und 11:30 nicht.
_EXTRA_MIN_GAP_MINUTES = 45

# Ein Rastertermin in fuenf Minuten waere keiner - "Heute" springt erst auf
# Zeiten, die weit genug weg sind, um noch eingeplant zu heissen.
_LEAD_MINUTES = 20


@dataclass(frozen=True)
class SlotPlan:
    """A resolved publish date, plus what kind of slot it turned out to be."""

    when: datetime
    kind: str  # "raster" | "extra" | "now"
    publish_now: bool = False
    note: str = ""

    @property
    def iso(self) -> str:
        return self.when.strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def label(self) -> str:
        return _format_slot(self.when.date(), self.when.hour, self.when.minute)


def _slot_kind(when: datetime) -> str:
    return "raster" if when.minute == 0 and when.hour in _preferred_hours() else "extra"


def _parse_custom_datetime(raw: str | None) -> datetime:
    value = (raw or "").strip()
    if not value:
        raise ValueError("Kein Datum angegeben")
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None, second=0, microsecond=0)
    except ValueError:
        raise ValueError(f"Datum nicht lesbar: {value}") from None


def _db_scheduled_datetimes(conn, exclude_article_id: int | None) -> list[datetime]:
    rows = conn.execute(
        """
        SELECT id, scheduled_publish_at FROM articles
        WHERE scheduled_publish_at IS NOT NULL
          AND scheduled_publish_at >= ?
          AND status NOT IN ('error', 'no_image')
        """,
        (_today_cet().isoformat() + "T00:00:00",),
    ).fetchall()
    found: list[datetime] = []
    for row in rows:
        if exclude_article_id is not None and int(row["id"]) == int(exclude_article_id):
            continue
        try:
            found.append(datetime.fromisoformat(row["scheduled_publish_at"]))
        except Exception:
            pass
    return found


def _is_free(when: datetime, taken: list[datetime]) -> bool:
    gap = timedelta(minutes=_EXTRA_MIN_GAP_MINUTES)
    return all(abs(when - other) >= gap for other in taken)


def _raster_candidates(day: date) -> list[datetime]:
    return [datetime.combine(day, time(hour, 0)) for hour in _preferred_hours()]


def _extra_candidates(day: date) -> list[datetime]:
    """Sondertermine liegen auf der halben Stunde, nie auf einer Rasterzeit."""
    # end_hour is the last raster hour, so the last half hour inside the window
    # is end_hour - 1 + 30 min - a 19:30 slot would sit outside it.
    start_hour, end_hour, _ = _schedule_bounds()
    return [datetime.combine(day, time(hour, 30)) for hour in range(start_hour, end_hour)]


def _first_free(
    candidates: list[datetime], taken: list[datetime], not_before: datetime | None = None
) -> datetime | None:
    for candidate in candidates:
        if not_before is not None and candidate < not_before:
            continue
        if _is_free(candidate, taken):
            return candidate
    return None


def _plan_slot(
    conn,
    mode: str,
    custom: str | None,
    exclude_article_id: int | None,
    wp_datetimes: list[datetime],
) -> SlotPlan:
    """Turn a scheduling wish into a concrete date. Writes nothing."""
    mode = (mode or "auto").strip() or "auto"
    if mode not in SLOT_MODES:
        raise ValueError(f"Unbekannter Terminwunsch: {mode}")

    taken = _db_scheduled_datetimes(conn, exclude_article_id) + list(wp_datetimes)
    now = _now_cet()

    if mode == "now":
        return SlotPlan(
            now + timedelta(minutes=1),
            kind="now",
            publish_now=True,
            note="Wird sofort veröffentlicht, der Plan bleibt unverändert.",
        )

    if mode == "custom":
        wanted = _parse_custom_datetime(custom)
        if wanted <= now:
            return SlotPlan(
                now + timedelta(minutes=1),
                kind="now",
                publish_now=True,
                note="Der gewählte Zeitpunkt liegt in der Vergangenheit — der Artikel wird sofort veröffentlicht.",
            )
        # Zwei Beitraege auf derselben Minute nimmt WordPress zwar an, aber so
        # will sie niemand lesen.
        while any(other == wanted for other in taken):
            wanted += timedelta(minutes=5)
        note = ""
        if not _is_free(wanted, taken):
            note = "Hinweis: Der Termin liegt dicht neben einem bereits geplanten Beitrag."
        return SlotPlan(wanted, kind=_slot_kind(wanted), note=note)

    if mode in {"today", "tomorrow"}:
        day = _today_cet() if mode == "today" else _today_cet() + timedelta(days=1)
        earliest = now + timedelta(minutes=_LEAD_MINUTES) if mode == "today" else None

        hit = _first_free(_raster_candidates(day), taken, earliest)
        if hit is not None:
            return SlotPlan(hit, kind="raster", note="Freier Rastertermin — es wird nichts verschoben.")

        hit = _first_free(_extra_candidates(day), taken, earliest)
        if hit is not None:
            return SlotPlan(
                hit,
                kind="extra",
                note="Alle Rasterzeiten belegt — Sondertermin dazwischen, der übrige Plan bleibt unverändert.",
            )

        if mode == "today":
            return SlotPlan(
                now + timedelta(minutes=1),
                kind="now",
                publish_now=True,
                note="Heute ist kein Termin mehr frei — der Artikel wird sofort veröffentlicht.",
            )
        # Morgen restlos dicht: der naechste freie Rastertermin ist ehrlicher
        # als ein erzwungener Sondertermin mitten in der Nacht.
        mode = "auto"

    # auto: erster freier Rastertermin ab morgen, Luecken zuerst
    tomorrow = _today_cet() + timedelta(days=1)
    for offset in range(0, 61):
        hit = _first_free(_raster_candidates(tomorrow + timedelta(days=offset)), taken)
        if hit is not None:
            return SlotPlan(hit, kind="raster")

    hours = _preferred_hours()
    return SlotPlan(datetime.combine(tomorrow, time(hours[0] if hours else 9, 0)), kind="raster")


def _record_schedule_choice(conn, article_id: int, plan: SlotPlan, mode: str, actor: str | None) -> None:
    """Note in the article's meta why it sits where it sits.

    The calendar reads this to mark hand-picked dates, and it is the trail for
    who moved a post off the grid and when.
    """
    row = conn.execute("SELECT meta_json FROM articles WHERE id = ?", (article_id,)).fetchone()
    try:
        meta = json.loads((row["meta_json"] if row else None) or "{}")
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta["schedule"] = {
        "mode": mode,
        "kind": plan.kind,
        "manual": mode != "auto",
        "scheduled_for": plan.iso,
        "set_by": actor or "system",
        "set_at": datetime.now(_BERLIN_TZ).isoformat(),
    }
    conn.execute(
        "UPDATE articles SET meta_json = ? WHERE id = ?",
        (json.dumps(meta, ensure_ascii=False), article_id),
    )


def plan_publish_slot(
    mode: str = "auto", custom: str | None = None, exclude_article_id: int | None = None
) -> SlotPlan:
    """Preview the date a wish would resolve to, without touching the article."""
    wp_datetimes = _fetch_wp_future_datetimes()
    with get_conn() as conn:
        return _plan_slot(conn, mode, custom, exclude_article_id, wp_datetimes)


def set_publish_slot(
    article_id: int,
    mode: str = "auto",
    custom: str | None = None,
    actor: str | None = None,
    keep_existing: bool = False,
) -> SlotPlan:
    """Resolve a wish and write it to the article's `scheduled_publish_at`.

    With `keep_existing` an already reserved slot wins - that is the behaviour
    the pipeline relies on, so a repeated run never moves a post. An explicit
    wish always overwrites: choosing "Heute" for a post that sits in November is
    the whole point.

    Uses a module-level lock so that concurrent pipeline runs (two threads)
    cannot read the same "free" slot and assign it twice.
    """
    mode = (mode or "auto").strip() or "auto"

    # Fetch WP-occupied slots BEFORE acquiring the lock - the API call can be slow
    # and must not block other threads unnecessarily.
    wp_datetimes = _fetch_wp_future_datetimes()

    with _slot_lock:
        # Single DB connection for the entire read-find-write cycle so the
        # slot we pick is still free when we write it.
        with get_conn() as conn:
            # Only the automatic mode defers to an existing slot. An explicit
            # wish is the caller saying "move it", so honouring the old date
            # there would silently do nothing.
            if keep_existing and mode == "auto":
                row = conn.execute(
                    "SELECT scheduled_publish_at FROM articles WHERE id = ?",
                    (article_id,),
                ).fetchone()
                existing = row["scheduled_publish_at"] if row else None
                if existing:
                    try:
                        when = datetime.fromisoformat(existing)
                        return SlotPlan(when, kind=_slot_kind(when))
                    except Exception:
                        pass  # invalid - fall through and assign a fresh slot

            plan = _plan_slot(conn, mode, custom, article_id, wp_datetimes)
            conn.execute(
                "UPDATE articles SET scheduled_publish_at = ? WHERE id = ?",
                (plan.iso, article_id),
            )
            _record_schedule_choice(conn, article_id, plan, mode, actor)
            return plan


def release_publish_slot(article_id: int) -> None:
    """Clear a previously reserved slot (e.g. when article is rejected after slot assignment)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET scheduled_publish_at = NULL WHERE id = ?",
            (article_id,),
        )


def restore_publish_slot(article_id: int, scheduled_at: str | None) -> None:
    """Write a slot back verbatim, e.g. after WordPress refused a new date.

    Unlike `set_publish_slot` this asks no questions: a rollback has to land on
    the exact old timestamp, even one that has meanwhile slipped into the past.
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET scheduled_publish_at = ? WHERE id = ?",
            (scheduled_at, article_id),
        )


def suggest_publish_slot() -> str:
    """Return a suggested publish datetime string (CET) for the next free slot."""
    return plan_publish_slot("auto").label


def reserve_publish_slot(
    article_id: int,
    mode: str = "auto",
    custom: str | None = None,
    actor: str | None = None,
) -> str:
    """Reserve a publish slot for an article and persist it in the DB.

    In the default mode an article that already has a slot keeps it. A caller
    that passes an explicit wish ("today", "custom", ...) wants the slot moved,
    so that one overwrites. Returns the formatted publish datetime string.
    """
    return set_publish_slot(
        article_id,
        mode=mode,
        custom=custom,
        actor=actor,
        keep_existing=(mode or "auto") == "auto",
    ).label
