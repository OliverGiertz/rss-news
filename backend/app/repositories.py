from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import datetime, timezone
from typing import Any

from .db import get_conn, rows_to_dicts


@dataclass(frozen=True)
class SourceCreate:
    name: str
    base_url: str | None
    terms_url: str | None
    license_name: str | None
    risk_level: str
    is_enabled: bool
    notes: str | None
    last_reviewed_at: str | None


@dataclass(frozen=True)
class FeedCreate:
    name: str
    url: str
    source_id: int | None
    is_enabled: bool


@dataclass(frozen=True)
class SourceUpdate:
    name: str
    base_url: str | None
    terms_url: str | None
    license_name: str | None
    risk_level: str
    is_enabled: bool
    notes: str | None
    last_reviewed_at: str | None


@dataclass(frozen=True)
class FeedUpdate:
    name: str
    url: str
    source_id: int | None
    is_enabled: bool


@dataclass(frozen=True)
class RunCreate:
    run_type: str
    status: str
    details: str | None = None


@dataclass(frozen=True)
class ArticleUpsert:
    feed_id: int | None
    source_article_id: str | None
    source_hash: str | None
    title: str
    source_url: str
    canonical_url: str | None
    published_at: str | None
    author: str | None
    summary: str | None
    content_raw: str | None
    content_rewritten: str | None
    image_urls_json: str | None
    press_contact: str | None
    source_name_snapshot: str | None
    source_terms_url_snapshot: str | None
    source_license_name_snapshot: str | None
    legal_checked: bool
    legal_checked_at: str | None
    legal_note: str | None
    wp_post_id: int | None
    wp_post_url: str | None
    publish_attempts: int
    publish_last_error: str | None
    published_to_wp_at: str | None
    word_count: int
    status: str
    meta_json: str | None


@dataclass(frozen=True)
class PublishJobCreate:
    article_id: int
    max_attempts: int = 3


def create_source(payload: SourceCreate) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO sources (name, base_url, terms_url, license_name, risk_level, is_enabled, notes, last_reviewed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                payload.base_url,
                payload.terms_url,
                payload.license_name,
                payload.risk_level,
                1 if payload.is_enabled else 0,
                payload.notes,
                payload.last_reviewed_at,
            ),
        )
        return int(cur.lastrowid)


def list_sources() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, base_url, terms_url, license_name, risk_level, is_enabled, notes, last_reviewed_at, created_at, updated_at
            FROM sources
            ORDER BY id DESC
            """
        ).fetchall()
    return rows_to_dicts(rows)


def get_source_by_id(source_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, base_url, terms_url, license_name, risk_level, is_enabled, notes, last_reviewed_at, created_at, updated_at
            FROM sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
    return dict(row) if row else None


def update_source(source_id: int, payload: SourceUpdate) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE sources
            SET name = ?, base_url = ?, terms_url = ?, license_name = ?, risk_level = ?, is_enabled = ?, notes = ?, last_reviewed_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.base_url,
                payload.terms_url,
                payload.license_name,
                payload.risk_level,
                1 if payload.is_enabled else 0,
                payload.notes,
                payload.last_reviewed_at,
                source_id,
            ),
        )
    return cur.rowcount > 0


def delete_source(source_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    return cur.rowcount > 0


def create_feed(payload: FeedCreate) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO feeds (name, url, source_id, is_enabled) VALUES (?, ?, ?, ?)",
            (payload.name.strip(), payload.url.strip(), payload.source_id, 1 if payload.is_enabled else 0),
        )
        return int(cur.lastrowid)


def list_feeds() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT f.id, f.name, f.url, f.source_id, f.is_enabled, f.etag, f.last_modified, f.last_checked_at,
                   f.created_at, f.updated_at, s.name AS source_name, s.license_name AS source_license_name,
                   s.terms_url AS source_terms_url, s.risk_level AS source_risk_level, s.base_url AS source_base_url,
                   s.last_reviewed_at AS source_last_reviewed_at, s.is_enabled AS source_is_enabled
            FROM feeds f
            LEFT JOIN sources s ON s.id = f.source_id
            ORDER BY f.id DESC
            """
        ).fetchall()
    return rows_to_dicts(rows)


