"""Einteilung der Blogbeiträge für die Bildbereinigung (tools/wp_cleanup.py)."""
import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "wp_cleanup", Path(__file__).resolve().parents[2] / "tools" / "wp_cleanup.py"
)
wp_cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wp_cleanup)
classify = wp_cleanup.classify


def post(pid, status="publish", date="2026-06-01T09:00:00", tool=True, featured=0):
    html = '<p class="article-attribution"><em>Quelle</em></p>' if tool else "<p>eigener text</p>"
    return {"id": pid, "status": status, "date": date, "title": {"rendered": f"Post {pid}"},
            "link": f"https://blog/p/{pid}", "featured_media": featured, "categories": [1],
            "content": {"raw": html}}


def media(mid, parent=0, caption=""):
    return {"id": mid, "date": "2026-06-01T09:00:00", "source_url": f"https://blog/u/{mid}.jpg",
            "post": parent, "caption": {"raw": caption}}


class TestPostGroups(unittest.TestCase):
    def test_attribution_block_splits_tool_posts_from_own_posts(self):
        g = classify([post(1), post(2, status="future"), post(3, tool=False, date="2024-01-01T00:00:00")], [])
        self.assertEqual([r["id"] for r in g["b"]], [1])
        self.assertEqual([r["id"] for r in g["a"]], [2])
        self.assertEqual([r["id"] for r in g["keep"]], [3])

    def test_own_posts_from_this_year_and_unpublished_ones_go_to_review(self):
        g = classify([post(1, tool=False), post(2, tool=False, status="draft", date="2023-01-01T00:00:00")], [])
        self.assertEqual({r["id"] for r in g["c"]}, {1, 2})

    def test_review_row_flags_a_foreign_featured_image(self):
        g = classify([post(1, tool=False, featured=10), post(2, tool=False, featured=11)],
                     [media(10, caption="Quelle: https://presseportal.de/x"), media(11, caption="eigenes Foto")])
        flags = {r["id"]: r["bild_fremd"] for r in g["c"]}
        self.assertEqual(flags, {1: "ja", 2: "nein"})


class TestMediaGroups(unittest.TestCase):
    def test_featured_image_of_a_tool_post_is_deleted(self):
        g = classify([post(1, featured=10)], [media(10, parent=1)])
        self.assertEqual([r["id"] for r in g["m"]], [10])

    def test_orphan_with_source_caption_is_deleted(self):
        g = classify([post(1, tool=False, date="2024-01-01T00:00:00")],
                     [media(10, parent=999, caption="Quelle: https://x")])
        self.assertEqual([r["id"] for r in g["m"]], [10])

    def test_orphan_without_source_caption_stays(self):
        g = classify([], [media(10, parent=999, caption="Urlaubsfoto")])
        self.assertEqual(g["m"], [])

    def test_image_shared_with_a_kept_post_is_never_deleted(self):
        """Presseportal-Bilder hingen an gelöschten und an bleibenden Beiträgen zugleich."""
        g = classify([post(1, featured=10), post(2, tool=False, date="2024-01-01T00:00:00", featured=10)],
                     [media(10, parent=1)])
        self.assertEqual(g["m"], [])
        self.assertEqual([r["id"] for r in g["shared"]], [10])

    def test_own_image_on_a_kept_post_is_untouched(self):
        g = classify([post(1, tool=False, date="2024-01-01T00:00:00", featured=10)], [media(10, parent=1)])
        self.assertEqual(g["m"], [])
        self.assertEqual(g["shared"], [])


if __name__ == "__main__":
    unittest.main()
