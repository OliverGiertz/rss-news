# main.py

import json
import os
from datetime import datetime
import feedparser
from utils.image_extractor import extract_images_with_metadata
from openai import OpenAI
from dotenv import load_dotenv
import logging


load_dotenv()

# Log-Verzeichnis sicherstellen
os.makedirs("logs", exist_ok=True)


client = OpenAI()
# 📝 Logging konfigurieren
logging.basicConfig(filename='logs/rss_tool.log', level=logging.INFO)

ARTICLES_FILE = "processed_articles.json"
FEEDS_FILE = "feeds.json"

def load_articles():
    if os.path.exists(ARTICLES_FILE):
        with open(ARTICLES_FILE, "r") as f:
            return json.load(f)
    return []

def save_articles(articles):
    with open(ARTICLES_FILE, "w") as f:
        json.dump(articles, f, indent=2)

def load_feeds():
    if os.path.exists(FEEDS_FILE):
        with open(FEEDS_FILE, "r") as f:
            return json.load(f)
    return []

def save_feeds(feeds):
    with open(FEEDS_FILE, "w") as f:
        json.dump(feeds, f, indent=2)

def fetch_and_process_feed(url):
    logging.info(f"Abrufen von Feed: {url}")
    feed = feedparser.parse(url)
    articles = load_articles()
    for entry in feed.entries:
        if any(a["link"] == entry.link for a in articles):
            continue
        try:
            images = extract_images_with_metadata(entry.link)
        except Exception as e:
            logging.warning(f"Fehler beim Bildextrakt: {e}")
            images = []
        article = {
            "id": f"{entry.link}",
            "title": entry.title,
            "summary": entry.summary,
            "link": entry.link,
            "date": entry.get("published", datetime.now().isoformat()),
            "text": entry.summary,
            "status": "New",
            "images": images,
            "tags": []
        }
        articles.append(article)
    save_articles(articles)

def process_articles():
    feeds = load_feeds()
    for url in feeds:
        fetch_and_process_feed(url)

def rewrite_articles():
    logging.info("Starte Umschreiben von Artikeln mit Status 'Rewrite' ...")
    articles = load_articles()
    updated = False
    for article in articles:
        if article["status"] != "Rewrite":
            continue
        try:
            prompt = f"Fasse diesen Text neu und interessant zusammen:\n\n{article['summary']}"
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            rewritten = response.choices[0].message.content.strip()
            article["text"] = rewritten
            article["status"] = "Done"

            # Tags generieren
            tag_prompt = f"Erstelle passende 3-5 Tags für diesen Text:\n\n{rewritten}"
            tag_response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": tag_prompt}]
            )
            tags = [tag.strip() for tag in tag_response.choices[0].message.content.split(",")]
            article["tags"] = tags

            updated = True
            logging.info(f"✅ Artikel '{article['title']}' umgeschrieben.")
        except Exception as e:
            logging.error(f"❌ Fehler beim Umschreiben von '{article['title']}':\n{e}")
    if updated:
        save_articles(articles)
