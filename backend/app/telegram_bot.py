"""Telegram Bot integration for RSS-News pipeline notifications and controls."""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import get_settings

logger = logging.getLogger(__name__)

_BASE = "https://api.telegram.org/bot{token}/{method}"
_N8N_APP_RELEASE_WEBHOOK = "https://n8n.vanityontour.de/webhook/tg-app-release-bot-v1/webhook"


# ---------------------------------------------------------------------------
# Low-level API helpers
# ---------------------------------------------------------------------------

def _call(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    token = settings.telegram_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nicht konfiguriert")
    url = _BASE.format(token=token, method=method)
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url=url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except URLError as exc:
        logger.error("Telegram API Fehler (%s): %s", method, exc)
        raise RuntimeError(f"Telegram API Fehler: {exc}") from exc


def _chat_id() -> str:
    settings = get_settings()
    cid = settings.telegram_chat_id
    if not cid:
        raise RuntimeError("TELEGRAM_CHAT_ID nicht konfiguriert")
    return cid


def _inline_keyboard(buttons: list[list[dict[str, str]]]) -> dict:
    return {"inline_keyboard": buttons}


# ---------------------------------------------------------------------------
# Public send functions
# ---------------------------------------------------------------------------

def send_message(text: str, reply_markup: dict | None = None, parse_mode: str = "HTML") -> dict:
    payload: dict[str, Any] = {
        "chat_id": _chat_id(),
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _call("sendMessage", payload)


def send_photo_message(
    photo_url: str,
    caption: str,
    reply_markup: dict | None = None,
    parse_mode: str = "HTML",
) -> dict:
    payload: dict[str, Any] = {
        "chat_id": _chat_id(),
        "photo": photo_url,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        return _call("sendPhoto", payload)
    except Exception:
        # Fall back to text message if photo fails (e.g. image URL no longer valid)
        return send_message(caption, reply_markup=reply_markup, parse_mode=parse_mode)


def answer_callback_query(callback_query_id: str, text: str = "") -> None:
    try:
        _call("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})
    except Exception as exc:
        logger.warning("answerCallbackQuery fehlgeschlagen: %s", exc)


def edit_message_reply_markup(chat_id: str, message_id: int, reply_markup: dict | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    else:
        payload["reply_markup"] = {"inline_keyboard": []}
    try:
        _call("editMessageReplyMarkup", payload)
    except Exception as exc:
        logger.warning("editMessageReplyMarkup fehlgeschlagen: %s", exc)


def setup_webhook(webhook_url: str) -> dict:
    settings = get_settings()
    payload: dict[str, Any] = {"url": webhook_url, "allowed_updates": ["message", "callback_query"]}
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret
    return _call("setWebhook", payload)


def delete_webhook() -> dict:
    return _call("deleteWebhook", {})


def _forward_to_n8n_app_release(update: dict[str, Any]) -> None:
    """Forward a Telegram update to the N8N App Release webhook."""
    try:
        data = json.dumps(update).encode("utf-8")
        req = Request(
            url=_N8N_APP_RELEASE_WEBHOOK,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as _:
            pass
    except Exception as exc:
        logger.debug("N8N App-Release-Forward fehlgeschlagen: %s", exc)


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------

def _format_tags(meta_json: str | None) -> str:
    if not meta_json:
        return ""
    try:
        meta = json.loads(meta_json)
        tags = meta.get("generated_tags") or []
        if tags:
            return " ".join(f"#{t.replace(' ', '_')}" for t in tags[:6])
    except Exception:
        pass
    return ""


def _score_emoji(score: int) -> str:
    if score >= 85:
        return "🟢"
    if score >= 70:
        return "🟡"
    return "🔴"


def notify_new_draft(
    article: dict[str, Any],
    score: int,
    suggested_publish_at: str | None = None,
) -> None:
    """Send Telegram notification for a newly created WP draft."""
    title = (article.get("title") or "Ohne Titel").strip()
    wp_url = article.get("wp_post_url") or ""
    tags_str = _format_tags(article.get("meta_json"))
    art_id = article.get("id")

    score_line = f"{_score_emoji(score)} Relevanz-Score: <b>{score}/100</b>"
    publish_line = f"📅 Vorgeschlagene Veröffentlichung: <b>{suggested_publish_at}</b>" if suggested_publish_at else ""
    link_line = f'🔗 <a href="{wp_url}">Draft in WordPress öffnen</a>' if wp_url else ""
    tags_line = f"🏷 {tags_str}" if tags_str else ""

    text_parts = [
        f"✅ <b>Neuer Draft erstellt</b>",
        f"📰 <b>{title}</b>",
        score_line,
    ]
    if publish_line:
        text_parts.append(publish_line)
    if tags_line:
        text_parts.append(tags_line)
    if link_line:
        text_parts.append(link_line)

    text = "\n".join(text_parts)

    keyboard = _inline_keyboard([
        [
            {"text": "✏️ Neu schreiben", "callback_data": f"rewrite:{art_id}"},
            {"text": "❌ Verwerfen", "callback_data": f"discard:{art_id}"},
        ]
    ])

    # Try with image first
    meta = {}
    try:
        meta = json.loads(article.get("meta_json") or "{}")
    except Exception:
        pass
    image_url = None
    image_review = meta.get("image_review") or {}
    if isinstance(image_review, dict):
        image_url = image_review.get("selected_url")
    if not image_url:
        image_sel = (meta.get("extraction") or {}).get("image_selection") or {}
        image_url = image_sel.get("primary")

    if image_url:
        send_photo_message(image_url, caption=text, reply_markup=keyboard)
    else:
        send_message(text, reply_markup=keyboard)


def notify_relevance_warning(article: dict[str, Any], score: int, reason: str) -> None:
    """Send Telegram warning for borderline articles (score between warn and auto thresholds)."""
    title = (article.get("title") or "Ohne Titel").strip()
    art_id = article.get("id")
    source_url = article.get("source_url") or ""

    text = (
        f"⚠️ <b>Artikel mit niedrigem Relevanz-Score</b>\n"
        f"📰 <b>{title}</b>\n"
        f"{_score_emoji(score)} Score: <b>{score}/100</b>\n"
        f"💬 {reason}\n"
        f'🔗 <a href="{source_url}">Originalartikel</a>'
    )
    keyboard = _inline_keyboard([
        [
            {"text": "➕ Trotzdem verarbeiten", "callback_data": f"override:{art_id}"},
            {"text": "❌ Ablehnen", "callback_data": f"reject:{art_id}"},
        ]
    ])
    send_message(text, reply_markup=keyboard)


def notify_rejected_summary(articles: list[dict[str, Any]]) -> None:
    """Send summary of rejected articles for this pipeline run."""
    if not articles:
        return
    lines = [f"🚫 <b>{len(articles)} Artikel abgelehnt (Score &lt; {get_settings().pipeline_relevance_warn})</b>\n"]
    for art in articles[:10]:
        title = (art.get("title") or "Ohne Titel")[:60]
        score = _get_relevance_score(art)
        reason = _get_rejection_reason(art)
        art_id = art.get("id")
        lines.append(f"• <b>{title}</b> (Score: {score}) — {reason}")
    if len(articles) > 10:
        lines.append(f"... und {len(articles) - 10} weitere")

    text = "\n".join(lines)
    # Build override buttons for first 5
    rows = []
    for art in articles[:5]:
        art_id = art.get("id")
        title = (art.get("title") or "")[:25]
        rows.append([{"text": f"➕ {title}…", "callback_data": f"override:{art_id}"}])

    keyboard = _inline_keyboard(rows) if rows else None
    send_message(text, reply_markup=keyboard)


def notify_error(message: str) -> None:
    """Send error alert to Telegram."""
    try:
        send_message(f"🔴 <b>Fehler im RSS-Pipeline</b>\n{message}")
    except Exception as exc:
        logger.error("Telegram Fehler-Benachrichtigung fehlgeschlagen: %s", exc)


def notify_pipeline_started(trigger: str = "auto") -> None:
    icon = "🤖" if trigger == "auto" else "👤"
    try:
        send_message(f"{icon} Pipeline gestartet (Auslöser: {trigger})")
    except Exception:
        pass


def notify_pipeline_done(stats: dict[str, Any]) -> None:
    ingested = stats.get("ingested", 0)
    processed = stats.get("processed", 0)
    drafts = stats.get("drafts_created", 0)
    rejected = stats.get("rejected", 0)
    warnings = stats.get("warnings", 0)
    errors = stats.get("errors", 0)

    lines = [
        "📊 <b>Pipeline abgeschlossen</b>",
        f"📥 Neue Artikel importiert: {ingested}",
        f"⚙️ Verarbeitet: {processed}",
        f"📝 Drafts erstellt: {drafts}",
    ]
    if rejected:
        lines.append(f"🚫 Abgelehnt: {rejected}")
    if warnings:
        lines.append(f"⚠️ Warnungen: {warnings}")
    if errors:
        lines.append(f"🔴 Fehler: {errors}")

    try:
        send_message("\n".join(lines))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helper to read relevance info from meta_json
# ---------------------------------------------------------------------------

def _get_relevance_score(article: dict[str, Any]) -> int:
    try:
        meta = json.loads(article.get("meta_json") or "{}")
        return int(meta.get("relevance", {}).get("score", 0))
    except Exception:
        return 0


def _get_rejection_reason(article: dict[str, Any]) -> str:
    try:
        meta = json.loads(article.get("meta_json") or "{}")
        return str(meta.get("relevance", {}).get("reason", ""))[:80]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Incoming update handler (called by webhook endpoint)
# ---------------------------------------------------------------------------

def handle_update(update: dict[str, Any]) -> None:
    """Process an incoming Telegram update."""
    # Import here to avoid circular imports
    from . import pipeline as _pipeline

    if "callback_query" in update:
        _handle_callback(update["callback_query"])
    elif "message" in update:
        _handle_message(update["message"])


def _handle_message(message: dict[str, Any]) -> None:
    from . import pipeline as _pipeline

    text = (message.get("text") or "").strip()
    if not text.startswith("/"):
        return

    cmd = text.split()[0].lower().lstrip("/")
    if "@" in cmd:
        cmd = cmd.split("@")[0]

    if cmd == "run":
        send_message("🤖 Pipeline wird manuell gestartet …")
        try:
            stats = _pipeline.run_auto_pipeline(trigger="manual")
            notify_pipeline_done(stats)
        except Exception as exc:
            notify_error(f"/run fehlgeschlagen: {exc}")

    elif cmd == "rejected":
        try:
            articles = _pipeline.get_recently_rejected(days=3)
            if not articles:
                send_message("✅ Keine abgelehnten Artikel in den letzten 3 Tagen.")
            else:
                notify_rejected_summary(articles)
        except Exception as exc:
            notify_error(f"/rejected fehlgeschlagen: {exc}")

    elif cmd == "status":
        try:
            status_text = _pipeline.get_pipeline_status_text()
            send_message(status_text)
        except Exception as exc:
            notify_error(f"/status fehlgeschlagen: {exc}")

    elif cmd == "help":
        send_message(
            "📋 <b>Verfügbare Befehle</b>\n"
            "/run — Pipeline manuell starten\n"
            "/rejected — Abgelehnte Artikel der letzten 3 Tage\n"
            "/status — Pipeline-Status\n"
            "/help — Diese Hilfe"
        )

    else:
        # Unbekannter Befehl → an N8N App-Release-Workflow weiterleiten
        _forward_to_n8n_app_release({"message": message})


def _handle_callback(callback_query: dict[str, Any]) -> None:
    from . import pipeline as _pipeline
    from .repositories import get_article_by_id, update_article_status

    query_id = callback_query.get("id", "")
    data = (callback_query.get("data") or "").strip()
    chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))
    message_id = int(callback_query.get("message", {}).get("message_id", 0))

    if ":" not in data:
        answer_callback_query(query_id, "Ungültige Aktion")
        return

    action, _, raw_id = data.partition(":")
    try:
        article_id = int(raw_id)
    except ValueError:
        answer_callback_query(query_id, "Ungültige Artikel-ID")
        return

    article = get_article_by_id(article_id)
    if not article:
        answer_callback_query(query_id, "Artikel nicht gefunden")
        return

    # Answer Telegram immediately so the spinning indicator stops
    action_labels = {
        "rewrite": "✏️ Artikel wird neu geschrieben …",
        "discard": "❌ Artikel verworfen",
        "override": "➕ Artikel wird verarbeitet …",
        "reject": "🚫 Abgelehnt",
    }
    answer_callback_query(query_id, action_labels.get(action, ""))
    edit_message_reply_markup(chat_id, message_id)

    logger.info("Callback: action=%s article_id=%s", action, article_id)

    if action == "rewrite":
        try:
            _pipeline.rewrite_and_update_draft(article_id)
            updated = get_article_by_id(article_id)
            if updated:
                from .scheduler import suggest_publish_slot
                slot = suggest_publish_slot()
                notify_new_draft(updated, score=_get_relevance_score(updated), suggested_publish_at=slot)
        except Exception as exc:
            logger.error("Rewrite #%d fehlgeschlagen: %s", article_id, exc)
            notify_error(f"Rewrite #{article_id} fehlgeschlagen: {exc}")

    elif action == "discard":
        try:
            _pipeline.discard_article(article_id)
        except Exception as exc:
            logger.error("Discard #%d fehlgeschlagen: %s", article_id, exc)
            notify_error(f"Verwerfen #{article_id} fehlgeschlagen: {exc}")

    elif action == "override":
        try:
            _pipeline.override_rejected_article(article_id)
        except Exception as exc:
            logger.error("Override #%d fehlgeschlagen: %s", article_id, exc)
            notify_error(f"Override #{article_id} fehlgeschlagen: {exc}")

    elif action == "reject":
        update_article_status(article_id, "error", actor="telegram", note="Manuell abgelehnt via Telegram")

    else:
        logger.warning("Unbekannte Callback-Aktion: %s", action)
