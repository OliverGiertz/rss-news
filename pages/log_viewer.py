# pages/log_viewer.py

import streamlit as st
import os
from utils.css_loader import load_css, apply_dark_theme
from datetime import datetime

# === CSS & Theme laden ===
load_css()
apply_dark_theme()

st.set_page_config(page_title="🧾 Log Viewer", layout="wide")

# Header
st.markdown("""
<div class="main-header">
    <h1>🧾 Log Viewer</h1>
    <p>Überwache Systemaktivitäten und Debug-Informationen</p>
</div>
""", unsafe_allow_html=True)

LOG_FILE = "logs/rss_tool.log"
MAX_LINES = 500

# === Log-Datei Kontrollen ===
st.markdown('<div class="filter-section">', unsafe_allow_html=True)
st.subheader("📁 Log-Datei Optionen")

col1, col2, col3, col4 = st.columns(4)

with col1:
    lines_to_show = st.selectbox(
        "Anzahl Zeilen", 
        [50, 100, 200, 500, 1000], 
        index=3,  # Default: 500
        key="lines_select"
    )

with col2:
    if st.button("🔄 Neu laden", use_container_width=True):
        st.rerun()

with col3:
    log_level_filter = st.selectbox(
        "Log Level Filter",
        ["Alle", "INFO", "WARNING", "ERROR", "DEBUG"],
        key="level_filter"
    )

with col4:
    search_term = st.text_input(
        "Suche in Logs",
        placeholder="Suchbegriff...",
        key="log_search"
    )

st.markdown('</div>', unsafe_allow_html=True)

# === Log-Datei Status ===
if not os.path.exists(LOG_FILE):
    st.markdown("""
    <div class="wp-status">
        <strong>⚠️ Keine Log-Datei gefunden</strong><br>
        <div class="text-secondary">
            Die Log-Datei wurde noch nicht erstellt oder befindet sich an einem anderen Ort.<br>
            Erwarteter Pfad: <code>{}</code>
        </div>
    </div>
    """.format(LOG_FILE), unsafe_allow_html=True)
