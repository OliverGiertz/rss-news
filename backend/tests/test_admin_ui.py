import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.main import app
from backend.app.repositories import ArticleUpsert, FeedCreate, SourceCreate, create_feed, create_source, upsert_article


class TestAdminUi(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "admin_ui.db")
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

    def test_admin_login_and_dashboard(self) -> None:
        login_page = self.client.get("/admin/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("rss-news Admin", login_page.text)

        login = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=True,
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("Admin Dashboard", login.text)

    def test_dashboard_redirects_if_not_logged_in(self) -> None:
        res = self.client.get("/admin/dashboard", follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers.get("location"), "/admin/login")

    def test_create_feed_with_empty_source_id_does_not_error(self) -> None:
        self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=True,
        )
        # empty source_id used to cause validation issues in form parsing
        res = self.client.post(
            "/admin/feeds/create",
            data={"name": "Feed X", "url": "https://example.org/feed.xml", "source_id": ""},
            follow_redirects=False,
        )
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers.get("location", "").startswith("/admin/dashboard"))

    def test_article_detail_page_renders(self) -> None:
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
        feed_id = create_feed(
            FeedCreate(
                name="Test Feed",
                url="https://example.org/feed.xml",
                source_id=source_id,
                is_enabled=True,
            )
        )
        article_id = upsert_article(
            ArticleUpsert(
                feed_id=feed_id,
                source_article_id="id-1",
                source_hash="hash-1",
                title="Titel A",
                source_url="https://example.org/a",
                canonical_url="https://example.org/a",
                published_at=None,
                author="Autor A",
                summary="Summary A",
                content_raw="Volltext A",
                content_rewritten=None,
                word_count=2,
                status="new",
                meta_json='{"extraction":{"images":["https://example.org/img.jpg"],"press_contact":"Kontakt"}}',
            )
        )

        self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=True,
        )
        res = self.client.get(f"/admin/articles/{article_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Artikel-Detail", res.text)
        self.assertIn("Rechts-Checkliste", res.text)


if __name__ == "__main__":
    unittest.main()
