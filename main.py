# main.py

import feedparser
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import logging
import openai
from utils.image_extractor import extract_images_with_metadata
from utils.article_extractor import extract_full_article
import hashlib
import time

load_dotenv()

# === Logging konfigurieren ===
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "rss_tool.log")

# Logging-Format verbessern
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # Auch in Konsole ausgeben
    ]
)

openai.api_key = os.getenv("OPENAI_API_KEY")

ARTICLES_FILE = "data/articles.json"
FEEDS_FILE = "data/feeds.json"
VALID_STATUSES = ["New", "Rewrite", "Process", "Online", "On Hold", "Trash"]

# === Datenordner erstellen ===
os.makedirs("data", exist_ok=True)

def generate_article_id(title, link, date):
    """Generiert eine eindeutige ID für einen Artikel basierend auf mehreren Attributen"""
    identifier = f"{title}_{link}_{date}"
    return hashlib.md5(identifier.encode('utf-8')).hexdigest()

def is_duplicate_article(new_article, existing_articles):
    """Prüft ob ein Artikel bereits existiert (erweiterte Duplikatserkennung)"""
    new_title = new_article.get("title", "").lower().strip()
    new_link = new_article.get("link", "").strip()
    
    for existing in existing_articles:
        existing_title = existing.get("title", "").lower().strip()
        existing_link = existing.get("link", "").strip()
        
        # Exakte URL-Übereinstimmung
        if new_link and existing_link and new_link == existing_link:
            return True
            
        # Sehr ähnliche Titel (mindestens 90% Übereinstimmung)
        if new_title and existing_title:
            similarity = calculate_similarity(new_title, existing_title)
            if similarity > 0.9:
                return True
    
    return False

def calculate_similarity(text1, text2):
    """Berechnet die Ähnlichkeit zwischen zwei Texten (vereinfachte Methode)"""
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0
        
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    return intersection / union if union > 0 else 0.0

def load_feeds():
    """Lädt RSS-Feeds aus der JSON-Datei"""
    try:
        if not os.path.exists(FEEDS_FILE):
            logging.info("Feeds-Datei existiert nicht, erstelle leere Liste")
            return []
        
        with open(FEEDS_FILE, "r", encoding='utf-8') as f:
            feeds = json.load(f)
            logging.info(f"✅ {len(feeds)} Feeds geladen")
            return feeds
    except Exception as e:
        logging.error(f"❌ Fehler beim Laden der Feeds: {e}")
        return []

def save_feeds(feeds):
    """Speichert RSS-Feeds in die JSON-Datei"""
    try:
        with open(FEEDS_FILE, "w", encoding='utf-8') as f:
            json.dump(feeds, f, indent=2, ensure_ascii=False)
        logging.info(f"✅ {len(feeds)} Feeds gespeichert")
    except Exception as e:
        logging.error(f"❌ Fehler beim Speichern der Feeds: {e}")

def load_articles():
    """Lädt Artikel aus der JSON-Datei"""
    try:
        if not os.path.exists(ARTICLES_FILE):
            logging.info("Artikel-Datei existiert nicht, erstelle leere Liste")
            return []
        
        with open(ARTICLES_FILE, "r", encoding='utf-8') as f:
            articles = json.load(f)

        # Status-Validierung
        for article in articles:
            if article.get("status") not in VALID_STATUSES:
                article["status"] = "New"
                logging.warning(f"⚠️ Ungültiger Status für Artikel '{article.get('title', 'Unbekannt')}' korrigiert")
        
        logging.info(f"✅ {len(articles)} Artikel geladen")
        return articles
    except Exception as e:
        logging.error(f"❌ Fehler beim Laden der Artikel: {e}")
        return []

def save_articles(articles):
    """Speichert Artikel in die JSON-Datei"""
    try:
        # Validierung vor dem Speichern
        valid_articles = []
        for article in articles:
            if "id" in article and "title" in article:
                valid_articles.append(article)
            else:
                logging.warning(f"⚠️ Ungültiger Artikel übersprungen: {article}")
        
        with open(ARTICLES_FILE, "w", encoding='utf-8') as f:
            json.dump(valid_articles, f, indent=2, ensure_ascii=False)
        
        logging.info(f"✅ {len(valid_articles)} Artikel gespeichert")
    except Exception as e:
        logging.error(f"❌ Fehler beim Speichern der Artikel: {e}")

def clean_html_content(content):
    """Bereinigt HTML-Inhalt und extrahiert Text"""
    try:
        soup = BeautifulSoup(content, "html.parser")
        
        # Entferne Script- und Style-Tags
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Hole sauberen Text
        clean_text = soup.get_text(" ", strip=True)
        
        # Entferne überschüssige Leerzeichen
        clean_text = " ".join(clean_text.split())
        
        return clean_text
    except Exception as e:
        logging.error(f"❌ Fehler beim Bereinigen des HTML-Inhalts: {e}")
        return content

