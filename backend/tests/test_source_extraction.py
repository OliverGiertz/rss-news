import unittest
from unittest.mock import patch

from backend.app.source_extraction import extract_article


SAMPLE_HTML = """
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta property="og:title" content="Demo Meldung von Presseportal" />
  <meta name="author" content="Max Mustermann" />
  <meta name="description" content="Kurzbeschreibung aus der Originalseite" />
  <meta property="og:image" content="/images/demo.jpg" />
  <link rel="canonical" href="https://www.presseportal.de/pm/118273/6158137" />
</head>
<body>
  <article>
    <p>Dies ist der vollstaendige Inhalt des Artikels.</p>
    <p>Weitere relevante Informationen fuer die Meldung.</p>
    <h3>Pressekontakt</h3>
    <p>Musterfirma GmbH, Kontakt: presse@example.org</p>
  </article>
</body>
</html>
"""

SAMPLE_HTML_AGENTUR = """
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta property="og:title" content="Demo Meldung Agentur" />
</head>
<body>
  <article>
    <p>Inhalt der Meldung.</p>
    <h3>Agentur</h3>
    <p>Agenturname GmbH</p>
    <p>presse@agentur.example</p>
    <p>Original-Content von Beispiel</p>
  </article>
</body>
</html>
"""


class _FakeHeaders:
    @staticmethod
    def get_content_charset():
        return "utf-8"


class _FakeResponse:
    headers = _FakeHeaders()

    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class TestSourceExtraction(unittest.TestCase):
    @patch("backend.app.source_extraction.urlopen")
    def test_extract_article_parses_author_images_and_press_contact(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse(SAMPLE_HTML)

        extracted = extract_article("https://www.presseportal.de/pm/118273/6158137")
        self.assertEqual(extracted.title, "Demo Meldung von Presseportal")
        self.assertEqual(extracted.author, "Max Mustermann")
        self.assertEqual(extracted.canonical_url, "https://www.presseportal.de/pm/118273/6158137")
        self.assertIn("vollstaendige Inhalt", extracted.content_text or "")
        self.assertIn("Kurzbeschreibung", extracted.summary or "")
        self.assertIn("https://www.presseportal.de/images/demo.jpg", extracted.images)
        self.assertIn("Pressekontakt", extracted.press_contact or "")
        self.assertIsNone(extracted.extraction_error)

    @patch("backend.app.source_extraction.urlopen")
    def test_extract_article_detects_agentur_block_as_press_contact(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _FakeResponse(SAMPLE_HTML_AGENTUR)
        extracted = extract_article("https://www.presseportal.de/pm/155103/6210401")
        self.assertIn("Agentur", extracted.press_contact or "")
        self.assertIn("Agenturname", extracted.press_contact or "")
        self.assertIn("presse@agentur.example", extracted.press_contact or "")


if __name__ == "__main__":
    unittest.main()
