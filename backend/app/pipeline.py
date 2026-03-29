"""Autonomous RSS-News pipeline.

Full automated flow:
1. Run RSS ingestion
2. For each new article:
   - Auto-select primary image
   - Score relevance via GPT
   - < warn threshold: reject (error status) → Telegram rejected summary
   - warn..auto threshold: Telegram warning with override button
   - >= auto threshold: rewrite → create WP draft → Telegram notification
3. Send pipeline summary to Telegram
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import get_settings
from .ingestion import run_ingestion
from .publisher import enqueue_publish, run_publisher
from .repositories import (
    ArticleUpsert,
    get_article_by_id,
    list_articles,
    set_article_image_decision,
    update_article_status,
    upsert_article as repo_upsert_article,
)
from .rewrite import generate_article_tags, merge_generated_tags, rewrite_article_text, score_article_relevance
from .scheduler import reserve_publish_slot
from .wordpress import publish_article_draft, selected_image_exists

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    ingested: int = 0
    processed: int = 0
    drafts_created: int = 0
    rejected: int = 0
    warnings: int = 0
    errors: int = 0
    no_image: int = 0
    rejected_articles: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _auto_select_image(article: dict[str, Any]) -> bool:
    """Auto-select the primary image from ingestion metadata if not already selected."""
    meta_json = article.get("meta_json") or "{}"
    try:
        meta = json.loads(meta_json)
    except Exception:
        return False

    # Already selected?
    image_review = meta.get("image_review") or {}
    if isinstance(image_review, dict) and image_review.get("selected_url"):
        return True

    # Try to get primary from ingestion extraction
    extraction = meta.get("extraction") or {}
    image_selection = extraction.get("image_selection") or {}
    primary = image_selection.get("primary")

    if not primary:
        # Fallback: use first URL from image_urls_json
        image_urls_json = article.get("image_urls_json") or "[]"
        try:
            urls = json.loads(image_urls_json)
            if urls:
                primary = urls[0]
        except Exception:
            pass

    if primary:
        set_article_image_decision(int(article["id"]), primary, "select", actor="pipeline")
        return True
    return False


def _store_relevance(article_id: int, relevance: dict[str, Any]) -> None:
    """Persist relevance score and reason in article meta_json and relevance_score column."""
    article = get_article_by_id(article_id)
    if not article:
        return
    try:
        meta = json.loads(article.get("meta_json") or "{}")
    except Exception:
        meta = {}
    meta["relevance"] = relevance
    new_meta = json.dumps(meta, ensure_ascii=False)
    from .db import get_conn
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET meta_json = ?, relevance_score = ? WHERE id = ?",
            (new_meta, relevance.get("score", 0), article_id),
        )


def _do_rewrite_and_draft(article: dict[str, Any]) -> tuple[int, str | None]:
    """Rewrite article and create WP draft. Returns (wp_post_id, wp_post_url)."""
    article_id = int(article["id"])

    # Rewrite
    logger.info("_do_rewrite_and_draft #%d: starte OpenAI-Rewrite", article_id)
    rewritten = rewrite_article_text(article)
    logger.info("_do_rewrite_and_draft #%d: Rewrite fertig (%d Wörter), generiere Tags", article_id, len(rewritten.split()))
    tags: list[str] = []
    try:
        tags = generate_article_tags(article, rewritten_text=rewritten)
    except Exception:
        pass
    merged_meta = merge_generated_tags(article.get("meta_json"), tags)

    # Save rewritten content + approved status
    repo_upsert_article(
        ArticleUpsert(
            feed_id=article.get("feed_id"),
            source_article_id=article.get("source_article_id"),
            source_hash=article.get("source_hash"),
            title=article.get("title", ""),
            source_url=article.get("source_url", ""),
            canonical_url=article.get("canonical_url"),
            published_at=article.get("published_at"),
            author=article.get("author"),
            summary=article.get("summary"),
            content_raw=article.get("content_raw"),
            content_rewritten=rewritten,
            image_urls_json=article.get("image_urls_json"),
            press_contact=article.get("press_contact"),
            source_name_snapshot=article.get("source_name_snapshot"),
            source_terms_url_snapshot=article.get("source_terms_url_snapshot"),
            source_license_name_snapshot=article.get("source_license_name_snapshot"),
            legal_checked=bool(int(article.get("legal_checked", 0))),
            legal_checked_at=article.get("legal_checked_at"),
            legal_note=article.get("legal_note"),
            wp_post_id=article.get("wp_post_id"),
            wp_post_url=article.get("wp_post_url"),
            publish_attempts=int(article.get("publish_attempts", 0)),
            publish_last_error=article.get("publish_last_error"),
            published_to_wp_at=article.get("published_to_wp_at"),
            word_count=len(rewritten.split()),
            status="approved",
            meta_json=merged_meta,
        )
    )

    # Reload after save to get updated meta_json
    fresh = get_article_by_id(article_id)
    if not fresh:
        raise RuntimeError(f"Artikel #{article_id} nach Rewrite nicht gefunden")

    # Ensure a publish slot is reserved — reserve one now if not yet set
    if not fresh.get("scheduled_publish_at"):
        from .scheduler import reserve_publish_slot
        logger.info("_do_rewrite_and_draft #%d: kein Slot gesetzt, reserviere jetzt", article_id)
        reserve_publish_slot(article_id)
        fresh = get_article_by_id(article_id)
        if not fresh:
            raise RuntimeError(f"Artikel #{article_id} nach Slot-Reservierung nicht gefunden")

    # Create WP draft
    logger.info("_do_rewrite_and_draft #%d: erstelle/aktualisiere WP Draft (wp_post_id=%s, sched=%s)", article_id, fresh.get("wp_post_id"), fresh.get("scheduled_publish_at"))
    wp_post_id, wp_post_url = publish_article_draft(fresh)
    logger.info("_do_rewrite_and_draft #%d: WP Draft fertig (post_id=%s)", article_id, wp_post_id)

    # Update WP info in DB
    from .repositories import mark_article_publish_result
    mark_article_publish_result(
        article_id,
        wp_post_id=wp_post_id,
        wp_post_url=wp_post_url,
        error=None,
        increment_attempts=True,
        set_published_status=False,
    )

    return wp_post_id, wp_post_url


# ---------------------------------------------------------------------------
# Public pipeline functions
# ---------------------------------------------------------------------------

def run_auto_pipeline(trigger: str = "auto") -> dict[str, Any]:
    """Run the full automated pipeline and return stats dict."""
    from . import telegram_bot as tg

    settings = get_settings()
    stats = PipelineStats()

    tg.notify_pipeline_started(trigger)

    # Step 1: Ingestion
    try:
        ingest_result = run_ingestion()
        stats.ingested = ingest_result.articles_upserted
    except Exception as exc:
        tg.notify_error(f"Ingestion fehlgeschlagen: {exc}")
        logger.error("Ingestion error: %s", exc)
        stats.errors += 1

    # Step 2: Process new articles
    new_articles = list_articles(limit=100, status_filter="new")

    for article in new_articles:
        article_id = int(article["id"])
        try:
            _process_article(article, stats, settings)
        except Exception as exc:
            logger.error("Fehler bei Artikel #%d: %s", article_id, exc)
            tg.notify_error(f"Fehler bei Artikel #{article_id} ({article.get('title','?')[:50]}): {exc}")
            stats.errors += 1
        # Rate limiting between OpenAI calls
        time.sleep(1)

    # Step 3: Send rejected summary if any
    if stats.rejected_articles:
        try:
            tg.notify_rejected_summary(stats.rejected_articles)
        except Exception as exc:
            logger.warning("Telegram rejected summary fehlgeschlagen: %s", exc)

    # Step 4: Summary
    result = {
        "ingested": stats.ingested,
        "processed": stats.processed,
        "drafts_created": stats.drafts_created,
        "rejected": stats.rejected,
        "no_image": stats.no_image,
        "warnings": stats.warnings,
        "errors": stats.errors,
    }
    tg.notify_pipeline_done(result)
    return result


def _process_article(article: dict[str, Any], stats: PipelineStats, settings: Any) -> None:
    """Process a single new article through the pipeline."""
    from . import telegram_bot as tg

    article_id = int(article["id"])

    # Auto-select image
    _auto_select_image(article)

    # Reload to get updated image_review
    article = get_article_by_id(article_id) or article

    # Exclude articles without a usable image
    try:
        meta = json.loads(article.get("meta_json") or "{}")
    except Exception:
        meta = {}
    has_image = bool((meta.get("image_review") or {}).get("selected_url"))
    if not has_image:
        update_article_status(
            article_id,
            "no_image",
            actor="pipeline",
            note="Kein Bild vorhanden – Artikel ausgeschlossen",
        )
        stats.no_image += 1
        logger.info("Artikel #%d ausgeschlossen: kein Bild gefunden", article_id)
        try:
            tg.send_message(
                f"🖼️ <b>Kein Bild</b> – Artikel #{article_id} ausgeschlossen\n"
                f"📰 {(article.get('title') or '')[:80]}"
            )
        except Exception:
            pass
        return

    # Score relevance
    try:
        relevance = score_article_relevance(article)
    except Exception as exc:
        logger.warning("Relevanz-Scoring für #%d fehlgeschlagen: %s", article_id, exc)
        relevance = {"score": 0, "reason": f"Scoring-Fehler: {exc}", "topics": []}

    score = relevance.get("score", 0)
    reason = relevance.get("reason", "")
    _store_relevance(article_id, relevance)

    stats.processed += 1

    if score < settings.pipeline_relevance_warn:
        # Reject
        update_article_status(
            article_id,
            "error",
            actor="pipeline",
            note=f"Abgelehnt: Score {score}/100 — {reason}",
        )
        stats.rejected += 1
        # Reload for summary (now has relevance in meta)
        updated = get_article_by_id(article_id)
        if updated:
            stats.rejected_articles.append(updated)

    elif score < settings.pipeline_relevance_auto:
        # Warning zone: set status to "review" so repeated /run calls don't re-warn
        update_article_status(
            article_id,
            "review",
            actor="pipeline",
            note=f"Niedrige Relevanz: Score {score}/100 — {reason}",
        )
        stats.warnings += 1
        try:
            tg.notify_relevance_warning(article, score, reason)
        except Exception as exc:
            logger.warning("Telegram warning für #%d fehlgeschlagen: %s", article_id, exc)

    else:
        # Auto-process: rewrite + WP draft
        try:
            # Reserve publish slot FIRST so it's available when WP draft is created
            slot = reserve_publish_slot(article_id)

            # Reload article to get updated image_review + scheduled_publish_at
            fresh = get_article_by_id(article_id)
            if not fresh:
                return
            wp_post_id, wp_post_url = _do_rewrite_and_draft(fresh)
            stats.drafts_created += 1

            # Reload for notification
            final = get_article_by_id(article_id)
            if final:
                try:
                    tg.notify_new_draft(final, score=score, suggested_publish_at=slot)
                except Exception as exc:
                    logger.warning("Telegram draft-Benachrichtigung für #%d fehlgeschlagen: %s", article_id, exc)

        except Exception as exc:
            logger.error("Draft-Erstellung für #%d fehlgeschlagen: %s", article_id, exc)
            update_article_status(article_id, "error", actor="pipeline", note=f"Draft-Fehler: {exc}")
            raise


# ---------------------------------------------------------------------------
# Callback actions (called from telegram_bot._handle_callback)
# ---------------------------------------------------------------------------

def rewrite_and_update_draft(article_id: int) -> None:
    """Rewrite article and update the existing WP draft."""
    article = get_article_by_id(article_id)
    if not article:
        raise RuntimeError(f"Artikel #{article_id} nicht gefunden")
    _auto_select_image(article)
    fresh = get_article_by_id(article_id)
    _do_rewrite_and_draft(fresh)


def discard_article(article_id: int) -> None:
    """Discard a draft: delete WP post if exists, set article to error."""
    article = get_article_by_id(article_id)
    if not article:
        return

    wp_post_id = article.get("wp_post_id")
    if wp_post_id:
        try:
            from .wordpress import delete_wp_post
            delete_wp_post(int(wp_post_id))
        except Exception as exc:
            logger.warning("WP Post #%d konnte nicht gelöscht werden: %s", wp_post_id, exc)

    update_article_status(article_id, "error", actor="telegram", note="Via Telegram verworfen")


def override_rejected_article(article_id: int) -> None:
    """Force-process a previously rejected article."""
    from . import telegram_bot as tg

    article = get_article_by_id(article_id)
    if not article:
        raise RuntimeError(f"Artikel #{article_id} nicht gefunden")

    # Reset to new so processing is allowed
    update_article_status(article_id, "new", actor="telegram", note="Manuell übernommen via Telegram")

    # Reload
    fresh = get_article_by_id(article_id)
    if not fresh:
        return

    _auto_select_image(fresh)
    fresh = get_article_by_id(article_id)

    # Get existing score or re-score
    try:
        meta = json.loads(fresh.get("meta_json") or "{}")
        score = int((meta.get("relevance") or {}).get("score", 0))
    except Exception:
        score = 0

    # Reserve publish slot FIRST so it's in the DB when WP draft is created
    slot = reserve_publish_slot(article_id)
    fresh = get_article_by_id(article_id)

    wp_post_id, wp_post_url = _do_rewrite_and_draft(fresh)

    final = get_article_by_id(article_id)
    if final:
        tg.notify_new_draft(final, score=score, suggested_publish_at=slot)


# ---------------------------------------------------------------------------
# Status helpers (used by /status command)
# ---------------------------------------------------------------------------

def get_recently_rejected(days: int = 3) -> list[dict[str, Any]]:
    """Return articles rejected in the last N days."""
    from .db import get_conn
    from .db import rows_to_dicts
    cutoff = datetime.now(timezone.utc).isoformat()[:10]
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, meta_json, source_url, created_at
            FROM articles
            WHERE status IN ('error', 'review')
            AND json_extract(meta_json, '$.relevance.score') IS NOT NULL
            AND date(updated_at) >= date('now', ?)
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (f"-{days} days",),
        ).fetchall()
    return rows_to_dicts(rows)


def get_pipeline_status_text() -> str:
    """Return a text summary of current pipeline state."""
    from .repositories import list_articles as _list
    new_count = len(_list(limit=500, status_filter="new"))
    approved_count = len(_list(limit=500, status_filter="approved"))
    published_count = len(_list(limit=500, status_filter="published"))
    error_count = len(_list(limit=500, status_filter="error"))

    return (
        f"📊 <b>Pipeline-Status</b>\n"
        f"🆕 Neu / wartend: {new_count}\n"
        f"✅ Draft / freigegeben: {approved_count}\n"
        f"📢 Veröffentlicht: {published_count}\n"
        f"🚫 Fehler / abgelehnt: {error_count}"
    )
