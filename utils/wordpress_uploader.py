# utils/wordpress_uploader.py

import requests
import json
import os
import logging
import base64
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# WordPress API Konfiguration
WP_BASE_URL = os.getenv("WP_BASE_URL", "https://vanityontour.de")
WP_USERNAME = os.getenv("WP_USERNAME", "ogiertz")
WP_PASSWORD = os.getenv("WP_PASSWORD", "whNEx9aZCIUXViV89Z3e7Z03")
WP_AUTH_BASE64 = os.getenv("WP_AUTH_BASE64", "b2dpZXJ0ejp3aE5FeDlhWkNJVVhWaVY4OVozZTdaMDM=")
WP_API_ENDPOINT = f"{WP_BASE_URL}/wp-json/wp/v2"

# Request-Konfiguration
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
USER_AGENT = 'RSS-Feed-Manager/1.6.1'

class WordPressUploader:
    """
    Klasse für den Upload von Artikeln zu WordPress über die REST API
    mit Base64-Authentifizierung
    """
    
    def __init__(self):
        self.base_url = WP_BASE_URL
        self.api_endpoint = WP_API_ENDPOINT
        self.username = WP_USERNAME
        self.password = WP_PASSWORD
        self.auth_base64 = WP_AUTH_BASE64
        
        # Session für bessere Performance
        self.session = requests.Session()
        
        # Authentifizierung über Authorization Header mit Base64
        if self.auth_base64:
            # Verwende bereitgestellten Base64-String
            self.session.headers.update({
                'Authorization': f'Basic {self.auth_base64}',
                'User-Agent': USER_AGENT,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            logging.info("✅ WordPress-Authentifizierung: Verwende bereitgestellten Base64-String")
        else:
            # Fallback: Generiere Base64 aus Username/Password
            if self.username and self.password:
                credentials = f"{self.username}:{self.password}"
                encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
                self.session.headers.update({
                    'Authorization': f'Basic {encoded_credentials}',
                    'User-Agent': USER_AGENT,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                })
                logging.info("✅ WordPress-Authentifizierung: Base64 aus Username/Password generiert")
            else:
                logging.error("❌ WordPress-Authentifizierung: Weder Base64-String noch Username/Password verfügbar")
                raise ValueError("WordPress-Authentifizierung nicht konfiguriert")
        
        # Standard-Kategorie ID ermitteln
        self.default_category_id = self._get_default_category_id()
        
    def _get_default_category_id(self) -> int:
        """
        Ermittelt die ID der Standard-Kategorie 'Allgemein'
        """
        try:
            response = self.session.get(
                f"{self.api_endpoint}/categories",
                params={'search': 'Allgemein', 'per_page': 10},
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            categories = response.json()
            
            for category in categories:
                if category['name'].lower() == 'allgemein':
                    logging.info(f"✅ Standard-Kategorie 'Allgemein' gefunden: ID {category['id']}")
                    return category['id']
            
            # Fallback: Erste Kategorie oder Standard-ID
            if categories:
                logging.warning(f"⚠️ Kategorie 'Allgemein' nicht gefunden, verwende '{categories[0]['name']}' (ID: {categories[0]['id']})")
                return categories[0]['id']
            else:
                logging.warning("⚠️ Keine Kategorien gefunden, verwende Standard-ID 1")
                return 1
                
        except Exception as e:
            logging.error(f"❌ Fehler beim Ermitteln der Standard-Kategorie: {e}")
            return 1  # WordPress Standard-Kategorie
    
    def _get_or_create_tags(self, tag_names: List[str]) -> List[int]:
        """
        Ermittelt oder erstellt Tags und gibt deren IDs zurück
        """
        tag_ids = []
        
        if not tag_names:
            return tag_ids
        
        try:
            # Bestehende Tags abrufen
            for tag_name in tag_names:
                tag_name = tag_name.strip()
                if not tag_name:
                    continue
                
                try:
                    # Suche nach existierendem Tag
                    response = self.session.get(
                        f"{self.api_endpoint}/tags",
                        params={'search': tag_name, 'per_page': 10},
                        timeout=REQUEST_TIMEOUT
                    )
                    response.raise_for_status()
                    
                    existing_tags = response.json()
                    tag_found = False
                    
                    # Exakte Übereinstimmung suchen
                    for tag in existing_tags:
                        if tag['name'].lower() == tag_name.lower():
                            tag_ids.append(tag['id'])
                            tag_found = True
                            logging.info(f"✅ Existierender Tag gefunden: '{tag_name}' (ID: {tag['id']})")
                            break
                    
                    # Tag erstellen falls nicht gefunden
                    if not tag_found:
                        create_response = self.session.post(
                            f"{self.api_endpoint}/tags",
                            json={'name': tag_name},
                            timeout=REQUEST_TIMEOUT
                        )
                        
                        if create_response.status_code == 201:
                            new_tag = create_response.json()
                            tag_ids.append(new_tag['id'])
                            logging.info(f"✅ Neuer Tag erstellt: '{tag_name}' (ID: {new_tag['id']})")
                        else:
                            logging.warning(f"⚠️ Tag '{tag_name}' konnte nicht erstellt werden: {create_response.status_code}")
                            continue
                
                except Exception as e:
                    logging.error(f"❌ Fehler beim Verarbeiten von Tag '{tag_name}': {e}")
                    continue
            
            logging.info(f"🏷️ Tags verarbeitet: {len(tag_ids)} Tag-IDs erstellt")
            return tag_ids
            
        except Exception as e:
            logging.error(f"❌ Allgemeiner Fehler bei Tag-Verarbeitung: {e}")
            return []
    def _prepare_post_data(self, article: Dict) -> Dict:
        """
        Bereitet die Artikel-Daten für WordPress vor
        """
        # Tags verarbeiten - WordPress benötigt Tag-IDs, nicht Namen
        tag_names = article.get('tags', [])
        tag_ids = self._get_or_create_tags(tag_names)
        
        # Basis Post-Daten
        post_data = {
            'title': article.get('title', 'Kein Titel'),
            'content': article.get('text', ''),
            'status': 'pending',  # Artikel als "Ausstehend" markieren
            'categories': [self.default_category_id],
            'excerpt': article.get('summary', '')[:300],  # WordPress Excerpt
            'meta': {
                'rss_source': article.get('source', ''),
                'rss_original_link': article.get('link', ''),
                'rss_import_date': datetime.now().isoformat(),
                'rss_article_id': article.get('id', '')
            }
        }
        
        # Tags nur hinzufügen wenn vorhanden
        if tag_ids:
            post_data['tags'] = tag_ids
        
        # Optional: Author setzen (falls unterschiedliche Autoren gewünscht)
        # post_data['author'] = 1  # WordPress User ID
        
        logging.info(f"📝 Post-Daten vorbereitet: Titel='{post_data['title']}', Tags={len(tag_ids)}, Kategorie={self.default_category_id}")
        return post_data
    
    def _check_duplicate(self, article: Dict) -> Optional[int]:
        """
        Prüft, ob ein Artikel bereits in WordPress existiert
        """
        try:
            # Suche nach Titel
            title = article.get('title', '')
            if not title:
                return None
                
            response = self.session.get(
                f"{self.api_endpoint}/posts",
                params={
                    'search': title,
                    'per_page': 5,
                    'status': 'any'  # Alle Status durchsuchen
                },
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            posts = response.json()
            
            for post in posts:
                # Exakte Titel-Übereinstimmung
                if post['title']['rendered'].strip() == title.strip():
                    logging.info(f"🔄 Duplikat gefunden: '{title}' (WordPress ID: {post['id']})")
                    return post['id']
                    
                # Prüfe auch Custom Meta Fields (RSS Article ID)
                article_id = article.get('id')
                if article_id:
                    # Meta-Felder würden eine separate API-Abfrage erfordern
                    # Für jetzt: Nur Titel-basierte Duplikatserkennung
                    pass
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Fehler bei Duplikatsprüfung für '{article.get('title', 'Unbekannt')}': {e}")
            return None
    
    def upload_article(self, article: Dict) -> Tuple[bool, str, Optional[int]]:
        """
        Lädt einen einzelnen Artikel zu WordPress hoch
        
        Returns:
            Tuple[bool, str, Optional[int]]: (Erfolg, Nachricht, WordPress Post ID)
        """
        title = article.get('title', 'Unbekannt')
        
        try:
            logging.info(f"📤 Starte WordPress-Upload: {title}")
            
            # Duplikatsprüfung
            existing_post_id = self._check_duplicate(article)
            if existing_post_id:
                return False, f"Artikel '{title}' existiert bereits in WordPress (ID: {existing_post_id})", existing_post_id
            
            # Post-Daten vorbereiten
            post_data = self._prepare_post_data(article)
            
            # Upload mit Retry-Logik
            for attempt in range(MAX_RETRIES):
                try:
                    response = self.session.post(
                        f"{self.api_endpoint}/posts",
                        json=post_data,
                        timeout=REQUEST_TIMEOUT
                    )
                    
                    if response.status_code == 201:
                        # Erfolgreich erstellt
                        wp_post = response.json()
                        wp_post_id = wp_post['id']
                        wp_url = wp_post['link']
                        
                        logging.info(f"✅ WordPress-Upload erfolgreich: '{title}' (ID: {wp_post_id})")
                        logging.info(f"🔗 WordPress-URL: {wp_url}")
                        return True, f"Erfolgreich hochgeladen: {wp_url}", wp_post_id
                        
                    elif response.status_code == 400:
                        # Client Error - nicht wiederholen
                        error_data = response.json()
                        error_msg = error_data.get('message', 'Unbekannter Fehler')
                        error_code = error_data.get('code', 'unknown')
                        
                        # Detaillierte Fehleranalyse
                        if 'parameter' in error_msg.lower() and 'tags' in error_msg.lower():
                            logging.error(f"❌ WordPress-Tag-Fehler für '{title}': {error_msg}")
                            logging.error(f"📋 Post-Daten: {json.dumps(post_data, indent=2, ensure_ascii=False)}")
                            return False, f"Tag-Fehler: {error_msg} (Artikel-Tags: {article.get('tags', [])})", None
                        else:
                            logging.error(f"❌ WordPress-Fehler 400 für '{title}': {error_msg} (Code: {error_code})")
                            logging.error(f"📋 Post-Daten: {json.dumps(post_data, indent=2, ensure_ascii=False)}")
                            return False, f"WordPress-Fehler: {error_msg}", None
                        
                    elif response.status_code == 401:
                        # Authentifizierungsfehler
                        logging.error(f"❌ WordPress-Authentifizierungsfehler für '{title}'")
                        return False, "Authentifizierungsfehler - bitte Zugangsdaten prüfen", None
                        
                    elif response.status_code == 403:
                        # Berechtigungsfehler
                        logging.error(f"❌ WordPress-Berechtigungsfehler für '{title}'")
                        return False, "Keine Berechtigung zum Erstellen von Posts", None
                        
                    else:
                        # Server Error - Retry möglich
                        if attempt < MAX_RETRIES - 1:
                            logging.warning(f"⚠️ WordPress-Upload Versuch {attempt + 1} fehlgeschlagen für '{title}' (Status: {response.status_code}), versuche erneut...")
                            continue
                        else:
                            logging.error(f"❌ WordPress-Upload nach {MAX_RETRIES} Versuchen fehlgeschlagen für '{title}' (Status: {response.status_code})")
                            return False, f"Upload fehlgeschlagen nach {MAX_RETRIES} Versuchen (HTTP {response.status_code})", None
                
                except requests.exceptions.Timeout:
                    if attempt < MAX_RETRIES - 1:
                        logging.warning(f"⏱️ Timeout bei WordPress-Upload für '{title}' (Versuch {attempt + 1}), versuche erneut...")
                        continue
                    else:
                        logging.error(f"❌ Timeout bei WordPress-Upload für '{title}' nach {MAX_RETRIES} Versuchen")
                        return False, f"Timeout nach {MAX_RETRIES} Versuchen", None
                        
                except requests.exceptions.ConnectionError as e:
                    if attempt < MAX_RETRIES - 1:
                        logging.warning(f"🌐 Verbindungsfehler bei WordPress-Upload für '{title}' (Versuch {attempt + 1}): {e}")
                        continue
                    else:
                        logging.error(f"❌ Verbindungsfehler bei WordPress-Upload für '{title}' nach {MAX_RETRIES} Versuchen: {e}")
                        return False, f"Verbindungsfehler nach {MAX_RETRIES} Versuchen", None
            
        except Exception as e:
            logging.error(f"❌ Unerwarteter Fehler bei WordPress-Upload für '{title}': {e}")
            return False, f"Unerwarteter Fehler: {str(e)}", None
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Testet die Verbindung zur WordPress API mit Base64-Authentifizierung
        """
        try:
            logging.info("🔧 Teste WordPress-API-Verbindung mit Base64-Auth...")
            
            # Debug: Auth-Header prüfen
            auth_header = self.session.headers.get('Authorization', 'Nicht gesetzt')
            logging.info(f"🔑 Authorization Header: {auth_header[:20]}..." if len(auth_header) > 20 else f"🔑 Authorization Header: {auth_header}")
            
            # Einfache Abfrage der Kategorien als Test
            response = self.session.get(
                f"{self.api_endpoint}/categories",
                params={'per_page': 1},
                timeout=REQUEST_TIMEOUT
            )
            
            logging.info(f"📡 API-Response Status: {response.status_code}")
            logging.info(f"📡 API-Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                logging.info("✅ WordPress-API-Verbindung erfolgreich")
                return True, "Verbindung zur WordPress API erfolgreich"
            elif response.status_code == 401:
                logging.error("❌ WordPress-API-Authentifizierung fehlgeschlagen")
                logging.error(f"Response Body: {response.text}")
                return False, "Authentifizierung fehlgeschlagen - bitte Base64-String oder Zugangsdaten prüfen"
            elif response.status_code == 403:
                logging.error("❌ WordPress-API-Berechtigung fehlgeschlagen")
                logging.error(f"Response Body: {response.text}")
                return False, "Keine Berechtigung - bitte Benutzerrechte prüfen"
            else:
                logging.error(f"❌ WordPress-API-Test fehlgeschlagen (Status: {response.status_code})")
                logging.error(f"Response Body: {response.text}")
                return False, f"API-Test fehlgeschlagen (HTTP {response.status_code}): {response.text[:100]}"
                
        except requests.exceptions.ConnectionError as e:
            logging.error(f"❌ Verbindungsfehler zur WordPress API: {e}")
            return False, f"Verbindungsfehler: {str(e)}"
        except Exception as e:
            logging.error(f"❌ Unerwarteter Fehler beim WordPress-API-Test: {e}")
            return False, f"Unerwarteter Fehler: {str(e)}"
    
    def upload_multiple_articles(self, articles: List[Dict]) -> Dict:
        """
        Lädt mehrere Artikel zu WordPress hoch
        
        Returns:
            Dict mit Statistiken über erfolgreiche und fehlgeschlagene Uploads
        """
        results = {
            'total': len(articles),
            'successful': 0,
            'failed': 0,
            'duplicates': 0,
            'details': []
        }
        
        logging.info(f"📦 Starte Batch-Upload von {len(articles)} Artikeln zu WordPress")
        
        for i, article in enumerate(articles, 1):
            title = article.get('title', f'Artikel {i}')
            logging.info(f"📤 Upload {i}/{len(articles)}: {title}")
            
            success, message, wp_post_id = self.upload_article(article)
            
            result_detail = {
                'article_id': article.get('id'),
                'title': title,
                'success': success,
                'message': message,
                'wp_post_id': wp_post_id
            }
            
            results['details'].append(result_detail)
            
            if success:
                results['successful'] += 1
            elif 'existiert bereits' in message:
                results['duplicates'] += 1
            else:
                results['failed'] += 1
            
            # Kurze Pause zwischen Uploads
            if i < len(articles):
                import time
                time.sleep(1)
        
        logging.info(f"📊 Batch-Upload abgeschlossen: {results['successful']} erfolgreich, {results['failed']} fehlgeschlagen, {results['duplicates']} Duplikate")
        return results
    
    def __del__(self):
        """
        Session sauber schließen
        """
        if hasattr(self, 'session'):
            self.session.close()


def upload_articles_to_wordpress(articles: List[Dict]) -> Dict:
    """
    Convenience-Funktion für den Upload von Artikeln zu WordPress
    """
    uploader = WordPressUploader()
    
    # Verbindung testen
    connection_ok, connection_msg = uploader.test_connection()
    if not connection_ok:
        logging.error(f"❌ WordPress-Verbindung fehlgeschlagen: {connection_msg}")
        return {
            'total': len(articles),
            'successful': 0,
            'failed': len(articles),
            'duplicates': 0,
            'error': connection_msg,
            'details': []
        }
    
    # Artikel hochladen
    return uploader.upload_multiple_articles(articles)


def upload_single_article_to_wordpress(article: Dict) -> Tuple[bool, str, Optional[int]]:
    """
    Convenience-Funktion für den Upload eines einzelnen Artikels
    """
    uploader = WordPressUploader()
    
    # Verbindung testen
    connection_ok, connection_msg = uploader.test_connection()
    if not connection_ok:
        return False, connection_msg, None
    
    # Artikel hochladen
    return uploader.upload_article(article)