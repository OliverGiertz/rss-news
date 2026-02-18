from datetime import datetime, timezone
import unittest

from backend.app.relevance import article_age_days, article_relevance


class TestRelevance(unittest.TestCase):
    def test_article_age_and_relevance(self) -> None:
        now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(article_age_days("2026-02-18T10:00:00Z", now=now), 0)
        self.assertEqual(article_relevance("2026-02-18T10:00:00Z", now=now), "hoch")

        self.assertEqual(article_age_days("2026-02-14T12:00:00Z", now=now), 4)
        self.assertEqual(article_relevance("2026-02-14T12:00:00Z", now=now), "mittel")

        self.assertEqual(article_relevance("2025-12-01T00:00:00Z", now=now), "alt")
        self.assertEqual(article_relevance(None, now=now), "unbekannt")


if __name__ == "__main__":
    unittest.main()
