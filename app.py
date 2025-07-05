# app.py

import streamlit as st
from datetime import datetime
from main import (
    load_feeds,
    save_feeds,
    load_articles,
    save_articles,
    process_articles,
    rewrite_articles
)
import os

st.set_page_config(page_title="📰 RSS Artikel Manager", layout="wide")
st.title("📰 RSS Artikel Manager")

# RSS Feed Verwaltung
st.sidebar.header("📡 RSS Feeds verwalten")
feeds = load_feeds()
new_feed = st.sidebar.text_input("Neuen RSS Feed hinzufügen")
if st.sidebar.button("Feed hinzufügen"):
    if new_feed and new_feed not in feeds:
        feeds.append({"url": new_feed})
        save_feeds(feeds)
        st.sidebar.success("Feed hinzugefügt")

#if feeds:
#    st.sidebar.write("### Aktuelle Feeds:")
#    for feed in feeds:
#        url = feed["url"] if isinstance(feed, dict) else feed
#        st.sidebar.markdown(f"- {url}")
#else:
#    st.sidebar.info("Noch keine Feeds hinzugefügt.")

# Artikel laden
if st.sidebar.button("🔄 Alle Feeds neu laden"):
    existing_ids = [a["id"] for a in load_articles()]
    process_articles(existing_ids)
    st.rerun()

if st.sidebar.button("✍️ Artikel umschreiben (Rewrite)"):
    rewrite_articles()
    st.rerun()

# Artikelübersicht
st.header("📋 Artikelübersicht")
status_filter = st.selectbox("Status filtern", ["Alle", "New", "Rewrite", "Process", "Online", "On Hold", "Trash"])

articles = load_articles()
if status_filter != "Alle":
    articles = [a for a in articles if a.get("status") == status_filter]

# Tabelle anzeigen
if articles:
    st.markdown("### 📄 Übersichtstabelle")
    st.write("**Spaltenübersicht:** Auswahl | Datum | Titel | Zusammenfassung | Wörter | Tags | Status")

    for article in articles:
        cols = st.columns([0.05, 0.1, 0.2, 0.25, 0.05, 0.2, 0.15])
        with cols[0]:
            st.checkbox("", key=f"select_{article['id']}")
        with cols[1]:
            st.markdown(datetime.strptime(article["date"], "%a, %d %b %Y %H:%M:%S %z").strftime("%d.%m.%y") if "GMT" in article["date"] or "+" in article["date"] else article["date"][:10])
        with cols[2]:
            st.markdown(f"**{article['title']}**")
        with cols[3]:
            st.markdown(article.get("summary", "")[:150])
        with cols[4]:
            st.markdown(str(len(article.get("text", "").split())))
        with cols[5]:
            st.markdown(", ".join(article.get("tags", [])))
        with cols[6]:
            status_options = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash"]
            current_status = article.get("status", "New")
            new_status = st.selectbox("", status_options, index=status_options.index(current_status), key=f"status_{article['id']}")
            if new_status != current_status:
                article["status"] = new_status
                save_articles(articles)
                st.rerun()

        with st.expander(f"🔍 {article['title']}"):
            st.markdown("#### ✍️ Artikeltext")
            st.code(f"{article['title']}\n\n{article['text']}\n\nQuelle: {article['link']}", language="markdown")

            st.markdown("#### 🏷️ Tags")
            st.code(", ".join(article.get("tags", [])), language="markdown")

            st.markdown("#### 🖼️ Bilder")
            for img in article.get("images", []):
                st.image(img["url"], caption=img.get("caption", "Kein Titel"), use_column_width=True)
                st.caption(f"© {img.get('copyright', 'Unbekannt')} | [Quelle]({img.get('copyright_url', '#')})")

else:
    st.info("Keine Artikel für den gewählten Status gefunden.")
