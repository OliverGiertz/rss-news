import streamlit as st
import feedparser
import json
import uuid
import os
from datetime import datetime
import pandas as pd
import openai
from openai import OpenAI
from dotenv import load_dotenv
import logging

# ==== Version ====
APP_VERSION = "1.1.0"

# ==== Logging konfigurieren ====
LOG_FILE = "app.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ==== Konfiguration ====
ARTICLES_FILE = "articles.json"
FEEDS_FILE = "feeds.json"
DEFAULT_STATUS = "New"
ALL_STATUSES = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash"]

# ==== API Schlüssel laden ====
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# ==== Hilfsfunktionen ====
def load_articles():
    if not os.path.exists(ARTICLES_FILE):
        return []
    try:
        with open(ARTICLES_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logging.error("Fehler beim Laden von articles.json")
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
        logging.error("Fehler beim Laden von feeds.json")
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

def rewrite_article_with_gpt(original_text, title):
    prompt = (
        "Schreibe folgenden Artikel um und formuliere ihn in journalistischem Stil neu. "
        "Füge am Ende eine Liste von 2–3 passenden Tags hinzu (nur Schlagwörter, keine Hashtags):\n"
        f"{original_text}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        result = response.choices[0].message.content
        logging.info(f"✅ Artikel umgeschrieben: {title}")
        return result
    except Exception as e:
        logging.error(f"❌ Fehler beim Umschreiben von '{title}': {e}")
        return f"FEHLER: {e}"

# ==== UI ====
st.set_page_config(page_title="RSS Artikel Manager", layout="wide")
st.title("📰 RSS Artikel Manager")
st.sidebar.markdown(f"🧩 Version: `{APP_VERSION}`")

# Bereich: Feed-Verwaltung
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
        logging.info(f"{len(new)} neue Artikel geladen.")
    else:
        st.info("Keine neuen Artikel gefunden.")

# Button zum Umschreiben aller Artikel mit Status "Rewrite"
rewrite_articles = [a for a in load_articles() if a["status"] == "Rewrite"]
if rewrite_articles:
    if st.button("✍️ Alle Artikel mit Status 'Rewrite' umschreiben"):
        all_articles = load_articles()
        progress_text = st.empty()
        with st.spinner("Artikel werden umgeschrieben..."):
            total = len([a for a in all_articles if a["status"] == "Rewrite"])
            count = 0
            for a in all_articles:
                if a["status"] == "Rewrite":
                    count += 1
                    progress_text.markdown(f"➡️ Umschreibe Artikel {count} von {total}: **{a['title']}**")
                    result = rewrite_article_with_gpt(a["content"], a["title"])
                    if "FEHLER:" not in result:
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

    selected_ids = []
    for i, article in enumerate(articles):
        cols = st.columns([0.5, 1.5, 3, 4, 1, 2, 1])
        with cols[0]:
            if st.checkbox("Auswählen", key=article["id"], label_visibility="collapsed"):
                selected_ids.append(article["id"])
        cols[1].markdown(format_date(article["date"]))
        cols[2].markdown(f"**{article['title']}**")
        cols[3].markdown(article["summary"])
        cols[4].markdown(str(article["word_count"]))
        cols[5].markdown(", ".join(article["tags"]) if article["tags"] else "")
        cols[6].markdown(article["status"])

    st.markdown("---")
    if selected_ids:
        all_articles = load_articles()
        selected_articles = [a for a in all_articles if a["id"] in selected_ids]

        
        with st.expander("📋 Inhalte für WordPress kopieren"):
            for a in selected_articles:
                with st.container():
                    st.markdown("""
                        <div style="border: 1px solid #CCC; padding: 1rem; border-radius: 10px; background-color: #F9F9F9;">
                    """, unsafe_allow_html=True)

                    st.markdown(f"### ✏️ {a['title']}")

                    st.markdown(f"<button style='margin-bottom:0.5rem;' onclick=\"navigator.clipboard.writeText('{a['title']}')\">🔗 Titel kopieren</button>", unsafe_allow_html=True)

                    st.text_area("📝 Artikeltext", value=a["content"], height=300, key=f"content_{a['id']}", help="CMD+C zum Kopieren")

                    st.markdown(f"<button style='margin-bottom:0.5rem;' onclick=\"navigator.clipboard.writeText(`{a['content']}`)\">📋 Artikeltext kopieren</button>", unsafe_allow_html=True)

                    st.text_input("🏷️ Tags", value=", ".join(a["tags"]), key=f"tags_{a['id']}", help="CMD+C zum Kopieren")

                    st.markdown(f"<button style='margin-bottom:0.5rem;' onclick=\"navigator.clipboard.writeText('{', '.join(a['tags'])}')\">📎 Tags kopieren</button>", unsafe_allow_html=True)

                    st.markdown(f"<a href='{a['link']}' target='_blank' style='text-decoration: none;'><button style='background-color:#e8f0fe; border:none; padding:0.5rem 1rem; border-radius:5px;'>🔗 Zum Originalartikel</button></a>", unsafe_allow_html=True)

                    st.markdown("</div>", unsafe_allow_html=True)


        new_status = st.selectbox("Neuen Status setzen für ausgewählte Artikel", ALL_STATUSES)
        if st.button("✅ Status ändern"):
            for a in all_articles:
                if a["id"] in selected_ids:
                    a["status"] = new_status
            save_articles(all_articles)
            st.success("Status aktualisiert.")
            logging.info(f"Status von {len(selected_ids)} Artikel(n) auf '{new_status}' gesetzt.")
            st.rerun()
else:
    st.warning(f"Keine Artikel mit Status '{status_filter}' vorhanden.")
