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
        self.assertIn("Checkliste", res.text)

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

    def test_manage_source_and_feed(self) -> None:
        source_id = create_source(
            SourceCreate(
                name="Edit Source",
                base_url="https://example.org",
                terms_url="https://example.org/terms",
                license_name="cc-by",
                risk_level="yellow",
                is_enabled=True,
                notes=None,
                last_reviewed_at=None,
            )
        )
        feed_id = create_feed(
            FeedCreate(
                name="Edit Feed",
                url="https://example.org/feed.xml",
                source_id=source_id,
                is_enabled=True,
            )
        )
        self.client.post("/admin/login", data={"username": "admin", "password": "secret"}, follow_redirects=True)

        update_source_res = self.client.post(
            f"/admin/sources/{source_id}/update",
            data={
                "name": "Edit Source 2",
                "base_url": "https://example.org/new",
                "terms_url": "https://example.org/new-terms",
                "license_name": "cc0",
                "risk_level": "green",
                "is_enabled": "1",
                "notes": "ok",
                "last_reviewed_at": "2026-02-21T12:00:00Z",
            },
            follow_redirects=False,
        )
        self.assertEqual(update_source_res.status_code, 303)

        update_feed_res = self.client.post(
            f"/admin/feeds/{feed_id}/update",
            data={
                "name": "Edit Feed 2",
                "url": "https://example.org/feed2.xml",
                "source_id": str(source_id),
                "is_enabled": "0",
            },
            follow_redirects=False,
        )
        self.assertEqual(update_feed_res.status_code, 303)

        delete_feed_res = self.client.post(f"/admin/feeds/{feed_id}/delete", follow_redirects=False)
        self.assertEqual(delete_feed_res.status_code, 303)
        delete_source_res = self.client.post(f"/admin/sources/{source_id}/delete", follow_redirects=False)
        self.assertEqual(delete_source_res.status_code, 303)

    def test_rewrite_save_and_reopen(self) -> None:
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
                source_article_id="id-published",
                source_hash="hash-published",
                title="Titel Published",
                source_url="https://example.org/published",
                canonical_url="https://example.org/published",
                published_at=None,
                author="Autor A",
                summary="Summary",
                content_raw="Raw",
                content_rewritten="<p>Alt</p>",
                image_urls_json=None,
                press_contact=None,
                source_name_snapshot="Test Source",
                source_terms_url_snapshot="https://example.org/terms",
                source_license_name_snapshot="cc-by",
                legal_checked=True,
                legal_checked_at="2026-02-21T10:00:00Z",
                legal_note=None,
                wp_post_id=123,
                wp_post_url="https://example.org/?p=123",
                publish_attempts=2,
                publish_last_error=None,
                published_to_wp_at="2026-02-21T10:10:00Z",
                word_count=1,
                status="published",
                meta_json="{}",
            )
        )
        self.client.post("/admin/login", data={"username": "admin", "password": "secret"}, follow_redirects=True)

        save_res = self.client.post(
            f"/admin/articles/{article_id}/rewrite-save",
            data={"content_rewritten": "<h2>Neu</h2><p>Text</p>"},
            follow_redirects=False,
        )
        self.assertEqual(save_res.status_code, 303)

        reopen_res = self.client.post(f"/admin/articles/{article_id}/reopen", follow_redirects=False)
        self.assertEqual(reopen_res.status_code, 303)

        article = get_article_by_id(article_id)
        self.assertIsNotNone(article)
        self.assertEqual(article.get("status"), "rewrite")
        self.assertIn("Neu", article.get("content_rewritten") or "")
        self.assertIsNone(article.get("wp_post_id"))

    @patch("backend.app.admin_ui.generate_article_tags")
    @patch("backend.app.admin_ui.rewrite_article_text")
    def test_batch_rewrite_run_processes_planned_articles(self, mock_rewrite_text, mock_tags) -> None:
        mock_rewrite_text.return_value = "<h2>Neu</h2><p>Text</p>"
        mock_tags.return_value = ["Rheingas", "Monheim"]

        source_id = create_source(
            SourceCreate(
                name="Batch Source",
                base_url="https://example.org",
                terms_url="https://example.org/terms",
                license_name="cc-by",
                risk_level="green",
                is_enabled=True,
                notes=None,
                last_reviewed_at=None,
            )
        )
        feed_id = create_feed(
            FeedCreate(
                name="Batch Feed",
                url="https://example.org/feed.xml",
                source_id=source_id,
                is_enabled=True,
            )
        )
        article_id = upsert_article(
            ArticleUpsert(
                feed_id=feed_id,
                source_article_id="batch-1",
                source_hash="batch-hash-1",
                title="Batch Titel",
                source_url="https://example.org/batch",
                canonical_url="https://example.org/batch",
                published_at=None,
                author="Autor",
                summary="Summary",
                content_raw="Raw",
                content_rewritten=None,
                image_urls_json=None,
                press_contact=None,
                source_name_snapshot="Batch Source",
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
                word_count=1,
                status="rewrite",
                meta_json="{}",
            )
        )
        self.client.post("/admin/login", data={"username": "admin", "password": "secret"}, follow_redirects=True)
        res = self.client.post("/admin/rewrite/run", data={"max_jobs": "10"}, follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        article = get_article_by_id(article_id)
        self.assertIsNotNone(article)
        self.assertEqual(article.get("status"), "approved")
        self.assertIn("generated_tags", article.get("meta_json", ""))

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
