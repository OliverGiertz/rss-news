from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import unquote, urlparse

import feedparser

from .policy import evaluate_source_policy
from .repositories import (
    ArticleUpsert,
    RunCreate,
    create_run,
    find_existing_article_for_upsert,
    finish_run,
    get_feed_by_id,
    list_enabled_feeds,
    update_feed_fetch_state,
    upsert_article,
)
from .source_extraction import extract_article, extracted_article_to_meta


@dataclass(frozen=True)
class IngestionStats:
    run_id: int
    feeds_processed: int
    entries_seen: int
    articles_upserted: int
    status: str
    message: str


MAX_FEED_FETCH_RETRIES = 3


def _entry_published_iso(entry: dict) -> str | None:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return None
    return datetime(*published[:6], tzinfo=timezone.utc).isoformat()


def _entry_text(entry: dict) -> tuple[str, str]:
    summary = entry.get("summary", "") or ""
    content = ""
    if entry.get("content") and isinstance(entry.get("content"), list):
        first = entry["content"][0]
        content = first.get("value", "") if isinstance(first, dict) else ""
    if not content:
        content = summary
    return summary, content


def _entry_hash(entry: dict, feed_id: int, link: str, title: str, summary: str) -> str:
    source_id = entry.get("id") or entry.get("guid") or ""
    published = _entry_published_iso(entry) or ""
    fingerprint = f"{feed_id}|{source_id}|{link}|{title.strip()}|{summary.strip()}|{published}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _parsed_get(parsed: object, key: str, default: object = None) -> object:
    if isinstance(parsed, dict):
        return parsed.get(key, default)
    return getattr(parsed, key, default)


