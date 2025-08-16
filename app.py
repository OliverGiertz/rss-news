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
from utils.dalle_generator import generate_dalle_image
import os
from collections import Counter
import time

# === Page Configuration ===
st.set_page_config(
    page_title="📰 RSS Artikel Manager",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === Custom CSS für modernes Design ===
st.markdown("""
<style>
    /* Hauptcontainer */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    
    /* Artikel Cards */
    .article-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #667eea;
        transition: transform 0.2s;
    }
    
    .article-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.15);
    }
    
    /* Status Badges */
    .status-badge {
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-right: 0.5rem;
    }
    
    .status-new { background-color: #e3f2fd; color: #1976d2; }
    .status-rewrite { background-color: #fff3e0; color: #f57c00; }
    .status-process { background-color: #f3e5f5; color: #7b1fa2; }
    .status-online { background-color: #e8f5e8; color: #388e3c; }
    .status-hold { background-color: #fce4ec; color: #c2185b; }
    .status-trash { background-color: #ffebee; color: #d32f2f; }
    
    /* Filter Section */
    .filter-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    /* Stats Cards */
    .stats-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .stats-number {
        font-size: 2rem;
        font-weight: bold;
        color: #667eea;
    }
    
    /* Action Buttons */
    .action-button {
        margin: 0.25rem;
    }
    
    /* Image Gallery */
    .image-gallery {
        display: flex;
        gap: 1rem;
        overflow-x: auto;
        padding: 1rem 0;
    }
    
    .image-item {
        min-width: 200px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# === Initialize Session State ===
if 'selected_articles' not in st.session_state:
    st.session_state.selected_articles = set()
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""
if 'status_filter' not in st.session_state:
    st.session_state.status_filter = "New"
if 'feed_filter' not in st.session_state:
    st.session_state.feed_filter = "Alle"

# === Helper Functions ===
def get_status_badge(status):
    """Erstellt einen farbigen Status-Badge"""
    status_classes = {
        "New": "status-new",
        "Rewrite": "status-rewrite", 
        "Process": "status-process",
        "Online": "status-online",
        "On Hold": "status-hold",
        "Trash": "status-trash"
    }
    class_name = status_classes.get(status, "status-new")
    return f'<span class="status-badge {class_name}">{status}</span>'

def format_date(date_str):
    """Formatiert Datum für bessere Lesbarkeit"""
    try:
        if "GMT" in date_str or "+" in date_str:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z").strftime("%d.%m.%Y %H:%M")
        else:
            return date_str[:16].replace("T", " ")
    except:
        return date_str[:10]

def get_word_count(text):
    """Zählt Wörter im Text"""
    return len(text.split()) if text else 0

def show_notification(message, type="success"):
    """Zeigt eine Benachrichtigung an"""
    if type == "success":
        st.success(message)
    elif type == "error":
        st.error(message)
    elif type == "warning":
        st.warning(message)
    elif type == "info":
        st.info(message)

# === Header ===
st.markdown("""
<div class="main-header">
    <h1>📰 RSS Artikel Manager</h1>
    <p>Moderne Verwaltung deiner RSS-Feeds und Artikel</p>
</div>
""", unsafe_allow_html=True)

# === Tab Navigation ===
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Dashboard", 
    "📰 Artikel", 
    "📡 Feeds", 
    "🖼️ Bilder", 
    "📊 Statistiken"
])

# === Dashboard Tab ===
with tab1:
    st.header("📊 Übersicht")
    
    # Lade Daten
    all_articles = load_articles()
    feeds = load_feeds()
    
    # Statistiken
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Gesamt Artikel</div>
        </div>
        """.format(len(all_articles)), unsafe_allow_html=True)
    
    with col2:
        new_count = len([a for a in all_articles if a.get("status") == "New"])
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Neue Artikel</div>
        </div>
        """.format(new_count), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>RSS Feeds</div>
        </div>
        """.format(len(feeds)), unsafe_allow_html=True)
    
    with col4:
        online_count = len([a for a in all_articles if a.get("status") == "Online"])
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Online</div>
        </div>
        """.format(online_count), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Quick Actions
    st.subheader("⚡ Schnellaktionen")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Alle Feeds aktualisieren", use_container_width=True):
            with st.spinner("Feeds werden aktualisiert..."):
                existing_ids = [a["id"] for a in all_articles]
                process_articles(existing_ids)
                show_notification("Feeds erfolgreich aktualisiert!")
                time.sleep(1)
                st.rerun()
    
    with col2:
        if st.button("✍️ Artikel umschreiben", use_container_width=True):
            rewrite_count = len([a for a in all_articles if a.get("status") == "Rewrite"])
            if rewrite_count > 0:
                with st.spinner(f"{rewrite_count} Artikel werden umgeschrieben..."):
                    rewrite_articles()
                    show_notification(f"{rewrite_count} Artikel erfolgreich umgeschrieben!")
                    time.sleep(1)
                    st.rerun()
            else:
                show_notification("Keine Artikel zum Umschreiben gefunden.", "info")
    
    with col3:
        if st.button("🧹 Aufräumen", use_container_width=True):
            trash_count = len([a for a in all_articles if a.get("status") == "Trash"])
            if trash_count > 0:
                show_notification(f"{trash_count} Artikel im Papierkorb gefunden.", "info")
            else:
                show_notification("Keine Artikel zum Aufräumen gefunden.", "info")
    
    # Neueste Artikel Preview
    st.subheader("🕒 Neueste Artikel")
    recent_articles = sorted(all_articles, key=lambda x: x.get("date", ""), reverse=True)[:5]
    
    for article in recent_articles:
        st.markdown(f"""
        <div class="article-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>{article.get('title', 'Kein Titel')}</strong>
                    <br>
                    <small>{format_date(article.get('date', ''))}</small>
                </div>
                <div>
                    {get_status_badge(article.get('status', 'New'))}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# === Artikel Tab ===
