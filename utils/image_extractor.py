import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def extract_images_with_metadata(article_url):
    """
    Versucht, Bilder mit Bildunterschrift und Copyright aus dem Originalartikel zu extrahieren.
    Gibt eine Liste mit Dictionaries zurück: {url, alt, copyright_text, copyright_link}
    """
    try:
        response = requests.get(article_url, timeout=10)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        images = []

        for img_tag in soup.find_all("img"):
            src = img_tag.get("src")
            if not src:
                continue

            # Vollständige URL bauen
            img_url = urljoin(article_url, src)
            alt_text = img_tag.get("alt", "").strip()

            # Copyright-Hinweis suchen: z. B. umgebender <figure> oder <div>
            copyright_text = ""
            copyright_link = ""

            parent = img_tag.find_parent(["figure", "div"])
            if parent:
                caption = parent.find("figcaption")
                if caption:
                    copyright_text = caption.get_text(strip=True)
                    link_tag = caption.find("a")
                    if link_tag and link_tag.has_attr("href"):
                        copyright_link = link_tag["href"]

            images.append({
                "url": img_url,
                "alt": alt_text or "Bild aus Originalartikel",
                "copyright_text": copyright_text or "Unbekannt",
                "copyright_link": copyright_link or article_url
            })

        return images

    except Exception as e:
        print(f"[extract_images_with_metadata] Fehler bei {article_url}: {e}")
        return []
