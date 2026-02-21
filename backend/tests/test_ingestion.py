import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.ingestion import run_ingestion
from backend.app.repositories import (
    ArticleUpsert,
    FeedCreate,
    SourceCreate,
    create_feed,
    create_source,
    get_article_by_id,
    list_articles,
    upsert_article,
)
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

    @patch("backend.app.ingestion.extract_article")
    @patch("backend.app.ingestion.feedparser.parse")
    def test_ingestion_preserves_existing_work_and_skips_closed(self, mock_parse, mock_extract_article) -> None:
        existing_closed_id = upsert_article(
            ArticleUpsert(
                feed_id=self.feed_id,
                source_article_id="closed-1",
                source_hash="closed-hash-1",
                title="Alt Closed",
                source_url="https://example.org/closed-article",
                canonical_url="https://example.org/closed-article",
                published_at=None,
                author="Autor",
                summary="Alt",
                content_raw="Alt Raw",
                content_rewritten="<p>Alt Rewrite Closed</p>",
                image_urls_json=None,
                press_contact="Kontakt Alt",
                source_name_snapshot="Test Source",
                source_terms_url_snapshot="https://example.org/terms",
                source_license_name_snapshot="cc-by",
                legal_checked=False,
                legal_checked_at=None,
                legal_note=None,
                wp_post_id=42,
                wp_post_url="https://wp.local/?p=42",
                publish_attempts=2,
                publish_last_error=None,
                published_to_wp_at="2026-02-21T12:00:00Z",
                word_count=3,
                status="error",  # UI: close
                meta_json='{"generated_tags":["AltTag"]}',
            )
        )
        existing_published_id = upsert_article(
            ArticleUpsert(
                feed_id=self.feed_id,
                source_article_id="published-1",
                source_hash="published-hash-1",
                title="Alt Published",
                source_url="https://example.org/published-article",
                canonical_url="https://example.org/published-article",
                published_at=None,
                author="Autor",
                summary="Alt",
                content_raw="Alt Raw",
                content_rewritten="<p>Alt Rewrite Published</p>",
                image_urls_json=None,
                press_contact="Kontakt Alt",
                source_name_snapshot="Test Source",
                source_terms_url_snapshot="https://example.org/terms",
                source_license_name_snapshot="cc-by",
                legal_checked=False,
                legal_checked_at=None,
                legal_note=None,
                wp_post_id=77,
                wp_post_url="https://wp.local/?p=77",
                publish_attempts=3,
                publish_last_error=None,
                published_to_wp_at="2026-02-21T12:10:00Z",
                word_count=3,
                status="published",
                meta_json='{"generated_tags":["Rheingas"],"image_review":{"selected_url":"https://img.local/1.jpg"}}',
            )
        )

        mock_extract_article.return_value = ExtractedArticle(
            title="Neu Titel",
            author="Neu Autor",
            canonical_url=None,
            summary="Neu Summary",
            content_text="Neu Volltext",
            images=["https://example.org/a.jpg"],
            press_contact=None,
            extraction_error=None,
        )
        mock_parse.return_value = {
            "etag": "etag-2",
            "modified": "Tue, 18 Feb 2026 11:00:00 GMT",
            "entries": [
                {
                    "id": "closed-1",
                    "title": "Closed Entry",
                    "link": "https://example.org/closed-article",
                    "summary": "X",
                },
                {
                    "id": "published-1",
                    "title": "Published Entry",
                    "link": "https://example.org/published-article",
                    "summary": "Y",
                },
            ],
        }

        stats = run_ingestion(feed_id=self.feed_id)
        self.assertEqual(stats.status, "success")
        closed_row = get_article_by_id(existing_closed_id) or {}
        self.assertEqual(closed_row["status"], "error")
        self.assertIn("Alt Rewrite Closed", closed_row.get("content_rewritten") or "")
        self.assertEqual(closed_row.get("wp_post_id"), 42)

        published_row = get_article_by_id(existing_published_id) or {}
        self.assertEqual(published_row["status"], "published")
        self.assertIn("Alt Rewrite Published", published_row.get("content_rewritten") or "")
        self.assertEqual(published_row.get("wp_post_id"), 77)
        self.assertIn("generated_tags", published_row.get("meta_json") or "")


if __name__ == "__main__":
    unittest.main()
