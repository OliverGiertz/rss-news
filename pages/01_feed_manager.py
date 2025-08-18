# pages/01_feed_manager.py

import streamlit as st
from main import load_feeds, save_feeds, load_articles
from utils.css_loader import load_css, apply_dark_theme
import logging

# === CSS & Theme laden ===
load_css()
apply_dark_theme()

# === Logging vorbereiten ===
log_dir = "logs"
log_file = f"{log_dir}/rss_tool.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

st.set_page_config(page_title="📡 Feed-Verwaltung")

# Header
st.markdown("""
<div class="main-header">
    <h1>📡 RSS Feed-Verwaltung</h1>
    <p>Verwalte deine RSS-Feeds zentral und effizient</p>
</div>
""", unsafe_allow_html=True)

feeds = load_feeds()
articles = load_articles()

# === Neuen Feed hinzufügen ===
st.markdown('<div class="filter-section">', unsafe_allow_html=True)
st.subheader("➕ Neuen Feed hinzufügen")

with st.form("add_feed_form"):
    col1, col2 = st.columns(2)
    with col1:
        new_url = st.text_input("Feed URL", "", placeholder="https://example.com/feed.xml")
    with col2:
        new_name = st.text_input("Feed Name", "", placeholder="Beispiel News")
    
    submitted = st.form_submit_button("Feed hinzufügen", use_container_width=True)
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

st.markdown('</div>', unsafe_allow_html=True)

# === Bestehende Feeds bearbeiten ===
st.subheader("🛠️ Vorhandene Feeds verwalten")

if not feeds:
    st.info("Noch keine Feeds konfiguriert. Füge oben deinen ersten Feed hinzu!")
else:
    for idx, feed in enumerate(feeds):
        feed_url = feed.get("url", "")
        feed_name = feed.get("name", "Unbekannt")
        article_count = sum(1 for a in articles if a.get("source") == feed_url)
        
        # Feed Card
        st.markdown(f"""
        <div class="article-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <div>
                    <h3 class="article-title">{feed_name}</h3>
                    <div class="article-meta">{feed_url}</div>
                </div>
                <div>
                    <span class="status-badge status-online">{article_count} Artikel</span>
                </div>
            </div>
            <div class="article-footer">
                📰 Verknüpfte Artikel: {article_count}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Actions
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("💾 Bearbeiten", key=f"edit_{idx}", use_container_width=True):
                st.session_state[f"edit_mode_{idx}"] = not st.session_state.get(f"edit_mode_{idx}", False)

        with col2:
            if st.button("🔄 Aktualisieren", key=f"refresh_{idx}", use_container_width=True):
                with st.spinner(f"Aktualisiere Feed '{feed_name}'..."):
                    # Hier könntest du eine einzelne Feed-Update-Funktion implementieren
                    from main import process_articles
                    existing_ids = [a["id"] for a in articles]
                    process_articles(existing_ids)
                    st.success(f"Feed '{feed_name}' aktualisiert!")
                    st.rerun()

        with col3:
            if st.button("🗑️ Löschen", key=f"delete_{idx}", use_container_width=True):
                # Bestätigung über Session State
                if not st.session_state.get(f"confirm_delete_{idx}", False):
                    st.session_state[f"confirm_delete_{idx}"] = True
                    st.warning(f"Klicke erneut um '{feed_name}' wirklich zu löschen!")
                else:
                    deleted_feed = feeds.pop(idx)
                    save_feeds(feeds)
                    logging.info(f"❌ Feed gelöscht: {deleted_feed.get('name')} ({deleted_feed.get('url')})")
                    st.success(f"Feed '{feed_name}' wurde gelöscht.")
                    # Cleanup Session State
                    if f"confirm_delete_{idx}" in st.session_state:
                        del st.session_state[f"confirm_delete_{idx}"]
                    st.rerun()

        # Edit Form (wenn aktiviert)
        if st.session_state.get(f"edit_mode_{idx}", False):
            st.markdown('<div class="filter-section" style="margin-top: 1rem;">', unsafe_allow_html=True)
            st.write("**Feed bearbeiten:**")
            
            with st.form(f"edit_form_{idx}"):
                col1, col2 = st.columns(2)
                with col1:
                    edited_url = st.text_input("Feed-URL", value=feed_url, key=f"edit_url_{idx}")
                with col2:
                    edited_name = st.text_input("Feed-Name", value=feed_name, key=f"edit_name_{idx}")
                
                form_col1, form_col2 = st.columns(2)
                with form_col1:
                    if st.form_submit_button("💾 Änderungen speichern", use_container_width=True):
                        old_url, old_name = feed.get("url"), feed.get("name")
                        feeds[idx]["url"] = edited_url
                        feeds[idx]["name"] = edited_name
                        save_feeds(feeds)
                        logging.info(f"✏️ Feed geändert: '{old_name}' ({old_url}) → '{edited_name}' ({edited_url})")
                        st.success("Änderungen gespeichert!")
                        st.session_state[f"edit_mode_{idx}"] = False
                        st.rerun()
                
                with form_col2:
                    if st.form_submit_button("❌ Abbrechen", use_container_width=True):
                        st.session_state[f"edit_mode_{idx}"] = False
                        st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

# === Feed-Statistiken ===
if feeds:
    st.markdown("---")
    st.subheader("📊 Feed-Statistiken")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Feeds Gesamt</div>
        </div>
        """.format(len(feeds)), unsafe_allow_html=True)
    
    with col2:
        total_articles = len(articles)
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Artikel Gesamt</div>
        </div>
        """.format(total_articles), unsafe_allow_html=True)
    
    with col3:
        avg_articles = total_articles // len(feeds) if feeds else 0
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Ø Artikel pro Feed</div>
        </div>
        """.format(avg_articles), unsafe_allow_html=True)