with tab2:
    st.header("📰 Artikel verwalten")
    
    # Filter Section
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.subheader("🔍 Filter & Suche")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_options = ["Alle", "New", "Rewrite", "Process", "Online", "On Hold", "Trash"]
        st.session_state.status_filter = st.selectbox(
            "Status", 
            status_options, 
            index=status_options.index(st.session_state.status_filter)
        )
    
    with col2:
        # Feed Filter
        source_to_name = {f.get("url"): f.get("name", "Unbekannt") for f in feeds}
        source_counter = Counter([a.get("source", "Unbekannt") for a in all_articles])
        
        feed_options = ["Alle"]
        feed_map = {"Alle": None}
        
        for source, count in source_counter.items():
            name = source_to_name.get(source, "Unbekannt")
            label = f"{name} ({count})"
            feed_options.append(label)
            feed_map[label] = source
        
        selected_feed_label = st.selectbox("Feed", feed_options)
        st.session_state.feed_filter = selected_feed_label
    
    with col3:
        st.session_state.search_query = st.text_input(
            "Suche", 
            value=st.session_state.search_query,
            placeholder="Titel, Text oder Tags durchsuchen..."
        )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Filter anwenden
    filtered_articles = all_articles
    
    # Status Filter
    if st.session_state.status_filter != "Alle":
        filtered_articles = [a for a in filtered_articles if a.get("status") == st.session_state.status_filter]
    
    # Feed Filter
    if st.session_state.feed_filter != "Alle":
        selected_source = feed_map[st.session_state.feed_filter]
        filtered_articles = [a for a in filtered_articles if a.get("source") == selected_source]
    
    # Suche
    if st.session_state.search_query:
        query = st.session_state.search_query.lower()
        filtered_articles = [
            a for a in filtered_articles 
            if query in a.get("title", "").lower() 
            or query in a.get("text", "").lower()
            or any(query in tag.lower() for tag in a.get("tags", []))
        ]
    
    # Ergebnisse anzeigen
    st.write(f"**{len(filtered_articles)} Artikel gefunden**")
    
    # Artikel Cards
    for article in filtered_articles:
        has_incomplete_images = any(
            not all(k in img and img[k] for k in ("caption", "copyright", "copyright_url"))
            for img in article.get("images", [])
        )
        
        # Article Card
        st.markdown('<div class="article-card">', unsafe_allow_html=True)
        
        # Header
        col1, col2 = st.columns([3, 1])
        
        with col1:
            title = article.get("title", "Kein Titel")
            if has_incomplete_images:
                title += " ⚠️"
            st.markdown(f"**{title}**")
            st.markdown(f"📅 {format_date(article.get('date', ''))}")
            
        with col2:
            st.markdown(get_status_badge(article.get("status", "New")), unsafe_allow_html=True)
        
        # Content Preview
        summary = article.get("summary", "")[:200]
        if len(summary) == 200:
            summary += "..."
        st.markdown(summary)
        
        # Meta Info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"📝 **{get_word_count(article.get('text', ''))} Wörter**")
        with col2:
            tags = article.get("tags", [])
            if tags:
                st.markdown(f"🏷️ {', '.join(tags[:3])}{'...' if len(tags) > 3 else ''}")
        with col3:
            source_name = source_to_name.get(article.get("source", ""), "Unbekannt")
            st.markdown(f"📡 {source_name}")
        
        # Actions
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Status ändern
            status_options = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash"]
            current_status = article.get("status", "New")
            new_status = st.selectbox(
                "Status", 
                status_options, 
                index=status_options.index(current_status),
                key=f"status_{article['id']}"
            )
            
            if new_status != current_status:
                # Artikel in der Liste finden und aktualisieren
                for idx, art in enumerate(all_articles):
                    if art["id"] == article["id"]:
                        all_articles[idx]["status"] = new_status
                        break
                save_articles(all_articles)
                show_notification(f"Status auf '{new_status}' geändert!")
                time.sleep(0.5)
                st.rerun()
        
        with col2:
            if st.button("📋 Text kopieren", key=f"copy_{article['id']}"):
                text_to_copy = f"{article['title']}\n\n{article['text']}\n\nQuelle: {article['link']}"
                st.code(text_to_copy, language="markdown")
                show_notification("Text bereit zum Kopieren!")
        
        with col3:
            if st.button("🔗 Original öffnen", key=f"link_{article['id']}"):
                st.markdown(f"[🔗 Artikel öffnen]({article.get('link', '#')})")
        
        with col4:
            # Details anzeigen
            if st.button("📖 Details", key=f"details_{article['id']}"):
                st.session_state[f"show_details_{article['id']}"] = not st.session_state.get(f"show_details_{article['id']}", False)
        
        # Details Section (wenn erweitert)
        if st.session_state.get(f"show_details_{article['id']}", False):
            st.markdown("---")
            
            # Artikel Text
            with st.expander("📝 Volltext", expanded=False):
                st.code(article.get("text", ""), language="markdown")
            
            # Tags bearbeiten
            with st.expander("🏷️ Tags bearbeiten", expanded=False):
                current_tags = ", ".join(article.get("tags", []))
                new_tags = st.text_area("Tags (getrennt durch Komma)", value=current_tags, key=f"tags_{article['id']}")
                
                if st.button("Tags speichern", key=f"save_tags_{article['id']}"):
                    tag_list = [tag.strip() for tag in new_tags.split(",") if tag.strip()]
                    for idx, art in enumerate(all_articles):
                        if art["id"] == article["id"]:
                            all_articles[idx]["tags"] = tag_list
                            break
                    save_articles(all_articles)
                    show_notification("Tags gespeichert!")
                    st.rerun()
            
            # Bilder
            if article.get("images"):
                with st.expander("🖼️ Bilder verwalten", expanded=False):
                    for i, img in enumerate(article.get("images", [])):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.image(img["url"], width=200)
                        
                        with col2:
                            caption = st.text_input("Bildtitel", value=img.get("caption", ""), key=f"caption_{article['id']}_{i}")
                            copyright_text = st.text_input("Copyright", value=img.get("copyright", ""), key=f"copyright_{article['id']}_{i}")
                            copyright_url = st.text_input("Quelle URL", value=img.get("copyright_url", ""), key=f"copyright_url_{article['id']}_{i}")
                            
                            if st.button("Bilddaten speichern", key=f"save_img_{article['id']}_{i}"):
                                img["caption"] = caption or "Kein Bildtitel vorhanden"
                                img["copyright"] = copyright_text or "Unbekannt"
                                img["copyright_url"] = copyright_url or "#"
                                
                                for idx, art in enumerate(all_articles):
                                    if art["id"] == article["id"]:
                                        all_articles[idx] = article
                                        break
                                save_articles(all_articles)
                                show_notification("Bilddaten gespeichert!")
                                st.rerun()
            
            # DALL-E Bildgenerierung
            if st.button("🪄 KI-Bild generieren", key=f"dalle_{article['id']}"):
                if not any(img.get("copyright") == "OpenAI DALL·E" for img in article.get("images", [])):
                    with st.spinner("Bild wird generiert..."):
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
                            show_notification("DALL·E-Bild erfolgreich hinzugefügt!")
                            st.rerun()
                        else:
                            show_notification("Fehler beim Erzeugen des Bildes.", "error")
                else:
                    show_notification("Ein KI-generiertes Bild ist bereits vorhanden.", "info")
        
        st.markdown('</div>', unsafe_allow_html=True)

