# app.py

import streamlit as st
from datetime import datetime
from main import (
    load_feeds,
    save_feeds,
    load_articles,
    save_articles,
    process_articles,
    rewrite_articles,
    upload_articles_to_wp
)
from utils.dalle_generator import generate_dalle_image
from utils.wordpress_uploader import WordPressUploader
from utils.css_loader import load_css, apply_dark_theme
from utils.config import validate_env
import os
from collections import Counter
import time

# === Page Configuration ===
st.set_page_config(
    page_title="📰 RSS Artikel Manager",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === CSS & Theme laden ===
load_css()
apply_dark_theme()

# === Environment-Validierung (.env) ===
env_check = validate_env()
if not env_check.get("ok"):
    st.error("🔒 Sicherheits-/Konfigurationshinweis: Bitte .env korrekt konfigurieren.")
    for msg in env_check.get("errors", []):
        st.markdown(f"- ❌ {msg}")
    for msg in env_check.get("warnings", []):
        st.markdown(f"- ⚠️ {msg}")
elif env_check.get("warnings"):
    st.info("ℹ️ Hinweise zur Konfiguration:")
    for msg in env_check.get("warnings", []):
        st.markdown(f"- ⚠️ {msg}")

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
        "Trash": "status-trash",
        "WordPress Pending": "status-wp-pending"
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

def test_wordpress_connection():
    """Testet die WordPress-Verbindung"""
    try:
        uploader = WordPressUploader()
        success, message = uploader.test_connection()
        return success, message
    except Exception as e:
        return False, f"Fehler beim Testen der Verbindung: {str(e)}"

# === Header ===
st.markdown("""
<div class="main-header">
    <h1>📰 RSS Artikel Manager</h1>
    <p>Moderne Verwaltung deiner RSS-Feeds und Artikel mit WordPress-Integration</p>
</div>
""", unsafe_allow_html=True)

# === Tab Navigation ===
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📋 Dashboard", 
    "📰 Artikel", 
    "📡 Feeds", 
    "🖼️ Bilder", 
    "📊 Statistiken",
    "🔧 WordPress"
])

