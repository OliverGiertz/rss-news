"""Tests for choosing a publish date at approval time.

The rule the whole feature rests on: pulling an article forward never moves
another article. A wanted time that is taken becomes a Sondertermin between two
raster times instead of pushing the queue along.
"""
import os
import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch

from backend.app import config as config_module
from backend.app import scheduler as scheduler_module
from backend.app.db import get_conn, init_db
from backend.app.scheduler import plan_publish_slot, set_publish_slot

# Ein Mittwoch, damit die Wochentagsausgabe stabil ist.
FIXED_TODAY = date(2026, 9, 9)


class SlotPlannerTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = os.path.join(self.tmp_dir.name, "planner.db")
        os.environ["PIPELINE_PUBLISH_HOURS"] = "9,12,15,18"
        os.environ["PIPELINE_PUBLISH_START_HOUR"] = "9"
        os.environ["PIPELINE_PUBLISH_END_HOUR"] = "19"
        os.environ.pop("WORDPRESS_BASE_URL", None)
        config_module.get_settings.cache_clear()
        init_db()

        # WordPress is not part of these tests; an empty answer keeps them local.
        self._wp_patch = patch.object(scheduler_module, "_fetch_wp_future_datetimes", return_value=[])
        self._wp_patch.start()

    def tearDown(self) -> None:
        self._wp_patch.stop()
        config_module.get_settings.cache_clear()
        for key in (
            "APP_DB_PATH",
            "PIPELINE_PUBLISH_HOURS",
            "PIPELINE_PUBLISH_START_HOUR",
            "PIPELINE_PUBLISH_END_HOUR",
        ):
            os.environ.pop(key, None)
        self.tmp_dir.cleanup()

    def _article(self, scheduled_at: str | None = None) -> int:
        self._seq = getattr(self, "_seq", 0) + 1
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO articles (title, source_url, status, scheduled_publish_at)
                VALUES (?, ?, 'approved', ?)
                """,
                (f"Artikel {self._seq}", f"https://example.org/a/{self._seq}", scheduled_at),
            )
            return int(cur.lastrowid)

    def _slot_of(self, article_id: int) -> str | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT scheduled_publish_at FROM articles WHERE id = ?", (article_id,)
            ).fetchone()
        return row["scheduled_publish_at"] if row else None

    def _at(self, now: datetime):
        """Freeze the clock so slot arithmetic is testable."""
        return patch.multiple(
            scheduler_module,
            _today_cet=lambda: now.date(),
            _now_cet=lambda: now,
        )


class TestPresets(SlotPlannerTestBase):
    def test_today_takes_the_next_free_raster_time(self) -> None:
        with self._at(datetime(2026, 9, 9, 10, 0)):
            plan = plan_publish_slot("today")
        self.assertEqual(plan.iso, "2026-09-09T12:00:00")
        self.assertEqual(plan.kind, "raster")
        self.assertFalse(plan.publish_now)

    def test_today_skips_raster_times_that_are_too_close(self) -> None:
        """11:50 is not a plan for the 12:00 slot, it is a scramble."""
        with self._at(datetime(2026, 9, 9, 11, 50)):
            plan = plan_publish_slot("today")
        self.assertEqual(plan.iso, "2026-09-09T15:00:00")

    def test_today_falls_back_to_a_sondertermin_between_raster_times(self) -> None:
        for hour in (9, 12, 15, 18):
            self._article(f"2026-09-09T{hour:02d}:00:00")

        with self._at(datetime(2026, 9, 9, 8, 0)):
            plan = plan_publish_slot("today")

        self.assertEqual(plan.kind, "extra")
        self.assertEqual(plan.iso, "2026-09-09T10:30:00")
        self.assertIn("Sondertermin", plan.note)

    def test_sondertermin_keeps_its_distance_from_both_neighbours(self) -> None:
        """A half hour next to a raster time would collide, 10:30 does not."""
        for hour in (9, 12, 15, 18):
            self._article(f"2026-09-09T{hour:02d}:00:00")
        self._article("2026-09-09T10:30:00")

        with self._at(datetime(2026, 9, 9, 8, 0)):
            plan = plan_publish_slot("today")

        self.assertEqual(plan.iso, "2026-09-09T13:30:00")

    def test_today_publishes_now_when_the_day_is_over(self) -> None:
        with self._at(datetime(2026, 9, 9, 20, 30)):
            plan = plan_publish_slot("today")
        self.assertTrue(plan.publish_now)
        self.assertEqual(plan.kind, "now")
        self.assertIn("sofort", plan.note)

    def test_tomorrow_takes_the_first_raster_time(self) -> None:
        with self._at(datetime(2026, 9, 9, 20, 30)):
            plan = plan_publish_slot("tomorrow")
        self.assertEqual(plan.iso, "2026-09-10T09:00:00")

    def test_now_publishes_immediately(self) -> None:
        with self._at(datetime(2026, 9, 9, 14, 12)):
            plan = plan_publish_slot("now")
        self.assertTrue(plan.publish_now)
        self.assertEqual(plan.iso, "2026-09-09T14:13:00")


class TestCustomDate(SlotPlannerTestBase):
    def test_custom_time_is_taken_verbatim(self) -> None:
        with self._at(datetime(2026, 9, 9, 10, 0)):
            plan = plan_publish_slot("custom", "2026-09-24T16:45")
        self.assertEqual(plan.iso, "2026-09-24T16:45:00")
        self.assertEqual(plan.kind, "extra")

    def test_custom_time_on_the_grid_counts_as_a_raster_slot(self) -> None:
        with self._at(datetime(2026, 9, 9, 10, 0)):
            plan = plan_publish_slot("custom", "2026-09-24T15:00")
        self.assertEqual(plan.kind, "raster")

    def test_custom_time_in_the_past_publishes_now(self) -> None:
        with self._at(datetime(2026, 9, 9, 10, 0)):
            plan = plan_publish_slot("custom", "2026-09-01T09:00")
        self.assertTrue(plan.publish_now)
        self.assertIn("Vergangenheit", plan.note)

    def test_exact_collision_is_nudged_and_flagged(self) -> None:
        self._article("2026-09-24T15:00:00")
        with self._at(datetime(2026, 9, 9, 10, 0)):
            plan = plan_publish_slot("custom", "2026-09-24T15:00")
        self.assertEqual(plan.iso, "2026-09-24T15:05:00")
        self.assertIn("dicht", plan.note)

    def test_unreadable_date_is_rejected(self) -> None:
        with self._at(datetime(2026, 9, 9, 10, 0)):
            with self.assertRaises(ValueError):
                plan_publish_slot("custom", "irgendwann")


class TestNothingElseMoves(SlotPlannerTestBase):
    def test_pulling_an_article_forward_leaves_every_other_date_alone(self) -> None:
        others = [self._article(f"2026-09-{day:02d}T09:00:00") for day in (10, 11, 12)]
        mover = self._article("2026-11-13T12:00:00")
        before = {aid: self._slot_of(aid) for aid in others}

        with self._at(datetime(2026, 9, 9, 8, 0)):
            plan = set_publish_slot(mover, mode="today", actor="oliver")

        self.assertEqual(plan.iso, "2026-09-09T09:00:00")
        self.assertEqual(self._slot_of(mover), "2026-09-09T09:00:00")
        self.assertEqual({aid: self._slot_of(aid) for aid in others}, before)

    def test_the_vacated_slot_is_offered_to_the_next_article(self) -> None:
        mover = self._article("2026-09-10T09:00:00")
        self._article("2026-09-10T12:00:00")
        self._article("2026-09-10T15:00:00")
        self._article("2026-09-10T18:00:00")
        newcomer = self._article()

        with self._at(datetime(2026, 9, 9, 8, 0)):
            set_publish_slot(mover, mode="today", actor="oliver")
            plan = set_publish_slot(newcomer, mode="auto")

        self.assertEqual(plan.iso, "2026-09-10T09:00:00")

    def test_a_sondertermin_does_not_block_the_neighbouring_raster_times(self) -> None:
        self._article("2026-09-10T10:30:00")
        newcomer = self._article()

        with self._at(datetime(2026, 9, 9, 8, 0)):
            plan = set_publish_slot(newcomer, mode="auto")

        self.assertEqual(plan.iso, "2026-09-10T09:00:00")

    def test_auto_keeps_a_slot_the_article_already_has(self) -> None:
        article_id = self._article("2026-11-13T12:00:00")
        with self._at(datetime(2026, 9, 9, 8, 0)):
            plan = set_publish_slot(article_id, mode="auto", keep_existing=True)
        self.assertEqual(plan.iso, "2026-11-13T12:00:00")

    def test_an_explicit_wish_overrides_an_existing_slot(self) -> None:
        article_id = self._article("2026-11-13T12:00:00")
        with self._at(datetime(2026, 9, 9, 8, 0)):
            plan = set_publish_slot(article_id, mode="tomorrow", keep_existing=True)
        self.assertEqual(plan.iso, "2026-09-10T09:00:00")


class TestScheduleTrail(SlotPlannerTestBase):
    def test_a_hand_picked_date_is_recorded_in_the_article_meta(self) -> None:
        import json

        article_id = self._article()
        with self._at(datetime(2026, 9, 9, 8, 0)):
            set_publish_slot(article_id, mode="today", actor="oliver")

        with get_conn() as conn:
            row = conn.execute("SELECT meta_json FROM articles WHERE id = ?", (article_id,)).fetchone()
        schedule = json.loads(row["meta_json"])["schedule"]

        self.assertTrue(schedule["manual"])
        self.assertEqual(schedule["mode"], "today")
        self.assertEqual(schedule["set_by"], "oliver")

    def test_the_automatic_date_is_not_marked_as_hand_picked(self) -> None:
        import json

        article_id = self._article()
        with self._at(datetime(2026, 9, 9, 8, 0)):
            set_publish_slot(article_id, mode="auto")

        with get_conn() as conn:
            row = conn.execute("SELECT meta_json FROM articles WHERE id = ?", (article_id,)).fetchone()
        self.assertFalse(json.loads(row["meta_json"])["schedule"]["manual"])


class TestUnknownMode(SlotPlannerTestBase):
    def test_an_unknown_wish_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            plan_publish_slot("irgendwann-mal")


if __name__ == "__main__":
    unittest.main()
