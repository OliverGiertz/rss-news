# utils/image_extractor.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging


def extract_images_with_metadata(article_url):
    """
    Versucht, Bilder mit Bildunterschrift und Copyright aus dem Originalartikel zu extrahieren.
    Gibt eine Liste mit Dictionaries zurück: {url, alt, copyright, copyright_url, caption}
    """
    images = []
    try:
        logging.info(f"📷 Extrahiere Bilder von {article_url}")
        response = requests.get(article_url, timeout=10)
        if response.status_code != 200:
            logging.warning(f"Keine gültige Antwort von {article_url} (Status {response.status_code})")
            return []

        soup = BeautifulSoup(response.content, "html.parser")

        for img_tag in soup.find_all("img"):
            src = img_tag.get("src")
            if not src:
                continue

            img_url = urljoin(article_url, src)
            alt_text = img_tag.get("alt", "").strip()

            copyright_text = "Unbekannt"
            copyright_link = article_url
            caption = alt_text or "Bild aus Originalartikel"

            parent = img_tag.find_parent(["figure", "div"])
            if parent:
                figcaption = parent.find("figcaption")
                if figcaption:
                    caption = figcaption.get_text(strip=True)
                    link_tag = figcaption.find("a")
                    if link_tag and link_tag.has_attr("href"):
                        copyright_link = link_tag["href"]
                        copyright_text = link_tag.get_text(strip=True)

            image_data = {
                "url": img_url,
                "alt": alt_text,
                "caption": caption or "Kein Bildtitel vorhanden",
                "copyright": copyright_text or "Unbekannt",
                "copyright_url": copyright_link or article_url
            }
            images.append(image_data)

        logging.info(f"{len(images)} Bilder gefunden bei {article_url}")
        return images

    except Exception as e:
        logging.exception(f"Fehler bei der Bildextraktion aus {article_url}:")
        return []