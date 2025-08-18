# utils/css_loader.py

import streamlit as st
import os
from pathlib import Path

def load_css():
    """
    Lädt die zentrale CSS-Datei und injiziert sie in die Streamlit-App
    """
    try:
        # Pfad zur CSS-Datei bestimmen
        css_file = Path(__file__).parent.parent / "static" / "styles.css"
        
        if css_file.exists():
            with open(css_file, "r", encoding="utf-8") as f:
                css_content = f.read()
            
            # CSS in Streamlit injizieren
            st.markdown(f"""
            <style>
            {css_content}
            </style>
            """, unsafe_allow_html=True)
            
            return True
        else:
            # Fallback: CSS-Datei erstellen
            create_css_file()
            return load_css()  # Rekursiver Aufruf nach Erstellung
            
    except Exception as e:
        st.error(f"Fehler beim Laden der CSS-Datei: {e}")
        return False

def create_css_file():
    """
    Erstellt die CSS-Datei falls sie nicht existiert
    """
    css_content = """/* ===============================================
   RSS Feed Manager - Zentrale CSS-Datei
   Dark-Mode optimiert mit Fallbacks
   =============================================== */

/* === ROOT VARIABLEN === */
:root {
    /* Dark Mode Farbpalette */
    --bg-primary: #1e1e1e;
    --bg-secondary: #2d2d30;
    --bg-card: #2d2d30;
    --bg-header: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --bg-filter: #363636;
    
    /* Text Farben */
    --text-primary: #ffffff;
    --text-secondary: #b0b0b0;
    --text-muted: #888888;
    --text-accent: #667eea;
    
    /* Status Farben */
    --status-new: #2196f3;
    --status-new-bg: #1565c0;
    --status-rewrite: #ff9800;
    --status-rewrite-bg: #ef6c00;
    --status-process: #9c27b0;
    --status-process-bg: #6a1b9a;
    --status-online: #4caf50;
    --status-online-bg: #2e7d32;
    --status-hold: #e91e63;
    --status-hold-bg: #ad1457;
    --status-trash: #f44336;
    --status-trash-bg: #c62828;
    --status-wp-pending: #00bcd4;
    --status-wp-pending-bg: #0097a7;
    
    /* Borders & Shadows */
    --border-color: #404040;
    --shadow-light: 0 2px 8px rgba(0, 0, 0, 0.3);
    --shadow-hover: 0 8px 20px rgba(0, 0, 0, 0.4);
    
    /* Accent Colors */
    --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --gradient-secondary: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

/* === LIGHT MODE FALLBACKS === */
[data-theme="light"], .stApp[data-theme="light"] {
    --bg-primary: #ffffff;
    --bg-secondary: #f8f9fa;
    --bg-card: #ffffff;
    --bg-filter: #f0f2f6;
    
    --text-primary: #212529;
    --text-secondary: #495057;
    --text-muted: #6c757d;
    --text-accent: #667eea;
    
    --border-color: #dee2e6;
    --shadow-light: 0 2px 8px rgba(0, 0, 0, 0.1);
    --shadow-hover: 0 8px 20px rgba(0, 0, 0, 0.15);
}

/* === HAUPTCONTAINER === */
.main-header {
    background: var(--bg-header);
    padding: 2rem;
    border-radius: 12px;
    margin-bottom: 2rem;
    color: var(--text-primary);
    text-align: center;
    box-shadow: var(--shadow-light);
}

.main-header h1 {
    color: var(--text-primary) !important;
    margin: 0 0 0.5rem 0;
    font-size: 2.5rem;
    font-weight: 700;
}

.main-header p {
    color: rgba(255, 255, 255, 0.9) !important;
    margin: 0;
    font-size: 1.1rem;
}

/* === ARTIKEL CARDS === */
.article-card {
    background: var(--bg-card) !important;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-light);
    border-left: 4px solid var(--text-accent);
    border: 1px solid var(--border-color);
    transition: all 0.3s ease;
    color: var(--text-primary) !important;
}

.article-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-hover);
    border-color: var(--text-accent);
}

.article-card h3,
.article-card .article-title {
    color: var(--text-primary) !important;
    margin: 0 0 0.5rem 0;
    font-size: 1.2rem;
    font-weight: 600;
    line-height: 1.4;
}

.article-card .article-meta {
    color: var(--text-secondary) !important;
    font-size: 0.9rem;
    margin-bottom: 1rem;
}

.article-card .article-summary {
    color: var(--text-secondary) !important;
    line-height: 1.5;
    margin-bottom: 1rem;
}

.article-card .article-footer {
    color: var(--text-muted) !important;
    font-size: 0.85rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* === STATUS BADGES === */
.status-badge {
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-right: 0.5rem;
    display: inline-block;
    color: white !important;
}

.status-new { 
    background-color: var(--status-new-bg) !important; 
    color: white !important; 
}

.status-rewrite { 
    background-color: var(--status-rewrite-bg) !important; 
    color: white !important; 
}

.status-process { 
    background-color: var(--status-process-bg) !important; 
    color: white !important; 
}

.status-online { 
    background-color: var(--status-online-bg) !important; 
    color: white !important; 
}

.status-hold { 
    background-color: var(--status-hold-bg) !important; 
    color: white !important; 
}

.status-trash { 
    background-color: var(--status-trash-bg) !important; 
    color: white !important; 
}

.status-wp-pending { 
    background-color: var(--status-wp-pending-bg) !important; 
    color: white !important; 
}

/* === FILTER SECTION === */
.filter-section {
    background: var(--bg-filter) !important;
    padding: 1.5rem;
    border-radius: 12px;
    margin-bottom: 2rem;
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-light);
}

.filter-section h3 {
    color: var(--text-primary) !important;
    margin: 0 0 1rem 0;
    font-size: 1.3rem;
    font-weight: 600;
}

/* === STATS CARDS === */
.stats-card {
    background: var(--bg-card) !important;
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: var(--shadow-light);
    border: 1px solid var(--border-color);
    transition: transform 0.2s ease;
}

.stats-card:hover {
    transform: translateY(-2px);
}

.stats-number {
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--text-accent) !important;
    margin-bottom: 0.5rem;
    display: block;
}

.stats-card div:last-child {
    color: var(--text-secondary) !important;
    font-weight: 500;
    font-size: 1rem;
}

/* === WORDPRESS STATUS === */
.wp-status {
    background: var(--bg-card) !important;
    padding: 1rem;
    border-radius: 8px;
    margin: 1rem 0;
    border-left: 4px solid var(--status-wp-pending);
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-light);
}

.wp-status strong {
    color: var(--text-primary) !important;
}

.wp-status small {
    color: var(--text-muted) !important;
}

/* === BUTTONS & ACTIONS === */
.stButton > button {
    background: var(--gradient-primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
}

/* === SELECTBOX & INPUT OVERRIDES === */
.stSelectbox > div > div {
    background-color: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
}

.stTextInput > div > div > input {
    background-color: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
}

/* === RESPONSIVE DESIGN === */
@media (max-width: 768px) {
    .main-header {
        padding: 1.5rem;
    }
    
    .main-header h1 {
        font-size: 2rem;
    }
    
    .article-card {
        padding: 1rem;
    }
    
    .stats-card {
        padding: 1rem;
    }
    
    .stats-number {
        font-size: 2rem;
    }
}
"""
    
    try:
        # Static-Ordner erstellen falls nicht vorhanden
        static_dir = Path(__file__).parent.parent / "static"
        static_dir.mkdir(exist_ok=True)
        
        # CSS-Datei schreiben
        css_file = static_dir / "styles.css"
        with open(css_file, "w", encoding="utf-8") as f:
            f.write(css_content)
            
        return True
    except Exception as e:
        st.error(f"Fehler beim Erstellen der CSS-Datei: {e}")
        return False

def apply_dark_theme():
    """
    Wendet das Dark Theme an (zusätzlich zur CSS-Datei)
    """
    st.markdown("""
    <script>
    // Dark Theme Detection und Anwendung
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (prefersDark) {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
    }
    </script>
    """, unsafe_allow_html=True)