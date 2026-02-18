import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.ingestion import run_ingestion
from backend.app.repositories import FeedCreate, SourceCreate, create_feed, create_source, list_articles
from backend.app.source_extraction import ExtractedArticle


class TestIngestion(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "ingestion.db")
        config_module.get_settings.cache_clear()
        init_db()

        source_id = create_source(
            SourceCreate(
                name="Test Source",
                base_url="https://example.org",
                terms_url="https://example.org/terms",
                license_name="cc-by",
                risk_level="green",
                is_enabled=True,
                notes=None,
                last_reviewed_at="2026-02-18T00:00:00Z",
            )
        )
        self.feed_id = create_feed(
            FeedCreate(
                name="Test Feed",
                url="https://example.org/feed.xml",
                source_id=source_id,
                is_enabled=True,
            )
        )

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        os.environ.pop("APP_DB_PATH", None)
        self.tmp_dir.cleanup()

    @patch("backend.app.ingestion.extract_article")
    @patch("backend.app.ingestion.feedparser.parse")
    def test_ingestion_deduplicates_by_feed_and_guid(self, mock_parse, mock_extract_article) -> None:
        mock_extract_article.return_value = ExtractedArticle(
            title="Artikel 1 original",
            author="Autorin A",
            canonical_url="https://example.org/article/1",
            summary="Original Summary",
            content_text="Original Volltext",
            images=["https://example.org/a.jpg"],
            press_contact="Pressekontakt: Team A",
            extraction_error=None,
        )
        mock_parse.return_value = {
            "etag": "etag-1",
            "modified": "Tue, 18 Feb 2026 10:00:00 GMT",
            "entries": [
                {
                    "id": "item-1",
                    "title": "Artikel 1",
                    "link": "https://example.org/article/1",
                    "summary": "A",
                },
                {
                    "id": "item-1",
                    "title": "Artikel 1 aktualisiert",
                    "link": "https://example.org/article/1-neu",
                    "summary": "B",
                },
            ],
        }

        stats = run_ingestion(feed_id=self.feed_id)
        self.assertEqual(stats.status, "success")
        self.assertEqual(stats.entries_seen, 2)
        self.assertEqual(len(list_articles()), 1)
        article = list_articles()[0]
        self.assertEqual(article["title"], "Artikel 1 original")
        self.assertEqual(article["author"], "Autorin A")
        self.assertIn("Original Volltext", article["content_raw"] or "")
        self.assertIn("Pressekontakt", article["meta_json"] or "")
        self.assertIsNotNone(article["image_urls_json"])

    @patch("backend.app.ingestion.extract_article")
    @patch("backend.app.ingestion.feedparser.parse")
    def test_ingestion_blocks_non_green_source(self, mock_parse, mock_extract_article) -> None:
        # Re-create source/feed with yellow risk to verify enforcement
        source_id = create_source(
            SourceCreate(
                name="Blocked Source",
                base_url="https://example.net",
                terms_url="https://example.net/terms",
                license_name="custom",
                risk_level="yellow",
                is_enabled=True,
                notes=None,
                last_reviewed_at="2026-02-18T00:00:00Z",
            )
        )
        blocked_feed_id = create_feed(
            FeedCreate(
                name="Blocked Feed",
                url="https://example.net/feed.xml",
                source_id=source_id,
                is_enabled=True,
            )
        )

        stats = run_ingestion(feed_id=blocked_feed_id)
        self.assertEqual(stats.status, "success")
        self.assertEqual(stats.articles_upserted, 0)
        mock_parse.assert_not_called()
        mock_extract_article.assert_not_called()


if __name__ == "__main__":
    unittest.main()