else:
    # Datei-Informationen
    file_size = os.path.getsize(LOG_FILE)
    file_mtime = datetime.fromtimestamp(os.path.getmtime(LOG_FILE))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{:.1f} KB</div>
            <div>Dateigröße</div>
        </div>
        """.format(file_size / 1024), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number" style="font-size: 1.5rem;">{}</div>
            <div>Letzte Änderung</div>
        </div>
        """.format(file_mtime.strftime("%H:%M:%S")), unsafe_allow_html=True)
    
    with col3:
        # Zeilen zählen
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                total_lines = sum(1 for _ in f)
        except:
            total_lines = 0
            
        st.markdown("""
        <div class="stats-card">
            <div class="stats-number">{}</div>
            <div>Zeilen Gesamt</div>
        </div>
        """.format(total_lines), unsafe_allow_html=True)

    # === Log-Inhalt anzeigen ===
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter anwenden
        filtered_lines = []
        
        for line in lines:
            # Log Level Filter
            if log_level_filter != "Alle":
                if f" - {log_level_filter} - " not in line:
                    continue
            
            # Suchfilter
            if search_term and search_term.lower() not in line.lower():
                continue
                
            filtered_lines.append(line)

        # Anzahl begrenzen
        display_lines = filtered_lines[-lines_to_show:] if len(filtered_lines) > lines_to_show else filtered_lines
        
        # Header für Log-Anzeige
        st.subheader(f"📋 Log-Einträge ({len(display_lines)} von {len(filtered_lines)} gefilterten Zeilen)")
        
        if display_lines:
            # Log-Inhalt mit Syntax-Highlighting
            log_content = "".join(display_lines)
            
            # Farbkodierung für verschiedene Log-Level
            colored_content = log_content
            colored_content = colored_content.replace(" - ERROR - ", " - 🔴 ERROR - ")
            colored_content = colored_content.replace(" - WARNING - ", " - 🟡 WARNING - ")
            colored_content = colored_content.replace(" - INFO - ", " - 🔵 INFO - ")
            colored_content = colored_content.replace(" - DEBUG - ", " - ⚪ DEBUG - ")
            
            # Log in Card anzeigen
            st.markdown("""
            <div class="article-card">
                <h3 class="article-title">📄 Log-Ausgabe</h3>
                <div class="article-meta">
                    Letzte {count} Einträge | Filter: {level} | Suche: "{search}"
                </div>
            </div>
            """.format(
                count=len(display_lines),
                level=log_level_filter,
                search=search_term or "Keine"
            ), unsafe_allow_html=True)
            
            # Code-Block mit Logs
            st.code(colored_content, language="text")
            
            # Download-Button
            st.download_button(
                label="💾 Log-Datei herunterladen",
                data=log_content,
                file_name=f"rss_tool_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        else:
            st.markdown("""
            <div class="wp-status">
                <strong>🔍 Keine Log-Einträge gefunden</strong><br>
                <div class="text-secondary">
                    Mit den aktuellen Filtern wurden keine Log-Einträge gefunden.<br>
                    Versuche andere Filter-Einstellungen.
                </div>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.markdown(f"""
        <div class="wp-status">
            <strong>❌ Fehler beim Lesen der Log-Datei</strong><br>
            <div class="text-secondary">
                {str(e)}
            </div>
        </div>
        """, unsafe_allow_html=True)

# === Log-Level Erklärung ===
with st.expander("ℹ️ Log-Level Erklärung", expanded=False):
    st.markdown("""
    <div class="article-card">
        <h3 class="article-title">📖 Log-Level Bedeutung</h3>
        <div class="article-summary">
            <strong>🔵 INFO:</strong> Normale Programmaktivitäten (Feed-Updates, Artikel verarbeitet)<br>
            <strong>🟡 WARNING:</strong> Potentielle Probleme (Duplikate, fehlende Daten)<br>
            <strong>🔴 ERROR:</strong> Fehler die das Programm beeinträchtigen<br>
            <strong>⚪ DEBUG:</strong> Detaillierte Entwickler-Informationen
        </div>
    </div>
    """, unsafe_allow_html=True)

# === Log-Datei verwalten ===
st.markdown("---")
st.subheader("🛠️ Log-Datei Verwaltung")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🗑️ Log-Datei leeren", use_container_width=True):
        if st.button("⚠️ Wirklich leeren?", key="confirm_clear"):
            try:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
                st.success("Log-Datei wurde geleert!")
                st.rerun()
            except Exception as e:
                st.error(f"Fehler beim Leeren der Log-Datei: {e}")

with col2:
    if st.button("📦 Log archivieren", use_container_width=True):
        try:
            archive_name = f"rss_tool_log_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                log_data = f.read()
            
            st.download_button(
                label=f"💾 {archive_name}",
                data=log_data,
                file_name=archive_name,
                mime="text/plain",
                key="archive_download"
            )
        except Exception as e:
            st.error(f"Fehler beim Archivieren: {e}")

with col3:
    if st.button("📊 Log-Statistiken", use_container_width=True):
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    all_lines = f.readlines()
                
                # Statistiken berechnen
                total_lines = len(all_lines)
                info_count = sum(1 for line in all_lines if " - INFO - " in line)
                warning_count = sum(1 for line in all_lines if " - WARNING - " in line)
                error_count = sum(1 for line in all_lines if " - ERROR - " in line)
                debug_count = sum(1 for line in all_lines if " - DEBUG - " in line)
                
                st.subheader("📈 Log-Statistiken")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("""
                    <div class="stats-card">
                        <div class="stats-number">{}</div>
                        <div>🔵 INFO</div>
                    </div>
                    """.format(info_count), unsafe_allow_html=True)
                
                with col2:
                    st.markdown("""
                    <div class="stats-card">
                        <div class="stats-number">{}</div>
                        <div>🟡 WARNING</div>
                    </div>
                    """.format(warning_count), unsafe_allow_html=True)
                
                with col3:
                    st.markdown("""
                    <div class="stats-card">
                        <div class="stats-number">{}</div>
                        <div>🔴 ERROR</div>
                    </div>
                    """.format(error_count), unsafe_allow_html=True)
                
                with col4:
                    st.markdown("""
                    <div class="stats-card">
                        <div class="stats-number">{}</div>
                        <div>⚪ DEBUG</div>
                    </div>
                    """.format(debug_count), unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Fehler beim Berechnen der Statistiken: {e}")

# === Auto-Refresh Option ===
if st.checkbox("🔄 Auto-Refresh (30s)", key="auto_refresh"):
    import time
    time.sleep(30)
    st.rerun()