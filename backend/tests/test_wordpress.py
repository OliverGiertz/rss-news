import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import config as config_module
from backend.app import wordpress as wordpress_module
from backend.app.db import init_db
from backend.app.wordpress import publish_article_draft


class TestWordpressPublish(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["WORDPRESS_BASE_URL"] = "https://example.org"
        os.environ["WORDPRESS_USERNAME"] = "wp-user"
        os.environ["WORDPRESS_APP_PASSWORD"] = "wp-pass"
        # Publishing records tag proposals, so it needs a database of its own -
        # otherwise the tests would write into the live one.
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "test.db")
        config_module.get_settings.cache_clear()
        init_db()
        # The category lookup is cached for the process lifetime; without this
        # one test would resolve a slug that the next one expects to be missing.
        wordpress_module._category_id_cache.clear()

    def tearDown(self) -> None:
        for key in (
            "WORDPRESS_BASE_URL",
            "WORDPRESS_USERNAME",
            "WORDPRESS_APP_PASSWORD",
            "APP_DB_PATH",
            "WORDPRESS_MAX_TAGS_PER_POST",
            "WORDPRESS_NEW_TAG_MIN_PROPOSALS",
        ):
            os.environ.pop(key, None)
        config_module.get_settings.cache_clear()
        self.tmp_dir.cleanup()

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
        self.assertIn("<!-- wp:paragraph -->", payload.get("content", ""))
        self.assertIn("<p>Inhalt</p>", payload.get("content", ""))
        self.assertNotIn("excerpt", payload)

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
        self.assertNotIn("Artikeldetails", content)

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_resolves_existing_tags_and_skips_unknown_ones(self, mock_wp_request, mock_upload_media) -> None:
        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "")
            if method == "GET" and endpoint.startswith("tags?search="):
                if "Rheingas" in endpoint:
                    return [{"id": 11, "name": "Rheingas"}]
                return []
            if method == "POST" and endpoint == "posts":
                return {"id": 900, "link": "https://example.org/?p=900"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        article = {
            "id": 1,
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
        # "Gasflasche" was proposed for the first time and is not created yet.
        self.assertEqual(payload.get("tags"), [11])
        self.assertFalse(
            any(c.kwargs.get("method") == "POST" and c.kwargs.get("endpoint") == "tags"
                for c in mock_wp_request.call_args_list)
        )

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_new_tag_is_created_once_enough_articles_proposed_it(self, mock_wp_request, mock_upload_media) -> None:
        created_names: list[str] = []

        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "")
            if method == "GET" and endpoint.startswith("tags?search="):
                return []
            if method == "POST" and endpoint == "tags":
                created_names.append(str((kwargs.get("payload") or {}).get("name")))
                return {"id": 55, "name": "Wintercamping"}
            if method == "POST" and endpoint == "posts":
                return {"id": 910, "link": "https://example.org/?p=910"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request

        def _article(article_id: int) -> dict:
            return {
                "id": article_id,
                "title": f"Artikel {article_id}",
                "content_raw": "Inhalt",
                "source_url": f"https://example.com/source/{article_id}",
                "canonical_url": f"https://example.com/source/{article_id}",
                "meta_json": '{"generated_tags":["Wintercamping"]}',
            }

        for article_id in (1, 2):
            publish_article_draft(_article(article_id))
        self.assertEqual(created_names, [])

        publish_article_draft(_article(3))
        self.assertEqual(created_names, ["Wintercamping"])
        payload = [c for c in mock_wp_request.call_args_list if c.kwargs.get("endpoint") == "posts"][-1].kwargs["payload"]
        self.assertEqual(payload.get("tags"), [55])

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_republishing_the_same_article_does_not_count_twice(self, mock_wp_request, mock_upload_media) -> None:
        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "")
            if method == "GET" and endpoint.startswith("tags?search="):
                return []
            if method == "POST" and endpoint == "tags":
                return {"id": 66, "name": "Solaranlage"}
            if method == "POST":
                return {"id": 920, "link": "https://example.org/?p=920"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        article = {
            "id": 7,
            "title": "Immer wieder derselbe Artikel",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"generated_tags":["Solaranlage"]}',
        }
        for _ in range(4):
            publish_article_draft(article)
        self.assertFalse(
            any(c.kwargs.get("method") == "POST" and c.kwargs.get("endpoint") == "tags"
                for c in mock_wp_request.call_args_list)
        )

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_caps_the_number_of_tags_per_post(self, mock_wp_request, mock_upload_media) -> None:
        looked_up: list[str] = []

        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "")
            if method == "GET" and endpoint.startswith("tags?search="):
                looked_up.append(endpoint)
                return []
            if method == "POST" and endpoint == "posts":
                return {"id": 930, "link": "https://example.org/?p=930"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        names = [f"Tag{i}" for i in range(1, 13)]
        article = {
            "id": 42,
            "title": "Viele Schlagwörter",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"generated_tags":' + str(names).replace("'", '"') + "}",
        }
        publish_article_draft(article)
        self.assertEqual(len(looked_up), 5)

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_tag_lookup_ignores_near_misses(self, mock_wp_request, mock_upload_media) -> None:
        """A search hit that is not the exact name must not be reused.

        Plain substring reuse filed "Camping" under the unrelated existing tag
        "Campingplatz" whenever the exact tag was missing.
        """
        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "")
            if method == "GET" and endpoint.startswith("tags?search="):
                return [{"id": 99, "name": "Campingplatz"}]
            if method == "POST" and endpoint == "posts":
                return {"id": 940, "link": "https://example.org/?p=940"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        article = {
            "id": 5,
            "title": "Naher Treffer",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"generated_tags":["Camping"]}',
        }
        publish_article_draft(article)
        payload = [c for c in mock_wp_request.call_args_list if c.kwargs.get("endpoint") == "posts"][0].kwargs["payload"]
        self.assertNotIn("tags", payload)

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_converts_html_to_wp_blocks_without_html_block(self, mock_wp_request, mock_upload_media) -> None:
        mock_wp_request.return_value = {"id": 111, "link": "https://example.org/?p=111"}
        article = {
            "title": "Block Test",
            "content_rewritten": "<h2>Überschrift</h2><p>Absatz 1</p><ul><li>A</li><li>B</li></ul>",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": "{}",
        }
        publish_article_draft(article)
        payload = mock_wp_request.call_args.kwargs["payload"]
        content = payload.get("content", "")
        self.assertIn("<!-- wp:heading", content)
        self.assertIn("<!-- wp:paragraph -->", content)
        self.assertIn("<!-- wp:list -->", content)
        self.assertNotIn("<!-- wp:html -->", content)

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_sets_category_from_rules(self, mock_wp_request, mock_upload_media) -> None:
        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            method = kwargs.get("method", "")
            if method == "GET" and endpoint.startswith("tags?search="):
                return [{"id": 21, "name": "Kühlbox"}]
            if method == "GET" and endpoint.startswith("categories?slug=ausruestung-tests"):
                return [{"id": 77, "slug": "ausruestung-tests"}]
            if method == "POST" and endpoint == "posts":
                return {"id": 901, "link": "https://example.org/?p=901"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        article = {
            "title": "Dometic CFX5 45 im Test: Top-Kühlbox für unterwegs",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"generated_tags":["Kühlbox"]}',
        }
        post_id, _ = publish_article_draft(article)
        self.assertEqual(post_id, 901)
        payload = [c for c in mock_wp_request.call_args_list if c.kwargs.get("endpoint") == "posts"][0].kwargs["payload"]
        self.assertEqual(payload.get("categories"), [77])

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_omits_category_when_no_rule_matches(self, mock_wp_request, mock_upload_media) -> None:
        def _fake_wp_request(**kwargs):
            if kwargs.get("method") == "POST" and kwargs.get("endpoint") == "posts":
                return {"id": 902, "link": "https://example.org/?p=902"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        article = {
            "title": "Weihnachten 2021",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"generated_tags":[]}',
        }
        publish_article_draft(article)
        payload = [c for c in mock_wp_request.call_args_list if c.kwargs.get("endpoint") == "posts"][0].kwargs["payload"]
        self.assertNotIn("categories", payload)
        self.assertFalse(any("categories?slug=" in (c.kwargs.get("endpoint") or "")
                             for c in mock_wp_request.call_args_list))

    @patch("backend.app.wordpress._upload_featured_media")
    @patch("backend.app.wordpress._wp_request")
    def test_publish_skips_category_when_slug_is_missing_in_wordpress(self, mock_wp_request, mock_upload_media) -> None:
        def _fake_wp_request(**kwargs):
            endpoint = kwargs.get("endpoint", "")
            if kwargs.get("method") == "GET" and endpoint.startswith("categories?slug="):
                return []
            if kwargs.get("method") == "POST" and endpoint == "posts":
                return {"id": 903, "link": "https://example.org/?p=903"}
            return {}

        mock_wp_request.side_effect = _fake_wp_request
        article = {
            "title": "Dometic CFX5 45 im Test: Top-Kühlbox für unterwegs",
            "content_raw": "Inhalt",
            "source_url": "https://example.com/source",
            "canonical_url": "https://example.com/source",
            "meta_json": '{"generated_tags":[]}',
        }
        publish_article_draft(article)
        payload = [c for c in mock_wp_request.call_args_list if c.kwargs.get("endpoint") == "posts"][0].kwargs["payload"]
        self.assertNotIn("categories", payload)


if __name__ == "__main__":
    unittest.main()
