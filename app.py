import streamlit as st
import feedparser
import json
import uuid
import os
from datetime import datetime
import pandas as pd
import openai
from dotenv import load_dotenv

# ==== Konfiguration ====
ARTICLES_FILE = "articles.json"
FEEDS_FILE = "feeds.json"
DEFAULT_STATUS = "New"
ALL_STATUSES = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash"]

# ==== API Schlüssel laden ====
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ==== Hilfsfunktionen ====
def load_articles():
    if not os.path.exists(ARTICLES_FILE):
        return []
    try:
        with open(ARTICLES_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_articles(articles):
    with open(ARTICLES_FILE, "w") as f:
        json.dump(articles, f, indent=2)

def load_feeds():
    if not os.path.exists(FEEDS_FILE):
        return []
    try:
        with open(FEEDS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_feeds(feeds):
    with open(FEEDS_FILE, "w") as f:
        json.dump(feeds, f, indent=2)

def fetch_articles_from_feeds(feeds):
    new_articles = []
    existing_links = {a['link'] for a in load_articles()}
    for feed_url in feeds:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries:
            if entry.link in existing_links:
                continue
            content = ""
            if 'content' in entry:
                content = entry.content[0].value
            elif 'summary' in entry:
                content = entry.summary
            article = {
                "id": str(uuid.uuid4()),
                "date": entry.get("published", datetime.now().isoformat()),
                "title": entry.get("title", "(kein Titel)"),
                "summary": content[:150],
                "content": content,
                "word_count": len(content.split()),
                "tags": [],
                "status": DEFAULT_STATUS,
                "link": entry.link
            }
            new_articles.append(article)
    return new_articles

def format_date(date_str):
    try:
        return datetime.fromisoformat(date_str).strftime("%d.%m.%y")
    except Exception:
        try:
            return datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S").strftime("%d.%m.%y")
        except Exception:
            return date_str

def rewrite_article_with_gpt(original_text):
    prompt = (
        "Schreibe folgenden Artikel um und formuliere ihn in journalistischem Stil neu. "
        "Füge am Ende eine Liste von 2–3 passenden Tags hinzu (nur Schlagwörter, keine Hashtags):\n"
        f"{original_text}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"FEHLER: {e}"

# ==== UI ====
st.set_page_config(page_title="RSS Artikel Manager", layout="wide")
st.title("📰 RSS Artikel Manager")

# Bereich: Feed-Verwaltung
st.sidebar.header("RSS Feeds verwalten")
feeds = load_feeds()
new_feed = st.sidebar.text_input("Neuen Feed hinzufügen")
if st.sidebar.button("➕ Feed hinzufügen") and new_feed:
    feeds.append(new_feed)
    save_feeds(feeds)
    st.rerun()

if feeds:
    remove_feed = st.sidebar.selectbox("Feed entfernen", [""] + feeds)
    if st.sidebar.button("🗑️ Entfernen") and remove_feed:
        feeds.remove(remove_feed)
        save_feeds(feeds)
        st.rerun()
else:
    st.sidebar.info("Noch keine Feeds hinzugefügt")

# Bereich: Artikel laden
if st.button("🔄 Artikel aus Feeds laden"):
    new = fetch_articles_from_feeds(feeds)
    if new:
        all_articles = load_articles() + new
        save_articles(all_articles)
        st.success(f"{len(new)} neue Artikel geladen.")
    else:
        st.info("Keine neuen Artikel gefunden.")

# Button zum Umschreiben aller Artikel mit Status "Rewrite"
rewrite_articles = [a for a in load_articles() if a["status"] == "Rewrite"]
if rewrite_articles:
    if st.button("✍️ Alle Artikel mit Status 'Rewrite' umschreiben"):
        all_articles = load_articles()
        with st.spinner("Artikel werden umgeschrieben..."):
            for a in all_articles:
                if a["status"] == "Rewrite":
                    result = rewrite_article_with_gpt(a["content"])
                    if "FEHLER:" not in result:
                        # Aufteilen in Text und Tags, falls möglich
                        if "Tags:" in result:
                            rewritten, tags = result.rsplit("Tags:", 1)
                            a["content"] = rewritten.strip()
                            a["tags"] = [t.strip() for t in tags.split(",")][:3]
                        else:
                            a["content"] = result.strip()
                        a["summary"] = a["content"][:150]
                        a["word_count"] = len(a["content"].split())
                        a["status"] = "Process"
        save_articles(all_articles)
        st.success("Artikel erfolgreich umgeschrieben und aktualisiert.")
        st.rerun()

# Bereich: Artikeltabelle
status_filter = st.selectbox("Status filtern", ALL_STATUSES, index=ALL_STATUSES.index(DEFAULT_STATUS))
articles = [a for a in load_articles() if a["status"] == status_filter]

if articles:
    st.markdown("---")
    st.subheader(f"Artikel mit Status '{status_filter}'")

    # Checkbox-Auswahl manuell verwalten
    selected_ids = []
    for i, article in enumerate(articles):
        cols = st.columns([0.5, 1.5, 3, 4, 1, 2, 1])
        with cols[0]:
            if st.checkbox("", key=article["id"]):
                selected_ids.append(article["id"])
        cols[1].markdown(format_date(article["date"]))
        cols[2].markdown(f"**{article['title']}**")
        cols[3].markdown(article["summary"])
        cols[4].markdown(str(article["word_count"]))
        cols[5].markdown(", ".join(article["tags"]) if article["tags"] else "")
        cols[6].markdown(article["status"])

    st.markdown("---")
    if selected_ids:
        new_status = st.selectbox("Neuen Status setzen für ausgewählte Artikel", ALL_STATUSES)
        if st.button("✅ Status ändern"):
            all_articles = load_articles()
            for a in all_articles:
                if a["id"] in selected_ids:
                    a["status"] = new_status
            save_articles(all_articles)
            st.success("Status aktualisiert.")
            st.rerun()
else:
    st.warning(f"Keine Artikel mit Status '{status_filter}' vorhanden.")