def fetch_and_process_feed(feed_url, existing_articles):
    """Lädt und verarbeitet einen einzelnen RSS-Feed"""
    new_articles = []
    feed_name = "Unbekannt"
    
    try:
        logging.info(f"🔄 Verarbeite Feed: {feed_url}")
        
        # Feed parsen
        feed = feedparser.parse(feed_url)
        
        if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
            feed_name = feed.feed.title
            logging.info(f"📡 Feed-Name: {feed_name}")
        
        if not feed.entries:
            logging.warning(f"⚠️ Keine Einträge in Feed gefunden: {feed_url}")
            return []
        
        logging.info(f"📰 {len(feed.entries)} Einträge gefunden")
        
        for entry in feed.entries:
            try:
                # Basis-Informationen extrahieren
                title = entry.get("title", "Kein Titel")
                date = entry.get("published", datetime.now().isoformat())
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                
                # Content extrahieren
                content = ""
                if hasattr(entry, 'content') and entry.content:
                    content = entry.content[0].get("value", "")
                elif hasattr(entry, 'description'):
                    content = entry.description
                else:
                    content = summary
                
                # HTML bereinigen
                clean_text = clean_html_content(content)
                
                # Volltext-Extraktion bei kurzen Artikeln
                if len(clean_text.split()) < 50 and link:
                    logging.info(f"🔍 Kurzer Artikel erkannt, versuche Volltext-Extraktion: {title}")
                    fetched_text = extract_full_article(link)
                    if len(fetched_text.split()) > len(clean_text.split()):
                        clean_text = fetched_text
                        logging.info(f"✅ Volltext extrahiert: {len(clean_text.split())} Wörter")
                
                # Artikel-ID generieren
                article_id = generate_article_id(title, link, date)
                
                # Neuen Artikel erstellen
                new_article = {
                    "id": article_id,
                    "title": title,
                    "date": date,
                    "summary": summary[:300] + "..." if len(summary) > 300 else summary,
                    "text": clean_text,
                    "tags": [],
                    "status": "New",
                    "link": link,
                    "images": [],
                    "source": feed_url,
                    "source_name": feed_name,
                    "created_at": datetime.now().isoformat(),
                    "word_count": len(clean_text.split())
                }
                
                # Duplikatsprüfung
                if not is_duplicate_article(new_article, existing_articles):
                    # Bilder extrahieren
                    if link:
                        try:
                            images = extract_images_with_metadata(link)
                            new_article["images"] = images
                            logging.info(f"🖼️ {len(images)} Bilder für '{title}' extrahiert")
                        except Exception as e:
                            logging.error(f"❌ Fehler bei Bildextraktion für '{title}': {e}")
                    
                    new_articles.append(new_article)
                    logging.info(f"✅ Neuer Artikel hinzugefügt: {title}")
                else:
                    logging.info(f"🔄 Duplikat übersprungen: {title}")
                    
            except Exception as e:
                logging.error(f"❌ Fehler beim Verarbeiten des Eintrags '{entry.get('title', 'Unbekannt')}': {e}")
                continue
        
        logging.info(f"✅ Feed verarbeitet: {len(new_articles)} neue Artikel aus {feed_url}")
        return new_articles
        
    except Exception as e:
        logging.error(f"❌ Kritischer Fehler beim Verarbeiten von {feed_url}: {e}")
        return []

def process_articles(existing_ids=None):
    """Verarbeitet alle RSS-Feeds und fügt neue Artikel hinzu"""
    try:
        start_time = time.time()
        logging.info("🚀 Starte Artikel-Verarbeitung")
        
        feeds = load_feeds()
        all_articles = load_articles()
        
        if not feeds:
            logging.warning("⚠️ Keine RSS-Feeds konfiguriert")
            return
        
        # Bestehende Artikel für Duplikatsprüfung
        existing_articles = all_articles.copy()
        
        total_new_articles = 0
        
        for feed in feeds:
            feed_url = feed.get("url") if isinstance(feed, dict) else feed
            
            if not feed_url:
                logging.warning("⚠️ Feed ohne URL übersprungen")
                continue
            
            try:
                new_articles = fetch_and_process_feed(feed_url, existing_articles)
                
                # Neue Artikel zur Gesamtliste hinzufügen
                for article in new_articles:
                    all_articles.append(article)
                    existing_articles.append(article)  # Für weitere Duplikatsprüfung
                
                total_new_articles += len(new_articles)
                
                # Kurze Pause zwischen Feeds
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"❌ Fehler beim Verarbeiten von Feed {feed_url}: {e}")
                continue
        
        # Artikel speichern
        if total_new_articles > 0:
            save_articles(all_articles)
            processing_time = time.time() - start_time
            logging.info(f"🎉 Verarbeitung abgeschlossen: {total_new_articles} neue Artikel in {processing_time:.2f}s hinzugefügt")
        else:
            logging.info("ℹ️ Keine neuen Artikel gefunden")
            
    except Exception as e:
        logging.error(f"❌ Kritischer Fehler bei der Artikel-Verarbeitung: {e}")