# === Feeds Tab ===
with tab3:
    st.header("📡 RSS Feeds verwalten")
    
    # Feed hinzufügen
    with st.expander("➕ Neuen Feed hinzufügen", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            new_url = st.text_input("Feed URL")
        with col2:
            new_name = st.text_input("Feed Name")
        
        if st.button("Feed hinzufügen", use_container_width=True):
            if new_url and new_name:
                if not any(f.get("url") == new_url for f in feeds):
                    feeds.append({"url": new_url, "name": new_name})
                    save_feeds(feeds)
                    show_notification(f"Feed '{new_name}' hinzugefügt!")
                    st.rerun()
                else:
                    show_notification("Dieser Feed existiert bereits.", "warning")
            else:
                show_notification("Bitte URL und Name eingeben.", "error")
    
    # Feeds anzeigen
    for idx, feed in enumerate(feeds):
        feed_url = feed.get("url", "")
        feed_name = feed.get("name", "Unbekannt")
        article_count = sum(1 for a in all_articles if a.get("source") == feed_url)
        
        st.markdown(f"""
        <div class="article-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>{feed_name}</strong>
                    <br>
                    <small>{feed_url}</small>
                    <br>
                    <span style="color: #667eea;">📰 {article_count} Artikel</span>
                </div>
                <div>
                    <span class="status-badge status-online">{article_count} Artikel</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Feed Actions
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✏️ Bearbeiten", key=f"edit_feed_{idx}"):
                st.session_state[f"edit_feed_{idx}"] = not st.session_state.get(f"edit_feed_{idx}", False)
        
        with col2:
            if st.button("🔄 Aktualisieren", key=f"refresh_feed_{idx}"):
                with st.spinner("Feed wird aktualisiert..."):
                    existing_ids = [a["id"] for a in all_articles]
                    # Hier könntest du eine einzelne Feed-Update-Funktion implementieren
                    process_articles(existing_ids)
                    show_notification(f"Feed '{feed_name}' aktualisiert!")
                    st.rerun()
        
        with col3:
            if st.button("🗑️ Löschen", key=f"delete_feed_{idx}"):
                feeds.pop(idx)
                save_feeds(feeds)
                show_notification(f"Feed '{feed_name}' gelöscht!", "warning")
                st.rerun()
        
        # Edit Form
        if st.session_state.get(f"edit_feed_{idx}", False):
            with st.form(f"edit_form_{idx}"):
                new_feed_url = st.text_input("URL", value=feed_url)
                new_feed_name = st.text_input("Name", value=feed_name)
                
                if st.form_submit_button("Änderungen speichern"):
                    feeds[idx]["url"] = new_feed_url
                    feeds[idx]["name"] = new_feed_name
                    save_feeds(feeds)
                    show_notification("Feed aktualisiert!")
                    st.session_state[f"edit_feed_{idx}"] = False
                    st.rerun()

# === Bilder Tab ===
with tab4:
    st.header("🖼️ Bilderverwaltung")
    
    # Alle Bilder sammeln
    all_images = []
    for article in all_articles:
        for img in article.get("images", []):
            img_data = img.copy()
            img_data["article_title"] = article.get("title", "Unbekannt")
            img_data["article_id"] = article.get("id")
            all_images.append(img_data)
    
    if all_images:
        st.write(f"**{len(all_images)} Bilder gefunden**")
        
        # Bilder in Spalten anzeigen
        cols = st.columns(3)
        for idx, img in enumerate(all_images):
            with cols[idx % 3]:
                st.image(img["url"], use_column_width=True)
                st.markdown(f"**{img.get('caption', 'Kein Titel')}**")
                st.markdown(f"📰 {img['article_title']}")
                st.markdown(f"©️ {img.get('copyright', 'Unbekannt')}")
                
                if img.get("copyright_url") and img["copyright_url"] != "#":
                    st.markdown(f"[🔗 Quelle]({img['copyright_url']})")
    else:
        st.info("Keine Bilder gefunden.")

# === Statistiken Tab ===
with tab5:
    st.header("📊 Detaillierte Statistiken")
    
    # Status Verteilung
    status_counts = Counter([a.get("status", "New") for a in all_articles])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Status Verteilung")
        for status, count in status_counts.items():
            percentage = (count / len(all_articles) * 100) if all_articles else 0
            st.markdown(f"{get_status_badge(status)} {count} ({percentage:.1f}%)", unsafe_allow_html=True)
    
    with col2:
        st.subheader("📡 Artikel pro Feed")
        feed_counts = Counter([source_to_name.get(a.get("source", ""), "Unbekannt") for a in all_articles])
        for feed_name, count in feed_counts.most_common():
            st.markdown(f"**{feed_name}:** {count} Artikel")
    
    # Weitere Statistiken
    st.subheader("📝 Textstatistiken")
    
    word_counts = [get_word_count(a.get("text", "")) for a in all_articles]
    if word_counts:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Durchschnittliche Wortanzahl", f"{sum(word_counts) // len(word_counts)}")
        
        with col2:
            st.metric("Längster Artikel", f"{max(word_counts)} Wörter")
        
        with col3:
            st.metric("Kürzester Artikel", f"{min(word_counts)} Wörter")
    
    # Tag Cloud Simulation
    st.subheader("🏷️ Häufigste Tags")
    all_tags = []
    for article in all_articles:
        all_tags.extend(article.get("tags", []))
    
    if all_tags:
        tag_counts = Counter(all_tags)
        for tag, count in tag_counts.most_common(10):
            st.markdown(f"**{tag}:** {count}x verwendet")
    else:
        st.info("Keine Tags gefunden.")