from __future__ import annotations

import base64
import json
from typing import Any
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


def publish_article_draft(article: dict[str, Any]) -> tuple[int, str | None]:
    settings = get_settings()
    if not settings.wordpress_base_url or not settings.wordpress_username or not settings.wordpress_app_password:
        raise RuntimeError("WordPress Konfiguration fehlt (base_url, username, app_password)")

    auth = _auth_header(settings.wordpress_username, settings.wordpress_app_password)

    source_url = article.get("source_url") or ""
    canonical_url = article.get("canonical_url") or source_url
    title = (article.get("title") or "Ohne Titel").strip()
    body = (article.get("content_rewritten") or article.get("content_raw") or "").strip()
    if not body:
        body = article.get("summary") or ""

    footer = "\n\n<hr />\n<p><strong>Quelle:</strong> "
    footer += f"<a href=\"{source_url}\">{source_url}</a></p>"
    if canonical_url and canonical_url != source_url:
        footer += f"\n<p><strong>Canonical:</strong> <a href=\"{canonical_url}\">{canonical_url}</a></p>"
    content = f"{body}{footer}"

    payload = {
        "title": title,
        "content": content,
        "status": settings.wordpress_default_status,
    }

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
