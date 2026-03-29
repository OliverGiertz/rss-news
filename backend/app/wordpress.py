from __future__ import annotations

import base64
from html import escape
import json
import mimetypes
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote_plus, urlparse
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
) -> Any:
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
    return json.loads(raw) if raw else {}


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


def _selected_tags_from_meta(meta_json: str | None) -> list[str]:
    if not meta_json:
        return []
    try:
        meta = json.loads(meta_json)
    except Exception:
        return []
    if not isinstance(meta, dict):
        return []
    raw_tags = meta.get("generated_tags")
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw_tags:
        value = str(item or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        tags.append(value)
        if len(tags) >= 12:
            break
    return tags


def _resolve_wp_tag_ids(*, base_url: str, auth_header: str, tags: list[str]) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for tag in tags:
        name = tag.strip()
        if not name:
            continue
        try:
            endpoint = f"tags?search={quote_plus(name)}&per_page=20"
            result = _wp_request(base_url=base_url, auth_header=auth_header, method="GET", endpoint=endpoint)
            tag_id: int | None = None
            if isinstance(result, list):
                for row in result:
                    if not isinstance(row, dict):
                        continue
                    row_name = str(row.get("name") or "")
                    rid = int(row.get("id", 0) or 0)
                    if rid <= 0:
                        continue
                    if row_name.casefold() == name.casefold():
                        tag_id = rid
                        break
                if tag_id is None:
                    for row in result:
                        if isinstance(row, dict) and int(row.get("id", 0) or 0) > 0:
                            tag_id = int(row.get("id", 0))
                            break
            if tag_id is None:
                created = _wp_request(
                    base_url=base_url,
                    auth_header=auth_header,
                    method="POST",
                    endpoint="tags",
                    payload={"name": name},
                )
                if isinstance(created, dict):
                    rid = int(created.get("id", 0) or 0)
                    if rid > 0:
                        tag_id = rid
            if tag_id is not None and tag_id > 0 and tag_id not in seen:
                seen.add(tag_id)
                ids.append(tag_id)
        except Exception:
            continue
    return ids


def _download_image_bytes(url: str, referer: str | None = None) -> tuple[bytes, str]:
    headers = {
        "User-Agent": "rss-news-publisher/1.0",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    req = Request(url=url, headers=headers)
    with urlopen(req, timeout=20) as resp:
        raw = resp.read()
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
    content_type = content_type.split(";")[0].strip() if content_type else "application/octet-stream"
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


def _get_image_meta_for_url(meta_json: str | None, image_url: str) -> dict:
    """Return the caption/credit dict for a specific image URL from extraction metadata."""
    if not meta_json or not image_url:
        return {}
    try:
        from urllib.parse import urlparse
        meta = json.loads(meta_json)
        image_metadata = (meta.get("extraction") or {}).get("image_metadata") or {}
        # Exact match first
        if image_url in image_metadata:
            return image_metadata[image_url]
        # Fuzzy match: compare without query string (handles ?w=1200 variants)
        base_url = urlparse(image_url)._replace(query="").geturl()
        for key, val in image_metadata.items():
            key_base = urlparse(key)._replace(query="").geturl()
            if key_base == base_url:
                return val
        return {}
    except Exception:
        return {}


def _build_image_caption(image_meta: dict, source_url: str) -> str:
    """Build a WP caption string from image metadata and source URL."""
    # caption from figcaption typically already contains the credit text
    caption = (image_meta.get("caption") or "").strip()
    if caption:
        return caption
    return f"Quelle: {source_url}"


def _upload_featured_media(
    *,
    base_url: str,
    auth_header: str,
    image_url: str,
    article_title: str,
    source_url: str,
    image_caption: str = "",
) -> int:
    image_bytes, content_type = _download_image_bytes(image_url, referer=source_url or None)
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

    _wp_request(
        base_url=base_url,
        auth_header=auth_header,
        method="POST",
        endpoint=f"media/{media_id}",
        payload={
            "title": f"{article_title[:120]} - Bild",
            "caption": image_caption or f"Quelle: {source_url}",
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


def _as_block_paragraphs(text: str) -> str:
    chunks = [chunk.strip() for chunk in re.split(r"\n{2,}", text.strip()) if chunk.strip()]
    if not chunks:
        return ""
    lines = []
    for chunk in chunks:
        compact = re.sub(r"\s*\n\s*", " ", chunk)
        lines.append(f"<!-- wp:paragraph --><p>{escape(compact)}</p><!-- /wp:paragraph -->")
    return "\n".join(lines)


def _strip_html_tags(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", text).strip()


def _html_to_wp_blocks(html: str) -> str:
    src = (html or "").strip()
    if not src:
        return ""
    pattern = re.compile(
        r"<h([2-6])[^>]*>[\s\S]*?</h\1>|<p[^>]*>[\s\S]*?</p>|<ul[^>]*>[\s\S]*?</ul>|<ol[^>]*>[\s\S]*?</ol>",
        re.IGNORECASE,
    )
    blocks: list[str] = []
    for match in pattern.finditer(src):
        block_html = match.group(0).strip()
        if not block_html:
            continue
        tag_match = re.match(r"<([a-z0-9]+)", block_html, re.IGNORECASE)
        tag = (tag_match.group(1).lower() if tag_match else "")
        if tag == "p":
            blocks.append(f"<!-- wp:paragraph -->{block_html}<!-- /wp:paragraph -->")
        elif tag in {"ul", "ol"}:
            ordered = tag == "ol"
            if ordered:
                blocks.append(f'<!-- wp:list {{"ordered":true}} -->{block_html}<!-- /wp:list -->')
            else:
                blocks.append(f"<!-- wp:list -->{block_html}<!-- /wp:list -->")
        elif tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            level = int(tag[1])
            blocks.append(f'<!-- wp:heading {{"level":{level}}} -->{block_html}<!-- /wp:heading -->')
    if blocks:
        return "\n".join(blocks)
    return _as_block_paragraphs(_strip_html_tags(src))


def _as_block_heading(level: int, text: str) -> str:
    safe_level = min(6, max(1, int(level)))
    return f'<!-- wp:heading {{"level":{safe_level}}} --><h{safe_level}>{escape(text)}</h{safe_level}><!-- /wp:heading -->'


def _as_block_list(items: list[str]) -> str:
    if not items:
        return ""
    content = "".join(f"<li>{item}</li>" for item in items)
    return f"<!-- wp:list --><ul>{content}</ul><!-- /wp:list -->"


def _sanitize_publish_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 3:
        lines = lines[3:]
    merged = "\n".join(lines)
    merged = re.sub(r"\n?\s*Pressekontakt[\s\S]*$", "", merged, flags=re.IGNORECASE).strip()
    return merged


def _build_attribution_block(article: dict[str, Any]) -> str:
    """Build a WP Gutenberg attribution block for the bottom of the article."""
    from urllib.parse import urlparse
    source_url = (article.get("canonical_url") or article.get("source_url") or "").strip()
    source_name = (article.get("source_name_snapshot") or "").strip()
    author = (article.get("author") or "").strip()

    # If the feed name is "Google Alerts" (or similar generic names), derive the
    # real source name from the hostname of the canonical URL.
    if not source_name or source_name.lower() in ("google alerts", "google"):
        try:
            hostname = urlparse(source_url).hostname or ""
            source_name = hostname.removeprefix("www.")
        except Exception:
            pass

    # Get image credit from extraction metadata (uses fuzzy URL match)
    meta_json = article.get("meta_json")
    credit = ""
    try:
        meta = json.loads(meta_json or "{}")
        selected_url = (meta.get("image_review") or {}).get("selected_url") or ""
        if selected_url:
            img_meta = _get_image_meta_for_url(meta_json, selected_url)
            raw_credit = (img_meta.get("credit") or "").strip()
            caption_text = (img_meta.get("caption") or "").strip()
            # If credit is just a bare marker prefix (e.g. "Foto:", "Bild:"),
            # clear it and extract the full credit from the caption text instead.
            _BARE_MARKERS = {"foto", "bild", "credit", "fotograf", "fotografie", "photo", "bildnachweis"}
            if raw_credit.endswith(":") and raw_credit[:-1].strip().lower() in _BARE_MARKERS:
                raw_credit = ""
            if raw_credit:
                credit = raw_credit
            elif caption_text:
                # Extract credit markers like "Foto: IMAGO/…", "© Agentur", "Bild: …"
                import re as _re
                m = _re.search(
                    r"(©[^\n]{1,120}|(?:Foto|Bild|Credit|Fotograf|Photo)\s*:[^\n]{1,120})",
                    caption_text,
                )
                credit = m.group(1).strip() if m else ""
    except Exception:
        pass

    parts: list[str] = []
    if source_url:
        label = source_name or source_url
        parts.append(f'Originalartikel: <a href="{source_url}">{escape(label)}</a>')
    if author:
        parts.append(f"Autor: {escape(author)}")
    if credit:
        parts.append(f"Bildnachweis: {escape(credit)}")

    if not parts:
        return ""

    inner = " &nbsp;|&nbsp; ".join(parts)
    return (
        "\n<!-- wp:separator {\"className\":\"is-style-wide\"} -->"
        "<hr class=\"wp-block-separator is-style-wide\"/><!-- /wp:separator -->\n"
        f'<!-- wp:paragraph {{\"className\":\"article-attribution\"}} -->'
        f'<p class="article-attribution"><em>{inner}</em></p>'
        "<!-- /wp:paragraph -->"
    )


def _build_post_content(article: dict[str, Any]) -> tuple[str, str | None]:
    summary = (article.get("summary") or "").strip()
    body_text = (article.get("content_rewritten") or article.get("content_raw") or "").strip()
    body_text = _sanitize_publish_text(body_text)
    if not body_text:
        body_text = summary

    has_html = bool(re.search(r"<[a-zA-Z][^>]*>", body_text))
    body_html = _html_to_wp_blocks(body_text) if has_html else _as_block_paragraphs(body_text)
    if not body_html:
        body_html = "<!-- wp:paragraph --><p>Kein Inhalt verfügbar.</p><!-- /wp:paragraph -->"

    attribution = _build_attribution_block(article)
    content = (body_html + attribution).strip()
    return content, None


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
        image_meta = _get_image_meta_for_url(article.get("meta_json"), selected_image_url)
        image_caption = _build_image_caption(image_meta, source_url)
        try:
            featured_media_id = _upload_featured_media(
                base_url=settings.wordpress_base_url,
                auth_header=auth,
                image_url=selected_image_url,
                article_title=title,
                source_url=source_url,
                image_caption=image_caption,
            )
        except Exception as img_exc:
            import logging
            logging.getLogger(__name__).warning(
                "Bild-Upload fehlgeschlagen (wird übersprungen): %s — %s", selected_image_url, img_exc
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
    scheduled_at = article.get("scheduled_publish_at")
    if scheduled_at:
        payload["date"] = scheduled_at  # e.g. "2026-03-24T09:00:00"
        # Use status "future" so WP schedules auto-publishing at the given date.
        # WP ignores date for drafts and shows "Sofort veröffentlichen" instead.
        try:
            from datetime import datetime as _dt
            if _dt.fromisoformat(scheduled_at) > _dt.now():
                payload["status"] = "future"
        except Exception:
            pass

    wp_post_id = article.get("wp_post_id")
    tag_ids = _resolve_wp_tag_ids(
        base_url=settings.wordpress_base_url,
        auth_header=auth,
        tags=_selected_tags_from_meta(article.get("meta_json")),
    )
    if tag_ids:
        payload["tags"] = tag_ids

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

    if not isinstance(result, dict):
        raise RuntimeError(f"WordPress Antwort im unerwarteten Format: {result}")
    post_id = int(result.get("id", 0))
    if post_id <= 0:
        raise RuntimeError(f"WordPress Antwort ohne Post-ID: {result}")
    post_url = result.get("link")
    return post_id, post_url if isinstance(post_url, str) else None


def selected_image_exists(article: dict[str, Any]) -> bool:
    return _selected_image_url_from_meta(article.get("meta_json")) is not None


def delete_wp_post(wp_post_id: int) -> None:
    """Permanently delete a WordPress post (moves to trash, then deletes)."""
    settings = get_settings()
    if not settings.wordpress_base_url or not settings.wordpress_username or not settings.wordpress_app_password:
        raise RuntimeError("WordPress Konfiguration fehlt")
    auth = _auth_header(settings.wordpress_username, settings.wordpress_app_password)
    # force=true skips trash
    _wp_request(
        base_url=settings.wordpress_base_url,
        auth_header=auth,
        method="DELETE",
        endpoint=f"posts/{wp_post_id}?force=true",
    )
