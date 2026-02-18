import os
import tempfile
import unittest
from pathlib import Path

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.repositories import (
    ArticleUpsert,
    FeedCreate,
    RunCreate,
    SourceCreate,
    create_feed,
    create_run,
    create_source,
    finish_run,
    list_articles,
    list_feeds,
    list_runs,
    list_sources,
    upsert_article,
)


class TestSQLiteRepositories(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "test.db")
        os.environ["APP_DB_PATH"] = self.db_path
        config_module.get_settings.cache_clear()
        init_db()

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        os.environ.pop("APP_DB_PATH", None)
        self.tmp_dir.cleanup()

    def test_end_to_end_basic_crud(self) -> None:
        source_id = create_source(
            SourceCreate(
                name="GovData",
                base_url="https://data.gov.de",
                terms_url="https://www.govdata.de/dl-de/by-2-0",
                license_name="dl-de/by-2-0",
                risk_level="green",
                is_enabled=True,
                notes="test source",
                last_reviewed_at="2026-02-18T00:00:00Z",
            )
        )
        self.assertGreater(source_id, 0)

        feed_id = create_feed(
            FeedCreate(
                name="GovData RSS",
                url="https://example.org/feed.xml",
                source_id=source_id,
                is_enabled=True,
            )
        )
        self.assertGreater(feed_id, 0)

        run_id = create_run(RunCreate(run_type="ingest", status="running", details="start"))
        self.assertGreater(run_id, 0)
        finish_run(run_id=run_id, status="success", details="ok")

        article_id = upsert_article(
            ArticleUpsert(
                feed_id=feed_id,
                source_article_id="abc-1",
                source_hash="hash-abc-1",
                title="Beispielartikel",
                source_url="https://example.org/articles/1",
                canonical_url="https://example.org/articles/1",
                published_at="2026-02-18T00:00:00Z",
                author="Max Mustermann",
                summary="Kurzfassung",
                content_raw="Originaltext",
                content_rewritten="Umschreibung",
                image_urls_json='["https://example.org/img.jpg"]',
                press_contact="Pressekontakt X",
                source_name_snapshot="GovData",
                source_terms_url_snapshot="https://www.govdata.de/dl-de/by-2-0",
                source_license_name_snapshot="dl-de/by-2-0",
                legal_checked=False,
                legal_checked_at=None,
                legal_note=None,
                word_count=120,
                status="review",
                meta_json='{"lang":"de"}',
            )
        )
        self.assertGreater(article_id, 0)

        # Upsert with same source_url updates same row
        article_id_2 = upsert_article(
            ArticleUpsert(
                feed_id=feed_id,
                source_article_id="abc-1",
                source_hash="hash-abc-1",
                title="Beispielartikel aktualisiert",
                source_url="https://example.org/articles/1",
                canonical_url="https://example.org/articles/1",
                published_at="2026-02-18T00:00:00Z",
                author="Max Mustermann",
                summary="Kurzfassung 2",
                content_raw="Originaltext 2",
                content_rewritten="Umschreibung 2",
                image_urls_json='["https://example.org/img2.jpg"]',
                press_contact="Pressekontakt Y",
                source_name_snapshot="GovData",
                source_terms_url_snapshot="https://www.govdata.de/dl-de/by-2-0",
                source_license_name_snapshot="dl-de/by-2-0",
                legal_checked=True,
                legal_checked_at="2026-02-18T00:10:00Z",
                legal_note="ok",
                word_count=140,
                status="approved",
                meta_json='{"lang":"de","v":2}',
            )
        )
        self.assertEqual(article_id, article_id_2)

        self.assertEqual(len(list_sources()), 1)
        self.assertEqual(len(list_feeds()), 1)
        self.assertEqual(len(list_runs()), 1)

        articles = list_articles()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Beispielartikel aktualisiert")
        self.assertEqual(articles[0]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