# === Dashboard Tab ===
with tab1:
    st.header("📊 Übersicht")
    
    # Lade Daten
    all_articles = load_articles()
    feeds = load_feeds()
    
    # Statistiken
    col1, col2, col3, col4, col5 = st.columns(5)
    
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
        process_count = len([a for a in all_articles if a.get("status") == "Process"])
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Bereit für WP</div>
        </div>
        """.format(process_count), unsafe_allow_html=True)
    
    with col4:
        wp_pending_count = len([a for a in all_articles if a.get("status") == "WordPress Pending"])
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>WP Ausstehend</div>
        </div>
        """.format(wp_pending_count), unsafe_allow_html=True)
    
    with col5:
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
    
    col1, col2, col3, col4 = st.columns(4)
    
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
        if st.button("📤 WordPress Upload", use_container_width=True):
            process_count = len([a for a in all_articles if a.get("status") == "Process"])
            if process_count > 0:
                with st.spinner(f"{process_count} Artikel werden zu WordPress hochgeladen..."):
                    upload_results = upload_articles_to_wp()
                    
                    if upload_results.get('error'):
                        show_notification(f"Fehler beim WordPress-Upload: {upload_results['error']}", "error")
                    else:
                        successful = upload_results.get('successful', 0)
                        failed = upload_results.get('failed', 0)
                        duplicates = upload_results.get('duplicates', 0)
                        
                        if successful > 0:
                            show_notification(f"✅ {successful} Artikel erfolgreich zu WordPress hochgeladen!")
                        if failed > 0:
                            show_notification(f"⚠️ {failed} Artikel konnten nicht hochgeladen werden.", "warning")
                        if duplicates > 0:
                            show_notification(f"ℹ️ {duplicates} Duplikate übersprungen.", "info")
                    
                    time.sleep(2)
                    st.rerun()
            else:
                show_notification("Keine Artikel für WordPress-Upload gefunden.", "info")
    
    with col4:
        if st.button("🧹 Aufräumen", use_container_width=True):
            trash_count = len([a for a in all_articles if a.get("status") == "Trash"])
            if trash_count > 0:
                show_notification(f"{trash_count} Artikel im Papierkorb gefunden.", "info")
            else:
                show_notification("Keine Artikel zum Aufräumen gefunden.", "info")
    
    # WordPress-Status-Übersicht
    if wp_pending_count > 0 or online_count > 0:
        st.subheader("🔗 WordPress-Status")
        
        wp_articles = [a for a in all_articles if a.get("status") in ["WordPress Pending", "Online"]]
        for article in wp_articles[:5]:  # Nur die ersten 5 anzeigen
            st.markdown(f"""
            <div class="wp-status">
                <strong>{article.get('title', 'Kein Titel')}</strong>
                {get_status_badge(article.get('status', 'Unknown'))}
                <br>
                <small>WP Post ID: {article.get('wp_post_id', 'Unbekannt')} | Upload: {format_date(article.get('wp_upload_date', ''))}</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Neueste Artikel Preview
    st.subheader("🕒 Neueste Artikel")
    recent_articles = sorted(all_articles, key=lambda x: x.get("date", ""), reverse=True)[:5]
    
    for article in recent_articles:
        st.markdown(f"""
        <div class="article-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 class="article-title">{article.get('title', 'Kein Titel')}</h3>
                    <div class="article-meta">{format_date(article.get('date', ''))}</div>
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
        status_options = ["Alle", "New", "Rewrite", "Process", "Online", "On Hold", "Trash", "WordPress Pending"]
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
    
    # Ergebnisse und Massenoperationen
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write(f"**{len(filtered_articles)} Artikel gefunden**")
    
    with col2:
        # Select All / None Buttons
        if filtered_articles:
            col_select_1, col_select_2 = st.columns(2)
            with col_select_1:
                if st.button("✓ Alle auswählen", key="select_all"):
                    for article in filtered_articles:
                        st.session_state.selected_articles.add(article['id'])
                    st.rerun()
            
            with col_select_2:
                if st.button("✗ Auswahl aufheben", key="select_none"):
                    st.session_state.selected_articles.clear()
                    st.rerun()
    
    # Bulk Operations Section
    selected_count = len(st.session_state.selected_articles)
    if selected_count > 0:
        st.markdown(f"""
        <div class="filter-section" style="margin-top: 10px;">
            <h4>⚡ Massenoperationen ({selected_count} Artikel ausgewählt)</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick Actions für ausgewählte Artikel
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("🔄 Feeds aktualisieren", use_container_width=True, key="bulk_update_feeds"):
                with st.spinner("Feeds werden aktualisiert..."):
                    existing_ids = [a["id"] for a in all_articles]
                    process_articles(existing_ids)
                    show_notification("Feeds erfolgreich aktualisiert!")
                    time.sleep(1)
                    st.rerun()
        
        with col2:
            # Bulk Status Change
            bulk_status = st.selectbox(
                "Status ändern", 
                ["--Auswählen--"] + ["New", "Rewrite", "Process", "Online", "On Hold", "Trash", "WordPress Pending"],
                key="bulk_status"
            )
            
            if bulk_status != "--Auswählen--" and st.button("Status anwenden", key="apply_bulk_status"):
                changed_count = 0
                for article in all_articles:
                    if article["id"] in st.session_state.selected_articles:
                        article["status"] = bulk_status
                        changed_count += 1
                
                if changed_count > 0:
                    save_articles(all_articles)
                    show_notification(f"{changed_count} Artikel auf '{bulk_status}' gesetzt!")
                    st.session_state.selected_articles.clear()
                    st.rerun()
        
        with col3:
            # Bulk Rewrite
            rewrite_selected_count = len([a for a in all_articles if a["id"] in st.session_state.selected_articles and a.get("status") != "Rewrite"])
            if st.button(f"✍️ Artikel umschreiben ({rewrite_selected_count})", use_container_width=True, key="bulk_rewrite"):
                # Ausgewählte Artikel auf "Rewrite" setzen
                for article in all_articles:
                    if article["id"] in st.session_state.selected_articles:
                        article["status"] = "Rewrite"
                
                save_articles(all_articles)
                
                # Umschreiben starten
                with st.spinner(f"{rewrite_selected_count} Artikel werden umgeschrieben..."):
                    rewrite_articles()
                    show_notification(f"{rewrite_selected_count} Artikel erfolgreich umgeschrieben!")
                    st.session_state.selected_articles.clear()
                    time.sleep(1)
                    st.rerun()
        
        with col4:
            # Bulk WordPress Upload
            wp_ready_selected = len([a for a in all_articles if a["id"] in st.session_state.selected_articles and a.get("status") == "Process"])
            if wp_ready_selected > 0:
                if st.button(f"📤 WordPress Upload ({wp_ready_selected})", use_container_width=True, key="bulk_wp_upload"):
                    with st.spinner(f"{wp_ready_selected} Artikel werden zu WordPress hochgeladen..."):
                        # Nur die ausgewählten "Process" Artikel hochladen
                        selected_process_articles = [a for a in all_articles if a["id"] in st.session_state.selected_articles and a.get("status") == "Process"]
                        
                        if selected_process_articles:
                            from utils.wordpress_uploader import upload_articles_to_wordpress
                            upload_results = upload_articles_to_wordpress(selected_process_articles)
                            
                            if upload_results.get('error'):
                                show_notification(f"Fehler beim WordPress-Upload: {upload_results['error']}", "error")
                            else:
                                successful = upload_results.get('successful', 0)
                                failed = upload_results.get('failed', 0)
                                duplicates = upload_results.get('duplicates', 0)
                                
                                # Status der erfolgreich hochgeladenen Artikel ändern
                                if successful > 0:
                                    for detail in upload_results.get('details', []):
                                        if detail.get('success'):
                                            article_id = detail.get('article_id')
                                            for article in all_articles:
                                                if article.get('id') == article_id:
                                                    article['status'] = "WordPress Pending"
                                                    article['wp_upload_date'] = datetime.now().isoformat()
                                                    article['wp_post_id'] = detail.get('wp_post_id')
                                                    break
                                    save_articles(all_articles)
                                
                                if successful > 0:
                                    show_notification(f"✅ {successful} Artikel erfolgreich zu WordPress hochgeladen!")
                                if failed > 0:
                                    show_notification(f"⚠️ {failed} Artikel konnten nicht hochgeladen werden.", "warning")
                                if duplicates > 0:
                                    show_notification(f"ℹ️ {duplicates} Duplikate übersprungen.", "info")
                        
                        st.session_state.selected_articles.clear()
                        time.sleep(2)
                        st.rerun()
            else:
                st.markdown("*Keine Process-Artikel ausgewählt*")
        
        with col5:
            # Bulk Delete/Trash
            if st.button("🗑️ In Papierkorb", use_container_width=True, key="bulk_trash"):
                trash_count = 0
                for article in all_articles:
                    if article["id"] in st.session_state.selected_articles:
                        article["status"] = "Trash"
                        trash_count += 1
                
                if trash_count > 0:
                    save_articles(all_articles)
                    show_notification(f"{trash_count} Artikel in Papierkorb verschoben!")
                    st.session_state.selected_articles.clear()
                    st.rerun()
    
    # Artikel Cards
    for article in filtered_articles:
        has_incomplete_images = any(
            not all(k in img and img[k] for k in ("caption", "copyright", "copyright_url"))
            for img in article.get("images", [])
        )
        
        # Article Card
        st.markdown('<div class="article-card">', unsafe_allow_html=True)
        
        # Header with Checkbox
        col_check, col_content, col_status = st.columns([0.3, 2.7, 1])
        
        with col_check:
            # Checkbox für Artikel-Auswahl
            is_selected = article["id"] in st.session_state.selected_articles
            if st.checkbox("", value=is_selected, key=f"check_{article['id']}"):
                st.session_state.selected_articles.add(article['id'])
            else:
                st.session_state.selected_articles.discard(article['id'])
        
        with col_content:
            title = article.get("title", "Kein Titel")
            if has_incomplete_images:
                title += " ⚠️"
            st.markdown(f'<h3 class="article-title">{title}</h3>', unsafe_allow_html=True)
            st.markdown(f'<div class="article-meta">📅 {format_date(article.get("date", ""))}</div>', unsafe_allow_html=True)
            
            # WordPress-Info anzeigen falls vorhanden
            if article.get("wp_post_id"):
                st.markdown(f'<div class="article-meta">🔗 WordPress ID: {article.get("wp_post_id")} | Upload: {format_date(article.get("wp_upload_date", ""))}</div>', unsafe_allow_html=True)
            
        with col_status:
            st.markdown(get_status_badge(article.get("status", "New")), unsafe_allow_html=True)
        
        # Content Preview
        summary = article.get("summary", "")[:200]
        if len(summary) == 200:
            summary += "..."
        st.markdown(f'<div class="article-summary">{summary}</div>', unsafe_allow_html=True)
        
        # Meta Info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="article-footer">📝 **{get_word_count(article.get("text", ""))} Wörter**</div>', unsafe_allow_html=True)
        with col2:
            tags = article.get("tags", [])
            if tags:
                st.markdown(f'<div class="article-footer">🏷️ {", ".join(tags[:3])}{"..." if len(tags) > 3 else ""}</div>', unsafe_allow_html=True)
        with col3:
            source_name = source_to_name.get(article.get("source", ""), "Unbekannt")
            st.markdown(f'<div class="article-footer">📡 {source_name}</div>', unsafe_allow_html=True)
        
        # Actions
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            # Status ändern
            status_options = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash", "WordPress Pending"]
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
            # WordPress Upload Button für einzelne Artikel
            if article.get("status") == "Process":
                if st.button("📤 WordPress", key=f"wp_upload_{article['id']}"):
                    with st.spinner("Lade zu WordPress hoch..."):
                        from utils.wordpress_uploader import upload_single_article_to_wordpress
                        success, message, wp_post_id = upload_single_article_to_wordpress(article)
                        
                        if success:
                            # Status ändern
                            for idx, art in enumerate(all_articles):
                                if art["id"] == article["id"]:
                                    all_articles[idx]["status"] = "WordPress Pending"
                                    all_articles[idx]["wp_upload_date"] = datetime.now().isoformat()
                                    all_articles[idx]["wp_post_id"] = wp_post_id
                                    break
                            save_articles(all_articles)
                            show_notification("✅ Erfolgreich zu WordPress hochgeladen!")
                        else:
                            show_notification(f"❌ WordPress-Upload fehlgeschlagen: {message}", "error")
                        
                        time.sleep(1)
                        st.rerun()
        
        with col5:
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
                    <h3 class="article-title">{feed_name}</h3>
                    <div class="article-meta">{feed_url}</div>
                    <div class="article-footer">📰 {article_count} Artikel</div>
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
                st.markdown('<div class="image-item">', unsafe_allow_html=True)
                st.image(img["url"], use_column_width=True)
                st.markdown(f'<strong class="text-primary">{img.get("caption", "Kein Titel")}</strong>', unsafe_allow_html=True)
                st.markdown(f'<div class="text-secondary">📰 {img["article_title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="text-muted">©️ {img.get("copyright", "Unbekannt")}</div>', unsafe_allow_html=True)
                
                if img.get("copyright_url") and img["copyright_url"] != "#":
                    st.markdown(f'<a href="{img["copyright_url"]}" target="_blank" class="text-accent">🔗 Quelle</a>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
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
            st.markdown(f"{get_status_badge(status)} <span class='text-primary'>{count} ({percentage:.1f}%)</span>", unsafe_allow_html=True)
    
    with col2:
        st.subheader("📡 Artikel pro Feed")
        feed_counts = Counter([source_to_name.get(a.get("source", ""), "Unbekannt") for a in all_articles])
        for feed_name, count in feed_counts.most_common():
            st.markdown(f'<div class="text-primary"><strong>{feed_name}:</strong> {count} Artikel</div>', unsafe_allow_html=True)
    
    # WordPress-Statistiken
    st.subheader("🔗 WordPress-Statistiken")
    wp_articles = [a for a in all_articles if a.get("wp_post_id")]
    
    if wp_articles:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="stats-card">
                <div class="stats-number">{}</div>
                <div>WordPress Artikel</div>
            </div>
            """.format(len(wp_articles)), unsafe_allow_html=True)
        
        with col2:
            pending_count = len([a for a in wp_articles if a.get("status") == "WordPress Pending"])
            st.markdown("""
            <div class="stats-card">
                <div class="stats-number">{}</div>
                <div>Ausstehend</div>
            </div>
            """.format(pending_count), unsafe_allow_html=True)
        
        with col3:
            online_wp_count = len([a for a in wp_articles if a.get("status") == "Online"])
            st.markdown("""
            <div class="stats-card">
                <div class="stats-number">{}</div>
                <div>Online</div>
            </div>
            """.format(online_wp_count), unsafe_allow_html=True)
        
        # Neueste WordPress-Uploads
        recent_wp = sorted([a for a in wp_articles if a.get("wp_upload_date")], 
                          key=lambda x: x.get("wp_upload_date", ""), reverse=True)[:5]
        
        if recent_wp:
            st.subheader("🕒 Neueste WordPress-Uploads")
            for article in recent_wp:
                st.markdown(f"""
                <div class="article-card">
                    <h3 class="article-title">{article.get('title', 'Kein Titel')}</h3>
                    {get_status_badge(article.get('status', 'Unknown'))}
                    <div class="article-meta">WP ID: {article.get('wp_post_id')} | Upload: {format_date(article.get('wp_upload_date', ''))}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Noch keine Artikel zu WordPress hochgeladen.")
    
    # Weitere Statistiken
    st.subheader("📝 Textstatistiken")
    
    word_counts = [get_word_count(a.get("text", "")) for a in all_articles]
    if word_counts:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="stats-card">
                <div class="stats-number">{}</div>
                <div>Durchschnittliche Wortanzahl</div>
            </div>
            """.format(sum(word_counts) // len(word_counts)), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="stats-card">
                <div class="stats-number">{}</div>
                <div>Längster Artikel (Wörter)</div>
            </div>
            """.format(max(word_counts)), unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="stats-card">
                <div class="stats-number">{}</div>
                <div>Kürzester Artikel (Wörter)</div>
            </div>
            """.format(min(word_counts)), unsafe_allow_html=True)
    
    # Tag Cloud Simulation
    st.subheader("🏷️ Häufigste Tags")
    all_tags = []
    for article in all_articles:
        all_tags.extend(article.get("tags", []))
    
    if all_tags:
        tag_counts = Counter(all_tags)
        for tag, count in tag_counts.most_common(10):
            st.markdown(f'<div class="text-primary"><strong>{tag}:</strong> {count}x verwendet</div>', unsafe_allow_html=True)
    else:
        st.info("Keine Tags gefunden.")

# === WordPress Tab ===
with tab6:
    st.header("🔧 WordPress-Integration")
    
    # Verbindungstest
    st.subheader("🔗 Verbindungstest")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🧪 WordPress-Verbindung testen", use_container_width=True):
            with st.spinner("Teste Verbindung..."):
                success, message = test_wordpress_connection()
                
                if success:
                    show_notification(f"✅ {message}")
                else:
                    show_notification(f"❌ {message}", "error")
    
    with col2:
        # WordPress-Konfiguration anzeigen
        wp_url = os.getenv("WP_BASE_URL", "Nicht konfiguriert")
        wp_user = os.getenv("WP_USERNAME", "Nicht konfiguriert")
        wp_base64 = os.getenv("WP_AUTH_BASE64", "")
        
        st.markdown(f"""
        <div class="wp-status">
            <strong>WordPress-Konfiguration:</strong><br>
            <div class="text-secondary">
                URL: {wp_url}<br>
                Benutzer: {wp_user}<br>
                Passwort: {'✅ Konfiguriert' if os.getenv("WP_PASSWORD") else '❌ Nicht konfiguriert'}<br>
                Base64 Auth: {'✅ Konfiguriert' if wp_base64 else '❌ Nicht konfiguriert'}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Sicherheit: Kein Anzeigen sensibler Auth-Details mehr
    
    # Bulk Upload
    st.subheader("📦 Massenupload")
    
    process_articles_list = [a for a in all_articles if a.get("status") == "Process"]
    
    if process_articles_list:
        st.write(f"**{len(process_articles_list)} Artikel bereit für WordPress-Upload:**")
        
        # Artikel-Vorschau
        for article in process_articles_list[:5]:  # Nur die ersten 5 anzeigen
            st.markdown(f'<div class="text-primary">• <strong>{article.get("title", "Kein Titel")}</strong> ({get_word_count(article.get("text", ""))} Wörter)</div>', unsafe_allow_html=True)
        
        if len(process_articles_list) > 5:
            st.markdown(f'<div class="text-muted">... und {len(process_articles_list) - 5} weitere</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📤 Alle zu WordPress hochladen", use_container_width=True):
                with st.spinner(f"Lade {len(process_articles_list)} Artikel zu WordPress hoch..."):
                    upload_results = upload_articles_to_wp()
                    
                    # Detaillierte Ergebnisse anzeigen
                    st.subheader("📊 Upload-Ergebnisse")
                    
                    if upload_results.get('error'):
                        show_notification(f"❌ Fehler: {upload_results['error']}", "error")
                    else:
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("""
                            <div class="stats-card">
                                <div class="stats-number">{}</div>
                                <div>Erfolgreich</div>
                            </div>
                            """.format(upload_results.get('successful', 0)), unsafe_allow_html=True)
                        with col2:
                            st.markdown("""
                            <div class="stats-card">
                                <div class="stats-number">{}</div>
                                <div>Fehlgeschlagen</div>
                            </div>
                            """.format(upload_results.get('failed', 0)), unsafe_allow_html=True)
                        with col3:
                            st.markdown("""
                            <div class="stats-card">
                                <div class="stats-number">{}</div>
                                <div>Duplikate</div>
                            </div>
                            """.format(upload_results.get('duplicates', 0)), unsafe_allow_html=True)
                        
                        # Details anzeigen
                        if upload_results.get('details'):
                            st.subheader("📋 Upload-Details")
                            for detail in upload_results['details']:
                                status_icon = "✅" if detail['success'] else "❌"
                                st.markdown(f'<div class="text-primary">{status_icon} <strong>{detail["title"]}:</strong> {detail["message"]}</div>', unsafe_allow_html=True)
                    
                    time.sleep(2)
                    st.rerun()
        
        with col2:
            st.markdown("""
            <div class="wp-status">
                <strong>💡 Info:</strong><br>
                <div class="text-secondary">
                    Artikel erhalten den Status 'WordPress Pending' nach erfolgreichem Upload.
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    else:
        st.info("Keine Artikel mit Status 'Process' gefunden. Artikel müssen zuerst umgeschrieben werden.")
    
    # WordPress-Artikel-Übersicht
    st.subheader("📋 WordPress-Artikel-Übersicht")
    
    wp_articles = [a for a in all_articles if a.get("wp_post_id")]
    
    if wp_articles:
        # Filter für WordPress-Artikel
        wp_status_filter = st.selectbox(
            "WordPress-Status filtern",
            ["Alle", "WordPress Pending", "Online"],
            key="wp_status_filter"
        )
        
        filtered_wp_articles = wp_articles
        if wp_status_filter != "Alle":
            filtered_wp_articles = [a for a in wp_articles if a.get("status") == wp_status_filter]
        
        st.write(f"**{len(filtered_wp_articles)} WordPress-Artikel gefunden**")
        
        # WordPress-Artikel anzeigen
        for article in filtered_wp_articles:
            st.markdown(f"""
            <div class="wp-status">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{article.get('title', 'Kein Titel')}</strong><br>
                        <small>WP ID: {article.get('wp_post_id')} | Upload: {format_date(article.get('wp_upload_date', ''))}</small>
                    </div>
                    <div>
                        {get_status_badge(article.get('status', 'Unknown'))}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    else:
        st.info("Noch keine Artikel zu WordPress hochgeladen.")
    
    # Konfigurationshilfe
    st.subheader("⚙️ Konfiguration")
    
    with st.expander("📋 .env-Datei Vorlage", expanded=False):
        st.code("""
# WordPress-Konfiguration
WP_BASE_URL=https://your-site.tld

# Entweder Base64 (empfohlen) ODER Benutzername/Passwort (Application Password)
WP_AUTH_BASE64=
# Oder alternativ:
WP_USERNAME=
WP_PASSWORD=

# OpenAI-Konfiguration (optional für Umschreibung)
OPENAI_API_KEY=
        """, language="bash")
    
    with st.expander("🔑 Base64-Authentifizierung verstehen", expanded=False):
        st.markdown("""
        <div class="article-card">
            <h3 class="article-title">WordPress REST API Authentifizierung:</h3>
            <div class="article-summary">
                Die WordPress REST API nutzt <code>Basic</code>-Auth mit Base64-kodierten Zugangsdaten:<br>
                <code>Authorization: Basic &lt;base64(username:password)&gt;</code><br><br>
                Empfehlung: In der .env <code>WP_AUTH_BASE64</code> setzen (aus <code>username:application_password</code> erzeugt).<br>
                Alternativ können <code>WP_USERNAME</code> und <code>WP_PASSWORD</code> gesetzt werden; dann wird Base64 zur Laufzeit generiert.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with st.expander("📖 WordPress-API Berechtigungen", expanded=False):
        st.markdown("""
        <div class="article-card">
            <h3 class="article-title">Erforderliche Berechtigungen für den WordPress-Benutzer:</h3>
            <div class="article-summary">
                • <code>edit_posts</code> - Beiträge erstellen und bearbeiten<br>
                • <code>publish_posts</code> - Beiträge veröffentlichen (für Status-Änderungen)<br>
                • <code>upload_files</code> - Dateien hochladen (für spätere Bild-Uploads)<br>
                • <code>edit_categories</code> - Kategorien verwalten<br>
                • <code>edit_tags</code> - Tags verwalten
                <br><br>
                <strong>Anwendungspasswort erstellen:</strong><br>
                1. WordPress Admin → Benutzer → Profil<br>
                2. Unter "Anwendungspasswörter" neues Passwort erstellen<br>
                3. Name: "RSS Feed Manager"<br>
                4. Generiertes Passwort in .env-Datei eintragen
            </div>
        </div>
        """, unsafe_allow_html=True)
