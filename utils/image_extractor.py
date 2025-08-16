# utils/image_extractor.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
import time
from typing import List, Dict

# Konfiguration
MAX_IMAGES = 5
MIN_IMAGE_SIZE = 100  # Mindestgröße in Pixeln
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
REQUEST_TIMEOUT = 10
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def is_valid_image_url(url: str) -> bool:
    """
    Prüft ob eine URL auf ein gültiges Bild zeigt
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Prüfe Dateiendung
        if not any(path.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            return False
        
        # Prüfe ob URL vollständig ist
        if not parsed.scheme or not parsed.netloc:
            return False
            
        # Blacklist für unerwünschte Bilder
        blacklist_patterns = [
            'avatar', 'profile', 'icon', 'logo', 'banner', 
            'advertisement', 'ads', 'tracking', 'pixel', 'social'
        ]
        
        return not any(pattern in url.lower() for pattern in blacklist_patterns)
        
    except Exception:
        return False

def get_image_dimensions(img_tag) -> tuple:
    """
    Versucht die Bildabmessungen aus HTML-Attributen zu ermitteln
    """
    try:
        width = img_tag.get('width')
        height = img_tag.get('height')
        
        if width and height:
            return int(width), int(height)
        
        # Aus Style-Attribut extrahieren
        style = img_tag.get('style', '')
        if 'width:' in style or 'height:' in style:
            # Vereinfachte Extraktion - könnte erweitert werden
            pass
            
        return None, None
    except:
        return None, None

def extract_image_metadata(img_tag, base_url: str) -> Dict:
    """
    Extrahiert alle verfügbaren Metadaten eines Bildes
    """
    try:
        # Basis-URL
        src = img_tag.get('src') or img_tag.get('data-src') or img_tag.get('data-lazy-src')
        if not src:
            return None
            
        img_url = urljoin(base_url, src)
        
        if not is_valid_image_url(img_url):
            return None
        
        # Alt-Text
        alt_text = img_tag.get('alt', '').strip()
        
        # Titel
        title = img_tag.get('title', '').strip()
        
        # Bildabmessungen
        width, height = get_image_dimensions(img_tag)
        
        # Überspringe sehr kleine Bilder
        if width and height and (width < MIN_IMAGE_SIZE or height < MIN_IMAGE_SIZE):
            return None
        
        # Caption und Copyright aus Parent-Elementen suchen
        caption = ""
        copyright_text = "Unbekannt"
        copyright_url = base_url
        
        # Suche in Parent-Elementen nach Caption
        parent = img_tag.find_parent(['figure', 'div', 'span', 'p'])
        if parent:
            # Figcaption
            figcaption = parent.find('figcaption')
            if figcaption:
                caption = figcaption.get_text(strip=True)
                
                # Copyright-Link in Figcaption suchen
                copyright_link = figcaption.find('a')
                if copyright_link:
                    copyright_url = urljoin(base_url, copyright_link.get('href', ''))
                    copyright_text = copyright_link.get_text(strip=True)
            
            # Alternative: Caption in kleinen Texten unter dem Bild
            caption_candidates = parent.find_all(['small', 'em', 'i'], limit=3)
            for candidate in caption_candidates:
                text = candidate.get_text(strip=True)
                if len(text) > 10 and len(text) < 200:  # Plausible Caption-Länge
                    if not caption:  # Nur wenn noch keine Caption gefunden
                        caption = text
        
        # Fallback für Caption
        if not caption:
            caption = title or alt_text or "Bild aus Originalartikel"
        
        return {
            "url": img_url,
            "alt": alt_text,
            "caption": caption[:300] if caption else "Kein Bildtitel vorhanden",
            "copyright": copyright_text or "Unbekannt", 
            "copyright_url": copyright_url or base_url,
            "width": width,
            "height": height,
            "title": title
        }
        
    except Exception as e:
        logging.error(f"Fehler bei Metadaten-Extraktion: {e}")
        return None

def extract_images_with_metadata(article_url: str) -> List[Dict]:
    """
    Hauptfunktion: Extrahiert Bilder mit Metadaten aus einem Artikel
    """
    images = []
    
    if not article_url:
        return images
        
    try:
        logging.info(f"🖼️ Starte Bildextraktion von: {article_url}")
        
        # HTTP-Request mit verbessertem Header
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(article_url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Alle img-Tags finden
        img_tags = soup.find_all("img")
        logging.info(f"🔍 {len(img_tags)} img-Tags gefunden")
        
        processed_urls = set()  # Duplikate vermeiden
        
        for img_tag in img_tags:
            try:
                # Metadaten extrahieren
                image_data = extract_image_metadata(img_tag, article_url)
                
                if image_data and image_data["url"] not in processed_urls:
                    images.append(image_data)
                    processed_urls.add(image_data["url"])
                    
                    logging.info(f"✅ Bild hinzugefügt: {image_data['caption'][:50]}...")
                    
                    # Maximum erreicht?
                    if len(images) >= MAX_IMAGES:
                        break
                        
            except Exception as e:
                logging.error(f"❌ Fehler beim Verarbeiten eines Bildes: {e}")
                continue
        
        # Bilder nach Größe sortieren (größere zuerst)
        images.sort(key=lambda x: (x.get('width', 0) * x.get('height', 0)), reverse=True)
        
        logging.info(f"🎉 {len(images)} Bilder erfolgreich extrahiert von {article_url}")
        return images[:MAX_IMAGES]  # Sicherheitshalber nochmal begrenzen
        
    except requests.RequestException as e:
        logging.error(f"🌐 Netzwerkfehler bei {article_url}: {e}")
        return []
    except Exception as e:
        logging.error(f"❌ Unerwarteter Fehler bei Bildextraktion von {article_url}: {e}")
        return []

def validate_image_url(url: str) -> bool:
    """
    Prüft ob ein Bild tatsächlich erreichbar ist
    """
    try:
        response = requests.head(url, timeout=5)
        content_type = response.headers.get('content-type', '').lower()
        return response.status_code == 200 and 'image' in content_type
    except:
        return False

def extract_featured_image(article_url: str) -> Dict:
    """
    Versucht das Hauptbild/Featured Image eines Artikels zu finden
    """
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(article_url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # OpenGraph Image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = urljoin(article_url, og_image['content'])
            if is_valid_image_url(img_url):
                return {
                    "url": img_url,
                    "alt": "Featured Image",
                    "caption": "Hauptbild des Artikels",
                    "copyright": "Unbekannt",
                    "copyright_url": article_url,
                    "type": "featured"
                }
        
        # Twitter Card Image
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            img_url = urljoin(article_url, twitter_image['content'])
            if is_valid_image_url(img_url):
                return {
                    "url": img_url,
                    "alt": "Featured Image",
                    "caption": "Hauptbild des Artikels",
                    "copyright": "Unbekannt", 
                    "copyright_url": article_url,
                    "type": "featured"
                }
        
        return None
        
    except Exception as e:
        logging.error(f"Fehler bei Featured Image Extraktion: {e}")
        return None

def clean_image_metadata(images: List[Dict]) -> List[Dict]:
    """
    Bereinigt und normalisiert Bildmetadaten
    """
    cleaned_images = []
    
    for img in images:
        try:
            # URL validieren
            if not img.get("url") or not is_valid_image_url(img["url"]):
                continue
            
            # Metadaten bereinigen
            cleaned_img = {
                "url": img["url"].strip(),
                "alt": (img.get("alt") or "").strip()[:200],
                "caption": (img.get("caption") or "Kein Bildtitel vorhanden").strip()[:300],
                "copyright": (img.get("copyright") or "Unbekannt").strip()[:100],
                "copyright_url": (img.get("copyright_url") or "#").strip(),
                "width": img.get("width"),
                "height": img.get("height"),
                "title": (img.get("title") or "").strip()[:200]
            }
            
            # Leere Felder mit Standardwerten füllen
            if not cleaned_img["caption"]:
                cleaned_img["caption"] = "Kein Bildtitel vorhanden"
            if not cleaned_img["copyright"]:
                cleaned_img["copyright"] = "Unbekannt"
            if not cleaned_img["copyright_url"] or cleaned_img["copyright_url"] == "#":
                cleaned_img["copyright_url"] = img["url"]  # Bild-URL als Fallback
            
            cleaned_images.append(cleaned_img)
            
        except Exception as e:
            logging.error(f"Fehler beim Bereinigen der Bildmetadaten: {e}")
            continue
    
    return cleaned_images

# Hauptfunktion für bessere Kompatibilität mit dem bestehenden Code
def extract_images_with_metadata_enhanced(article_url: str) -> List[Dict]:
    """
    Erweiterte Bildextraktion mit Fallback-Strategien
    """
    all_images = []
    
    # 1. Featured Image versuchen
    featured = extract_featured_image(article_url)
    if featured:
        all_images.append(featured)
    
    # 2. Normale Bildextraktion
    content_images = extract_images_with_metadata(article_url)
    all_images.extend(content_images)
    
    # 3. Duplikate entfernen
    seen_urls = set()
    unique_images = []
    for img in all_images:
        if img["url"] not in seen_urls:
            unique_images.append(img)
            seen_urls.add(img["url"])
    
    # 4. Metadaten bereinigen
    cleaned_images = clean_image_metadata(unique_images)
    
    return cleaned_images[:MAX_IMAGES]