def list_enabled_feeds() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT f.id, f.name, f.url, f.source_id, f.is_enabled, f.etag, f.last_modified, f.last_checked_at,
                   s.name AS source_name, s.license_name AS source_license_name, s.terms_url AS source_terms_url,
                   s.risk_level AS source_risk_level, s.base_url AS source_base_url,
                   s.last_reviewed_at AS source_last_reviewed_at, s.is_enabled AS source_is_enabled
            FROM feeds f
            LEFT JOIN sources s ON s.id = f.source_id
            WHERE f.is_enabled = 1
            ORDER BY f.id ASC
            """
        ).fetchall()
    return rows_to_dicts(rows)


def get_feed_by_id(feed_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT f.id, f.name, f.url, f.source_id, f.is_enabled, f.etag, f.last_modified, f.last_checked_at,
                   s.name AS source_name, s.license_name AS source_license_name, s.terms_url AS source_terms_url,
                   s.risk_level AS source_risk_level, s.base_url AS source_base_url,
                   s.last_reviewed_at AS source_last_reviewed_at, s.is_enabled AS source_is_enabled
            FROM feeds f
            LEFT JOIN sources s ON s.id = f.source_id
            WHERE f.id = ?
            """,
            (feed_id,),
        ).fetchone()
    return dict(row) if row else None


def update_feed(feed_id: int, payload: FeedUpdate) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE feeds
            SET name = ?, url = ?, source_id = ?, is_enabled = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.url.strip(),
                payload.source_id,
                1 if payload.is_enabled else 0,
                feed_id,
            ),
        )
    return cur.rowcount > 0


def delete_feed(feed_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
    return cur.rowcount > 0


def update_feed_fetch_state(feed_id: int, etag: str | None, last_modified: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE feeds
            SET etag = ?, last_modified = ?, last_checked_at = datetime('now')
            WHERE id = ?
            """,
            (etag, last_modified, feed_id),
        )


def create_run(payload: RunCreate) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO runs (run_type, status, details) VALUES (?, ?, ?)",
            (payload.run_type, payload.status, payload.details),
        )
        return int(cur.lastrowid)


def finish_run(run_id: int, status: str, details: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE runs
            SET status = ?, details = ?, finished_at = datetime('now')
            WHERE id = ?
            """,
            (status, details, run_id),
        )


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 500))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, run_type, status, started_at, finished_at, details
            FROM runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return rows_to_dicts(rows)


