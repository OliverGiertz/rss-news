# main.py

import feedparser
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import logging
from utils.image_extractor import extract_images_with_metadata
import openai

load_dotenv()

# Logging konfigurieren
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, "rss_tool.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

openai.api_key = os.getenv("OPENAI_API_KEY")

ARTICLES_FILE = "data/articles.json"
FEEDS_FILE = "data/feeds.json"

VALID_STATUSES = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash"]


def load_feeds():
    if not os.path.exists(FEEDS_FILE):
        return []
    with open(FEEDS_FILE, "r") as f:
        return json.load(f)

def save_feeds(feeds):
    with open(FEEDS_FILE, "w") as f:
        json.dump(feeds, f, indent=2)

def load_articles():
    if not os.path.exists(ARTICLES_FILE):
        return []
    with open(ARTICLES_FILE, "r") as f:
        articles = json.load(f)

    # Sicherstellen, dass jeder Artikel einen gültigen Status hat
    for article in articles:
        if article.get("status") not in VALID_STATUSES:
            article["status"] = "New"
    return articles

def save_articles(articles):
    with open(ARTICLES_FILE, "w") as f:
        json.dump(articles, f, indent=2)

def fetch_and_process_feed(feed_url, existing_ids):
    feed = feedparser.parse(feed_url)
    new_articles = []

    for entry in feed.entries:
        article_id = entry.get("id") or entry.get("link")
        if not article_id or article_id in existing_ids:
            continue

        title = entry.get("title", "Kein Titel")
        date = entry.get("published", datetime.now().isoformat())
        summary = entry.get("summary", "")
        content = entry.get("content", [{}])[0].get("value") or entry.get("description", "")

        soup = BeautifulSoup(content, "html.parser")
        clean_text = soup.get_text(" ", strip=True)

        images = extract_images_with_metadata(entry.link)

        new_articles.append({
            "id": article_id,
            "title": title,
            "date": date,
            "summary": summary,
            "text": clean_text,
            "tags": [],
            "status": "New",
            "link": entry.get("link", ""),
            "images": images
        })

    return new_articles

def process_articles(existing_ids):
    feeds = load_feeds()
    all_articles = load_articles()
    new_entries = []

    for feed in feeds:
        if isinstance(feed, dict):
            url = feed.get("url")
        else:
            url = feed

        if not url:
            continue

        try:
            logging.info(f"Lade Feed: {url}")
            entries = fetch_and_process_feed(url, existing_ids)
            new_entries.extend(entries)
            logging.info(f"{len(entries)} neue Artikel gefunden in {url}")
        except Exception as e:
            logging.error(f"Fehler beim Verarbeiten von {url}: {e}")

    # Nur neue Artikel speichern, deren ID noch nicht vorhanden ist
    existing_article_ids = set(article["id"] for article in all_articles)
    unique_new_entries = [a for a in new_entries if a["id"] not in existing_article_ids]

    if unique_new_entries:
        all_articles.extend(unique_new_entries)
        save_articles(all_articles)
        logging.info(f"{len(unique_new_entries)} neue Artikel gespeichert.")
    else:
        logging.info("Keine neuen Artikel gefunden.")

def rewrite_articles():
    articles = load_articles()
    for article in articles:
        if article.get("status") == "Rewrite":
            try:
                logging.info(f"✍️ Umschreiben von: {article['title']}")
                prompt = f"Schreibe folgenden Artikel um und fasse ihn verständlich zusammen:\n\n{article['text']}"
                response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Du bist ein professioneller Redakteur."},
                        {"role": "user", "content": prompt}
                    ]
                )
                new_text = response.choices[0].message.content.strip()
                article["text"] = f"{article['title']}\n\n{new_text}"
                article["status"] = "Process"

                tag_prompt = f"Erstelle 3 passende, kurze Stichwörter (Tags) für diesen Artikel:\n\n{new_text}"
                tag_response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Du bist ein Blog-Tag-Generator."},
                        {"role": "user", "content": tag_prompt}
                    ]
                )
                tags_raw = tag_response.choices[0].message.content.strip()
                tags = [tag.strip(" ,") for tag in tags_raw.replace("\n", ",").split(",") if tag.strip()]
                article["tags"] = tags

                # Sicherstellen, dass Bildmetadaten vollständig sind
                for img in article.get("images", []):
                    if "caption" not in img:
                        img["caption"] = "Kein Bildtitel vorhanden"
                    if "copyright" not in img:
                        img["copyright"] = "Unbekannt"
                    if "copyright_url" not in img:
                        img["copyright_url"] = "#"

                logging.info(f"✅ Artikel umgeschrieben: {article['title']}")

            except Exception as e:
                logging.error(f"❌ Fehler beim Umschreiben von '{article['title']}': {e}")

    save_articles(articles)
    logging.info("Alle Artikel mit Status 'Rewrite' wurden verarbeitet.")