def _normalize_tokens(text: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return {token for token in normalized.split() if len(token) >= 4}


def _rank_image_candidates(source_url: str, title: str, images: list[str]) -> list[dict[str, Any]]:
    source_host = (urlparse(source_url).hostname or "").lower()
    is_presseportal = "presseportal.de" in source_host
    title_tokens = _normalize_tokens(title)
    blocked_patterns = ("logo", "badge", "app-store", "google-play", "na-logo", "sprite", "icon", "favicon", "tracking", "pixel")

    ranked: list[dict[str, Any]] = []
    for url in images:
        parsed = urlparse(url)
        path = unquote(parsed.path.lower())
        full = f"{parsed.netloc.lower()}{path}"
        score = 0
        reasons: list[str] = []

        if any(token in full for token in blocked_patterns):
            score -= 150
            reasons.append("blocked-pattern")

        if is_presseportal and "/thumbnail/story_big/" in path:
            score += 120
            reasons.append("presseportal-story-big")
        elif is_presseportal and "/thumbnail/highlight/" in path:
            score += 45
            reasons.append("presseportal-highlight")
        elif is_presseportal and "/thumbnail/liste/" in path:
            score -= 40
            reasons.append("presseportal-list")

        if "crop=" in (parsed.query or "").lower():
            score -= 10
            reasons.append("cropped-preview")

        path_tokens = _normalize_tokens(path.replace("-", " "))
        overlap = len(title_tokens.intersection(path_tokens))
        if overlap > 0:
            score += min(30, overlap * 6)
            reasons.append(f"title-match:{overlap}")

        ranked.append({"url": url, "score": score, "reasons": reasons})

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def _select_relevant_images(source_url: str, title: str, images: list[str], max_keep: int = 3) -> tuple[list[str], str | None, list[dict[str, Any]]]:
    # dedupe incoming order first
    deduped: list[str] = []
    seen: set[str] = set()
    for image in images:
        if image and image not in seen:
            seen.add(image)
            deduped.append(image)

    ranked = _rank_image_candidates(source_url, title, deduped)
    kept = [item["url"] for item in ranked if item["score"] > 0][:max_keep]
    if not kept and ranked:
        kept = [ranked[0]["url"]]
    primary = kept[0] if kept else None
    return kept, primary, ranked


def _merge_ingestion_meta(existing_meta_json: str | None, attribution: dict[str, Any], extraction_meta: dict[str, Any]) -> str:
    meta: dict[str, Any] = {}
    if existing_meta_json:
        try:
            parsed = json.loads(existing_meta_json)
            if isinstance(parsed, dict):
                meta = parsed
        except Exception:
            meta = {}
    meta["attribution"] = attribution
    meta["extraction"] = extraction_meta
    return json.dumps(meta, ensure_ascii=False)


def run_ingestion(feed_id: int | None = None) -> IngestionStats:
    run_id = create_run(RunCreate(run_type="ingestion", status="running", details="started"))
    feeds_processed = 0
    entries_seen = 0
    articles_upserted = 0
    feed_results: list[dict[str, object]] = []

    try:
        if feed_id is not None:
            feed = get_feed_by_id(feed_id)
            feeds = [feed] if feed and int(feed.get("is_enabled", 0)) == 1 else []
        else:
            feeds = list_enabled_feeds()

        for feed in feeds:
            if not feed:
                continue
            feeds_processed += 1

            source_snapshot = {
                "id": feed.get("source_id"),
                "name": feed.get("source_name"),
                "base_url": feed.get("source_base_url"),
                "terms_url": feed.get("source_terms_url"),
                "license_name": feed.get("source_license_name"),
                "risk_level": feed.get("source_risk_level"),
                "last_reviewed_at": feed.get("source_last_reviewed_at"),
                "is_enabled": feed.get("source_is_enabled"),
            }
            policy_issues = evaluate_source_policy(source_snapshot)
            if policy_issues:
                feed_results.append(
                    {
                        "feed_id": int(feed["id"]),
                        "feed_url": feed["url"],
                        "status": "blocked",
                        "policy_issues": policy_issues,
                        "entries_seen": 0,
                        "upserts": 0,
                    }
                )
                continue

            parsed = None
            feed_error = None
            for attempt in range(1, MAX_FEED_FETCH_RETRIES + 1):
                try:
                    parsed = feedparser.parse(
                        feed["url"],
                        etag=feed.get("etag"),
                        modified=feed.get("last_modified"),
                    )
                    break
                except Exception as exc:
                    feed_error = str(exc)
                    if attempt < MAX_FEED_FETCH_RETRIES:
                        time.sleep(0.5 * attempt)

            if parsed is None:
                feed_results.append(
                    {
                        "feed_id": int(feed["id"]),
                        "feed_url": feed["url"],
                        "status": "failed",
                        "error": feed_error or "unknown",
                        "entries_seen": 0,
                        "upserts": 0,
                    }
                )
                continue

            # Persist ETag/Last-Modified for conditional requests.
            parsed_etag = _parsed_get(parsed, "etag")
            parsed_modified = _parsed_get(parsed, "modified")
            if parsed_modified and not isinstance(parsed_modified, str):
                parsed_modified = str(parsed_modified)
            update_feed_fetch_state(
                feed_id=int(feed["id"]),
                etag=parsed_etag if isinstance(parsed_etag, str) else None,
                last_modified=parsed_modified if isinstance(parsed_modified, str) else None,
            )

            feed_entries_seen = 0
            feed_upserts = 0
            for entry in _parsed_get(parsed, "entries", []):
                entries_seen += 1
                feed_entries_seen += 1
                link = entry.get("link")
                if not link:
                    continue

                summary, content_raw = _entry_text(entry)
                title = entry.get("title") or "Ohne Titel"
                extracted = extract_article(link)

                final_title = extracted.title or title
                final_author = extracted.author or entry.get("author")
                final_summary = extracted.summary or (summary[:1000] if summary else None)
                final_content_raw = extracted.content_text or content_raw
                final_canonical = extracted.canonical_url or entry.get("link")
                selected_images, primary_image, ranked_images = _select_relevant_images(
                    link,
                    final_title,
                    extracted.images,
                    max_keep=3,
                )

                source_hash = _entry_hash(
                    entry,
                    int(feed["id"]),
                    link,
                    final_title,
                    final_summary or "",
                )
                attribution = {
                    "source_name": feed.get("source_name"),
                    "source_base_url": feed.get("source_base_url"),
                    "source_terms_url": feed.get("source_terms_url"),
                    "source_license_name": feed.get("source_license_name"),
                    "source_risk_level": feed.get("source_risk_level"),
                    "original_link": link,
                    "feed_name": feed.get("name"),
                    "feed_id": int(feed["id"]),
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                }
                extraction_meta: dict[str, Any] = extracted_article_to_meta(extracted)
                extraction_meta["fetched_from"] = link
                extraction_meta["image_selection"] = {
                    "primary": primary_image,
                    "selected_count": len(selected_images),
                    "total_candidates": len(extracted.images),
                    "ranked": ranked_images,
                }
                base_payload = ArticleUpsert(
                    feed_id=int(feed["id"]),
                    source_article_id=entry.get("id") or entry.get("guid"),
                    source_hash=source_hash,
                    title=final_title,
                    source_url=link,
                    canonical_url=final_canonical,
                    published_at=_entry_published_iso(entry),
                    author=final_author,
                    summary=final_summary,
                    content_raw=final_content_raw,
                    content_rewritten=None,
                    image_urls_json=json.dumps(selected_images, ensure_ascii=False) if selected_images else None,
                    press_contact=extracted.press_contact,
                    source_name_snapshot=feed.get("source_name"),
                    source_terms_url_snapshot=feed.get("source_terms_url"),
                    source_license_name_snapshot=feed.get("source_license_name"),
                    legal_checked=False,
                    legal_checked_at=None,
                    legal_note=None,
                    wp_post_id=None,
                    wp_post_url=None,
                    publish_attempts=0,
                    publish_last_error=None,
                    published_to_wp_at=None,
                    word_count=len((final_content_raw or "").split()),
                    status="new",
                    meta_json=json.dumps({"attribution": attribution, "extraction": extraction_meta}, ensure_ascii=False),
                )
                existing = find_existing_article_for_upsert(base_payload)
                if existing and existing.get("status") == "error":
                    # Explicitly closed article: ignore on subsequent ingestion runs.
                    continue

                payload = base_payload
                if existing:
                    payload = ArticleUpsert(
                        feed_id=base_payload.feed_id,
                        source_article_id=base_payload.source_article_id,
                        source_hash=base_payload.source_hash,
                        title=base_payload.title,
                        source_url=base_payload.source_url,
                        canonical_url=base_payload.canonical_url,
                        published_at=base_payload.published_at,
                        author=base_payload.author,
                        summary=base_payload.summary,
                        content_raw=base_payload.content_raw,
                        content_rewritten=existing.get("content_rewritten"),
                        image_urls_json=base_payload.image_urls_json,
                        press_contact=base_payload.press_contact or existing.get("press_contact"),
                        source_name_snapshot=base_payload.source_name_snapshot,
                        source_terms_url_snapshot=base_payload.source_terms_url_snapshot,
                        source_license_name_snapshot=base_payload.source_license_name_snapshot,
                        legal_checked=bool(int(existing.get("legal_checked", 0))),
                        legal_checked_at=existing.get("legal_checked_at"),
                        legal_note=existing.get("legal_note"),
                        wp_post_id=existing.get("wp_post_id"),
                        wp_post_url=existing.get("wp_post_url"),
                        publish_attempts=int(existing.get("publish_attempts", 0)),
                        publish_last_error=existing.get("publish_last_error"),
                        published_to_wp_at=existing.get("published_to_wp_at"),
                        word_count=base_payload.word_count,
                        status=existing.get("status") or "new",
                        meta_json=_merge_ingestion_meta(existing.get("meta_json"), attribution, extraction_meta),
                    )

                article_id = upsert_article(payload)
                if article_id:
                    articles_upserted += 1
                    feed_upserts += 1

            feed_results.append(
                {
                    "feed_id": int(feed["id"]),
                    "feed_url": feed["url"],
                    "status": "success",
                    "entries_seen": feed_entries_seen,
                    "upserts": feed_upserts,
                }
            )

        finish_run(
            run_id=run_id,
            status="success",
            details=json.dumps(
                {
                    "feeds_processed": feeds_processed,
                    "entries_seen": entries_seen,
                    "upserts": articles_upserted,
                    "feeds": feed_results,
                },
                ensure_ascii=False,
            ),
        )
        return IngestionStats(
            run_id=run_id,
            feeds_processed=feeds_processed,
            entries_seen=entries_seen,
            articles_upserted=articles_upserted,
            status="success",
            message="Ingestion abgeschlossen",
        )
    except Exception as exc:
        finish_run(run_id=run_id, status="failed", details=str(exc))
        return IngestionStats(
            run_id=run_id,
            feeds_processed=feeds_processed,
            entries_seen=entries_seen,
            articles_upserted=articles_upserted,
            status="failed",
            message=str(exc),
        )
