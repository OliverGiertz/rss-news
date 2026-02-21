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


if __name__ == "__main__":
    unittest.main()
