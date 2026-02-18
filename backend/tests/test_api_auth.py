import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.main import app


class TestApiAuth(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "api.db")
        os.environ["APP_ADMIN_USERNAME"] = "admin"
        os.environ["APP_ADMIN_PASSWORD"] = "secret"
        config_module.get_settings.cache_clear()
        init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        os.environ.pop("APP_DB_PATH", None)
        os.environ.pop("APP_ADMIN_USERNAME", None)
        os.environ.pop("APP_ADMIN_PASSWORD", None)
        self.tmp_dir.cleanup()

    def test_login_and_protected_endpoint(self) -> None:
        r = self.client.post("/auth/login", json={"username": "admin", "password": "secret"})
        self.assertEqual(r.status_code, 200)

        p = self.client.get("/api/protected")
        self.assertEqual(p.status_code, 200)
        self.assertTrue(p.json().get("ok"))

    def test_protected_requires_auth(self) -> None:
        r = self.client.get("/api/protected")
        self.assertEqual(r.status_code, 401)

    def test_run_detail_endpoint(self) -> None:
        login = self.client.post("/auth/login", json={"username": "admin", "password": "secret"})
        self.assertEqual(login.status_code, 200)

        created = self.client.post("/api/runs", json={"run_type": "ingestion", "status": "running"})
        self.assertEqual(created.status_code, 200)
        run_id = created.json()["id"]

        detail = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["item"]["id"], run_id)

    def test_source_policy_check_endpoint(self) -> None:
        login = self.client.post("/auth/login", json={"username": "admin", "password": "secret"})
        self.assertEqual(login.status_code, 200)

        created = self.client.post(
            "/api/sources",
            json={
                "name": "Policy Source",
                "risk_level": "yellow",
                "is_enabled": True,
            },
        )
        self.assertEqual(created.status_code, 200)
        source_id = created.json()["id"]

        check = self.client.get(f"/api/sources/{source_id}/policy-check")
        self.assertEqual(check.status_code, 200)
        body = check.json()
        self.assertFalse(body["allowed"])
        self.assertGreaterEqual(len(body["issues"]), 1)

    def test_articles_export_json_and_csv_contains_relevance(self) -> None:
        login = self.client.post("/auth/login", json={"username": "admin", "password": "secret"})
        self.assertEqual(login.status_code, 200)

        source = self.client.post(
            "/api/sources",
            json={
                "name": "Export Source",
                "base_url": "https://example.org",
                "terms_url": "https://example.org/terms",
                "license_name": "cc-by",
                "risk_level": "green",
                "is_enabled": True,
                "last_reviewed_at": "2026-02-18T00:00:00Z",
            },
        )
        self.assertEqual(source.status_code, 200)
        source_id = source.json()["id"]

        feed = self.client.post(
            "/api/feeds",
            json={"name": "Export Feed", "url": "https://example.org/feed.xml", "source_id": source_id, "is_enabled": True},
        )
        self.assertEqual(feed.status_code, 200)
        feed_id = feed.json()["id"]

        article = self.client.post(
            "/api/articles/upsert",
            json={
                "feed_id": feed_id,
                "source_article_id": "exp-1",
                "source_hash": "exp-hash-1",
                "title": "Export Artikel",
                "source_url": "https://example.org/article/1",
                "canonical_url": "https://example.org/article/1",
                "published_at": "2026-02-18T00:00:00Z",
                "author": "Autor",
                "summary": "Kurz",
                "content_raw": "Langtext",
                "image_urls_json": "[\"https://example.org/img.jpg\"]",
                "press_contact": "Kontakt",
                "source_name_snapshot": "Export Source",
                "source_terms_url_snapshot": "https://example.org/terms",
                "source_license_name_snapshot": "cc-by",
                "status": "review",
            },
        )
        self.assertEqual(article.status_code, 200)

        export_json = self.client.get("/api/articles/export?format=json")
        self.assertEqual(export_json.status_code, 200)
        body = export_json.json()
        self.assertTrue(body.get("ok"))
        self.assertGreaterEqual(body.get("count", 0), 1)
        first = body["items"][0]
        self.assertIn("published_at", first)
        self.assertIn("days_old", first)
        self.assertIn("relevance", first)

        export_csv = self.client.get("/api/articles/export?format=csv")
        self.assertEqual(export_csv.status_code, 200)
        self.assertIn("text/csv", export_csv.headers.get("content-type", ""))
        csv_text = export_csv.text
        self.assertIn("published_at", csv_text)
        self.assertIn("days_old", csv_text)
        self.assertIn("relevance", csv_text)


if __name__ == "__main__":
    unittest.main()
