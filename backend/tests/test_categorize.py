import unittest

from backend.app.categorize import CATEGORY_SLUGS, category_slug, classify


class TestCategorize(unittest.TestCase):
    def test_tags_decide_the_category(self) -> None:
        self.assertEqual(
            classify("Neuer Platz am Wasser", ["Campingplatz", "5-Sterne-Campingplätze"]),
            "campingplaetze",
        )
        self.assertEqual(classify("Unterwegs im Norden", ["Nordsee", "Niedersachsen"]), "reiseziele")
        self.assertEqual(classify("Update vom Van", ["Wohnmobil", "Truma", "Solar"]), "fahrzeug-technik")

    def test_title_alone_is_enough(self) -> None:
        self.assertEqual(classify("Dometic CFX5 45 im Test: Top-Kühlbox", []), "ausruestung-tests")
        self.assertEqual(classify("Führerscheine müssen getauscht werden", []), "recht-vorschriften")

    def test_discount_signal_beats_the_product_topic(self) -> None:
        # Without the override this lands in "Ausruestung & Tests", because the
        # product tags outnumber the single discount signal.
        self.assertEqual(
            classify("Campingzelte bei Amazon im Sale: bis zu 55 %", ["Zelte", "Schlafsack", "Rabatt"]),
            "angebote-rabatte",
        )

    def test_keywords_respect_word_boundaries(self) -> None:
        # "klage" must not match the city name "Klagenfurt" - plain substring
        # matching filed this campsite opening under "Recht & Vorschriften".
        self.assertEqual(
            classify("Falkensteiner Camping Wörthersee startet in die erste Saison",
                     ["Campingplatz", "Klagenfurt", "Saisonstart"]),
            "campingplaetze",
        )

    def test_compound_nouns_only_match_with_opt_in(self) -> None:
        # "campingplatz*" is marked as a compound, so this still matches.
        self.assertEqual(classify("Was Campingplatzbetreiber jetzt planen", []), "campingplaetze")

    def test_returns_none_when_nothing_matches(self) -> None:
        self.assertIsNone(classify("Weihnachten 2021", ["Weihnachten"]))
        self.assertIsNone(category_slug("Weihnachten 2021", ["Weihnachten"]))

    def test_umlauts_and_entities_are_normalised(self) -> None:
        self.assertEqual(classify("Stellplätze an der Küste", []), "stellplaetze")
        self.assertEqual(classify("Ausr&amp;uuml;stung", ["Schlafsack"]), "ausruestung-tests")

    def test_renamed_categories_keep_their_original_slug(self) -> None:
        # Both were renamed in WordPress but kept the indexed archive URL.
        self.assertEqual(CATEGORY_SLUGS["fahrzeug-technik"], "fahrzeug")
        self.assertEqual(CATEGORY_SLUGS["news-branche"], "news")
        self.assertEqual(category_slug("Update vom Van", ["Wohnmobil", "Truma"]), "fahrzeug")

    def test_every_rule_maps_to_a_known_slug(self) -> None:
        self.assertEqual(len(CATEGORY_SLUGS), 11)
        for key, slug in CATEGORY_SLUGS.items():
            self.assertTrue(slug and slug.islower(), f"{key} has a suspicious slug: {slug!r}")


if __name__ == "__main__":
    unittest.main()