def get_run_by_id(run_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, run_type, status, started_at, finished_at, details
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
    return dict(row) if row else None


def get_article_by_id(article_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT a.id, a.feed_id, a.source_article_id, a.source_hash, a.title, a.source_url, a.canonical_url, a.published_at, a.author,
                   a.summary, a.content_raw, a.content_rewritten, a.image_urls_json, a.press_contact,
                   a.source_name_snapshot, a.source_terms_url_snapshot, a.source_license_name_snapshot,
                   a.legal_checked, a.legal_checked_at, a.legal_note,
                   a.wp_post_id, a.wp_post_url, a.publish_attempts, a.publish_last_error, a.published_to_wp_at,
                   a.word_count, a.status, a.meta_json, a.created_at, a.updated_at
            FROM articles a
            WHERE a.id = ?
            """,
            (article_id,),
        ).fetchone()
    return dict(row) if row else None


def _merge_review_event(meta_json: str | None, event: dict[str, Any]) -> str:
    meta: dict[str, Any] = {}
    if meta_json:
        try:
            meta = json.loads(meta_json)
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}

    events = meta.get("review_events")
    if not isinstance(events, list):
        events = []
    events.append(event)
    meta["review_events"] = events
    return json.dumps(meta, ensure_ascii=False)


def _load_meta(meta_json: str | None) -> dict[str, Any]:
    if not meta_json:
        return {}
    try:
        parsed = json.loads(meta_json)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def update_article_status(
    article_id: int,
    new_status: str,
    *,
    actor: str | None = None,
    note: str | None = None,
    decision: str | None = None,
) -> bool:
    article = get_article_by_id(article_id)
    if not article:
        return False

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from_status": article.get("status"),
        "to_status": new_status,
        "actor": actor or "system",
        "note": note,
        "decision": decision,
    }
    merged_meta = _merge_review_event(article.get("meta_json"), event)

    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET status = ?, meta_json = ? WHERE id = ?",
            (new_status, merged_meta, article_id),
        )
    return True


def set_article_legal_review(article_id: int, approved: bool, note: str | None, actor: str | None = None) -> bool:
    article = get_article_by_id(article_id)
    if not article:
        return False

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "legal_review",
        "approved": approved,
        "actor": actor or "system",
        "note": note,
    }
    merged_meta = _merge_review_event(article.get("meta_json"), event)
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE articles
            SET legal_checked = ?, legal_checked_at = datetime('now'), legal_note = ?, meta_json = ?
            WHERE id = ?
            """,
            (1 if approved else 0, note, merged_meta, article_id),
        )
    return True


def set_article_image_decision(article_id: int, image_url: str, action: str, actor: str | None = None) -> bool:
    article = get_article_by_id(article_id)
    if not article:
        return False
    url = (image_url or "").strip()
    if not url:
        return False
    if action not in {"select", "exclude", "restore"}:
        return False

    meta = _load_meta(article.get("meta_json"))
    image_review = meta.get("image_review")
    if not isinstance(image_review, dict):
        image_review = {}

    excluded = image_review.get("excluded_urls")
    if not isinstance(excluded, list):
        excluded = []
    excluded_set = {str(item) for item in excluded if item}

    selected_url = image_review.get("selected_url")
    if not isinstance(selected_url, str):
        selected_url = None

    if action == "select":
        selected_url = url
        excluded_set.discard(url)
    elif action == "exclude":
        excluded_set.add(url)
        if selected_url == url:
            selected_url = None
    elif action == "restore":
        excluded_set.discard(url)

    image_review["selected_url"] = selected_url
    image_review["excluded_urls"] = sorted(excluded_set)
    image_review["updated_at"] = datetime.now(timezone.utc).isoformat()
    image_review["updated_by"] = actor or "system"
    meta["image_review"] = image_review

    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET meta_json = ? WHERE id = ?",
            (json.dumps(meta, ensure_ascii=False), article_id),
        )
    return True


def create_publish_job(payload: PublishJobCreate) -> int:
    with get_conn() as conn:
        existing = conn.execute(
            """
            SELECT id FROM publish_jobs
            WHERE article_id = ? AND status IN ('queued', 'running')
            ORDER BY id DESC
            LIMIT 1
            """,
            (payload.article_id,),
        ).fetchone()
        if existing:
            return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO publish_jobs (article_id, status, attempts, max_attempts)
            VALUES (?, 'queued', 0, ?)
            """,
            (payload.article_id, max(1, payload.max_attempts)),
        )
        return int(cur.lastrowid)


def list_publish_jobs(limit: int = 100) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 500))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT j.id, j.article_id, j.status, j.attempts, j.max_attempts, j.error_message, j.wp_post_id, j.wp_post_url,
                   j.created_at, j.started_at, j.finished_at, a.title AS article_title
            FROM publish_jobs j
            LEFT JOIN articles a ON a.id = j.article_id
            ORDER BY j.id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return rows_to_dicts(rows)


def claim_next_publish_job() -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, article_id, status, attempts, max_attempts, error_message, wp_post_id, wp_post_url
            FROM publish_jobs
            WHERE status = 'queued' AND attempts < max_attempts
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        job_id = int(row["id"])
        conn.execute(
            """
            UPDATE publish_jobs
            SET status = 'running',
                attempts = attempts + 1,
                started_at = datetime('now'),
                finished_at = NULL
            WHERE id = ?
            """,
            (job_id,),
        )
        claimed = conn.execute(
            """
            SELECT id, article_id, status, attempts, max_attempts, error_message, wp_post_id, wp_post_url
            FROM publish_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
    return dict(claimed) if claimed else None


