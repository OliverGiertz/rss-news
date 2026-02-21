from __future__ import annotations

import base64
from html import escape
import json
import mimetypes
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import get_settings


def _auth_header(username: str, app_password: str) -> str:
    token = base64.b64encode(f"{username}:{app_password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _wp_request(
    *,
    base_url: str,
    auth_header: str,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/wp-json/wp/v2/{endpoint.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(
        url=url,
        data=data,
        method=method,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "rss-news-publisher/1.0",
        },
    )
    with urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw) if raw else {}
    return parsed if isinstance(parsed, dict) else {}


def _selected_image_url_from_meta(meta_json: str | None) -> str | None:
    if not meta_json:
        return None
    try:
        meta = json.loads(meta_json)
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    image_review = meta.get("image_review")
    if not isinstance(image_review, dict):
        return None
    selected = image_review.get("selected_url")
    return selected if isinstance(selected, str) and selected.strip() else None


def _download_image_bytes(url: str) -> tuple[bytes, str]:
    req = Request(
        url=url,
        headers={
            "User-Agent": "rss-news-publisher/1.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=20) as resp:
        raw = resp.read()
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
    if not content_type.lower().startswith("image/"):
        raise RuntimeError(f"Ausgewählte Bild-URL liefert kein Bild ({content_type})")
    return raw, content_type


def _guess_filename(image_url: str, content_type: str) -> str:
    parsed = urlparse(image_url)
    stem = Path(parsed.path).name or "article-image"
    if "." not in stem:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
        stem = f"{stem}{ext}"
    return stem


def _upload_featured_media(
    *,
    base_url: str,
    auth_header: str,
    image_url: str,
    article_title: str,
    source_url: str,
) -> int:
    image_bytes, content_type = _download_image_bytes(image_url)
    filename = _guess_filename(image_url, content_type)

    media_url = f"{base_url.rstrip('/')}/wp-json/wp/v2/media"
    media_req = Request(
        url=media_url,
        data=image_bytes,
        method="POST",
        headers={
            "Authorization": auth_header,
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Accept": "application/json",
            "User-Agent": "rss-news-publisher/1.0",
        },
    )
    with urlopen(media_req, timeout=30) as resp:
        media_raw = resp.read().decode("utf-8", errors="replace")
    media_payload = json.loads(media_raw) if media_raw else {}
    media_id = int(media_payload.get("id", 0)) if isinstance(media_payload, dict) else 0
    if media_id <= 0:
        raise RuntimeError(f"WordPress Media-Upload fehlgeschlagen: {media_payload}")

    # Optional metadata update for traceability.
    _wp_request(
        base_url=base_url,
        auth_header=auth_header,
        method="POST",
        endpoint=f"media/{media_id}",
        payload={
            "title": f"{article_title[:120]} - Bild",
            "caption": f"Quelle: {source_url}",
            "alt_text": article_title[:200],
        },
    )
    return media_id


def _as_paragraph_html(text: str) -> str:
    chunks = [chunk.strip() for chunk in re.split(r"\n{2,}", text.strip()) if chunk.strip()]
    if not chunks:
        return ""
    lines = []
    for chunk in chunks:
        compact = re.sub(r"\s*\n\s*", " ", chunk)
        lines.append(f"<p>{escape(compact)}</p>")
    return "\n".join(lines)


def _build_post_content(article: dict[str, Any]) -> tuple[str, str | None]:
    source_url = article.get("source_url") or ""
    canonical_url = article.get("canonical_url") or source_url
    summary = (article.get("summary") or "").strip()
    body_text = (article.get("content_rewritten") or article.get("content_raw") or "").strip()
    if not body_text:
        body_text = summary

    # Keep existing HTML if already present, otherwise wrap plain text into paragraphs.
    has_html = bool(re.search(r"<[a-zA-Z][^>]*>", body_text))
    body_html = body_text if has_html else _as_paragraph_html(body_text)
    if not body_html:
        body_html = "<p>Kein Inhalt verfügbar.</p>"

    author = (article.get("author") or "").strip()
    published_at = (article.get("published_at") or "").strip()
    source_name = (article.get("source_name_snapshot") or "").strip()
    license_name = (article.get("source_license_name_snapshot") or "").strip()
    terms_url = (article.get("source_terms_url_snapshot") or "").strip()
    press_contact = (article.get("press_contact") or "").strip()

    lead_html = f"<p><em>{escape(summary)}</em></p>\n" if summary else ""

    facts: list[str] = []
    if author:
        facts.append(f"<li><strong>Autor:</strong> {escape(author)}</li>")
    if published_at:
        facts.append(f"<li><strong>Veröffentlicht (Quelle):</strong> {escape(published_at)}</li>")
    if source_name:
        facts.append(f"<li><strong>Quelle:</strong> {escape(source_name)}</li>")
    if license_name:
        facts.append(f"<li><strong>Lizenz:</strong> {escape(license_name)}</li>")
    if terms_url:
        facts.append(f"<li><strong>Lizenzhinweise:</strong> <a href=\"{escape(terms_url)}\">{escape(terms_url)}</a></li>")

    facts_html = (
        "<h3>Artikeldetails</h3>\n<ul>\n" + "\n".join(facts) + "\n</ul>\n"
        if facts
        else ""
    )
    press_contact_html = (
        f"<h3>Pressekontakt</h3>\n<p>{escape(press_contact)}</p>\n" if press_contact else ""
    )
    attribution_html = (
        "<hr />\n<section class=\"rss-news-attribution\">\n"
        "<h3>Quelle</h3>\n"
        f"<p>Originalartikel: <a href=\"{escape(source_url)}\">{escape(source_url)}</a></p>\n"
    )
    if canonical_url and canonical_url != source_url:
        attribution_html += f"<p>Canonical: <a href=\"{escape(canonical_url)}\">{escape(canonical_url)}</a></p>\n"
    attribution_html += "</section>"

    content = f"{lead_html}{body_html}\n\n{facts_html}{press_contact_html}{attribution_html}".strip()
    excerpt_source = summary or re.sub(r"\s+", " ", body_text).strip()
    excerpt = excerpt_source[:220] if excerpt_source else None
    return content, excerpt


def publish_article_draft(article: dict[str, Any]) -> tuple[int, str | None]:
    settings = get_settings()
    if not settings.wordpress_base_url or not settings.wordpress_username or not settings.wordpress_app_password:
        raise RuntimeError("WordPress Konfiguration fehlt (base_url, username, app_password)")

    auth = _auth_header(settings.wordpress_username, settings.wordpress_app_password)

    title = (article.get("title") or "Ohne Titel").strip()
    content, excerpt = _build_post_content(article)
    source_url = article.get("source_url") or ""

    featured_media_id = None
    selected_image_url = _selected_image_url_from_meta(article.get("meta_json"))
    if selected_image_url:
        featured_media_id = _upload_featured_media(
            base_url=settings.wordpress_base_url,
            auth_header=auth,
            image_url=selected_image_url,
            article_title=title,
            source_url=source_url,
        )

    payload = {
        "title": title,
        "content": content,
        "status": settings.wordpress_default_status,
    }
    if excerpt:
        payload["excerpt"] = excerpt
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    wp_post_id = article.get("wp_post_id")
    if wp_post_id:
        result = _wp_request(
            base_url=settings.wordpress_base_url,
            auth_header=auth,
            method="POST",
            endpoint=f"posts/{int(wp_post_id)}",
            payload=payload,
        )
    else:
        result = _wp_request(
            base_url=settings.wordpress_base_url,
            auth_header=auth,
            method="POST",
            endpoint="posts",
            payload=payload,
        )

    post_id = int(result.get("id", 0))
    if post_id <= 0:
        raise RuntimeError(f"WordPress Antwort ohne Post-ID: {result}")
    post_url = result.get("link")
    return post_id, post_url if isinstance(post_url, str) else None


def selected_image_exists(article: dict[str, Any]) -> bool:
    return _selected_image_url_from_meta(article.get("meta_json")) is not None
