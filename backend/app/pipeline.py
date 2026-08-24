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
    clear_article_editorial_review,
    list_articles,
    set_article_editorial_review,
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
    pending_review: int = 0
    rejected: int = 0
    quality_gate_rejected: int = 0
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


def editorial_gate_active() -> bool:
    """Is the human sign-off required before an article may be published?"""
    return bool(getattr(get_settings(), "editorial_review_required", True))


def post_rewrite_status() -> str:
    """Status an article gets right after a rewrite.

    With the gate active it waits for a person; without it, it goes straight to
    `approved` the way it did before. Every rewrite path in the app uses this so
    none of them can quietly become a back door into publishing.
    """
    return "pending_review" if editorial_gate_active() else "approved"


def _do_rewrite_and_draft(
    article: dict[str, Any],
    *,
    create_wp_draft: bool = True,
) -> tuple[int | None, str | None]:
    """Rewrite article and (optionally) create the WP draft.

    With `create_wp_draft=False` the article stops at status `pending_review`:
    no publish slot, no WordPress post. That is the editorial gate — a human
    signs the article off in the portal first (Art. 50 Abs. 4 KI-VO), and only
    then does `approve_article()` finish the job.

    Returns (wp_post_id, wp_post_url), both None when the draft was skipped.
    """
    article_id = int(article["id"])
    settings = get_settings()

    # ── Quality gate 1: raw content length ──────────────────────────────────
    import re as _re
    raw_text = _re.sub(r"<[^>]+>", " ", article.get("content_raw") or "")
    raw_words = len(raw_text.split())
    if raw_words < settings.pipeline_min_words_raw:
        note = (
            f"Zu wenig Rohinhalt: {raw_words} Wörter "
            f"(Minimum: {settings.pipeline_min_words_raw})"
        )
        logger.warning("_do_rewrite_and_draft #%d: %s — überspringe", article_id, note)
        update_article_status(article_id, "error", actor="pipeline", note=note)
        raise ValueError(note)

    # Rewrite
    logger.info("_do_rewrite_and_draft #%d: starte OpenAI-Rewrite (%d Roh-Wörter)", article_id, raw_words)
    rewritten = rewrite_article_text(article)

    # ── Quality gate 2: rewritten content length ─────────────────────────────
    rewritten_words = len(rewritten.split())
    if rewritten_words < settings.pipeline_min_words_rewritten:
        note = (
            f"Rewrite zu kurz: {rewritten_words} Wörter "
            f"(Minimum: {settings.pipeline_min_words_rewritten})"
        )
        logger.warning("_do_rewrite_and_draft #%d: %s — überspringe", article_id, note)
        update_article_status(article_id, "error", actor="pipeline", note=note)
        raise ValueError(note)
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
            status="approved" if create_wp_draft else "pending_review",
            meta_json=merged_meta,
        )
    )

    # Reload after save to get updated meta_json
    fresh = get_article_by_id(article_id)
    if not fresh:
        raise RuntimeError(f"Artikel #{article_id} nach Rewrite nicht gefunden")

    if not create_wp_draft:
        # The text is new, so an older sign-off no longer covers it.
        clear_article_editorial_review(article_id)
        logger.info(
            "_do_rewrite_and_draft #%d: Rewrite gespeichert, wartet auf redaktionelle Freigabe",
            article_id,
        )
        return None, None

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
        "pending_review": stats.pending_review,
        "rejected": stats.rejected,
        "quality_gate_rejected": stats.quality_gate_rejected,
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
        # Auto-process: rewrite, then either park the article for the editorial
        # sign-off or (gate disabled) go straight to the WP draft as before.
        gate = editorial_gate_active()
        try:
            # Without the gate the slot must exist before the WP draft is built.
            # With the gate the slot is reserved at approval time instead, so a
            # pending article does not sit on a publish slot for hours.
            slot: str | None = None
            if not gate:
                slot = reserve_publish_slot(article_id)

            # Reload article to get updated image_review + scheduled_publish_at
            fresh = get_article_by_id(article_id)
            if not fresh:
                return
            _do_rewrite_and_draft(fresh, create_wp_draft=not gate)

            # Reload for notification
            final = get_article_by_id(article_id)
            if gate:
                stats.pending_review += 1
                if final:
                    try:
                        tg.notify_pending_review(final, score=score)
                    except Exception as exc:
                        logger.warning("Telegram Freigabe-Hinweis für #%d fehlgeschlagen: %s", article_id, exc)
            else:
                stats.drafts_created += 1
                if final:
                    try:
                        tg.notify_new_draft(final, score=score, suggested_publish_at=slot)
                    except Exception as exc:
                        logger.warning("Telegram draft-Benachrichtigung für #%d fehlgeschlagen: %s", article_id, exc)

        except ValueError as exc:
            # Quality gate rejection (too short etc.) — status already set in _do_rewrite_and_draft
            # Release the reserved slot so it's available for the next article
            from .scheduler import release_publish_slot
            release_publish_slot(article_id)
            # Clean up any stale WP draft from a previous pipeline run
            stale = get_article_by_id(article_id)
            if stale and stale.get("wp_post_id"):
                try:
                    from .wordpress import delete_wp_post
                    delete_wp_post(int(stale["wp_post_id"]))
                    logger.info("Artikel #%d: veralteten WP-Draft #%s gelöscht", article_id, stale["wp_post_id"])
                except Exception as del_exc:
                    logger.warning("Artikel #%d: WP-Draft konnte nicht gelöscht werden: %s", article_id, del_exc)
            stats.quality_gate_rejected += 1
            logger.info("Artikel #%d wegen Qualitätsprüfung abgelehnt: %s", article_id, exc)
            # Individual Telegram notification for quality gate rejection
            try:
                title = (article.get("title") or "Ohne Titel")[:80]
                tg.send_message(
                    f"✂️ <b>Qualitätsprüfung nicht bestanden</b>\n"
                    f"📰 {title}\n"
                    f"💯 Score: {score}/100\n"
                    f"⚠️ {exc}"
                )
            except Exception as tg_exc:
                logger.warning("Telegram QG-Benachrichtigung für #%d fehlgeschlagen: %s", article_id, tg_exc)

        except Exception as exc:
            logger.error("Draft-Erstellung für #%d fehlgeschlagen: %s", article_id, exc)
            update_article_status(article_id, "error", actor="pipeline", note=f"Draft-Fehler: {exc}")
            # Release reserved slot so it's not permanently blocked by a failed article
            from .scheduler import release_publish_slot
            release_publish_slot(article_id)
            raise


