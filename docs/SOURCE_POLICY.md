# Source Policy und Feed-Vorschlaege

## Grundsatz
Es werden nur Quellen genutzt, deren Nutzungsbedingungen die geplante Nutzung erlauben oder fuer die eine explizite Genehmigung vorliegt.

## Pflichtdaten pro Quelle
- Quellname
- Feed-URL
- Originalartikel-URL
- Autor/Herausgeber (wenn vorhanden)
- Lizenz/Nutzungsgrundlage
- Einschraenkungen (kommerziell, Bearbeitung, Bildrechte, Archivierung)
- Datum der letzten Pruefung
- Link auf Nutzungsbedingungen

## Einstufung (Ampel)
- Gruen: Nutzung fuer geplantes Modell klar erlaubt
- Gelb: teilklar/mit Einschraenkungen, manuelle Pruefung erforderlich
- Rot: fuer das Modell nicht geeignet ohne Zusatzvertrag

## Verbindliche Regeln
- Keine neue Quelle ohne Eintrag im Source-Register
- Kein automatischer Publish bei Gelb/Rot
- Bilder separat pruefen (Textrecht != Bildrecht)
- Quartalsweiser Re-Check der Terms

## Ersteinschaetzung (Stand: 16.02.2026)

### Rot
1. Reuters / Thomson Reuters
- Grund: Inhalte sind urheberrechtlich geschuetzt; Reproduktion/Verteilung laut Terms nur mit vorheriger Zustimmung.
- Folge: Nur mit explizitem Vertrag/Lizenz.
- Referenz:
  - https://www.thomsonreuters.com/en/terms-of-use

2. tagesschau.de RSS
- Grund: Inhalte nur privat/nicht-kommerziell; Veroeffentlichung grundsaetzlich nicht erlaubt (ausser explizit CC-lizenziert).
- Folge: Nicht fuer das geplante Modell geeignet.
- Referenz:
  - https://www.tagesschau.de/infoservices/rssfeeds

### Gelb
1. Presseportal / ots
- Grund: Redaktionelle Nutzung grundsaetzlich moeglich, aber Verantwortung liegt beim Verwender; darueber hinausgehende Geschaeftsnutzung nur mit Genehmigung.
- Folge: Nur mit strikter Einzelpruefung pro Meldung (insb. Bild-/Drittrechte).
- Referenz:
  - https://www.presseportal.de/nutzungsbedingungen
  - https://www.presseportal.de/feeds/

2. Bundesbehoerden-RSS ohne explizite freie Weiterverwendungs-Lizenz
- Grund: RSS wird bereitgestellt, aber nicht immer als offene Lizenz zur kommerziellen Nachnutzung formuliert.
- Folge: Je Behoerde einzeln pruefen und dokumentieren.
- Beispiele:
  - https://www.bundesfinanzministerium.de/Content/DE/Standardartikel/Service/rss_base.html
  - https://bmas.bund.de/EN/Services/RSS/rss.html

### Gruen (mit korrekter Attribution)
1. GovData / Open-Data-Portale mit `dl-de/by-2-0`, `dl-de/zero-2-0`, `CC BY 4.0` oder `CC0`
- Grund: Diese Lizenzen erlauben grundsaetzlich auch kommerzielle Weiterverwendung (je nach Lizenzbedingungen).
- Folge: Sehr gut fuer stabile Automatisierung geeignet.
- Referenz:
  - https://www.govdata.de/dl-de/by-2-0
  - https://data.gov.de/informationen/lizenzen
  - https://www.dcat-ap.de/def/licenses/dl-zero-de/2.0

2. EU-Quellen mit expliziter `CC BY 4.0` Wiederverwendungsregel
- Grund: EU-Inhalte sind haeufig unter CC BY 4.0 wiederverwendbar, sofern nicht anders gekennzeichnet.
- Folge: Geeignet, wenn Drittinhalte ausgenommen werden.
- Referenz:
  - https://commission.europa.eu/legal-notice_en
  - https://eur-lex.europa.eu/content/help/content/legal-notice/legal-notice.html

## Quelle im Register freischalten (Definition of Done)
- Terms-Link hinterlegt
- Lizenzklasse (Gruen/Gelb/Rot) gesetzt
- Pflicht-Attribution dokumentiert
- Bildrechtsregel dokumentiert
- Letzte Pruefung und Verantwortlicher gepflegt

## Hinweis
Keine Rechtsberatung. Bei unklaren oder wirtschaftlich kritischen Quellen ist eine juristische Prüfung sinnvoll.
