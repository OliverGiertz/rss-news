# utils/article_extractor.py

import requests
from bs4 import BeautifulSoup

def extract_full_article(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Promobil & WordPress & allgemeine Fallbacks
        candidates = [
            {"tag": "div", "class_": "article__text"},     # Promobil
            {"tag": "div", "class_": "entry-content"},     # WordPress Standard
            {"tag": "article", "class_": None},            # Generisch
        ]

        for selector in candidates:
            el = soup.find(selector["tag"], class_=selector["class_"])
            if el and len(el.get_text(strip=True).split()) > 50:
                return el.get_text(" ", strip=True)

        # Fallback: ganzer Seiteninhalt
        return soup.get_text(" ", strip=True)
    except Exception:
        return ""