# ---------------------------------------------------------------------------
# Callback actions (called from telegram_bot._handle_callback)
# ---------------------------------------------------------------------------

def rewrite_and_update_draft(article_id: int) -> None:
    """Rewrite article and update the existing WP draft.

    An article that already lives in WordPress keeps its post updated. One that
    never got there (because it is waiting for the editorial sign-off) stays in
    the review queue and must be approved again after the rewrite.
    """
    article = get_article_by_id(article_id)
    if not article:
        raise RuntimeError(f"Artikel #{article_id} nicht gefunden")
    _auto_select_image(article)
    fresh = get_article_by_id(article_id)
    gate = editorial_gate_active()
    keep_wp_in_sync = bool(fresh.get("wp_post_id")) or not gate
    _do_rewrite_and_draft(fresh, create_wp_draft=keep_wp_in_sync)


def approve_article(article_id: int, actor: str, note: str | None = None) -> dict[str, Any]:
    """Record the human editorial sign-off, then publish to WP and schedule it.

    This is the single door to `approved`: it stamps who approved and when
    (Art. 50 Abs. 4 KI-VO), reserves the publish slot and creates the scheduled
    WordPress post. If WordPress fails, the article falls back into the review
    queue with its slot released, so the approval can simply be repeated.
    """
    from . import telegram_bot as tg

    article = get_article_by_id(article_id)
    if not article:
        raise RuntimeError(f"Artikel #{article_id} nicht gefunden")

    if not (article.get("content_rewritten") or "").strip():
        raise ValueError("Kein Rewrite-Text vorhanden — Artikel kann nicht freigegeben werden")
    if not selected_image_exists(article):
        raise ValueError("Kein Hauptbild ausgewählt — Artikel kann nicht freigegeben werden")

    reviewed_at = set_article_editorial_review(article_id, actor=actor, note=note)
    update_article_status(
        article_id,
        "approved",
        actor=actor,
        note=note or "Redaktionell geprüft und freigegeben",
        decision="editorial_approval",
    )

    try:
        slot = reserve_publish_slot(article_id)
        fresh = get_article_by_id(article_id)
        if not fresh:
            raise RuntimeError(f"Artikel #{article_id} nach Freigabe nicht gefunden")
        wp_post_id, wp_post_url = publish_article_draft(fresh)
    except Exception as exc:
        from .scheduler import release_publish_slot
        release_publish_slot(article_id)
        update_article_status(
            article_id,
            "pending_review",
            actor="system",
            note=f"WordPress-Fehler nach Freigabe: {exc}",
        )
        logger.error("Freigabe von #%d fehlgeschlagen: %s", article_id, exc)
        raise

    from .repositories import mark_article_publish_result
    mark_article_publish_result(
        article_id,
        wp_post_id=wp_post_id,
        wp_post_url=wp_post_url,
        error=None,
        increment_attempts=True,
        set_published_status=False,
    )

    final = get_article_by_id(article_id) or {}
    try:
        tg.notify_approved(final, scheduled_at=slot)
    except Exception as exc:
        logger.warning("Telegram Freigabe-Bestätigung für #%d fehlgeschlagen: %s", article_id, exc)

    return {
        "article_id": article_id,
        "reviewed_at": reviewed_at,
        "reviewed_by": actor,
        "scheduled_publish_at": slot,
        "wp_post_id": wp_post_id,
        "wp_post_url": wp_post_url,
    }


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

    gate = editorial_gate_active()
    if gate:
        # "Trotzdem verarbeiten" means process it, not publish it — the article
        # still has to pass the editorial sign-off in the portal.
        _do_rewrite_and_draft(fresh, create_wp_draft=False)
        final = get_article_by_id(article_id)
        if final:
            tg.notify_pending_review(final, score=score)
        return

    # Reserve publish slot FIRST so it's in the DB when WP draft is created
    slot = reserve_publish_slot(article_id)
    fresh = get_article_by_id(article_id)

    _do_rewrite_and_draft(fresh)

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
    pending_count = len(_list(limit=500, status_filter="pending_review"))
    approved_count = len(_list(limit=500, status_filter="approved"))
    published_count = len(_list(limit=500, status_filter="published"))
    error_count = len(_list(limit=500, status_filter="error"))

    return (
        f"📊 <b>Pipeline-Status</b>\n"
        f"🆕 Neu / wartend: {new_count}\n"
        f"📝 Wartet auf Freigabe: {pending_count}\n"
        f"✅ Draft / freigegeben: {approved_count}\n"
        f"📢 Veröffentlicht: {published_count}\n"
        f"🚫 Fehler / abgelehnt: {error_count}"
    )
