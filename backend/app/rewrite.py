from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request, urlopen

from .config import get_settings


def _sanitize_source_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 3:
        lines = lines[3:]

    joined = "\n".join(lines)
    # Remove press contact block at end from "Pressekontakt" onward.
    joined = re.sub(
        r"\n?\s*Pressekontakt[\s\S]*$",
        "",
        joined,
        flags=re.IGNORECASE,
    ).strip()
    return joined


def _normalize_tags(tags: list[str], max_tags: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        value = re.sub(r"\s+", " ", str(raw or "").strip())
        value = re.sub(r"^[#\-•\s]+", "", value)
        value = re.sub(r"[;,.:\s]+$", "", value)
        if not value:
            continue
        if len(value) < 2 or len(value) > 40:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
        if len(out) >= max_tags:
            break
    return out


def _openai_chat(system: str, user: str, temperature: float = 0.4) -> str:
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY fehlt")

    payload = {
        "model": settings.openai_model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = Request(
        url="https://api.openai.com/v1/chat/completions",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"Ungültige OpenAI-Antwort: {data}")
    message = choices[0].get("message", {})
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI lieferte keinen Inhalt")
    return content.strip()


def rewrite_article_text(article: dict[str, Any]) -> str:
    source_text = _sanitize_source_text(article.get("content_raw") or "")
    if not source_text:
        source_text = (article.get("summary") or "").strip()
    if not source_text:
        raise RuntimeError("Kein Quelltext für Rewrite verfügbar")

    title = (article.get("title") or "").strip()
    prompt = (
        "Schreibe den folgenden News-Text neu auf Deutsch in persönlicher Du-Form. "
        "Stil: ausführlich, gut lesbar, ohne Einleitung mit Datum/Uhrzeit/Firma/Ort, "
        "ohne Pressekontakt, ohne Quellenblock. "
        "Nutze klare Absätze und Zwischenüberschriften in HTML (<h2>, <p>, <ul><li> falls passend). "
        "Inhaltlich korrekt bleiben, nichts erfinden.\n\n"
        f"Titel: {title}\n\n"
        f"Originaltext:\n{source_text}"
    )
    return _openai_chat(
        "Du bist ein deutscher News-Redakteur.",
        prompt,
        temperature=0.4,
    )


def generate_article_tags(article: dict[str, Any], rewritten_text: str | None = None, max_tags: int = 8) -> list[str]:
    source_text = rewritten_text or _sanitize_source_text(article.get("content_raw") or "") or (article.get("summary") or "")
    source_text = str(source_text).strip()
    if not source_text:
        return []
    title = (article.get("title") or "").strip()
    prompt = (
        "Erzeuge präzise Schlagwörter für einen deutschen News-Artikel. "
        f"Maximal {max_tags} Tags. Nur relevante Begriffe, keine allgemeinen Wörter wie News/Artikel. "
        "Gib ausschließlich ein JSON-Array mit Strings zurück, ohne Erklärung.\n\n"
        f"Titel: {title}\n\n"
        f"Text:\n{source_text[:3500]}"
    )
    raw = _openai_chat(
        "Du extrahierst präzise, kurze News-Tags auf Deutsch.",
        prompt,
        temperature=0.2,
    )
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return _normalize_tags([str(x) for x in parsed], max_tags=max_tags)
    except Exception:
        pass
    # fallback: extract first JSON-like array if model wrapped output
    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return _normalize_tags([str(x) for x in parsed], max_tags=max_tags)
        except Exception:
            return []
    return []


def merge_generated_tags(meta_json: str | None, tags: list[str]) -> str:
    meta: dict[str, Any] = {}
    if meta_json:
        try:
            parsed = json.loads(meta_json)
            if isinstance(parsed, dict):
                meta = parsed
        except Exception:
            meta = {}
    meta["generated_tags"] = _normalize_tags(tags)
    return json.dumps(meta, ensure_ascii=False)
