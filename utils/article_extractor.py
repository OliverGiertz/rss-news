# utils/article_extractor.py

import requests
from bs4 import BeautifulSoup
import logging
import time
from typing import Optional

# Konfiguration
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Website-spezifische Selektoren
CONTENT_SELECTORS = {
    # Promobil & Camping-spezifisch
    'promobil.de': [
        {'tag': 'div', 'class': 'article__text'},
        {'tag': 'div', 'class': 'article-content'},
        {'tag': 'div', 'class': 'content-text'}
    ],
    'camping.info': [
        {'tag': 'div', 'class': 'article-body'},
        {'tag': 'div', 'class': 'post-content'}
    ],
    'caravaning.de': [
        {'tag': 'div', 'class': 'article__content'},
        {'tag': 'div', 'class': 'entry-content'}
    ],
    
    # WordPress Standard-Selektoren
    'wordpress': [
        {'tag': 'div', 'class': 'entry-content'},
        {'tag': 'div', 'class': 'post-content'},
        {'tag': 'div', 'class': 'content'},
        {'tag': 'main', 'class': 'main-content'},
        {'tag': 'article', 'class': None}
    ],
    
    # Allgemeine Fallbacks
    'generic': [
        {'tag': 'article', 'class': None},
        {'tag': 'div', 'class': 'content'},
        {'tag': 'div', 'class': 'post'},
        {'tag': 'div', 'class': 'entry'},
        {'tag': 'main', 'class': None},
        {'tag': 'div', 'id': 'content'},
        {'tag': 'div', 'id': 'main'}
    ]
}

def get_domain_from_url(url: str) -> str:
    """
    Extrahiert die Domain aus einer URL
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""

def get_selectors_for_domain(domain: str) -> list:
    """
    Gibt die passenden Selektoren für eine Domain zurück
    """
    # Direkte Domain-Matches
    for known_domain in CONTENT_SELECTORS:
        if known_domain != 'wordpress' and known_domain != 'generic' and known_domain in domain:
            return CONTENT_SELECTORS[known_domain]
    
    # WordPress erkennen (wird später durch Meta-Tags erkannt)
    return CONTENT_SELECTORS['generic']

def is_wordpress_site(soup: BeautifulSoup) -> bool:
    """
    Erkennt WordPress-Websites anhand von Meta-Tags
    """
    try:
        # WordPress Generator Meta-Tag
        generator = soup.find('meta', attrs={'name': 'generator'})
        if generator and 'wordpress' in generator.get('content', '').lower():
            return True
        
        # WordPress-spezifische Link-Tags
        wp_links = soup.find_all('link', href=lambda x: x and '/wp-' in x)
        if wp_links:
            return True
            
        # WordPress REST API
        rest_api = soup.find('link', attrs={'rel': 'https://api.w.org/'})
        if rest_api:
            return True
            
        return False
    except:
        return False

def clean_extracted_text(text: str) -> str:
    """
    Bereinigt extrahierten Text von unerwünschten Elementen
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Überspringe sehr kurze Zeilen (wahrscheinlich Navigation/Werbung)
        if len(line) < 10:
            continue
            
        # Überspringe typische Navigation/Footer-Texte
        skip_patterns = [
            'cookie', 'datenschutz', 'impressum', 'agb', 'newsletter',
            'folgen sie uns', 'social media', 'teilen', 'weiterlesen',
            'mehr zum thema', 'ähnliche artikel', 'kommentare',
            'anzeige', 'werbung', 'advertisement'
        ]
        
        if any(pattern in line.lower() for pattern in skip_patterns):
            continue
            
        # Überspringe Zeilen mit zu vielen Sonderzeichen (Navigation)
        if len([c for c in line if c in '|•→←↑↓']) > 3:
            continue
            
        cleaned_lines.append(line)
    
    # Text zusammenfügen
    cleaned_text = ' '.join(cleaned_lines)
    
    # Mehrfache Leerzeichen entfernen
    cleaned_text = ' '.join(cleaned_text.split())
    
    return cleaned_text

