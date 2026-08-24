"""Tests for the editorial sign-off gate (Art. 50 Abs. 4 KI-VO).

The gate exists so that no AI-rewritten article reaches WordPress before a
person read it. These tests pin the two properties that carry the legal weight:
nothing gets published without a stamp, and the stamp records who and when.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app import pipeline as pipeline_module
from backend.app.admin_ui import _safe_admin_redirect, _sanitize_preview_html
from backend.app.db import init_db
from backend.app.main import app
from backend.app.publisher import _can_publish
from backend.app.repositories import (
    ArticleUpsert,
    FeedCreate,
    SourceCreate,
    create_feed,
    create_source,
    get_article_by_id,
    upsert_article,
)
from backend.app.workflow import internal_to_ui_status, ui_to_internal_status

LONG_TEXT = "<p>" + " ".join(["Wort"] * 400) + "</p>"


class EditorialReviewTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "editorial.db")
        os.environ["APP_ADMIN_USERNAME"] = "admin"
        os.environ["APP_ADMIN_PASSWORD"] = "secret"
        config_module.get_settings.cache_clear()
        init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        for key in ("APP_DB_PATH", "APP_ADMIN_USERNAME", "APP_ADMIN_PASSWORD"):
            os.environ.pop(key, None)
        self.tmp_dir.cleanup()

    def _create_article(self, *, with_image: bool = True, status: str = "new", rewritten: str | None = None) -> int:
        source_id = create_source(
            SourceCreate(
                name="Editorial Source",
                base_url="https://example.org",
                terms_url="https://example.org/terms",
                license_name="cc-by",
                risk_level="green",
                is_enabled=True,
                notes=None,
                last_reviewed_at="2026-08-01T00:00:00Z",
            )
        )
        feed_id = create_feed(
            FeedCreate(
                name="Editorial Feed",
                url="https://example.org/feed.xml",
                source_id=source_id,
                is_enabled=True,
            )
        )
        meta: dict = {}
        if with_image:
            meta["image_review"] = {"selected_url": "https://example.org/bild.jpg"}

        return upsert_article(
            ArticleUpsert(
                feed_id=feed_id,
                source_article_id="ed-1",
                source_hash="hash-ed-1",
                title="Artikel zur Freigabe",
                source_url="https://example.org/artikel-1",
                canonical_url=None,
                published_at="2026-08-20T08:00:00Z",
                author="Redaktion",
                summary="Zusammenfassung",
                content_raw=LONG_TEXT,
                content_rewritten=rewritten,
                image_urls_json=json.dumps(["https://example.org/bild.jpg"]),
                press_contact=None,
                source_name_snapshot="Editorial Source",
                source_terms_url_snapshot="https://example.org/terms",
                source_license_name_snapshot="cc-by",
                legal_checked=True,
                legal_checked_at="2026-08-20T08:00:00Z",
                legal_note=None,
                wp_post_id=None,
                wp_post_url=None,
                publish_attempts=0,
                publish_last_error=None,
                published_to_wp_at=None,
                word_count=0,
                status=status,
                meta_json=json.dumps(meta, ensure_ascii=False),
            )
        )


class TestStatusModel(unittest.TestCase):
    def test_pending_review_maps_to_freigabe(self) -> None:
        self.assertEqual(internal_to_ui_status("pending_review"), "freigabe")
        self.assertEqual(ui_to_internal_status("freigabe"), "pending_review")

    def test_existing_status_mapping_unchanged(self) -> None:
        self.assertEqual(internal_to_ui_status("approved"), "publish")
        self.assertEqual(ui_to_internal_status("publish"), "approved")


class TestRewriteStopsAtGate(EditorialReviewTestBase):
    def test_rewrite_without_draft_parks_article_in_review_queue(self) -> None:
        article_id = self._create_article()
        article = get_article_by_id(article_id)

        with patch.object(pipeline_module, "rewrite_article_text", return_value=LONG_TEXT), \
             patch.object(pipeline_module, "generate_article_tags", return_value=["Camping"]), \
             patch.object(pipeline_module, "publish_article_draft") as wp_draft, \
             patch.object(pipeline_module, "reserve_publish_slot") as reserve:
            wp_post_id, wp_post_url = pipeline_module._do_rewrite_and_draft(article, create_wp_draft=False)

        self.assertIsNone(wp_post_id)
        self.assertIsNone(wp_post_url)
        wp_draft.assert_not_called()
        reserve.assert_not_called()

        stored = get_article_by_id(article_id)
        self.assertEqual(stored["status"], "pending_review")
        self.assertIsNone(stored["editorial_review_at"])
        self.assertIsNone(stored["scheduled_publish_at"])
        self.assertTrue(stored["content_rewritten"])


class TestPipelineGate(EditorialReviewTestBase):
    def test_high_scoring_article_waits_for_approval(self) -> None:
        """The full pipeline path: high score, but still no WordPress post."""
        from backend.app import telegram_bot

        article_id = self._create_article()
        article = get_article_by_id(article_id)
        stats = pipeline_module.PipelineStats()
        settings = config_module.get_settings()

        with patch.object(pipeline_module, "score_article_relevance", return_value={"score": 95, "reason": "passt", "topics": []}), \
             patch.object(pipeline_module, "rewrite_article_text", return_value=LONG_TEXT), \
             patch.object(pipeline_module, "generate_article_tags", return_value=["Camping"]), \
             patch.object(pipeline_module, "publish_article_draft") as wp_draft, \
             patch.object(pipeline_module, "reserve_publish_slot") as reserve, \
             patch.object(telegram_bot, "notify_pending_review") as notify_pending, \
             patch.object(telegram_bot, "notify_new_draft") as notify_draft:
            pipeline_module._process_article(article, stats, settings)

        wp_draft.assert_not_called()
        reserve.assert_not_called()
        notify_draft.assert_not_called()
        notify_pending.assert_called_once()
        self.assertEqual(stats.pending_review, 1)
        self.assertEqual(stats.drafts_created, 0)

        stored = get_article_by_id(article_id)
        self.assertEqual(stored["status"], "pending_review")
        self.assertIsNone(stored["wp_post_id"])


class TestApproveArticle(EditorialReviewTestBase):
    def test_approval_stamps_reviewer_and_publishes(self) -> None:
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        with patch.object(pipeline_module, "reserve_publish_slot", return_value="2026-08-25 09:00:00") as reserve, \
             patch.object(pipeline_module, "publish_article_draft", return_value=(4711, "https://blog/p/4711")) as wp_draft:
            result = pipeline_module.approve_article(article_id, actor="oliver", note="gelesen und geprüft")

        reserve.assert_called_once_with(article_id)
        wp_draft.assert_called_once()
        self.assertEqual(result["wp_post_id"], 4711)
        self.assertEqual(result["scheduled_publish_at"], "2026-08-25 09:00:00")

        stored = get_article_by_id(article_id)
        self.assertEqual(stored["status"], "approved")
        self.assertEqual(stored["editorial_review_by"], "oliver")
        self.assertEqual(stored["editorial_review_note"], "gelesen und geprüft")
        self.assertTrue(stored["editorial_review_at"])
        self.assertEqual(stored["wp_post_id"], 4711)

        # The sign-off is also in the audit trail.
        events = json.loads(stored["meta_json"]).get("review_events", [])
        self.assertTrue(any(e.get("event") == "editorial_review" for e in events))

    def test_approval_refuses_article_without_image(self) -> None:
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT, with_image=False)

        with patch.object(pipeline_module, "publish_article_draft") as wp_draft:
            with self.assertRaises(ValueError):
                pipeline_module.approve_article(article_id, actor="oliver")

        wp_draft.assert_not_called()
        stored = get_article_by_id(article_id)
        self.assertIsNone(stored["editorial_review_at"])
        self.assertEqual(stored["status"], "pending_review")

    def test_approval_refuses_article_without_rewrite(self) -> None:
        article_id = self._create_article(status="pending_review", rewritten=None)

        with self.assertRaises(ValueError):
            pipeline_module.approve_article(article_id, actor="oliver")

        self.assertIsNone(get_article_by_id(article_id)["editorial_review_at"])

    def test_wordpress_failure_returns_article_to_the_queue(self) -> None:
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        with patch.object(pipeline_module, "reserve_publish_slot", return_value="2026-08-25 09:00:00"), \
             patch.object(pipeline_module, "publish_article_draft", side_effect=RuntimeError("WP 401")):
            with self.assertRaises(RuntimeError):
                pipeline_module.approve_article(article_id, actor="oliver")

        stored = get_article_by_id(article_id)
        self.assertEqual(stored["status"], "pending_review")
        self.assertIsNone(stored["scheduled_publish_at"])
        # The review itself happened, so the stamp stays: retrying is enough.
        self.assertTrue(stored["editorial_review_at"])


class TestAdminUiApproval(EditorialReviewTestBase):
    def _login(self) -> None:
        self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=False,
        )

    def test_detail_page_offers_approval_button(self) -> None:
        self._login()
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        page = self.client.get(f"/admin/articles/{article_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Redaktionelle Freigabe", page.text)
        self.assertIn(f"/admin/articles/{article_id}/approve", page.text)

    def test_approve_route_stamps_and_schedules(self) -> None:
        self._login()
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        with patch.object(pipeline_module, "reserve_publish_slot", return_value="2026-08-25 09:00:00"), \
             patch.object(pipeline_module, "publish_article_draft", return_value=(99, "https://blog/p/99")):
            response = self.client.post(
                f"/admin/articles/{article_id}/approve",
                data={"note": "geprüft"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        stored = get_article_by_id(article_id)
        self.assertEqual(stored["status"], "approved")
        self.assertEqual(stored["editorial_review_by"], "admin")
        self.assertTrue(stored["editorial_review_at"])

    def test_manual_transition_to_publish_also_stamps(self) -> None:
        """The status dropdown must not be a way around the gate."""
        self._login()
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        with patch.object(pipeline_module, "reserve_publish_slot", return_value="2026-08-25 09:00:00"), \
             patch.object(pipeline_module, "publish_article_draft", return_value=(100, "https://blog/p/100")):
            self.client.post(
                f"/admin/articles/{article_id}/transition",
                data={"target_status": "publish", "note": ""},
                follow_redirects=False,
            )

        stored = get_article_by_id(article_id)
        self.assertEqual(stored["status"], "approved")
        self.assertTrue(stored["editorial_review_at"])


class TestStampFollowsTheText(EditorialReviewTestBase):
    def test_rewrite_after_approval_drops_the_stale_stamp(self) -> None:
        """A stamp says a person read *this* text. New text, new sign-off."""
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        with patch.object(pipeline_module, "reserve_publish_slot", return_value="2026-08-25 09:00:00"), \
             patch.object(pipeline_module, "publish_article_draft", return_value=(1, "https://blog/p/1")):
            pipeline_module.approve_article(article_id, actor="oliver")
        self.assertTrue(get_article_by_id(article_id)["editorial_review_at"])

        article = get_article_by_id(article_id)
        with patch.object(pipeline_module, "rewrite_article_text", return_value=LONG_TEXT + "<p>neu</p>"), \
             patch.object(pipeline_module, "generate_article_tags", return_value=[]):
            pipeline_module._do_rewrite_and_draft(article, create_wp_draft=False)

        stored = get_article_by_id(article_id)
        self.assertEqual(stored["status"], "pending_review")
        self.assertIsNone(stored["editorial_review_at"])
        self.assertIsNone(stored["editorial_review_by"])


class TestDashboardSurfacesQueue(EditorialReviewTestBase):
    def test_dashboard_shows_pending_review_banner(self) -> None:
        self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=False,
        )
        self._create_article(status="pending_review", rewritten=LONG_TEXT)

        page = self.client.get("/admin/dashboard")
        self.assertEqual(page.status_code, 200)
        self.assertIn("warten auf deine redaktionelle Freigabe", page.text)
        self.assertIn('href="/admin/freigabe"', page.text)


class TestPreviewSanitizer(unittest.TestCase):
    """The rewrite text is model output over scraped pages — render it filtered."""

    def test_keeps_article_markup(self) -> None:
        html = _sanitize_preview_html("<h2>Titel</h2><p>Text mit <strong>Betonung</strong></p><ul><li>Punkt</li></ul>")
        self.assertIn("<h2>Titel</h2>", html)
        self.assertIn("<strong>Betonung</strong>", html)
        self.assertIn("<li>Punkt</li>", html)

    def test_drops_scripts_and_their_content(self) -> None:
        html = _sanitize_preview_html('<p>Text</p><script>alert("x")</script>')
        self.assertIn("<p>Text</p>", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("alert", html)

    def test_strips_event_handlers_and_unknown_tags(self) -> None:
        html = _sanitize_preview_html('<p onclick="evil()">Hallo</p><iframe src="x"></iframe>')
        self.assertNotIn("onclick", html)
        self.assertNotIn("<iframe", html)
        self.assertIn("Hallo", html)

    def test_keeps_only_http_links(self) -> None:
        html = _sanitize_preview_html('<p><a href="javascript:evil()">bad</a> <a href="https://ok.de">gut</a></p>')
        self.assertNotIn("javascript:", html)
        self.assertIn('href="https://ok.de"', html)

    def test_plain_text_gets_a_paragraph(self) -> None:
        self.assertEqual(_sanitize_preview_html("Nur Text"), "<p>Nur Text</p>")

    def test_empty_input(self) -> None:
        self.assertEqual(_sanitize_preview_html(None), "")
        self.assertEqual(_sanitize_preview_html("   "), "")


class TestSafeRedirect(unittest.TestCase):
    def test_accepts_admin_paths(self) -> None:
        self.assertEqual(_safe_admin_redirect("/admin/freigabe", "/fallback"), "/admin/freigabe")

    def test_rejects_foreign_targets(self) -> None:
        for bad in ("https://evil.example/x", "//evil.example", "/admin//evil.example", "", None):
            self.assertEqual(_safe_admin_redirect(bad, "/fallback"), "/fallback")


class TestReviewQueuePage(EditorialReviewTestBase):
    def _login(self) -> None:
        self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=False,
        )

    def test_queue_lists_pending_articles_with_all_three_actions(self) -> None:
        self._login()
        article_id = self._create_article(status="pending_review", rewritten="<h2>Kapitel</h2><p>Inhalt hier</p>")

        page = self.client.get("/admin/freigabe")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Artikel zur Freigabe", page.text)      # Titel
        self.assertIn("Inhalt hier", page.text)               # lesbarer Text
        self.assertIn(f"/admin/articles/{article_id}/approve", page.text)
        self.assertIn(f"/admin/articles/{article_id}/rewrite-run", page.text)
        self.assertIn(f"/admin/articles/{article_id}/transition", page.text)

    def test_queue_hides_articles_in_other_states(self) -> None:
        self._login()
        self._create_article(status="published", rewritten=LONG_TEXT)

        page = self.client.get("/admin/freigabe")
        self.assertIn("Nichts zu prüfen", page.text)

    def test_approving_from_queue_returns_to_the_queue(self) -> None:
        self._login()
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        with patch.object(pipeline_module, "reserve_publish_slot", return_value="2026-08-25 09:00:00"), \
             patch.object(pipeline_module, "publish_article_draft", return_value=(7, "https://blog/p/7")):
            response = self.client.post(
                f"/admin/articles/{article_id}/approve",
                data={"note": "", "redirect_to": "/admin/freigabe"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("/admin/freigabe?"))
        self.assertEqual(get_article_by_id(article_id)["status"], "approved")

    def test_discarding_from_queue_returns_to_the_queue(self) -> None:
        self._login()
        article_id = self._create_article(status="pending_review", rewritten=LONG_TEXT)

        response = self.client.post(
            f"/admin/articles/{article_id}/transition",
            data={"target_status": "close", "note": "", "redirect_to": "/admin/freigabe"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("/admin/freigabe?"))
        self.assertEqual(get_article_by_id(article_id)["status"], "error")

    def test_queue_requires_login(self) -> None:
        response = self.client.get("/admin/freigabe", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("/admin/login", response.headers["location"])


class TestLegacyArticlesKeepPublishing(EditorialReviewTestBase):
    def test_approved_article_without_stamp_still_publishes(self) -> None:
        """Altbestand: approved before the gate existed, must not get stuck."""
        article_id = self._create_article(status="approved", rewritten=LONG_TEXT)
        article = get_article_by_id(article_id)
        self.assertIsNone(article["editorial_review_at"])

        allowed, reason = _can_publish(article)
        self.assertTrue(allowed, msg=reason)


if __name__ == "__main__":
    unittest.main()
