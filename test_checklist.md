## ✅ Artikel-Rewrite prüfen

| Testschritt                                         | Erwartung                     | Erfüllt? (✔/✘) |
|-----------------------------------------------------|-------------------------------|----------------|
| Artikel mit Status "Rewrite" umschreiben           | Text wird ersetzt             |                |
| Andere Artikel bleiben unverändert                 | Kein Datenverlust             |                |
| Tags bei anderen Artikeln bleiben erhalten         | Keine versehentliche Änderung |                |
| Nur bearbeitete Artikel bekommen neue Tags         | Zielgenaue Verarbeitung       |                |
| JSON enthält alle Artikel                          | Kein Verlust nach save()      |                |

## ✅ DALL·E-Bildgenerierung prüfen

| Testschritt                                         | Erwartung                                 | Erfüllt? (✔/✘) |
|-----------------------------------------------------|-------------------------------------------|----------------|
| KI-Button klickbar                                 | Nur wenn noch kein DALL·E-Bild vorhanden  |                |
| Bild wird korrekt generiert                        | URL, Metadaten vorhanden                  |                |
| Nur ein Bild wird hinzugefügt                      | Keine Duplikate                           |                |
| Bild wird korrekt gespeichert                      | In `images[]` mit passendem Prompt        |                |
| Andere Artikel bleiben unverändert                 | Kein Datenverlust                         |                |

## ✅ Statusänderung prüfen

| Testschritt                                         | Erwartung                     | Erfüllt? (✔/✘) |
|-----------------------------------------------------|-------------------------------|----------------|
| Artikelstatus ändern (z. B. auf Trash)             | Wird korrekt übernommen       |                |
| Nur ein Artikel wird verändert                     | Kein Einfluss auf andere      |                |
| Artikel bleibt in JSON erhalten                    | Kein versehentliches Löschen  |                |

## ✅ Gesamtsystemprüfung

| Testschritt                                         | Erwartung                                 | Erfüllt? (✔/✘) |
|-----------------------------------------------------|-------------------------------------------|----------------|
| `articles.json` vollständig                        | Alle Artikel erhalten                     |                |
| Keine Fehlermeldungen im UI oder Log               | Logging funktioniert, keine Exceptions    |                |
| Filterfunktion bleibt erhalten nach Aktion         | Kein Verlust des Statusfilters            |                |
