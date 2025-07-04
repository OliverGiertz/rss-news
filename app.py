# app.py

import streamlit as st
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from email.utils import parsedate_to_datetime
from main import load_articles, save_articles, process_articles, fetch_and_process_feed, rewrite_articles

load_dotenv()

st.set_page_config(layout="wide", page_title="RSS Article Manager")

# Artikelstatusfilter
status_filter = st.sidebar.selectbox("🔍 Artikelstatus filtern", ["Alle", "New", "Rewrite", "Process", "Online", "On Hold", "Trash"])

# Neuen Feed hinzufügen
st.sidebar.markdown("---")
st.sidebar.header("➕ RSS Feed hinzufügen")
new_feed_url = st.sidebar.text_input("Feed URL")
if st.sidebar.button("Feed hinzufügen") and new_feed_url:
    fetch_and_process_feed(new_feed_url)
    st.rerun()

# Alle Feeds neu laden
if st.sidebar.button("Alle Feeds neu laden"):
    process_articles()
    st.rerun()

# Artikel laden
try:
    articles = load_articles()
except json.decoder.JSONDecodeError:
    articles = []

# Artikel nach Status filtern
if status_filter != "Alle":
    articles = [a for a in articles if a.get("status") == status_filter]

# Artikelübersicht
st.title("📰 RSS Artikel Übersicht")
st.markdown("---")

if not articles:
    st.info("Keine Artikel gefunden.")
else:
    st.markdown("### 📄 Artikelliste")
    selected_ids = []
    all_statuses = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash"]

    for article in articles:
        col1, col2, col3, col4, col5, col6, col7 = st.columns([0.5, 1.2, 2.5, 2, 1, 2, 1.2])
        with col1:
            if st.checkbox("", key=f"select_{article['id']}"):
                selected_ids.append(article['id'])
        with col2:
            date = parsedate_to_datetime(article['date']).strftime("%d.%m.%y")
            st.markdown(date)
        with col3:
            st.markdown(article['title'])
        with col4:
            st.markdown(article['summary'][:150] + ("..." if len(article['summary']) > 150 else ""))
        with col5:
            word_count = len(article['text'].split())
            st.markdown(str(word_count))
        with col6:
            st.markdown(", ".join(article.get("tags", [])))
        with col7:
            status = st.selectbox("", all_statuses, index=all_statuses.index(article.get("status", "New")), key=f"status_{article['id']}")
            if status != article.get("status"):
                article["status"] = status
                save_articles(articles)
                st.rerun()

    if selected_ids:
        new_status = st.selectbox("Status für ausgewählte Artikel setzen", all_statuses)
        if st.button("✅ Status aktualisieren"):
            for article in articles:
                if article['id'] in selected_ids:
                    article['status'] = new_status
            save_articles(articles)
            st.success("Status aktualisiert.")
            st.rerun()

    st.markdown("---")

    if st.button("✍️ Artikel mit Status 'Rewrite' umschreiben"):
        rewrite_articles()
        st.rerun()

    st.markdown("---")