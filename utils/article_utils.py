# utils/article_utils.py

import hashlib

def clean_text(text: str) -> str:
    return text.strip()

def generate_id(link: str) -> str:
    return hashlib.md5(link.encode("utf-8")).hexdigest()

def categorize_article(text: str) -> str:
    # Dummy-Kategorie
    return "Allgemein"

def tag_article(text: str) -> list:
    # Dummy-Tags
    return ["tag1", "tag2"]

def summarize_text(text: str) -> str:
    return text[:200] + "..."

def rewrite_text(text: str) -> str:
    return text  # Platzhalter, z. B. für GPT-Rewrite später
