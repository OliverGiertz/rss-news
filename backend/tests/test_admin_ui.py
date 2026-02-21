import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.main import app
from backend.app.repositories import (
    ArticleUpsert,
    FeedCreate,
    SourceCreate,
    create_feed,
    create_source,
    get_article_by_id,
    upsert_article,
)


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
                image_urls_json='["https://example.org/img.jpg"]',
                press_contact="Kontakt",
                source_name_snapshot="Test Source",
                source_terms_url_snapshot="https://example.org/terms",
                source_license_name_snapshot="cc-by",
                legal_checked=False,
                legal_checked_at=None,
                legal_note=None,
                wp_post_id=None,
                wp_post_url=None,
                publish_attempts=0,
                publish_last_error=None,
                published_to_wp_at=None,
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

        decision = self.client.post(
            f"/admin/articles/{article_id}/images/decision",
            data={"image_url": "https://example.org/img.jpg", "action": "select"},
            follow_redirects=True,
        )
        self.assertEqual(decision.status_code, 200)
        self.assertIn("Ausgewähltes Hauptbild", decision.text)

        article = get_article_by_id(article_id)
        self.assertIsNotNone(article)
        self.assertIn("selected_url", article.get("meta_json", ""))

    @patch("backend.app.admin_ui.urlopen")
    def test_image_proxy_returns_image_data(self, mock_urlopen) -> None:
        class _FakeHeaders:
            def get(self, key: str, default=None):
                if key.lower() == "content-type":
                    return "image/jpeg"
                return default

        class _FakeResponse:
            headers = _FakeHeaders()

            def read(self):
                return b"\xff\xd8\xff\xd9"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return False

        mock_urlopen.return_value = _FakeResponse()

        self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=True,
        )
        res = self.client.get("/admin/images/proxy?url=https%3A%2F%2Fexample.org%2Fimg.jpg")
        self.assertEqual(res.status_code, 200)
        self.assertIn("image/jpeg", res.headers.get("content-type", ""))

    @patch("backend.app.admin_ui._run_connectivity_check")
    @patch("backend.app.admin_ui._build_connectivity_targets")
    def test_connectivity_page_renders(self, mock_targets, mock_check) -> None:
        mock_targets.return_value = [
            {"label": "OpenAI API", "kind": "host", "value": "api.openai.com"},
            {"label": "WordPress REST", "kind": "url", "value": "https://example.org/wp-json/wp/v2"},
        ]
        mock_check.side_effect = [
            {
                "label": "OpenAI API",
                "kind": "host",
                "target": "api.openai.com",
                "dns_ok": True,
                "dns_info": "1.2.3.4",
                "tcp_ok": True,
                "tcp_info": "port 443 erreichbar",
                "http_ok": True,
                "http_info": "n/a (host-only)",
                "duration_ms": 12,
                "ok": True,
            },
            {
                "label": "WordPress REST",
                "kind": "url",
                "target": "https://example.org/wp-json/wp/v2",
                "dns_ok": False,
                "dns_info": "Name or service not known",
                "tcp_ok": False,
                "tcp_info": "-",
                "http_ok": False,
                "http_info": "-",
                "duration_ms": 10,
                "ok": False,
            },
        ]

        self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=True,
        )
        res = self.client.get("/admin/connectivity", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Connectivity Check", res.text)
        self.assertIn("OpenAI API", res.text)
        self.assertIn("WordPress REST", res.text)


if __name__ == "__main__":
    unittest.main()
