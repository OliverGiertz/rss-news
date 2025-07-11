# app.py (aktualisiert mit Feed-Dropdown)

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
from utils.dalle_generator import generate_dalle_image
import os
from collections import Counter

st.set_page_config(page_title="📰 RSS Artikel Manager", layout="wide")
st.title("📰 RSS Artikel Manager")

# === Sidebar: Feed-Verwaltung ===
st.sidebar.header("📡 RSS Feeds verwalten")
feeds = load_feeds()
new_feed = st.sidebar.text_input("Neuen RSS Feed hinzufügen")
if st.sidebar.button("Feed hinzufügen"):
    if new_feed and new_feed not in [f.get("url", f) for f in feeds]:
        feeds.append({"url": new_feed, "name": "Neuer Feed"})
        save_feeds(feeds)
        st.sidebar.success("Feed hinzugefügt")

if st.sidebar.button("🔄 Alle Feeds neu laden"):
    existing_ids = [a["id"] for a in load_articles()]
    process_articles(existing_ids)
    st.rerun()

if st.sidebar.button("✍️ Artikel umschreiben (Rewrite)"):
    rewrite_articles()
    st.rerun()

# === Hauptbereich: Artikelübersicht ===
st.header("📋 Artikelübersicht")
status_filter = st.selectbox("Status filtern", ["Alle", "New", "Rewrite", "Process", "Online", "On Hold", "Trash"], index=1)

all_articles = load_articles()
articles = all_articles

if status_filter != "Alle":
    articles = [a for a in articles if a.get("status") == status_filter]

# === Feed-Filter ===
source_to_name = {f.get("url"): f.get("name", "unidentified") for f in feeds}
source_counter = Counter([a.get("source", "unidentified") for a in articles])

feed_options = ["Alle ({})".format(len(articles))]
feed_map = {}

for source, count in source_counter.items():
    name = source_to_name.get(source, "unidentified")
    label = f"{name} ({count})"
    feed_options.append(label)
    feed_map[label] = source

selected_feed_label = st.selectbox("Feed-Auswahl", feed_options)

if selected_feed_label != feed_options[0]:  # nicht „Alle“
    selected_source = feed_map[selected_feed_label]
    articles = [a for a in articles if a.get("source", "unidentified") == selected_source]

# === Artikel-Tabelle ===
if articles:
    st.markdown("### 📄 Übersichtstabelle")
    st.write("**Spaltenübersicht:** Auswahl | Datum | Titel | Zusammenfassung | Wörter | Tags | Status")

    for article in articles:
        has_incomplete_images = any(
            not all(k in img and img[k] for k in ("caption", "copyright", "copyright_url"))
            for img in article.get("images", [])
        )

        cols = st.columns([0.05, 0.1, 0.2, 0.25, 0.05, 0.2, 0.15])
        with cols[0]:
            st.checkbox("", key=f"select_{article['id']}")
        with cols[1]:
            date_str = article["date"]
            if "GMT" in date_str or "+" in date_str:
                date_str = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z").strftime("%d.%m.%y")
            else:
                date_str = date_str[:10]
            st.markdown(date_str)
        with cols[2]:
            title = f"**{article['title']}**"
            if has_incomplete_images:
                title += " ⚠️"
            st.markdown(title)
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
                for idx, art in enumerate(all_articles):
                    if art["id"] == article["id"]:
                        all_articles[idx] = article
                        break
                save_articles(all_articles)
                st.rerun()

        with st.expander(f"🔍 {article['title']}"):
            st.markdown("#### ✍️ Artikeltext")
            st.code(f"{article['title']}\n\n{article['text']}\n\nQuelle: {article['link']}", language="markdown")

            st.markdown("#### 🌿 Tags")
            st.code(", ".join(article.get("tags", [])), language="markdown")

            st.markdown("#### 🖼️ Bilder")
            for i, img in enumerate(article.get("images", [])):
                st.image(img["url"], caption=img.get("caption", "Kein Titel"), use_column_width=True)

                with st.form(f"edit_image_{article['id']}_{i}", clear_on_submit=False):
                    caption = st.text_input("Bildtitel", value=img.get("caption", ""))
                    copyright = st.text_input("Copyright", value=img.get("copyright", ""))
                    copyright_url = st.text_input("Quelle", value=img.get("copyright_url", ""))
                    if st.form_submit_button("Änderungen speichern"):
                        img["caption"] = caption or "Kein Bildtitel vorhanden"
                        img["copyright"] = copyright or "Unbekannt"
                        img["copyright_url"] = copyright_url or "#"
                        for idx, art in enumerate(all_articles):
                            if art["id"] == article["id"]:
                                all_articles[idx] = article
                                break
                        save_articles(all_articles)
                        st.success("Bilddaten gespeichert")

            if st.button("🪄 KI-Bild generieren", key=f"dalle_{article['id']}"):
                if not any(img.get("copyright") == "OpenAI DALL·E" for img in article.get("images", [])):
                    prompt = article["title"]
                    image_url = generate_dalle_image(prompt)
                    if image_url:
                        article.setdefault("images", []).append({
                            "url": image_url,
                            "alt": f"KI-generiertes Titelbild zu: {prompt}",
                            "caption": f"KI-generiertes Titelbild zu: {prompt}",
                            "copyright": "OpenAI DALL·E",
                            "copyright_url": "https://openai.com/dall-e"
                        })
                        for idx, art in enumerate(all_articles):
                            if art["id"] == article["id"]:
                                all_articles[idx] = article
                                break
                        save_articles(all_articles)
                        st.success("DALL·E-Bild erfolgreich hinzugefügt")
                        st.rerun()
                    else:
                        st.error("Fehler beim Erzeugen des Bildes.")
                else:
                    st.info("Ein KI-generiertes Bild ist bereits vorhanden.")
else:
    st.info("Keine Artikel für den gewählten Status gefunden.")
