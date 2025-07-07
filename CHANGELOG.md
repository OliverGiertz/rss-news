## [v1.4.6] – 2025-07-07

### 💡 Neue Funktionen
- Automatischer Release-Workflow bei `git tag v*`
- Release-Text aus `CHANGELOG.md` wird extrahiert und als GitHub Release verwendet

### 🔧 Änderungen & Fixes
- Fehlerbehebung bei Bilddatenextraktion
- Erweiterung von `versioning.py` um automatische Tag-Erstellung und Push

### 📦 Internes
- Erweiterte `release.yml` zur zuverlässigen Release-Erstellung
- GitHub Actions mit `softprops/action-gh-release`


## [v1.4.5] – 2025-07-07

### 💡 Neue Funktionen
- Umstellung des versioning.py-Skripts auf eine moderne Typer-CLI:
- create zum Erstellen neuer Versionen mit Level und Push-Option
- rollback zum Zurücknehmen der letzten Version
- list zur Anzeige aller Versionen im CHANGELOG.md
- Validierung, ob der CHANGELOG.md-Eintrag vor Release wirklich ausgefüllt wurde
- Interaktive CLI-Prompts zur besseren Benutzerführung

### 🔧 Änderungen & Fixes
- versioning.py ersetzt bisherige manuelle Menüs durch Typer-Kommandos
- requirements.txt um typer[all]==0.12.3 ergänzt

### 📦 Internes
- Vorbereitung für globale CLI-Nutzung (versioning als Befehl möglich)
- Automatisierung des Release-Prozesses mit GitHub Actions weiterhin vorbereitet


## [v1.4.4] – 2025-07-07

### 💡 Neue Funktionen
- 

### 🔧 Änderungen & Fixes
- 

### 📦 Internes
- automatische Versionierung eingebunden und direktes GitHub puschen der Änderungen

- ## [v1.4.3] – 2025-07-07

### 💡 Neue Funktionen
- ⚠️ Visuelle Warnanzeige in der Artikeltabelle für unvollständige Bildmetadaten (fehlende Caption, Copyright oder Quelle)
- ✍️ Inline-Bearbeitung von Bilddaten (Caption, Copyright, Quelle) direkt in der Detailansicht
- 🪵 Neue separate Seite `Log-Viewer` zur Anzeige der letzten Log-Einträge (automatisch über `pages/log_viewer.py`)
- 📂 Startfilter für Artikelansicht auf „New“ voreingestellt für fokussierten Workflow

### 🔧 Änderungen & Fixes
- ✅ Artikel aus Feeds überschreiben bestehende Artikel **nicht mehr** – Status, Tags und andere manuelle Änderungen bleiben erhalten
- 🧹 `get_recent_logs()` wurde entfernt und die Sidebar-Logausgabe aus `app.py` entfernt
- 🔗 Sidebar-Link zur Log-Seite hinzugefügt (mittlerweile durch native Seiten-Navigation ersetzt)
- 🧭 Navigation durch Nutzung von Streamlit-Multipage-Struktur (`pages/`)

### 📦 Internes
- Refactoring von `process_articles()` zur sicheren ID-basierten Artikelzusammenführung
- Verbesserte Logging-Ausgabe bei bereits vorhandenen Artikeln
- Robusteres Fehlerhandling in `image_extractor.py`


## [v1.4.2] – 2025-07-03

### 💡 Neue Funktionen
- Komplett überarbeitete Artikel-Tabelle mit:
  - Auswahlcheckboxen
  - Inline-Statuswechsel mit Dropdown
  - Wortanzahl, Tag-Anzeige, Datum kompakt
- Copy-to-Clipboard Funktion für Titel, Text und Tags
- Bildanzeige inkl. Caption und Copyright-Quelle im Detailbereich
- Titel wird automatisch beim Kopieren des Texts vorangestellt

### 🔧 Änderungen & Fixes
- `st.experimental_rerun()` durch `st.rerun()` ersetzt
- Statusfilter „Alle“ funktioniert jetzt korrekt
- UI-Tuning für bessere Lesbarkeit
- Feedliste aus der Sidebar entfernt
- Fix: Bilddaten ohne Caption verursachen keine Fehler mehr
- Artikelüberschriften korrekt in Kopiertext eingebaut

### 📦 Internes
- Logging bleibt aktiv im Verzeichnis `/logs`
- Vorbereitung für Bildquellen-Import aus Original-Artikel umgesetzt


## [1.4.1] – 2025-07-03
### Hinzugefügt
- Logging für `process_articles()`, damit nachvollziehbar ist, welche Feeds verarbeitet wurden
- Rückmeldung in der App bei Klick auf „Alle Feeds neu laden“

### Geändert
- `main.py`: Inhalte aus `content`, `summary` oder `description` werden vollständig geladen und mit `BeautifulSoup` bereinigt
- Sicherstellung, dass `fetch_and_process_feed()` alle relevanten Artikelinformationen vollständig speichert

### Fehlerbehebungen
- Problem behoben, bei dem Artikeltexte nicht vollständig übernommen wurden

## [1.3.1] – 2025-07-03
### Added
- Tabellenansicht mit Checkbox, Titel, Datum, Zusammenfassung, Wortanzahl, Tags, Status
- Direktes Bearbeiten des Status über Dropdown-Menü
- Massenbearbeitung von Artikeln per Checkbox
- Rewrite-Button für alle Artikel mit Status 'Rewrite'


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