def rewrite_articles():
    """Schreibt Artikel mit Status 'Rewrite' um"""
    try:
        logging.info("✍️ Starte Artikel-Umschreibung")
        
        articles = load_articles()
        rewrite_articles_list = [a for a in articles if a.get("status") == "Rewrite"]
        
        if not rewrite_articles_list:
            logging.info("ℹ️ Keine Artikel zum Umschreiben gefunden")
            return
        
        if not openai.api_key:
            logging.error("❌ OpenAI API-Key nicht konfiguriert")
            return
        
        changed = False
        
        for article in rewrite_articles_list:
            try:
                logging.info(f"✍️ Umschreiben von: {article['title']}")
                
                # Artikel umschreiben
                prompt = f"""Schreibe den folgenden Artikel um und fasse ihn verständlich zusammen. 
                Behalte die wichtigsten Informationen bei, aber formuliere alles neu:

                {article['text']}"""
                
                response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Du bist ein professioneller Redakteur, der Artikel umschreibt und verbessert."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1500,
                    temperature=0.7
                )
                
                new_text = response.choices[0].message.content.strip()
                
                # Tags generieren
                tag_prompt = f"""Erstelle 3-5 passende, kurze Stichwörter (Tags) für diesen Artikel.
                Gib nur die Tags zurück, getrennt durch Kommas:

                {new_text}"""
                
                tag_response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "Du generierst präzise Tags für Blog-Artikel."},
                        {"role": "user", "content": tag_prompt}
                    ],
                    max_tokens=100,
                    temperature=0.5
                )
                
                tags_raw = tag_response.choices[0].message.content.strip()
                tags = [tag.strip().strip(',') for tag in tags_raw.split(",") if tag.strip()]
                
                # Artikel aktualisieren
                article["text"] = new_text
                article["tags"] = tags
                article["status"] = "Process"
                article["rewritten_at"] = datetime.now().isoformat()
                article["word_count"] = len(new_text.split())
                
                # Bildmetadaten vervollständigen falls nötig
                for img in article.get("images", []):
                    if "caption" not in img or not img["caption"]:
                        img["caption"] = "Kein Bildtitel vorhanden"
                    if "copyright" not in img or not img["copyright"]:
                        img["copyright"] = "Unbekannt"
                    if "copyright_url" not in img or not img["copyright_url"]:
                        img["copyright_url"] = "#"
                
                logging.info(f"✅ Artikel erfolgreich umgeschrieben: {article['title']}")
                changed = True
                
                # Kurze Pause zwischen API-Calls
                time.sleep(2)
                
            except Exception as e:
                logging.error(f"❌ Fehler beim Umschreiben von '{article['title']}': {e}")
                continue
        
        if changed:
            save_articles(articles)
            logging.info(f"🎉 {len(rewrite_articles_list)} Artikel erfolgreich umgeschrieben")
        
    except Exception as e:
        logging.error(f"❌ Kritischer Fehler beim Umschreiben: {e}")

def get_article_stats():
    """Gibt Statistiken über die Artikel zurück"""
    try:
        articles = load_articles()
        
        stats = {
            "total_articles": len(articles),
            "status_distribution": {},
            "word_count_stats": {},
            "source_distribution": {},
            "images_count": 0
        }
        
        # Status-Verteilung
        for article in articles:
            status = article.get("status", "New")
            stats["status_distribution"][status] = stats["status_distribution"].get(status, 0) + 1
        
        # Wortanzahl-Statistiken
        word_counts = [article.get("word_count", 0) for article in articles if article.get("word_count")]
        if word_counts:
            stats["word_count_stats"] = {
                "average": sum(word_counts) // len(word_counts),
                "min": min(word_counts),
                "max": max(word_counts)
            }
        
        # Quellen-Verteilung
        for article in articles:
            source = article.get("source_name", "Unbekannt")
            stats["source_distribution"][source] = stats["source_distribution"].get(source, 0) + 1
        
        # Bilder zählen
        stats["images_count"] = sum(len(article.get("images", [])) for article in articles)
        
        return stats
        
    except Exception as e:
        logging.error(f"❌ Fehler beim Erstellen der Statistiken: {e}")
        return {}