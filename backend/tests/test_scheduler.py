import json
import os
import tempfile
import unittest
from unittest.mock import patch

from backend.app import config as config_module
from backend.app.db import get_conn, init_db
from backend.app.scheduler import _fetch_wp_occupied_slots, _preferred_hours, reserve_publish_slot


class _MockResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestScheduler(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = os.path.join(self.tmp_dir.name, "scheduler.db")
        os.environ["WORDPRESS_BASE_URL"] = "https://example.org"
        os.environ["WORDPRESS_USERNAME"] = "wp-user"
        os.environ["WORDPRESS_APP_PASSWORD"] = "wp-pass"
        config_module.get_settings.cache_clear()
        init_db()

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        for key in (
            "APP_DB_PATH",
            "WORDPRESS_BASE_URL",
            "WORDPRESS_USERNAME",
            "WORDPRESS_APP_PASSWORD",
            "PIPELINE_PUBLISH_HOURS",
            "PIPELINE_PUBLISH_START_HOUR",
            "PIPELINE_PUBLISH_END_HOUR",
            "PIPELINE_PUBLISH_MIN_GAP_HOURS",
        ):
            os.environ.pop(key, None)
        self.tmp_dir.cleanup()

    def _insert_article(self, idx: int) -> int:
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO articles (title, source_url, status)
                VALUES (?, ?, 'approved')
                """,
                (f"Artikel {idx}", f"https://example.org/article/{idx}"),
            )
            return int(cur.lastrowid)

    def test_preferred_hours_expand_with_gap_and_window(self) -> None:
        self.assertEqual(_preferred_hours(), [9, 14, 17])

    @patch("backend.app.scheduler._today_cet")
    @patch("backend.app.scheduler._fetch_wp_occupied_slots", return_value=set())
    def test_reserve_publish_slot_uses_overflow_hours(self, _mock_wp, mock_today) -> None:
        from datetime import date

        mock_today.return_value = date(2026, 7, 24)
        article_ids = [self._insert_article(idx) for idx in range(1, 5)]

        slots = []
        for article_id in article_ids:
            reserve_publish_slot(article_id)
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT scheduled_publish_at FROM articles WHERE id = ?",
                    (article_id,),
                ).fetchone()
            slots.append(row["scheduled_publish_at"])

        self.assertEqual(
            slots,
            [
                "2026-07-25T09:00:00",
                "2026-07-25T14:00:00",
                "2026-07-25T17:00:00",
                "2026-07-26T09:00:00",
            ],
        )

    @patch("backend.app.scheduler.urllib.request.urlopen")
    def test_fetch_wp_occupied_slots_reads_multiple_pages(self, mock_urlopen) -> None:
        page1 = [{"id": idx, "date": f"2026-08-{(idx % 28) + 1:02d}T09:00:00"} for idx in range(1, 101)]
        page2 = [{"id": 101, "date": "2026-10-31T17:00:00"}]
        mock_urlopen.side_effect = [_MockResponse(page1), _MockResponse(page2)]

        occupied = _fetch_wp_occupied_slots()

        self.assertIn(("2026-10-31", 17), occupied)
        self.assertEqual(len(occupied), 29)


if __name__ == "__main__":
    unittest.main()
