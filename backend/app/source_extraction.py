from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_USER_AGENT = "rss-news-bot/1.0 (+https://news.vanityontour.de)"


@dataclass(frozen=True)
class ExtractedArticle:
    title: str | None
    author: str | None
    canonical_url: str | None
    summary: str | None
    content_text: str | None
    images: list[str]
    press_contact: str | None
    extraction_error: str | None = None


def _clean_text(raw: str | None) -> str | None:
    if not raw:
        return None
    text = unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _strip_noise(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<noscript[\s\S]*?</noscript>", " ", html, flags=re.IGNORECASE)
    return html


def _meta_content(html: str, attr: str, value: str) -> str | None:
    pattern = re.compile(
        rf"<meta[^>]+{attr}\s*=\s*[\"']{re.escape(value)}[\"'][^>]*content\s*=\s*[\"']([^\"']+)[\"'][^>]*>",
        re.IGNORECASE,
    )
    match = pattern.search(html)
    if match:
        return _clean_text(match.group(1))

    # handle reversed attribute order
    pattern_rev = re.compile(
        rf"<meta[^>]+content\s*=\s*[\"']([^\"']+)[\"'][^>]*{attr}\s*=\s*[\"']{re.escape(value)}[\"'][^>]*>",
        re.IGNORECASE,
    )
    match = pattern_rev.search(html)
    if match:
        return _clean_text(match.group(1))
    return None


def _extract_title(html: str) -> str | None:
    title = _meta_content(html, "property", "og:title")
    if title:
        return title

    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.IGNORECASE)
    if match:
        cleaned = _clean_text(match.group(1))
        if cleaned:
            return cleaned

    match = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, re.IGNORECASE)
    if match:
        return _clean_text(match.group(1))
    return None


def _extract_canonical(html: str) -> str | None:
    match = re.search(
        r"<link[^>]+rel\s*=\s*[\"']canonical[\"'][^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>",
        html,
        re.IGNORECASE,
    )
    if match:
        return _clean_text(match.group(1))

    match = re.search(
        r"<link[^>]+href\s*=\s*[\"']([^\"']+)[\"'][^>]*rel\s*=\s*[\"']canonical[\"'][^>]*>",
        html,
        re.IGNORECASE,
    )
    if match:
        return _clean_text(match.group(1))
    return None


def _extract_author(html: str) -> str | None:
    for attr, value in (("name", "author"), ("property", "article:author"), ("property", "og:article:author")):
        author = _meta_content(html, attr, value)
        if author:
            return author

    for pattern in (
        r"(?:Von|Autor(?:in)?)\s*[:\-]\s*([^<\n\r]{3,120})",
        r"class=[\"'][^\"']*(?:author|byline)[^\"']*[\"'][^>]*>([\s\S]{1,180})<",
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            author = _clean_text(match.group(1))
            if author:
                return author
    return None


def _extract_images(html: str, page_url: str) -> list[str]:
    images: list[str] = []
    seen: set[str] = set()

    for prop in ("og:image", "twitter:image"):
        pattern = re.compile(
            rf"<meta[^>]+property\s*=\s*[\"']{re.escape(prop)}[\"'][^>]*content\s*=\s*[\"']([^\"']+)[\"'][^>]*>",
            re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            src = match.group(1).strip()
            abs_src = urljoin(page_url, src)
            if abs_src not in seen:
                seen.add(abs_src)
                images.append(abs_src)

    for match in re.finditer(r"<img[^>]+src\s*=\s*[\"']([^\"']+)[\"'][^>]*>", html, re.IGNORECASE):
        src = match.group(1).strip()
        abs_src = urljoin(page_url, src)
        if abs_src not in seen:
            seen.add(abs_src)
            images.append(abs_src)

    return images


def _extract_content_text(html: str) -> str | None:
    section = None
    for pattern in (
        r"<article[^>]*>([\s\S]*?)</article>",
        r"<main[^>]*>([\s\S]*?)</main>",
        r"<body[^>]*>([\s\S]*?)</body>",
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            section = match.group(1)
            break

    if not section:
        section = html

    paragraphs = []
    for match in re.finditer(r"<h[2-4][^>]*>([\s\S]*?)</h[2-4]>", section, re.IGNORECASE):
        text = _clean_text(match.group(1))
        if text and re.search(r"\b(pressekontakt|press contact|kontakt|agentur)\b", text, re.IGNORECASE):
            paragraphs.append(text)

    for match in re.finditer(r"<p[^>]*>([\s\S]*?)</p>", section, re.IGNORECASE):
        text = _clean_text(match.group(1))
        if text and len(text) > 2:
            paragraphs.append(text)

    if paragraphs:
        return "\n".join(paragraphs)

    stripped = _clean_text(section)
    return stripped


def _extract_press_contact(content_text: str | None) -> str | None:
    if not content_text:
        return None

    lines = [line.strip() for line in content_text.split("\n") if line.strip()]
    marker_re = re.compile(r"\b(pressekontakt|press contact|presse\-kontakt|agentur)\b", re.IGNORECASE)
    for idx, line in enumerate(lines):
        if marker_re.search(line):
            chunk = [line]
            for nxt in lines[idx + 1 : idx + 6]:
                if re.search(r"\b(original\-content von|ots:|newsroom:|alle meldungen|zum newsroom)\b", nxt, re.IGNORECASE):
                    break
                chunk.append(nxt)
            return _clean_text("\n".join(chunk))

    match = re.search(
        r"((?:Pressekontakt|Agentur)[\s\S]{0,1200}?)(?:Original-Content von|OTS:|newsroom:|Alle Meldungen|Zum Newsroom|$)",
        content_text,
        re.IGNORECASE,
    )
    if match:
        return _clean_text(match.group(1))
    return None


def extract_article(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> ExtractedArticle:
    try:
        req = Request(
            url=url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            },
        )
        with urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
    except Exception as exc:
        return ExtractedArticle(
            title=None,
            author=None,
            canonical_url=None,
            summary=None,
            content_text=None,
            images=[],
            press_contact=None,
            extraction_error=str(exc),
        )

    html = _strip_noise(html)
    title = _extract_title(html)
    author = _extract_author(html)
    canonical_url = _extract_canonical(html)
    summary = _meta_content(html, "name", "description")
    content_text = _extract_content_text(html)
    if not summary and content_text:
        summary = _clean_text(content_text[:320])
    images = _extract_images(html, url)
    press_contact = _extract_press_contact(content_text)

    return ExtractedArticle(
        title=title,
        author=author,
        canonical_url=canonical_url,
        summary=summary,
        content_text=content_text,
        images=images,
        press_contact=press_contact,
        extraction_error=None,
    )


def extracted_article_to_meta(article: ExtractedArticle) -> dict[str, Any]:
    return {
        "title": article.title,
        "author": article.author,
        "canonical_url": article.canonical_url,
        "summary": article.summary,
        "images": article.images,
        "press_contact": article.press_contact,
        "extraction_error": article.extraction_error,
    }
