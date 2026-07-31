"""Assign a WordPress category to an article.

The rules mirror the one-off backfill of 2026-07-31 that moved 955 existing
posts out of the catch-all "Allgemein" category, so newly published articles
land in the same buckets as the archive.

Matching notes:
- Keywords match on a word boundary. Plain substring matching is wrong here:
  "klage" would match the city name "Klagenfurt".
- A trailing "*" opts a keyword into German compound nouns, so "campingplatz*"
  also matches "Campingplatzbetreiber".
- Tags weigh more than the title. Tags were chosen deliberately, while titles
  often carry incidental place names.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

# Category key -> WordPress category slug.
CATEGORY_SLUGS: dict[str, str] = {
    "angebote-rabatte": "angebote-rabatte",
    "in-eigener-sache": "in-eigener-sache",
    "recht-vorschriften": "recht-vorschriften",
    "fahrzeug-technik": "fahrzeug",
    "ausruestung-tests": "ausruestung-tests",
    "campingplaetze": "campingplaetze",
    "stellplaetze": "stellplaetze",
    "news-branche": "news",
    "reiseziele": "reiseziele",
    "camping-tipps": "camping-tipps",
    "vanlife": "vanlife",
}

# Ordered by priority: on a points tie the earlier entry wins.
_RULES: tuple[tuple[str, tuple[tuple[str, int], ...]], ...] = (
    ("angebote-rabatte", (
        ("amazon sale", 3), ("amazon-sale", 3), ("amazon-angebote", 3), ("im sale", 3),
        ("rabatt*", 3), ("schnaeppchen*", 3), ("prime day", 3), ("black friday", 3),
        ("gutschein*", 3), ("sparangebot*", 3), ("top-angebot*", 3), ("sommerangebot*", 3),
        ("knaller", 3), ("ausverkauf", 3), ("tiefpreis*", 3), ("rekordpreis*", 3),
        ("preissturz", 3), ("bestpreis*", 3), ("deal", 2), ("deals", 2),
        # Lidl and Aldi articles are always discount posts on this blog, so they
        # carry enough weight to trigger the override below on their own.
        ("lidl", 3), ("aldi", 3), ("im angebot", 3),
        ("reduziert", 2), ("sale", 1), ("prozent auf", 3), ("guenstiger*", 1),
    )),
    ("in-eigener-sache", (
        ("vanityontour", 3), ("vanitycast", 3), ("expense logbook", 3),
        ("jahresrueckblick", 3), ("rueckblick", 2), ("website", 3), ("in eigener sache", 3),
        ("blog", 2), ("discord", 3), ("newsletter", 2), ("appstore", 2), ("app store", 2),
        ("ausfall", 2), ("stoerung", 2), ("podcast", 2), ("campertag", 3), ("styyl", 3),
    )),
    ("recht-vorschriften", (
        ("stvo", 3), ("fuehrerschein*", 3), ("bussgeld*", 3), ("gesetz*", 3),
        ("vorschrift*", 3), ("verkehrsrecht*", 3), ("versicherungsschutz", 3),
        ("tempolimit", 3), ("promillegrenze", 3), ("maut", 3), ("urteil*", 3),
        ("rechtslage", 3), ("abgemahnt", 3), ("bauantrag", 3), ("baurecht", 3),
        ("genehmigung*", 2), ("verboten", 2), ("erlaubt", 2), ("strafe*", 2), ("haftung", 2),
        ("illegal", 2), ("stellplatzverordnung", 3), ("datenschutz", 2), ("kurtaxe", 3),
        ("uebernachtungssteuer", 3), ("kfz-versicherung", 3), ("kfz versicherung", 3),
        ("versicherung*", 1), ("handyverbot", 3), ("regeln", 1),
        ("landschaftsschutzgebiet", 2),
    )),
    ("fahrzeug-technik", (
        ("wohnmobil*", 3), ("wohnwagen*", 3), ("reisemobil*", 3), ("kastenwagen", 3),
        ("camper van", 3), ("camper-van*", 3), ("truma", 3), ("klimaanlage*", 3),
        ("standheizung*", 3), ("energieversorgung", 3), ("ecoflow", 3), ("jackery", 3),
        ("powerstation*", 3), ("solar*", 3), ("batterie*", 3), ("wechselrichter", 3),
        ("notstrom", 3), ("generator", 3), ("stromversorgung", 3), ("umbau", 3), ("ausbau", 3),
        ("selbstausbau", 3), ("fahrverhalten", 3), ("reifen", 3), ("gasanlage*", 3),
        ("gasflasche*", 3), ("werkstatt", 3), ("tuev", 3), ("caravaning", 3), ("caravan", 2),
        ("dometic", 3), ("anhaengerkupplung", 3), ("chassis", 3), ("dieselheizung*", 3),
        ("wasserpumpe*", 3), ("osram", 3), ("auffahrkeil*", 3), ("mover", 3), ("dachluke*", 3),
        ("aufbau", 1), ("heizung", 2), ("strom", 2), ("motor", 2), ("led", 2), ("autark", 2),
        ("ladedose", 3), ("bordtechnik", 3), ("gewicht", 1), ("auflastung", 3),
        ("wiegeaktion", 3), ("gebrauchtwagen*", 3), ("kfz", 2), ("gasversorgung", 3),
        ("flaschengas*", 3), ("marder*", 3), ("reparatur", 2), ("diy", 2),
    )),
    ("ausruestung-tests", (
        ("kuehlbox*", 3), ("kuehltasche*", 3), ("schlafsack*", 3), ("schlafsaecke", 3),
        ("dachzelt*", 3), ("campingbett*", 3), ("zelt*", 3), ("gaskocher", 3),
        ("campingkocher", 3), ("kopfkissen", 3), ("campingstuhl*", 3), ("campingstuehle", 3),
        ("sonnensegel", 3), ("luftmatratze*", 3), ("isomatte*", 3), ("campingdusche*", 3),
        ("produkttest*", 3), ("testbericht*", 3), ("im test", 3), ("getestet", 3),
        ("decathlon", 3), ("coleman", 3), ("campingaz", 3), ("quechua", 3), ("ausruestung", 3),
        ("campingausruestung", 3), ("gadget*", 3), ("markise*", 3), ("nachttisch*", 3),
        ("geschirr", 3), ("grill*", 3), ("campingmoebel", 3), ("stirnlampe*", 3),
        ("powerbank*", 3), ("wasserkanister", 3), ("vorzelt*", 3), ("haengematte*", 3),
        ("campingkueche*", 3), ("campingtisch*", 3), ("camping-helfer", 3),
        ("kaffeemaschine*", 3), ("campingtoilette*", 3), ("rucksack*", 3), ("wanderschuh*", 3),
        ("thermacell", 3), ("kabeltrommel*", 3), ("fernglas", 3), ("fernglaeser", 3),
        ("tarp", 3), ("lichterkette*", 3), ("klapptisch*", 3), ("uv-schutz", 2),
        ("wasserdicht*", 2), ("belueftung", 2), ("kaufberatung", 3), ("marktcheck", 3),
        ("mueckenschutz", 3), ("sonnenschutz", 2), ("ventilator*", 3), ("campinggeschirr", 3),
        ("campingzelt*", 3), ("wurfzelt*", 3), ("tunnelzelt*", 3), ("familienzelt*", 3),
        ("trekkingzelt*", 3), ("aufblasbare*", 2), ("trenntoilette*", 3),
        ("kassettentoilette*", 3), ("toilette*", 2), ("gaswarner", 3), ("rauchmelder", 3),
        ("feuerloescher", 3), ("co melder", 3), ("router", 3), ("mobilfunk", 3), ("wlan", 3),
        ("lte", 3), ("5g", 3), ("internet", 2), ("buchtipp*", 2),
        ("duschzelt*", 3), ("kuppelzelt*", 3), ("pop-up-zelt*", 3), ("messer", 3),
        ("stuhl", 3), ("faltstuhl*", 3), ("klappstuhl*", 3),
    )),
    ("campingplaetze", (
        ("campingplatz*", 3), ("campingplaetze", 3), ("5-sterne*", 3), ("fuenf sterne", 3),
        ("adac-superplatz", 3), ("adac bewertung", 3), ("adac-bewertung", 3),
        ("superplatz*", 3), ("glamping", 3), ("wellness-camping", 3), ("suedsee-camp", 3),
        ("wirthshof", 3), ("trekking-camp*", 3), ("naturcamping*", 3), ("campingpark*", 3),
        ("ferienpark*", 3), ("sanitaer*", 3), ("platz des jahres", 3), ("campingdorf", 3),
        ("campinganlage*", 3), ("campingplatzbetreiber", 3), ("campingfuehrer", 3),
        ("pincamp", 3), ("dauercamp*", 3), ("camping-check", 3), ("campingresort", 3),
        ("stammgaeste", 2), ("kinderanimation", 2), ("resort", 2), ("wellness", 2),
        ("campingplatz-ranking", 3), ("platzbewertung", 3),
    )),
    ("stellplaetze", (
        ("stellplatz*", 3), ("stellplaetze", 3), ("freistehen", 3), ("wildcamp*", 3),
        ("camping-car park", 3), ("wohnmobilstellplatz*", 3), ("wohnmobilstellplaetze", 3),
        ("wohnmobilhafen", 3), ("wohnmobil-stellplaetze", 3), ("stellplatzfuehrer", 3),
        ("uebernachtungsmoeglichkeit*", 2), ("stellplatz-radar", 3), ("parkplatz", 1),
        ("parken", 1), ("church4night", 3), ("raststaette*", 2), ("autohof*", 2),
    )),
    ("news-branche", (
        ("bvcd", 3), ("bundesverband", 3), ("camping-boom", 3), ("campingboom", 3),
        ("uebernachtungszahlen", 3), ("preisanalyse", 3), ("preisentwicklung", 3),
        ("campingpreise", 3), ("preisanstieg", 3), ("preiserhoehung*", 3), ("destatis", 3),
        ("camping-trends", 3), ("campingtrend*", 3), ("marktanalyse", 3), ("caravan salon", 3),
        ("messe", 3), ("promobil", 3), ("insolvenz", 3), ("saisonstart", 3),
        ("jahreszahlen", 3), ("uebernachtungen", 3), ("rekordzahl", 3), ("statistik*", 3),
        ("umfrage", 3), ("studie", 3), ("branche", 3), ("investitionen", 2), ("tourismus", 2),
        ("nachfrage", 2), ("bilanz", 2), ("rekord", 2), ("auszeichnung", 2),
        ("ausgezeichnet", 2), ("preisvergleich", 2), ("eroeffnung", 2), ("eroeffnet", 2),
        ("uebernimmt", 2), ("verkauft", 2), ("pressemeldung", 2), ("feuerwehr", 3),
        ("polizei", 2), ("unfall", 3), ("verletzte", 3), ("hochwasser", 2), ("evakuiert", 3),
        ("veranstaltung*", 2),
    )),
    ("reiseziele", (
        ("nordsee", 3), ("ostsee", 3), ("niedersachsen", 3), ("bodensee", 3),
        ("lueneburger heide", 3), ("thueringen", 3), ("harz", 3), ("italien", 3),
        ("kroatien", 3), ("schweiz", 3), ("oesterreich", 3), ("norwegen", 3), ("schweden", 3),
        ("niederlande", 3), ("holland", 3), ("ruegen", 3), ("fehmarn", 3), ("gardasee", 3),
        ("schwarzwald", 3), ("sauerland", 3), ("edersee", 3), ("bayern", 3), ("hessen", 3),
        ("nrw", 3), ("mecklenburg*", 3), ("baden-wuerttemberg", 3), ("adriakueste", 3),
        ("daenemark", 3), ("frankreich", 3), ("spanien", 3), ("portugal", 3), ("slowenien", 3),
        ("weserradweg", 3), ("waldeck*", 3), ("sylt", 3), ("usedom", 3), ("allgaeu", 3),
        ("eifel", 3), ("mosel", 3), ("alpen", 3), ("toskana", 3), ("brandenburg", 3),
        ("sachsen", 3), ("schleswig-holstein", 3), ("rheinland-pfalz", 3), ("saarland", 3),
        ("tirol", 3), ("suedtirol", 3), ("belgien", 3), ("tschechien", 3), ("polen", 3),
        ("ungarn", 3), ("pyrenaeen", 3), ("nationalpark*", 3), ("reiseziel*", 3),
        ("rundreise*", 3), ("roadtrip*", 3), ("reisebericht*", 3), ("ausflugsziel*", 3),
        ("kurztrip*", 3), ("europa", 2), ("kueste", 2), ("region", 1), ("uckermark", 3),
        ("lausitz", 3), ("schwaebische alb", 3), ("ausflug*", 2), ("geheimtipp*", 2),
        ("uebersee", 2), ("kanada", 3), ("pfalz", 1), ("erzgebirge", 2),
        ("spreewald", 2), ("vogtland", 2), ("rhoen", 2), ("odenwald", 2),
        ("chiemsee", 2), ("ammersee", 2), ("muensterland", 2), ("ostfriesland", 2),
        ("emsland", 2), ("altmuehltal", 2), ("teutoburger wald", 2), ("taunus", 2),
        ("westerwald", 2), ("bergisches land", 2), ("nordwesten", 2),
    )),
    ("camping-tipps", (
        ("tipp", 3), ("tipps", 3), ("tricks", 3), ("ratgeber", 3), ("anleitung", 3),
        ("checkliste", 3), ("packliste", 3), ("buchungstipp*", 3), ("reiseplanung", 3),
        ("urlaubsplanung", 3), ("camping apps", 3), ("nebensaison", 3), ("wintercamping", 3),
        ("campingsaison", 3), ("camping-saison", 3), ("angrillen", 3), ("reisetipp*", 3),
        ("erste hilfe", 3), ("diebstahlschutz", 3), ("so geht", 2), ("so funktioniert", 2),
        ("worauf", 2), ("das sollten", 2), ("muss man wissen", 2), ("wie man", 2),
        ("vermeiden", 2), ("hygiene", 2), ("sicherheit", 2), ("vorbereitung", 2), ("hitze", 2),
        ("wetter", 1), ("guide", 2), ("mythos", 2), ("mythen", 2), ("mit hund", 2),
        ("hundefreundlich*", 2),
    )),
    ("vanlife", (
        ("vanlife", 3), ("van-life", 3), ("van life", 3), ("minimalismus", 3),
        ("digitale nomaden", 3), ("aussteiger", 3), ("slow travel", 3),
        ("campergemeinschaft", 3), ("camper-gemeinschaft", 3), ("lebensgefuehl", 3),
        ("auszeit", 2), ("freiheit", 2), ("abenteuer", 2), ("gedanken", 2),
        ("nachhaltigkeit", 2),
    )),
)

_PRIORITY = {key: i for i, (key, _) in enumerate(_RULES)}

# A clear discount signal decides on its own: a tent on sale is first of all an
# offer. Otherwise "Ausruestung & Tests" wins on the sheer number of product
# tags and the offers category stays nearly empty.
_OFFER_KEY = "angebote-rabatte"
_OFFER_OVERRIDE_MIN_WEIGHT = 3


def _normalise(text: str) -> str:
    text = text.lower()
    for src, dst in (("\u00e4", "ae"), ("\u00f6", "oe"), ("\u00fc", "ue"), ("\u00df", "ss")):
        text = text.replace(src, dst)
    text = text.replace("&amp;", " ").replace("&", " ")
    text = re.sub(r"[\u201e\u201c\u201d\u2018\u2019\u00ab\u00bb\"']", " ", text)
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip()


def _compile(keyword: str) -> re.Pattern[str]:
    compound = keyword.endswith("*")
    core = _normalise(keyword[:-1] if compound else keyword)
    body = re.escape(core).replace(r"\ ", r"\s+")
    tail = r"[a-z0-9]*" if compound else r"(?![a-z0-9])"
    return re.compile(r"(?<![a-z0-9])" + body + tail)


_PATTERNS: dict[str, tuple[tuple[re.Pattern[str], int], ...]] = {
    key: tuple((_compile(kw), weight) for kw, weight in keywords) for key, keywords in _RULES
}


def classify(title: str, tags: Sequence[str] | None = None) -> str | None:
    """Return a category key, or None when no rule matches.

    Callers should leave the category unset in that case so the article stays
    visible in WordPress' default category instead of being filed wrongly.
    """
    title_text = _normalise(title or "")
    tag_text = _normalise(" | ".join(tags or []))

    scores: dict[str, int] = {}
    for key, patterns in _PATTERNS.items():
        total = 0
        for pattern, weight in patterns:
            if pattern.search(tag_text):
                total += 3 * weight
            if pattern.search(title_text):
                total += 2 * weight
        if total:
            scores[key] = total

    if not scores:
        return None

    for pattern, weight in _PATTERNS[_OFFER_KEY]:
        if weight >= _OFFER_OVERRIDE_MIN_WEIGHT and (
            pattern.search(tag_text) or pattern.search(title_text)
        ):
            return _OFFER_KEY

    return max(scores.items(), key=lambda item: (item[1], -_PRIORITY[item[0]]))[0]


def category_slug(title: str, tags: Sequence[str] | None = None) -> str | None:
    """Return the WordPress category slug for an article, or None."""
    key = classify(title, tags)
    return CATEGORY_SLUGS.get(key) if key else None
