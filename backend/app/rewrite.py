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


def rewrite_article_text(article: dict[str, Any]) -> str:
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY fehlt")

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

    payload = {
        "model": settings.openai_model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": "Du bist ein deutscher News-Redakteur."},
            {"role": "user", "content": prompt},
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
        raise RuntimeError("OpenAI lieferte keinen Rewrite-Text")
    return content.strip()

