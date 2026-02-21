import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.main import app


class TestArticleWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "workflow.db")
        os.environ["APP_ADMIN_USERNAME"] = "admin"
        os.environ["APP_ADMIN_PASSWORD"] = "secret"
        config_module.get_settings.cache_clear()
        init_db()
        self.client = TestClient(app)
        self.client.post("/auth/login", json={"username": "admin", "password": "secret"})

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        os.environ.pop("APP_DB_PATH", None)
        os.environ.pop("APP_ADMIN_USERNAME", None)
        os.environ.pop("APP_ADMIN_PASSWORD", None)
        self.tmp_dir.cleanup()

    def _create_article(self) -> int:
        source = self.client.post(
            "/api/sources",
            json={
                "name": "Workflow Source",
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
            json={"name": "Workflow Feed", "url": "https://example.org/feed.xml", "source_id": source_id, "is_enabled": True},
        )
        feed_id = feed.json()["id"]

        article = self.client.post(
            "/api/articles/upsert",
            json={
                "feed_id": feed_id,
                "source_article_id": "wf-1",
                "source_url": "https://example.org/a1",
                "title": "Workflow Artikel",
                "summary": "s",
                "content_raw": "c",
                "status": "new",
            },
        )
        return article.json()["id"]

    def test_valid_transition_chain(self) -> None:
        article_id = self._create_article()

        t1 = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "rewrite"})
        self.assertEqual(t1.status_code, 200)

        t2 = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "publish"})
        self.assertEqual(t2.status_code, 200)

        t3 = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "published"})
        self.assertEqual(t3.status_code, 200)

        t4 = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "rewrite"})
        self.assertEqual(t4.status_code, 200)

        final = self.client.get(f"/api/articles/{article_id}")
        self.assertEqual(final.status_code, 200)
        self.assertEqual(final.json()["item"]["status"], "rewrite")
        self.assertEqual(final.json()["item"]["status_ui"], "rewrite")

    def test_invalid_transition_rejected(self) -> None:
        article_id = self._create_article()
        bad = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "published"})
        self.assertEqual(bad.status_code, 400)

    def test_legacy_review_endpoint_is_gone(self) -> None:
        article_id = self._create_article()
        bad = self.client.post(f"/api/articles/{article_id}/review", json={"decision": "approve"})
        self.assertEqual(bad.status_code, 410)

    @patch("backend.app.main.rewrite_article_text")
    def test_rewrite_run_sets_publish_status(self, mock_rewrite) -> None:
        mock_rewrite.return_value = "<h2>Neu</h2><p>Umschreibung</p>"
        article_id = self._create_article()
        self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "rewrite"})
        r = self.client.post(f"/api/articles/{article_id}/rewrite-run")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "publish")
        final = self.client.get(f"/api/articles/{article_id}")
        self.assertEqual(final.json()["item"]["status_ui"], "publish")


if __name__ == "__main__":
    unittest.main()