def extract_with_selectors(soup: BeautifulSoup, selectors: list) -> str:
    """
    Versucht Text mit einer Liste von Selektoren zu extrahieren
    """
    for selector in selectors:
        try:
            element = None
            
            if selector.get('class'):
                element = soup.find(selector['tag'], class_=selector['class'])
            elif selector.get('id'):
                element = soup.find(selector['tag'], id=selector['id'])
            else:
                element = soup.find(selector['tag'])
            
            if element:
                # Entferne Script- und Style-Tags
                for script in element(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    script.decompose()
                
                text = element.get_text(' ', strip=True)
                
                # Nur zurückgeben wenn genügend Text vorhanden
                if len(text.split()) > 50:
                    logging.info(f"✅ Erfolgreiche Extraktion mit Selektor: {selector}")
                    return clean_extracted_text(text)
                    
        except Exception as e:
            logging.debug(f"Selektor {selector} fehlgeschlagen: {e}")
            continue
    
    return ""

def extract_from_paragraphs(soup: BeautifulSoup) -> str:
    """
    Fallback: Extrahiert Text aus allen Paragraph-Tags
    """
    try:
        paragraphs = soup.find_all('p')
        
        if not paragraphs:
            return ""
        
        # Sammle alle Paragraph-Texte
        texts = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 20:  # Nur längere Absätze
                texts.append(text)
        
        combined_text = ' '.join(texts)
        
        if len(combined_text.split()) > 30:
            logging.info(f"✅ Fallback-Extraktion aus {len(paragraphs)} Paragraphen")
            return clean_extracted_text(combined_text)
            
        return ""
        
    except Exception as e:
        logging.error(f"Fehler bei Paragraph-Extraktion: {e}")
        return ""

def extract_full_article(url: str) -> str:
    """
    Hauptfunktion: Extrahiert den vollständigen Artikeltext von einer URL
    """
    if not url:
        return ""
    
    retries = 0
    
    while retries < MAX_RETRIES:
        try:
            logging.info(f"📰 Starte Volltextextraktion von: {url} (Versuch {retries + 1})")
            
            # HTTP-Request mit verbessertem Header
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
            response.raise_for_status()
            
            # Encoding sicherstellen
            if response.encoding.lower() in ['iso-8859-1', 'windows-1252']:
                response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Domain-spezifische Selektoren ermitteln
            domain = get_domain_from_url(url)
            selectors = get_selectors_for_domain(domain)
            
            # WordPress erkennen und entsprechende Selektoren verwenden
            if is_wordpress_site(soup):
                logging.info("🔧 WordPress-Site erkannt")
                selectors = CONTENT_SELECTORS['wordpress'] + selectors
            
            # 1. Versuch: Domain-spezifische Selektoren
            extracted_text = extract_with_selectors(soup, selectors)
            
            if extracted_text and len(extracted_text.split()) > 50:
                logging.info(f"🎉 Erfolgreiche Extraktion: {len(extracted_text.split())} Wörter")
                return extracted_text
            
            # 2. Versuch: Generische Selektoren
            if not extracted_text:
                logging.info("🔄 Fallback auf generische Selektoren")
                extracted_text = extract_with_selectors(soup, CONTENT_SELECTORS['generic'])
            
            if extracted_text and len(extracted_text.split()) > 50:
                logging.info(f"🎉 Erfolgreiche Extraktion (generisch): {len(extracted_text.split())} Wörter")
                return extracted_text
            
            # 3. Versuch: Paragraph-Extraktion
            if not extracted_text:
                logging.info("🔄 Fallback auf Paragraph-Extraktion")
                extracted_text = extract_from_paragraphs(soup)
            
            if extracted_text and len(extracted_text.split()) > 30:
                logging.info(f"🎉 Erfolgreiche Extraktion (Paragraphen): {len(extracted_text.split())} Wörter")
                return extracted_text
            
            # 4. Letzter Versuch: Gesamter Body-Text
            if not extracted_text:
                logging.info("🔄 Letzter Fallback: Body-Text")
                body = soup.find('body')
                if body:
                    # Entferne Navigation, Header, Footer
                    for element in body(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                        element.decompose()
                    
                    body_text = body.get_text(' ', strip=True)
                    if len(body_text.split()) > 100:
                        extracted_text = clean_extracted_text(body_text)
                        logging.info(f"⚠️ Body-Extraktion: {len(extracted_text.split())} Wörter")
                        return extracted_text
            
            # Kein brauchbarer Text gefunden
            if not extracted_text:
                logging.warning(f"⚠️ Keine verwertbaren Inhalte gefunden bei: {url}")
                return ""
            
            return extracted_text
            
        except requests.RequestException as e:
            retries += 1
            logging.warning(f"🌐 Netzwerkfehler bei {url} (Versuch {retries}): {e}")
            
            if retries < MAX_RETRIES:
                time.sleep(2 ** retries)  # Exponential backoff
                continue
            else:
                logging.error(f"❌ Maximale Anzahl Versuche erreicht für: {url}")
                return ""
                
        except Exception as e:
            logging.error(f"❌ Unerwarteter Fehler bei Volltextextraktion von {url}: {e}")
            return ""
    
    return ""

def extract_article_summary(full_text: str, max_length: int = 300) -> str:
    """
    Erstellt eine intelligente Zusammenfassung aus dem Volltext
    """
    if not full_text:
        return ""
    
    sentences = full_text.split('.')
    
    # Erste 2-3 sinnvolle Sätze als Summary verwenden
    summary_sentences = []
    current_length = 0
    
    for sentence in sentences[:5]:  # Maximal erste 5 Sätze prüfen
        sentence = sentence.strip()
        
        if len(sentence) < 20:  # Zu kurze Sätze überspringen
            continue
            
        if current_length + len(sentence) > max_length:
            break
            
        summary_sentences.append(sentence)
        current_length += len(sentence)
    
    summary = '. '.join(summary_sentences)
    
    if summary and not summary.endswith('.'):
        summary += '.'
    
    return summary[:max_length]

def validate_extracted_content(text: str) -> bool:
    """
    Validiert ob der extrahierte Inhalt brauchbar ist
    """
    if not text or len(text.strip()) < 100:
        return False
    
    words = text.split()
    
    # Mindestens 50 Wörter
    if len(words) < 50:
        return False
    
    # Nicht zu viele Sonderzeichen (Navigation etc.)
    special_chars = len([c for c in text if c in '|•→←↑↓'])
    if special_chars > len(text) * 0.05:  # Mehr als 5% Sonderzeichen
        return False
    
    # Durchschnittliche Wortlänge prüfen (zu kurz = Navigation)
    avg_word_length = sum(len(word) for word in words) / len(words)
    if avg_word_length < 3:
        return False
    
    return True