def complete_publish_job(job_id: int, wp_post_id: int | None, wp_post_url: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE publish_jobs
            SET status = 'success',
                wp_post_id = ?,
                wp_post_url = ?,
                error_message = NULL,
                finished_at = datetime('now')
            WHERE id = ?
            """,
            (wp_post_id, wp_post_url, job_id),
        )


def fail_publish_job(job_id: int, error_message: str, requeue: bool) -> None:
    next_status = "queued" if requeue else "failed"
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE publish_jobs
            SET status = ?,
                error_message = ?,
                finished_at = datetime('now')
            WHERE id = ?
            """,
            (next_status, error_message[:2000], job_id),
        )


def mark_article_publish_result(
    article_id: int,
    *,
    wp_post_id: int | None,
    wp_post_url: str | None,
    error: str | None,
    increment_attempts: bool,
    set_published_status: bool,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE articles
            SET wp_post_id = ?,
                wp_post_url = ?,
                publish_attempts = CASE WHEN ? THEN publish_attempts + 1 ELSE publish_attempts END,
                publish_last_error = ?,
                published_to_wp_at = CASE WHEN ? IS NOT NULL THEN datetime('now') ELSE published_to_wp_at END,
                status = CASE WHEN ? THEN 'published' ELSE status END
            WHERE id = ?
            """,
            (
                wp_post_id,
                wp_post_url,
                1 if increment_attempts else 0,
                error[:2000] if error else None,
                wp_post_id,
                1 if set_published_status else 0,
                article_id,
            ),
        )


def _resolve_existing_article_id(payload: ArticleUpsert) -> int | None:
    with get_conn() as conn:
        # 1) strongest key: source_url
        row = conn.execute(
            "SELECT id FROM articles WHERE source_url = ?",
            (payload.source_url.strip(),),
        ).fetchone()
        if row:
            return int(row["id"])

        # 2) stable feed+guid combo
        if payload.feed_id is not None and payload.source_article_id:
            row = conn.execute(
                "SELECT id FROM articles WHERE feed_id = ? AND source_article_id = ?",
                (payload.feed_id, payload.source_article_id),
            ).fetchone()
            if row:
                return int(row["id"])

        # 3) content hash fallback
        if payload.source_hash:
            row = conn.execute(
                "SELECT id FROM articles WHERE source_hash = ?",
                (payload.source_hash,),
            ).fetchone()
            if row:
                return int(row["id"])

    return None


def find_existing_article_for_upsert(payload: ArticleUpsert) -> dict[str, Any] | None:
    article_id = _resolve_existing_article_id(payload)
    if article_id is None:
        return None
    return get_article_by_id(article_id)


def upsert_article(payload: ArticleUpsert) -> int:
    existing_id = _resolve_existing_article_id(payload)
    with get_conn() as conn:
        if existing_id is None:
            conn.execute(
                """
                INSERT INTO articles (
                    feed_id, source_article_id, source_hash, title, source_url, canonical_url, published_at, author,
                    summary, content_raw, content_rewritten, image_urls_json, press_contact,
                    source_name_snapshot, source_terms_url_snapshot, source_license_name_snapshot,
                    legal_checked, legal_checked_at, legal_note,
                    wp_post_id, wp_post_url, publish_attempts, publish_last_error, published_to_wp_at,
                    word_count, status, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.feed_id,
                    payload.source_article_id,
                    payload.source_hash,
                    payload.title.strip(),
                    payload.source_url.strip(),
                    payload.canonical_url,
                    payload.published_at,
                    payload.author,
                    payload.summary,
                    payload.content_raw,
                    payload.content_rewritten,
                    payload.image_urls_json,
                    payload.press_contact,
                    payload.source_name_snapshot,
                    payload.source_terms_url_snapshot,
                    payload.source_license_name_snapshot,
                    1 if payload.legal_checked else 0,
                    payload.legal_checked_at,
                    payload.legal_note,
                    payload.wp_post_id,
                    payload.wp_post_url,
                    payload.publish_attempts,
                    payload.publish_last_error,
                    payload.published_to_wp_at,
                    payload.word_count,
                    payload.status,
                    payload.meta_json,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE articles
                SET
                    feed_id = ?,
                    source_article_id = ?,
                    source_hash = ?,
                    title = ?,
                    source_url = ?,
                    canonical_url = ?,
                    published_at = ?,
                    author = ?,
                    summary = ?,
                    content_raw = ?,
                    content_rewritten = ?,
                    image_urls_json = ?,
                    press_contact = ?,
                    source_name_snapshot = ?,
                    source_terms_url_snapshot = ?,
                    source_license_name_snapshot = ?,
                    legal_checked = ?,
                    legal_checked_at = ?,
                    legal_note = ?,
                    wp_post_id = ?,
                    wp_post_url = ?,
                    publish_attempts = ?,
                    publish_last_error = ?,
                    published_to_wp_at = ?,
                    word_count = ?,
                    status = ?,
                    meta_json = ?
                WHERE id = ?
                """,
                (
                    payload.feed_id,
                    payload.source_article_id,
                    payload.source_hash,
                    payload.title.strip(),
                    payload.source_url.strip(),
                    payload.canonical_url,
                    payload.published_at,
                    payload.author,
                    payload.summary,
                    payload.content_raw,
                    payload.content_rewritten,
                    payload.image_urls_json,
                    payload.press_contact,
                    payload.source_name_snapshot,
                    payload.source_terms_url_snapshot,
                    payload.source_license_name_snapshot,
                    1 if payload.legal_checked else 0,
                    payload.legal_checked_at,
                    payload.legal_note,
                    payload.wp_post_id,
                    payload.wp_post_url,
                    payload.publish_attempts,
                    payload.publish_last_error,
                    payload.published_to_wp_at,
                    payload.word_count,
                    payload.status,
                    payload.meta_json,
                    existing_id,
                ),
            )
        row = conn.execute("SELECT id FROM articles WHERE source_url = ?", (payload.source_url.strip(),)).fetchone()
        if row:
            return int(row["id"])
    return int(existing_id) if existing_id else 0


def list_articles(limit: int = 100, status_filter: str | None = None) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 500))
    with get_conn() as conn:
        if status_filter:
            rows = conn.execute(
                """
                SELECT a.id, a.feed_id, a.source_article_id, a.source_hash, a.title, a.source_url, a.canonical_url, a.published_at, a.author,
                       a.summary, a.content_raw, a.word_count, a.status, a.meta_json, a.created_at, a.updated_at, f.name AS feed_name,
                       a.image_urls_json, a.press_contact, a.source_name_snapshot, a.source_terms_url_snapshot,
                       a.source_license_name_snapshot, a.legal_checked, a.legal_checked_at, a.legal_note,
                       a.wp_post_id, a.wp_post_url, a.publish_attempts, a.publish_last_error, a.published_to_wp_at
                FROM articles a
                LEFT JOIN feeds f ON f.id = a.feed_id
                WHERE a.status = ?
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (status_filter, safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT a.id, a.feed_id, a.source_article_id, a.source_hash, a.title, a.source_url, a.canonical_url, a.published_at, a.author,
                       a.summary, a.content_raw, a.word_count, a.status, a.meta_json, a.created_at, a.updated_at, f.name AS feed_name,
                       a.image_urls_json, a.press_contact, a.source_name_snapshot, a.source_terms_url_snapshot,
                       a.source_license_name_snapshot, a.legal_checked, a.legal_checked_at, a.legal_note,
                       a.wp_post_id, a.wp_post_url, a.publish_attempts, a.publish_last_error, a.published_to_wp_at
                FROM articles a
                LEFT JOIN feeds f ON f.id = a.feed_id
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
    return rows_to_dicts(rows)
