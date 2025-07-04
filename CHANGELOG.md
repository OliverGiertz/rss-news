# CHANGELOG.md

## [1.2.0] - 2025-07-04
### Hinzugefügt
- Automatische Bilderkennung beim Einlesen von Artikeln
  - Extrahieren von Bildern aus dem Originalartikel (bis zu 3 Bilder)
  - Speicherung von Bild-URLs, Alt-Texten (Bildbeschreibung) und Copyright-Hinweisen
- Fehlerbehandlung für nicht erreichbare Seiten
- Darstellung der Bilder (inkl. Beschreibung & Copyright) in der Artikelansicht

### Geändert
- Bilder werden direkt beim Einlesen eines RSS-Artikels verarbeitet und gespeichert
- `app.py` zeigt nun auch Bildinformationen innerhalb der Artikeldetailansicht an

### Behoben
- Keine

---

## [1.1.0] - 2025-07-04
### Hinzugefügt
- Visuell aufgewertete Box zur Darstellung eines Artikels mit:
  - Kopierbutton für Titel
  - Kopierbutton für Artikeltext
  - Kopierbutton für Tags
  - Button zum Öffnen des Originalartikels im neuen Tab
- Artikelansicht ist nun in einer grauen, abgerundeten Box gekapselt
- Icons unterstützen visuelle Orientierung (📝, 🗌, 📌 etc.)

### Geändert
- Artikelkopierfunktion für WordPress ist nun interaktiv über Buttons möglich
- HTML-Markup innerhalb von Streamlit für flexibleres Styling

### Behoben
- Keine

---

## [1.0.0] - 2025-07-03
### Initialversion
- Artikel aus RSS-Feeds einlesen
- Speichern in JSON-Datei
- Anzeige in Tabelle mit Statusfilter
- Rewrite per ChatGPT mit Zusammenfassung und Tag-Generierung
- Exportierbare Inhalte für manuelles Posting auf WordPress
