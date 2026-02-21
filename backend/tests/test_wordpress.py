import os
import unittest
from unittest.mock import patch

from backend.app import config as config_module
from backend.app.wordpress import publish_article_draft


class TestWordpressPublish(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["WORDPRESS_BASE_URL"] = "https://example.org"
        os.environ["WORDPRESS_USERNAME"] = "wp-user"
        os.environ["WORDPRESS_APP_PASSWORD"] = "wp-pass"
        config_module.get_settings.cache_clear()

    def tearDown(self) -> None:
        for key in ("WORDPRESS_BASE_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD"):
            os.environ.pop(key, None)
        config_module.get_settings.cache_clear()

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_sets_featured_media_when_selected_image_exists(self, mock_wp_request, mock_upload_media) -> None:
        mock_upload_media.return_value = 456
        mock_wp_request.return_value = {"id": 321, "link": "https://example.org/?p=321"}

        article = {
            "title": "Testartikel",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"image_review":{"selected_url":"https://example.com/image.jpg"}}',
        }
        post_id, post_url = publish_article_draft(article)

        self.assertEqual(post_id, 321)
        self.assertIn("?p=321", post_url or "")
        self.assertTrue(mock_upload_media.called)
        payload = mock_wp_request.call_args.kwargs["payload"]
        self.assertEqual(payload.get("featured_media"), 456)
        self.assertIn("<h3>Quelle</h3>", payload.get("content", ""))
        self.assertIn("Originalartikel", payload.get("content", ""))
        self.assertEqual(payload.get("excerpt"), "Inhalt")

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_without_selected_image_has_no_featured_media(self, mock_wp_request, mock_upload_media) -> None:
        mock_wp_request.return_value = {"id": 654, "link": "https://example.org/?p=654"}

        article = {
            "title": "Testartikel",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": "{}",
        }
        post_id, _ = publish_article_draft(article)

        self.assertEqual(post_id, 654)
        self.assertFalse(mock_upload_media.called)
        payload = mock_wp_request.call_args.kwargs["payload"]
        self.assertNotIn("featured_media", payload)
        self.assertIn("<p>Inhalt</p>", payload.get("content", ""))

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_strips_feed_header_and_press_contact(self, mock_wp_request, mock_upload_media) -> None:
        mock_wp_request.return_value = {"id": 100, "link": "https://example.org/?p=100"}
        article = {
            "title": "Header Test",
            "content_raw": "21.02.2026 10:00\nFirma GmbH\n(ots)\nDas ist der eigentliche Text.\nPressekontakt: Test Person",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": "{}",
        }
        publish_article_draft(article)
        payload = mock_wp_request.call_args.kwargs["payload"]
        content = payload.get("content", "")
        self.assertNotIn("Firma GmbH", content)
        self.assertNotIn("Pressekontakt", content)
        self.assertIn("eigentliche Text", content)

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_resolves_and_sets_tags(self, mock_wp_request, mock_upload_media) -> None:
        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "")
            if method == "GET" and endpoint.startswith("tags?search="):
                if "Rheingas" in endpoint:
                    return [{"id": 11, "name": "Rheingas"}]
                return []
            if method == "POST" and endpoint == "tags":
                name = (kwargs.get("payload") or {}).get("name")
                if name == "Gasflasche":
                    return {"id": 12, "name": "Gasflasche"}
                return {"id": 13, "name": str(name)}
            if method == "POST" and endpoint == "posts":
                return {"id": 900, "link": "https://example.org/?p=900"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        article = {
            "title": "Tag Test",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"generated_tags":["Rheingas","Gasflasche"]}',
        }
        post_id, _ = publish_article_draft(article)
        self.assertEqual(post_id, 900)
        post_calls = [call for call in mock_wp_request.call_args_list if call.kwargs.get("endpoint") == "posts"]
        self.assertEqual(len(post_calls), 1)
        payload = post_calls[0].kwargs.get("payload", {})
        self.assertEqual(payload.get("tags"), [11, 12])


if __name__ == "__main__":
    unittest.main()
