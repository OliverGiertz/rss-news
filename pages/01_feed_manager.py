# pages/01_feed_manager.py

import streamlit as st
from main import load_feeds, save_feeds, load_articles
import logging

# === Logging vorbereiten ===
log_dir = "logs"
log_file = f"{log_dir}/rss_tool.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

st.set_page_config(page_title="📡 Feed-Verwaltung")

st.title("📡 RSS Feed-Verwaltung")
feeds = load_feeds()
articles = load_articles()

# === Neuen Feed hinzufügen ===
st.subheader("➕ Neuen Feed hinzufügen")

with st.form("add_feed_form"):
    new_url = st.text_input("Feed URL", "")
    new_name = st.text_input("Feed Name", "")
    submitted = st.form_submit_button("Feed hinzufügen")
    if submitted:
        if new_url and new_name:
            if not any(f.get("url") == new_url for f in feeds):
                feeds.append({"url": new_url, "name": new_name})
                save_feeds(feeds)
                logging.info(f"🔗 Neuer Feed hinzugefügt: {new_name} ({new_url})")
                st.success(f"Feed '{new_name}' hinzugefügt.")
                st.rerun()
            else:
                st.warning("⚠️ Dieser Feed existiert bereits.")
        else:
            st.error("❌ Bitte gib sowohl URL als auch Name ein.")

# === Bestehende Feeds bearbeiten ===
st.subheader("🛠️ Vorhandene Feeds bearbeiten oder löschen")

for idx, feed in enumerate(feeds):
    with st.expander(f"🔗 {feed.get('name')}"):
        url = st.text_input(f"Feed-URL {idx}", value=feed.get("url"), key=f"url_{idx}")
        name = st.text_input(f"Feed-Name {idx}", value=feed.get("name"), key=f"name_{idx}")
        count = sum(1 for a in articles if a.get("source") == feed.get("url"))

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Änderungen speichern", key=f"save_{idx}"):
                old_url, old_name = feed.get("url"), feed.get("name")
                feeds[idx]["url"] = url
                feeds[idx]["name"] = name
                save_feeds(feeds)
                logging.info(f"✏️ Feed geändert: '{old_name}' ({old_url}) → '{name}' ({url})")
                st.success("Änderungen gespeichert.")
                st.rerun()

        with col2:
            if st.button("🗑️ Feed löschen", key=f"delete_{idx}"):
                deleted_feed = feeds.pop(idx)
                save_feeds(feeds)
                logging.info(f"❌ Feed gelöscht: {deleted_feed.get('name')} ({deleted_feed.get('url')})")
                st.warning("Feed gelöscht.")
                st.rerun()

        st.caption(f"📰 Verknüpfte Artikel: {count}")