# === Bulk Actions ===
if feeds:
    st.markdown("---")
    st.subheader("⚡ Bulk-Aktionen")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Alle Feeds aktualisieren", use_container_width=True):
            with st.spinner("Aktualisiere alle Feeds..."):
                from main import process_articles
                existing_ids = [a["id"] for a in articles]
                process_articles(existing_ids)
                st.success(f"Alle {len(feeds)} Feeds wurden aktualisiert!")
                st.rerun()
    
    with col2:
        if st.button("📊 Feed-Performance anzeigen", use_container_width=True):
            st.subheader("📈 Feed-Performance")
            
            # Performance-Daten sammeln
            feed_performance = []
            for feed in feeds:
                feed_url = feed.get("url", "")
                feed_name = feed.get("name", "Unbekannt")
                feed_articles = [a for a in articles if a.get("source") == feed_url]
                
                performance = {
                    "name": feed_name,
                    "url": feed_url,
                    "total_articles": len(feed_articles),
                    "new_articles": len([a for a in feed_articles if a.get("status") == "New"]),
                    "processed_articles": len([a for a in feed_articles if a.get("status") in ["Process", "Online", "WordPress Pending"]])
                }
                feed_performance.append(performance)
            
            # Sortiere nach Artikel-Anzahl
            feed_performance.sort(key=lambda x: x["total_articles"], reverse=True)
            
            # Anzeige als Cards
            for perf in feed_performance:
                success_rate = (perf["processed_articles"] / perf["total_articles"] * 100) if perf["total_articles"] > 0 else 0
                
                st.markdown(f"""
                <div class="article-card">
                    <h3 class="article-title">{perf["name"]}</h3>
                    <div class="article-footer">
                        📰 {perf["total_articles"]} Artikel | 
                        🆕 {perf["new_articles"]} Neu | 
                        ✅ {perf["processed_articles"]} Verarbeitet | 
                        📊 {success_rate:.1f}% Success Rate
                    </div>
                </div>
                """, unsafe_allow_html=True)