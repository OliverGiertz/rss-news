import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

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

        t1 = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "review"})
        self.assertEqual(t1.status_code, 200)

        r1 = self.client.post(f"/api/articles/{article_id}/review", json={"decision": "approve", "note": "ok"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["to_status"], "approved")

        t2 = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "published"})
        self.assertEqual(t2.status_code, 200)

        final = self.client.get(f"/api/articles/{article_id}")
        self.assertEqual(final.status_code, 200)
        self.assertEqual(final.json()["item"]["status"], "published")

    def test_invalid_transition_rejected(self) -> None:
        article_id = self._create_article()
        bad = self.client.post(f"/api/articles/{article_id}/transition", json={"target_status": "published"})
        self.assertEqual(bad.status_code, 400)

    def test_review_only_allowed_in_review_status(self) -> None:
        article_id = self._create_article()
        bad = self.client.post(f"/api/articles/{article_id}/review", json={"decision": "approve"})
        self.assertEqual(bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
