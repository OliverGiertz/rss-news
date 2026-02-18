import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.main import app


class TestPublisher(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "publisher.db")
        os.environ["APP_ADMIN_USERNAME"] = "admin"
        os.environ["APP_ADMIN_PASSWORD"] = "secret"
        os.environ["WORDPRESS_BASE_URL"] = "https://example.org"
        os.environ["WORDPRESS_USERNAME"] = "wp-user"
        os.environ["WORDPRESS_APP_PASSWORD"] = "wp-pass"
        config_module.get_settings.cache_clear()
        init_db()
        self.client = TestClient(app)
        self.client.post("/auth/login", json={"username": "admin", "password": "secret"})

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        for key in (
            "APP_DB_PATH",
            "APP_ADMIN_USERNAME",
            "APP_ADMIN_PASSWORD",
            "WORDPRESS_BASE_URL",
            "WORDPRESS_USERNAME",
            "WORDPRESS_APP_PASSWORD",
        ):
            os.environ.pop(key, None)
        self.tmp_dir.cleanup()

    def _create_publishable_article(self) -> int:
        source = self.client.post(
            "/api/sources",
            json={
                "name": "WP Source",
                "base_url": "https://example.org",
                "terms_url": "https://example.org/terms",
                "license_name": "cc-by",
                "risk_level": "green",
                "is_enabled": True,
                "last_reviewed_at": "2026-02-18T00:00:00Z",
            },
        )
        source_id = source.json()["id"]
        feed = self.client.post(
            "/api/feeds",
            json={"name": "WP Feed", "url": "https://example.org/feed.xml", "source_id": source_id, "is_enabled": True},
        )
        feed_id = feed.json()["id"]

        article = self.client.post(
            "/api/articles/upsert",
            json={
                "feed_id": feed_id,
                "source_article_id": "pub-1",
                "source_hash": "pub-hash-1",
                "title": "Publish Artikel",
                "source_url": "https://example.org/article/1",
                "canonical_url": "https://example.org/article/1",
                "published_at": "2026-02-18T00:00:00Z",
                "author": "Autor",
                "summary": "Kurz",
                "content_raw": "Langtext",
                "image_urls_json": "[\"https://example.org/img.jpg\"]",
                "press_contact": "Kontakt",
                "source_name_snapshot": "WP Source",
                "source_terms_url_snapshot": "https://example.org/terms",
                "source_license_name_snapshot": "cc-by",
                "legal_checked": True,
                "status": "approved",
                "meta_json": "{\"image_review\":{\"selected_url\":\"https://example.org/img.jpg\"}}",
            },
        )
        return article.json()["id"]

    @patch("backend.app.publisher.publish_article_draft")
    def test_enqueue_and_run_publisher(self, mock_publish) -> None:
        mock_publish.return_value = (777, "https://example.org/?p=777")
        article_id = self._create_publishable_article()

        enqueue = self.client.post("/api/publisher/enqueue", json={"article_id": article_id, "max_attempts": 3})
        self.assertEqual(enqueue.status_code, 200)

        run = self.client.post("/api/publisher/run", json={"max_jobs": 5})
        self.assertEqual(run.status_code, 200)
        stats = run.json()["stats"]
        self.assertEqual(stats["success"], 1)

        article = self.client.get(f"/api/articles/{article_id}")
        self.assertEqual(article.status_code, 200)
        item = article.json()["item"]
        self.assertEqual(item["status"], "published")
        self.assertEqual(item["wp_post_id"], 777)
        self.assertIn("?p=777", item["wp_post_url"] or "")

        jobs = self.client.get("/api/publisher/jobs")
        self.assertEqual(jobs.status_code, 200)
        self.assertGreaterEqual(len(jobs.json()["items"]), 1)


if __name__ == "__main__":
    unittest.main()
