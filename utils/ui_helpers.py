# utils/ui_helpers.py

import streamlit as st
from datetime import datetime
import logging

def show_toast(message, type="success", duration=3):
    """
    Zeigt eine Toast-Benachrichtigung an
    """
    if type == "success":
        st.success(message)
    elif type == "error":
        st.error(message)
    elif type == "warning":
        st.warning(message)
    elif type == "info":
        st.info(message)

def format_datetime(date_str):
    """
    Formatiert Datetime-Strings für bessere Lesbarkeit
    """
    try:
        if isinstance(date_str, str):
            if "GMT" in date_str or "+" in date_str:
                dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
                return dt.strftime("%d.%m.%Y %H:%M")
            elif "T" in date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return dt.strftime("%d.%m.%Y %H:%M")
            else:
                return date_str[:16].replace("T", " ")
        return str(date_str)
    except Exception as e:
        logging.warning(f"Datum konnte nicht formatiert werden: {date_str} - {e}")
        return str(date_str)[:16]

def get_status_color(status):
    """
    Gibt die passende Farbe für einen Status zurück
    """
    colors = {
        "New": "#2196f3",
        "Rewrite": "#ff9800", 
        "Process": "#9c27b0",
        "Online": "#4caf50",
        "On Hold": "#e91e63",
        "Trash": "#f44336"
    }
    return colors.get(status, "#2196f3")

def create_status_badge(status):
    """
    Erstellt einen HTML-Status-Badge
    """
    color = get_status_color(status)
    return f"""
    <span style="
        background-color: {color}20; 
        color: {color}; 
        padding: 0.25rem 0.5rem; 
        border-radius: 12px; 
        font-size: 0.8rem; 
        font-weight: 600;
        border: 1px solid {color}40;
    ">{status}</span>
    """

def truncate_text(text, max_length=150):
    """
    Kürzt Text auf maximale Länge
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length].rsplit(' ', 1)[0] + "..."

def calculate_reading_time(text):
    """
    Berechnet geschätzte Lesezeit (200 Wörter/Minute)
    """
    if not text:
        return 0
    
    word_count = len(text.split())
    reading_time = max(1, word_count // 200)
    return reading_time

def validate_url(url):
    """
    Validiert eine URL
    """
    import re
    pattern = re.compile(
        r'^https?://'  # http:// oder https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...oder IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return pattern.match(url) is not None

def create_article_card_html(article, source_name="Unbekannt"):
    """
    Erstellt HTML für eine Artikel-Karte
    """
    has_images = len(article.get("images", [])) > 0
    word_count = len(article.get("text", "").split())
    reading_time = calculate_reading_time(article.get("text", ""))
    
    # Unvollständige Bilder prüfen
    incomplete_images = any(
        not all(k in img and img[k] for k in ("caption", "copyright", "copyright_url"))
        for img in article.get("images", [])
    )
    
    warning_icon = " ⚠️" if incomplete_images else ""
    
    return f"""
    <div style="
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid {get_status_color(article.get('status', 'New'))};
        transition: transform 0.2s ease;
    " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
        
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
            <div style="flex: 1;">
                <h3 style="margin: 0 0 0.5rem 0; color: #333; font-size: 1.1rem;">
                    {article.get('title', 'Kein Titel')}{warning_icon}
                </h3>
                <div style="font-size: 0.85rem; color: #666; margin-bottom: 0.5rem;">
                    📅 {format_datetime(article.get('date', ''))} • 
                    📝 {word_count} Wörter • 
                    ⏱️ {reading_time} Min Lesezeit
                    {'• 🖼️ ' + str(len(article.get('images', []))) + ' Bilder' if has_images else ''}
                </div>
            </div>
            <div>
                {create_status_badge(article.get('status', 'New'))}
            </div>
        </div>
        
        <div style="margin-bottom: 1rem; color: #555; line-height: 1.4;">
            {truncate_text(article.get('summary', ''), 200)}
        </div>
        
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #888;">
            <div>
                📡 {source_name}
            </div>
            <div>
                🏷️ {', '.join(article.get('tags', [])[:3])}{'...' if len(article.get('tags', [])) > 3 else ''}
            </div>
        </div>
    </div>
    """

def create_stats_card(title, value, icon="📊", color="#667eea"):
    """
    Erstellt eine Statistik-Karte
    """
    return f"""
    <div style="
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-top: 4px solid {color};
    ">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
        <div style="font-size: 2rem; font-weight: bold; color: {color}; margin-bottom: 0.5rem;">{value}</div>
        <div style="color: #666; font-weight: 500;">{title}</div>
    </div>
    """

def show_loading_spinner(text="Lädt..."):
    """
    Zeigt einen Lade-Spinner mit Text
    """
    return st.empty().markdown(f"""
    <div style="text-align: center; padding: 2rem;">
        <div style="
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem auto;
        "></div>
        <div style="color: #666;">{text}</div>
    </div>
    <style>
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    """, unsafe_allow_html=True)

def create_filter_section():
    """
    Erstellt einen modernen Filter-Bereich
    """
    return """
    <div style="
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    ">
        <h3 style="margin: 0 0 1rem 0; color: #333;">🔍 Filter & Suche</h3>
    """

def get_error_message(error_type, details=""):
    """
    Gibt formatierte Fehlermeldungen zurück
    """
    messages = {
        "feed_error": f"❌ Fehler beim Laden des Feeds: {details}",
        "save_error": f"❌ Fehler beim Speichern: {details}",
        "api_error": f"❌ API-Fehler: {details}",
        "validation_error": f"⚠️ Validierungsfehler: {details}",
        "network_error": f"🌐 Netzwerkfehler: {details}"
    }
    return messages.get(error_type, f"❌ Unbekannter Fehler: {details}")