## [1.8.1] - 2026-08-24

### 📋 Freigabe-Seite
  - Neue Seite `/admin/freigabe`: alle Artikel im Status „Wartet auf Freigabe" auf einer Arbeitsliste
  - Pro Artikel: Hauptbild, Relevanz-Score mit Begründung, Tags, Wortzahl, Alter, Link zum Originalartikel
  - Der umgeschriebene Text wird **lesbar gerendert** statt als Markup — durch einen Tag-Whitelist-Filter, weil er aus Modell-Ausgabe über fremde Webseiten stammt
  - Drei Aktionen direkt an jedem Artikel: ✅ Freigeben (mit Notizfeld), ✏️ Neu schreiben, ❌ Verwerfen
  - Nach jeder Aktion zurück zur Liste, damit sich eine Warteschlange am Stück abarbeiten lässt
  - Verlinkt aus der Navigation aller Admin-Seiten, mit Zähler im Dashboard

### 🧹 Status-Altlasten entfernt
  - Artikelliste zeigte interne Kürzel (`pending_review`, `approved`, `error`) — jetzt überall Klartext
  - Status `review` (Relevanz-Warnzone 60–79) wurde als „Rewrite" angezeigt, was etwas anderes bedeutet — heißt jetzt „Niedrige Relevanz"
  - Übergang `Rewrite → Freigegeben` entfernt: ein zweiter Weg an der Freigabe vorbei
  - Übergang `Freigegeben → Veröffentlicht` entfernt: das setzen WordPress bzw. der WP-Sync, nicht die Hand
  - API-Statusliste wird aus dem Statusmodell abgeleitet statt handgepflegt (kannte `freigabe` nicht und lehnte den Wechsel mit 422 ab)

### 🐛 Behoben
  - `list_articles` las `content_rewritten` nicht mit — die Freigabe-Seite hätte nie einen Text angezeigt

---

## [1.8.0] - 2026-08-24

### ⚖️ Redaktionelle Freigabe vor der Veröffentlichung (Art. 50 Abs. 4 KI-VO)
  - Neuer Status **„Wartet auf Freigabe"** (`pending_review`) zwischen Rewrite und Publish
  - Die Pipeline endet jetzt beim Rewrite: **kein WordPress-Beitrag und kein Publish-Slot**, bevor ein Mensch den Artikel freigegeben hat
  - Neuer Button „✅ Redaktionell geprüft & freigeben" auf der Artikel-Detailseite, mit optionaler Prüfnotiz
  - Freigabe stempelt Prüfer und **Systemzeit** in `editorial_review_at` / `_by` / `_note` — nicht editierbar, zusätzlich im Audit-Trail (`review_events`)
  - Erst die Freigabe reserviert den Slot und legt den WordPress-Beitrag an (Status `future`)
  - Schlägt WordPress dabei fehl, fällt der Artikel mit freigegebenem Slot zurück in die Warteschlange — Freigabe einfach wiederholen
  - Kein Schlupfloch: auch der manuelle Statuswechsel nach `publish` (Admin-UI und API) stempelt die Freigabe
  - Altbestand bleibt unberührt: bereits freigegebene/veröffentlichte Artikel brauchen keinen Stempel

### 📨 Telegram
  - Neue Meldung „📝 Neuer Artikel wartet auf Freigabe" mit Deep-Link ins Portal, bewusst **ohne** Freigabe-Button
  - Neue Bestätigung „✅ Freigegeben und eingeplant" mit Prüfer und Slot
  - Relevanz-Warnung enthält zusätzlich den Portal-Link
  - Pipeline-Zusammenfassung und `/status` zeigen die Zahl der wartenden Artikel

### 🖥️ Admin-UI
  - Dashboard-Banner mit Anzahl der Artikel, die auf Freigabe warten, inkl. Direktfilter
  - Klartext-Bezeichnungen für alle Status statt interner Kürzel
  - Publish-Bereitschaft weist „Redaktionelle Freigabe fehlt" aus

### 🔧 Technisch
  - Migration: Spalten `editorial_review_at/_by/_note`, Status-CHECK um `pending_review` erweitert
  - Spalten-Migration wird nach den Tabellen-Neubauten erneut angewandt (der ältere `no_image`-Rebuild hat frisch angelegte Spalten sonst wieder verworfen)
  - Neue Konfiguration `EDITORIAL_REVIEW_REQUIRED` (Default `true`) und `PORTAL_BASE_URL`
  - Neue Doku `docs/KI-VO.md`; `docs/AUTOMATION.md` an den neuen Ablauf angepasst
  - 12 neue Tests in `backend/tests/test_editorial_review.py`

---

## [1.7.1] - 2025-08-24

###  ✨ Security angepasst
  - alle Credentials in die .env Datei verschoben
  - beim Start der App werden die Credentials geprüft und beim fehlen entsprechende Meldungen ausgegeben

---

## [1.7.0] - 2025-08-24

###  Multi-Select & Massenoperationen:
  - ✅ Checkboxes für Artikel-Auswahl im "Artikel verwalten" Bereich
  - ✅ "Alle auswählen" / "Auswahl aufheben" Buttons
  - ✅ Massenoperationen für ausgewählte Artikel:
    - Bulk Status-Änderung für mehrere Artikel gleichzeitig
    - Bulk Artikel-Umschreibung mit automatischer Status-Verwaltung
    - Bulk WordPress-Upload nur für "Process"-Artikel
    - Bulk Papierkorb-Funktion

###  Schnellaktionen Integration:
  - ✅ Feed-Aktualisierung direkt im Artikel-Tab verfügbar
  - ✅ Alle Dashboard-Schnellaktionen in Artikel-Verwaltung integriert
  - ✅ Intelligente Anzeige nur relevanter Operationen (z.B. WordPress-Upload nur bei Process-Artikeln)

###  🔧 Verbesserungen

  - UI/UX: Verbesserte Artikel-Card-Layouts mit Checkbox-Integration
  - Workflow: Streamlined Artikel-Management ohne Tab-Wechsel nötig
  - Feedback: Detaillierte Statusmeldungen bei Massenoperationen
  - Performance: Optimierte Session-State-Verwaltung für Artikel-Auswahl

###  🏗️ Technische Änderungen

  - Session State Erweiterung um selected_articles Set
  - Neue Bulk-Operation-Funktionen in app.py:326-467
  - Überarbeitetes Artikel-Card-Layout mit 3-Spalten-Design
  - Integration bestehender WordPress-Upload und Rewrite-Funktionen

---

## [1.6.3] - 2025-08-18

### 🔧 Verbesserungen
- **SyleSheet erneut hinzugefügt
  - Style wurde bei einem Release leider vergessen
  - Style auf DarkMode angepasst

---

## [v1.6.2] - 2025-08-16

### 🐛 Kritische Fehlerbehebung

- **WordPress-Tag-Upload-Fehler behoben:**
  - WordPress REST API benötigt Tag-IDs statt Tag-Namen im `tags`-Parameter
  - Neue Funktion `_get_or_create_tags()` ermittelt existierende Tag-IDs oder erstellt neue Tags
  - Automatische Tag-Erstellung wenn Tags nicht existieren
  - Robuste Fehlerbehandlung für Tag-Verarbeitungsfehler

### 🔧 Verbesserungen

- **Erweiterte Fehleranalyse:**
  - Detaillierte Logging-Ausgaben für Post-Daten bei Fehlern
  - Spezielle Behandlung von Tag-Parameter-Fehlern
  - JSON-formatierte Debug-Ausgaben für bessere Fehleranalyse

- **Tag-Management:**
  - Suche nach existierenden Tags mit exakter Namensübereinstimmung
  - Automatische Erstellung fehlender Tags über WordPress REST API
  - Tag-IDs werden korrekt im Post-Daten-Objekt verwendet
  - Leere/ungültige Tags werden übersprungen

### 🛠 Technische Details

- Tag-Verarbeitung erfolgt vor Post-Erstellung
- WordPress `/wp-json/wp/v2/tags` Endpoint für Tag-Management
- Fallback-Verhalten bei Tag-Erstellungsfehlern
- Verbesserte Logging-Ausgaben für Tag-Operationen

---

## [v1.6.1] - 2025-08-16

### 💡 Neue Funktionen

- **WordPress-Integration** implementiert:
  - Vollständige WordPress REST API-Anbindung über `utils/wordpress_uploader.py`
  - **Base64-Authentifizierung** mit Authorization Header (wie von WordPress API benötigt)
  - Neuer Status "WordPress Pending" für hochgeladene Artikel
  - Artikel mit Status "Process" können einzeln oder als Batch zu WordPress hochgeladen werden
  - Automatische Duplikatserkennung basierend auf Titel-Übereinstimmung
  - Meta-Felder werden gesetzt (RSS-Quelle, Original-Link, Import-Datum, RSS-Artikel-ID)

- **Erweiterte UI-Funktionen**:
  - Neuer Tab "WordPress" mit Verbindungstest und Konfigurationsübersicht
  - WordPress-Upload-Buttons in der Artikel-Übersicht (einzeln und global)
  - WordPress-Artikel-Statistiken im Dashboard und Statistiken-Tab
  - Detaillierte Upload-Ergebnisse mit Erfolgs-/Fehlerstatistiken
  - Debug-Modus für Auth-Details (Entwicklung)

- **Verbesserte Artikel-Verwaltung**:
  - WordPress Post ID und Upload-Datum werden in Artikeln gespeichert
  - Status-Workflow: New → Rewrite → Process → WordPress Pending → Online
  - Anzeige von WordPress-Informationen in der Artikel-Detailansicht

### 🔧 Verbesserungen

- **Korrekte WordPress-API-Authentifizierung**:
  - Unterstützung für bereitgestellten Base64-Auth-String (`WP_AUTH_BASE64`)
  - Fallback auf automatische Base64-Generierung aus Username/Password
  - Authorization Header im korrekten Format: `Basic <base64_credentials>`
  - Erweiterte Debug-Ausgaben für Authentifizierung

- **Robuste Fehlerbehandlung**:
  - Ausführliches Logging für alle WordPress-Operationen inkl. Auth-Details
  - Retry-Mechanismus mit exponential backoff bei Netzwerkfehlern
  - Detaillierte Fehlermeldungen für verschiedene HTTP-Status-Codes (401, 403, etc.)
  - Verbindungstest vor Upload-Operationen mit Auth-Verifikation

- **Erweiterte WordPress-API-Funktionen**:
  - Automatische Ermittlung der Standard-Kategorie "Allgemein"
  - Session-basierte HTTP-Verbindungen für bessere Performance
  - Unterstützung für WordPress-Meta-Felder zur Nachverfolgung
  - Berücksichtigung verschiedener WordPress-Authentifizierungsfehler

- **UI/UX-Verbesserungen**:
  - Neuer Status-Badge für "WordPress Pending" mit eigenem Styling
  - Dashboard zeigt WordPress-spezifische Statistiken
  - Konfigurationshilfen und .env-Vorlagen im WordPress-Tab
  - Massenupload-Funktionalität mit Progress-Feedback
  - Base64-Auth-Status in Konfigurationsübersicht

### 🛠 Interne Änderungen

- `main.py` erweitert um `upload_articles_to_wp()` Funktion
- `VALID_STATUSES` um "WordPress Pending" erweitert
- Neue Umgebungsvariable `WP_AUTH_BASE64` für direkte Base64-Authentifizierung
- Erweiterte Artikel-Datenstruktur um WordPress-spezifische Felder
- Session-Management für HTTP-Verbindungen implementiert
- Base64-Authentifizierung mit Fallback-Mechanismus

### 📁 Neue Dateien

- `utils/wordpress_uploader.py` - Vollständige WordPress REST API-Integration mit Base64-Auth
- Erweiterte `.env`-Vorlage mit WordPress-Konfiguration inkl. Base64-String

### 🔒 Sicherheit

- WordPress-Credentials werden sicher über Umgebungsvariablen verwaltet
- Base64-Auth über Anwendungspasswort (sicherer als Haupt-Login)
- Keine sensiblen Daten in Logs oder Fehlermeldungen
- Authorization Header im WordPress-Standard-Format

### 📋 Authentifizierungs-Setup

**Bereitgestellte Konfiguration:**
```bash
WP_AUTH_BASE64=b2dpZXJ0ejp3aE5FeDlhWkNJVVhWaVY4OVozZTdaMDM=
# Dekodiert: ogiertz:whNEx9aZCIUXViV89Z3e7Z03
```

**Authorization Header:**
```
Authorization: Basic b2dpZXJ0ejp3aE5FeDlhWkNJVVhWaVY4OVozZTdaMDM=
```

---

## [v1.5.3] - 2025-07-11

### 💡 Neue Funktionen

- **WordPress-Integration** implementiert:
  - Vollständige WordPress REST API-Anbindung über `utils/wordpress_uploader.py`
  - Neuer Status "WordPress Pending" für hochgeladene Artikel
  - Artikel mit Status "Process" können einzeln oder als Batch zu WordPress hochgeladen werden
  - Automatische Duplikatserkennung basierend auf Titel-Übereinstimmung
  - Meta-Felder werden gesetzt (RSS-Quelle, Original-Link, Import-Datum, RSS-Artikel-ID)

- **Erweiterte UI-Funktionen**:
  - Neuer Tab "WordPress" mit Verbindungstest und Konfigurationsübersicht
  - WordPress-Upload-Buttons in der Artikel-Übersicht (einzeln und global)
  - WordPress-Artikel-Statistiken im Dashboard und Statistiken-Tab
  - Detaillierte Upload-Ergebnisse mit Erfolgs-/Fehlerstatistiken

- **Verbesserte Artikel-Verwaltung**:
  - WordPress Post ID und Upload-Datum werden in Artikeln gespeichert
  - Status-Workflow: New → Rewrite → Process → WordPress Pending → Online
  - Anzeige von WordPress-Informationen in der Artikel-Detailansicht

### 🔧 Verbesserungen

- **Robuste Fehlerbehandlung**:
  - Ausführliches Logging für alle WordPress-Operationen
  - Retry-Mechanismus mit exponential backoff bei Netzwerkfehlern
  - Detaillierte Fehlermeldungen für verschiedene HTTP-Status-Codes
  - Verbindungstest vor Upload-Operationen

- **Erweiterte WordPress-API-Funktionen**:
  - Automatische Ermittlung der Standard-Kategorie "Allgemein"
  - Session-basierte HTTP-Verbindungen für bessere Performance
  - Unterstützung für WordPress-Meta-Felder zur Nachverfolgung
  - Berücksichtigung verschiedener WordPress-Authentifizierungsfehler

- **UI/UX-Verbesserungen**:
  - Neuer Status-Badge für "WordPress Pending" mit eigenem Styling
  - Dashboard zeigt WordPress-spezifische Statistiken
  - Konfigurationshilfen und .env-Vorlagen im WordPress-Tab
  - Massenupload-Funktionalität mit Progress-Feedback

### 🛠 Interne Änderungen

- `main.py` erweitert um `upload_articles_to_wp()` Funktion
- `VALID_STATUSES` um "WordPress Pending" erweitert
- Neue Umgebungsvariablen für WordPress-Konfiguration
- Erweiterte Artikel-Datenstruktur um WordPress-spezifische Felder
- Session-Management für HTTP-Verbindungen implementiert

### 📁 Neue Dateien

- `utils/wordpress_uploader.py` - Vollständige WordPress REST API-Integration
- Erweiterte `.env`-Vorlage mit WordPress-Konfiguration

### 🔒 Sicherheit

- WordPress-Credentials werden sicher über Umgebungsvariablen verwaltet
- Basic Auth über Anwendungspasswort (sicherer als Haupt-Login)
- Keine sensiblen Daten in Logs oder Fehlermeldungen

---

## [v1.5.3] - 2025-07-11

### ✨ Neue Funktionen

- Automatischer Volltextabruf bei zu kurzen Artikeln (< 50 Wörter)
  - Inhalte werden direkt von der Originalseite geladen (ähnlich wie bei der Bildextraktion)
  - Promobil, Camping-News und andere gängige WordPress-Seiten werden unterstützt

- Neue Verwaltungsseite `Feed-Verwaltung` unter `pages/01_feed_manager.py`
  - RSS-Feeds können nun über eine dedizierte Oberfläche hinzugefügt, bearbeitet und gelöscht werden
  - Anzahl verknüpfter Artikel pro Feed wird angezeigt
  - Änderungen werden protokolliert und per `st.rerun()` sofort sichtbar

### 🔧 Verbesserungen

- Feed-Filter in der Artikelübersicht zeigt jetzt die **korrekten Feed-Namen mit Artikelanzahl**
  - Beispiel: „Promobil News (12)" statt nur „Alle (20)"
  - Basierend auf `source`-Feld im Artikelobjekt

- Verbesserte Logging-Ausgaben bei Feed-Aktionen (hinzufügen, ändern, löschen)

### 📁 Neue Dateien

- `utils/article_extractor.py` – Logik zum Abrufen vollständiger Artikeltexte von Originalseiten
- `pages/01_feed_manager.py` – Eigenständige Verwaltungsseite für RSS-Feeds

### 🛠 Interne Änderungen

- `main.py` erweitert: Automatischer Fallback auf `extract_full_article()` bei zu kurzem Text
- Logging konsolidiert und mit Feed-Aktionen ergänzt

## [v1.5.2] - 2025-07-09

- Fehlerbehandlung bei `CHANGELOG.md`-Doppelungen hinzugefügt
- Signaturlogik robuster (SSH, GPG, fallback)
- Farbige Terminalausgabe verbessert
- dry-run Argument hinzugefügt:
  * Versionsnummer wird berechnet ✅
  * Änderungen (Version, Changelog, Commit, Tag, Push) werden nur angezeigt, nicht ausgeführt ✅
  * Ausgabe erfolgt farbig und klar gegliedert ✅

## [1.5.1] - 2025-07-09

SSH-Commit-Signatur in versioning.py eingebaut
Automatischer Fallback auf GPG oder keine Signatur
Farbige Terminalausgabe zur Signaturmethode
Readme erweitert mit Setup-Anleitung

## [v1.5.0] – 2025-07-08

### 💡 Neue Funktionen
- 🪄 DALL·E-Bildgenerierung per Button direkt im Artikel-Expander
- Automatische Metadaten (Caption, Copyright, Quelle) für KI-generierte Bilder

### 🔧 Änderungen & Fixes
- 🔒 Kritischer Bugfix: Artikel gingen nach DALL·E oder Rewrite verloren → jetzt sichere `save_articles()`-Logik über alle Artikel
- Status-Änderungen, Rewrite und Bilderfassung überschreiben nicht mehr die Gesamtdatei
- Kein `st.rerun()` mehr nach jedem Klick – flüssiger Workflow 

### 📦 Internes
- Neue Datei `utils/dalle_generator.py` für DALL·E-Integration
- Erweiterung der Teststrategie um strukturierte `TEST-CHECKLIST.md`
- Verbesserte Update-Strategie für Einzelartikel bei Bearbeitung

## [v1.4.8] – 2025-07-07

### 💡 Neue Funktionen
- 

### 🔧 Änderungen & Fixes
- Fehlerbehebung bei neuen Release, CHANGELOG wurde nicht angehangen, es wird nun die gesamte Datei übernommen

### 📦 Internes
- 

## [v1.4.7] – 2025-07-07

### 💡 Neue Funktionen
- Automatischer Release-Workflow bei `git tag v*`
- Release-Text aus `CHANGELOG.md` wird extrahiert und als GitHub Release verwendet

### 🔧 Änderungen & Fixes
- Fehlerbehebung bei neuen Release, CHANGELOG wurde nicht angehangen

### 📦 Internes
- Erweiterte `release.yml` zur zuverlässigen Release-Erstellung
- GitHub Actions mit `softprops/action-gh-release`

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
- 📂 Startfilter für Artikelansicht auf „New" voreingestellt für fokussierten Workflow

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
- Statusfilter „Alle" funktioniert jetzt korrekt
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
- Rückmeldung in der App bei Klick auf „Alle Feeds neu laden"

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

---


## [v1.6.1] - 2025-08-16

### 💡 Neue Funktionen

- **WordPress-Integration** implementiert:
  - Vollständige WordPress REST API-Anbindung über `utils/wordpress_uploader.py`
  - **Base64-Authentifizierung** mit Authorization Header (wie von WordPress API benötigt)
  - Neuer Status "WordPress Pending" für hochgeladene Artikel
  - Artikel mit Status "Process" können einzeln oder als Batch zu WordPress hochgeladen werden
  - Automatische Duplikatserkennung basierend auf Titel-Übereinstimmung
  - Meta-Felder werden gesetzt (RSS-Quelle, Original-Link, Import-Datum, RSS-Artikel-ID)

- **Erweiterte UI-Funktionen**:
  - Neuer Tab "WordPress" mit Verbindungstest und Konfigurationsübersicht
  - WordPress-Upload-Buttons in der Artikel-Übersicht (einzeln und global)
  - WordPress-Artikel-Statistiken im Dashboard und Statistiken-Tab
  - Detaillierte Upload-Ergebnisse mit Erfolgs-/Fehlerstatistiken
  - Debug-Modus für Auth-Details (Entwicklung)

- **Verbesserte Artikel-Verwaltung**:
  - WordPress Post ID und Upload-Datum werden in Artikeln gespeichert
  - Status-Workflow: New → Rewrite → Process → WordPress Pending → Online
  - Anzeige von WordPress-Informationen in der Artikel-Detailansicht

### 🔧 Verbesserungen

- **Korrekte WordPress-API-Authentifizierung**:
  - Unterstützung für bereitgestellten Base64-Auth-String (`WP_AUTH_BASE64`)
  - Fallback auf automatische Base64-Generierung aus Username/Password
  - Authorization Header im korrekten Format: `Basic <base64_credentials>`
  - Erweiterte Debug-Ausgaben für Authentifizierung

- **Robuste Fehlerbehandlung**:
  - Ausführliches Logging für alle WordPress-Operationen inkl. Auth-Details
  - Retry-Mechanismus mit exponential backoff bei Netzwerkfehlern
  - Detaillierte Fehlermeldungen für verschiedene HTTP-Status-Codes (401, 403, etc.)
  - Verbindungstest vor Upload-Operationen mit Auth-Verifikation

- **Erweiterte WordPress-API-Funktionen**:
  - Automatische Ermittlung der Standard-Kategorie "Allgemein"
  - Session-basierte HTTP-Verbindungen für bessere Performance
  - Unterstützung für WordPress-Meta-Felder zur Nachverfolgung
  - Berücksichtigung verschiedener WordPress-Authentifizierungsfehler

- **UI/UX-Verbesserungen**:
  - Neuer Status-Badge für "WordPress Pending" mit eigenem Styling
  - Dashboard zeigt WordPress-spezifische Statistiken
  - Konfigurationshilfen und .env-Vorlagen im WordPress-Tab
  - Massenupload-Funktionalität mit Progress-Feedback
  - Base64-Auth-Status in Konfigurationsübersicht

### 🛠 Interne Änderungen

- `main.py` erweitert um `upload_articles_to_wp()` Funktion
- `VALID_STATUSES` um "WordPress Pending" erweitert
- Neue Umgebungsvariable `WP_AUTH_BASE64` für direkte Base64-Authentifizierung
- Erweiterte Artikel-Datenstruktur um WordPress-spezifische Felder
- Session-Management für HTTP-Verbindungen implementiert
- Base64-Authentifizierung mit Fallback-Mechanismus

### 📁 Neue Dateien

- `utils/wordpress_uploader.py` - Vollständige WordPress REST API-Integration mit Base64-Auth
- Erweiterte `.env`-Vorlage mit WordPress-Konfiguration inkl. Base64-String

### 🔒 Sicherheit

- WordPress-Credentials werden sicher über Umgebungsvariablen verwaltet
- Base64-Auth über Anwendungspasswort (sicherer als Haupt-Login)
- Keine sensiblen Daten in Logs oder Fehlermeldungen
- Authorization Header im WordPress-Standard-Format

### 📋 Authentifizierungs-Setup

**Bereitgestellte Konfiguration:**
```bash
WP_AUTH_BASE64=b2dpZXJ0ejp3aE5FeDlhWkNJVVhWaVY4OVozZTdaMDM=
# Dekodiert: ogiertz:whNEx9aZCIUXViV89Z3e7Z03
```

**Authorization Header:**
```
Authorization: Basic b2dpZXJ0ejp3aE5FeDlhWkNJVVhWaVY4OVozZTdaMDM=
```

---

## [v1.5.3] - 2025-07-11

### 💡 Neue Funktionen

- **WordPress-Integration** implementiert:
  - Vollständige WordPress REST API-Anbindung über `utils/wordpress_uploader.py`
  - Neuer Status "WordPress Pending" für hochgeladene Artikel
  - Artikel mit Status "Process" können einzeln oder als Batch zu WordPress hochgeladen werden
  - Automatische Duplikatserkennung basierend auf Titel-Übereinstimmung
  - Meta-Felder werden gesetzt (RSS-Quelle, Original-Link, Import-Datum, RSS-Artikel-ID)

- **Erweiterte UI-Funktionen**:
  - Neuer Tab "WordPress" mit Verbindungstest und Konfigurationsübersicht
  - WordPress-Upload-Buttons in der Artikel-Übersicht (einzeln und global)
  - WordPress-Artikel-Statistiken im Dashboard und Statistiken-Tab
  - Detaillierte Upload-Ergebnisse mit Erfolgs-/Fehlerstatistiken

- **Verbesserte Artikel-Verwaltung**:
  - WordPress Post ID und Upload-Datum werden in Artikeln gespeichert
  - Status-Workflow: New → Rewrite → Process → WordPress Pending → Online
  - Anzeige von WordPress-Informationen in der Artikel-Detailansicht

### 🔧 Verbesserungen

- **Robuste Fehlerbehandlung**:
  - Ausführliches Logging für alle WordPress-Operationen
  - Retry-Mechanismus mit exponential backoff bei Netzwerkfehlern
  - Detaillierte Fehlermeldungen für verschiedene HTTP-Status-Codes
  - Verbindungstest vor Upload-Operationen

- **Erweiterte WordPress-API-Funktionen**:
  - Automatische Ermittlung der Standard-Kategorie "Allgemein"
  - Session-basierte HTTP-Verbindungen für bessere Performance
  - Unterstützung für WordPress-Meta-Felder zur Nachverfolgung
  - Berücksichtigung verschiedener WordPress-Authentifizierungsfehler

- **UI/UX-Verbesserungen**:
  - Neuer Status-Badge für "WordPress Pending" mit eigenem Styling
  - Dashboard zeigt WordPress-spezifische Statistiken
  - Konfigurationshilfen und .env-Vorlagen im WordPress-Tab
  - Massenupload-Funktionalität mit Progress-Feedback

### 🛠 Interne Änderungen

- `main.py` erweitert um `upload_articles_to_wp()` Funktion
- `VALID_STATUSES` um "WordPress Pending" erweitert
- Neue Umgebungsvariablen für WordPress-Konfiguration
- Erweiterte Artikel-Datenstruktur um WordPress-spezifische Felder
- Session-Management für HTTP-Verbindungen implementiert

### 📁 Neue Dateien

- `utils/wordpress_uploader.py` - Vollständige WordPress REST API-Integration
- Erweiterte `.env`-Vorlage mit WordPress-Konfiguration

### 🔒 Sicherheit

- WordPress-Credentials werden sicher über Umgebungsvariablen verwaltet
- Basic Auth über Anwendungspasswort (sicherer als Haupt-Login)
- Keine sensiblen Daten in Logs oder Fehlermeldungen

---

## [v1.5.3] - 2025-07-11

### ✨ Neue Funktionen

- Automatischer Volltextabruf bei zu kurzen Artikeln (< 50 Wörter)
  - Inhalte werden direkt von der Originalseite geladen (ähnlich wie bei der Bildextraktion)
  - Promobil, Camping-News und andere gängige WordPress-Seiten werden unterstützt

- Neue Verwaltungsseite `Feed-Verwaltung` unter `pages/01_feed_manager.py`
  - RSS-Feeds können nun über eine dedizierte Oberfläche hinzugefügt, bearbeitet und gelöscht werden
  - Anzahl verknüpfter Artikel pro Feed wird angezeigt
  - Änderungen werden protokolliert und per `st.rerun()` sofort sichtbar

### 🔧 Verbesserungen

- Feed-Filter in der Artikelübersicht zeigt jetzt die **korrekten Feed-Namen mit Artikelanzahl**
  - Beispiel: „Promobil News (12)" statt nur „Alle (20)"
  - Basierend auf `source`-Feld im Artikelobjekt

- Verbesserte Logging-Ausgaben bei Feed-Aktionen (hinzufügen, ändern, löschen)

### 📁 Neue Dateien

- `utils/article_extractor.py` – Logik zum Abrufen vollständiger Artikeltexte von Originalseiten
- `pages/01_feed_manager.py` – Eigenständige Verwaltungsseite für RSS-Feeds

### 🛠 Interne Änderungen

- `main.py` erweitert: Automatischer Fallback auf `extract_full_article()` bei zu kurzem Text
- Logging konsolidiert und mit Feed-Aktionen ergänzt

## [v1.5.2] - 2025-07-09

- Fehlerbehandlung bei `CHANGELOG.md`-Doppelungen hinzugefügt
- Signaturlogik robuster (SSH, GPG, fallback)
- Farbige Terminalausgabe verbessert
- dry-run Argument hinzugefügt:
  * Versionsnummer wird berechnet ✅
  * Änderungen (Version, Changelog, Commit, Tag, Push) werden nur angezeigt, nicht ausgeführt ✅
  * Ausgabe erfolgt farbig und klar gegliedert ✅

## [1.5.1] - 2025-07-09

SSH-Commit-Signatur in versioning.py eingebaut
Automatischer Fallback auf GPG oder keine Signatur
Farbige Terminalausgabe zur Signaturmethode
Readme erweitert mit Setup-Anleitung

## [v1.5.0] – 2025-07-08

### 💡 Neue Funktionen
- 🪄 DALL·E-Bildgenerierung per Button direkt im Artikel-Expander
- Automatische Metadaten (Caption, Copyright, Quelle) für KI-generierte Bilder

### 🔧 Änderungen & Fixes
- 🔒 Kritischer Bugfix: Artikel gingen nach DALL·E oder Rewrite verloren → jetzt sichere `save_articles()`-Logik über alle Artikel
- Status-Änderungen, Rewrite und Bilderfassung überschreiben nicht mehr die Gesamtdatei
- Kein `st.rerun()` mehr nach jedem Klick – flüssiger Workflow 

### 📦 Internes
- Neue Datei `utils/dalle_generator.py` für DALL·E-Integration
- Erweiterung der Teststrategie um strukturierte `TEST-CHECKLIST.md`
- Verbesserte Update-Strategie für Einzelartikel bei Bearbeitung

## [v1.4.8] – 2025-07-07

### 💡 Neue Funktionen
- 

### 🔧 Änderungen & Fixes
- Fehlerbehebung bei neuen Release, CHANGELOG wurde nicht angehangen, es wird nun die gesamte Datei übernommen

### 📦 Internes
- 

## [v1.4.7] – 2025-07-07

### 💡 Neue Funktionen
- Automatischer Release-Workflow bei `git tag v*`
- Release-Text aus `CHANGELOG.md` wird extrahiert und als GitHub Release verwendet

### 🔧 Änderungen & Fixes
- Fehlerbehebung bei neuen Release, CHANGELOG wurde nicht angehangen

### 📦 Internes
- Erweiterte `release.yml` zur zuverlässigen Release-Erstellung
- GitHub Actions mit `softprops/action-gh-release`

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
- 📂 Startfilter für Artikelansicht auf „New" voreingestellt für fokussierten Workflow

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
- Statusfilter „Alle" funktioniert jetzt korrekt
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
- Rückmeldung in der App bei Klick auf „Alle Feeds neu laden"

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

----

## [v1.6.0] - 2025-08-15

### 🎨 Komplette UI-Überarbeitung

- **Modernes Tab-basiertes Design** mit Dashboard, Artikel, Feeds, Bilder und Statistiken-Tabs
- **Card-basierte Artikelansicht** ersetzt die alte Tabellenstruktur
- **Gradient-Header** und moderne CSS-Styling für professionelleres Aussehen
- **Responsive Layout** mit verbesserter mobiler Darstellung
- **Status-Badges** mit farbkodierten Indikatoren
- **Toast-Benachrichtigungen** für besseres User-Feedback

### 🔍 Erweiterte Filter- und Suchfunktionen

- **Kombinierte Filter** für Status, Feed und Volltextsuche
- **Live-Suche** durch Titel, Inhalt und Tags
- **Feed-spezifische Filterung** mit Artikelanzahl-Anzeige
- **Session State Management** für persistente Filter-Einstellungen

### 📊 Neues Dashboard

- **Statistik-Karten** mit visuellen Metriken (Gesamt-Artikel, neue Artikel, Feeds, Online-Artikel)
- **Schnellaktionen** für häufige Aufgaben (Feed-Update, Rewrite, Aufräumen)
- **Neueste Artikel Preview** mit Status-Anzeige
- **Übersichtliche Zahlen** mit modernem Design

### 🖼️ Verbesserte Bildverwaltung

- **Dedizierte Bilder-Seite** mit Galerie-Ansicht
- **Erweiterte Bildextraktion** mit Featured Image Detection
- **OpenGraph und Twitter Card** Unterstützung
- **Intelligente Bildfilterung** (Größe, Typ, Blacklist)
- **Metadaten-Bereinigung** mit Fallback-Werten

### 📰 Optimierte Artikelverarbeitung

- **Erweiterte Duplikatserkennung** basierend auf Titel-Ähnlichkeit und URL
- **Verbesserte Volltextextraktion** mit website-spezifischen Selektoren
- **WordPress-Erkennung** für optimierte Content-Extraktion
- **Retry-Mechanismus** mit exponential backoff
- **Bessere Textbereinigung** und Validierung

### 🛠️ Backend-Verbesserungen

- **Strukturiertes Logging** mit Funktions- und Zeilennummern
- **Session State Management** für bessere Performance
- **Verbesserte Fehlerbehandlung** mit spezifischen Error-Messages
- **JSON-Validierung** vor dem Speichern
- **Encoding-Fixes** für internationale Zeichen
- **Memory-optimierte Verarbeitung**

### 📊 Neue Statistiken-Seite

- **Status-Verteilung** mit Prozentanzeigen
- **Feed-Artikel-Übersicht** sortiert nach Anzahl
- **Textstatistiken** (Durchschnitt, Min/Max Wortanzahl)
- **Tag-Häufigkeiten** der meist verwendeten Tags
- **Lesezeit-Berechnungen** (200 Wörter pro Minute)

### 🔧 Technische Verbesserungen

- **UI Helper Functions** in `utils/ui_helpers.py` für wiederverwendbare Komponenten
- **Verbesserte URL-Validierung** und Domain-Erkennung
- **Smart Content Selectors** für verschiedene Website-Typen
- **Robustes Error Handling** mit spezifischen Fehlermeldungen
- **Performance-Optimierungen** durch reduzierte `st.rerun()` Calls
- **Memory-Management** für große Artikel-Listen

### 📱 UX-Verbesserungen

- **Inline-Bearbeitung** von Artikel-Status direkt in der Card-Ansicht
- **Erweiterte Details-Ansicht** mit Collapsible-Bereichen
- **Copy-to-Clipboard** Funktionalität mit formatiertem Text
- **Hover-Effekte** und Animations für bessere Interaktion
- **Breadcrumb-Navigation** in komplexen Ansichten
- **Loading-Spinner** für längere Operationen

### 🗂️ Neue Dateistruktur

```
├── app.py (komplett überarbeitet)
├── main.py (erweiterte Backend-Logik)
├── utils/
│   ├── ui_helpers.py (neue UI-Komponenten)
│   ├── image_extractor.py (verbesserte Bildextraktion)
│   ├── article_extractor.py (erweiterte Artikelextraktion)
│   └── dalle_generator.py (unverändert)
├── pages/
│   ├── 01_feed_manager.py (bestehend)
│   └── log_viewer.py (bestehend)
└── logs/ (verbessertes Logging)
```

### 🔄 Migration & Kompatibilität

- **Vollständige Rückwärtskompatibilität** mit bestehenden JSON-Daten
- **Automatische Datenmigration** für neue Felder (source_name, word_count, etc.)
- **Graceful Degradation** bei fehlenden Feldern
- **Validierung und Reparatur** ungültiger Datenstrukturen

### ⚡ Performance-Optimierungen

- **Lazy Loading** für große Artikel-Listen
- **Effiziente Filtering** ohne komplette Neuladung
- **Optimierte Bildverarbeitung** mit Größen-Caching
- **Reduzierte API-Calls** durch besseres State Management
- **Memory-optimierte JSON-Verarbeitung**

### 🐛 Bugfixes

- **Status-Änderungen** gehen nicht mehr verloren nach Reload
- **Bildmetadaten** werden korrekt gespeichert und angezeigt
- **Duplikat-Artikel** werden zuverlässig erkannt
- **Encoding-Probleme** bei internationalen Zeichen behoben
- **Feed-Namen** werden korrekt in Filter-Dropdown angezeigt
- **Session State** Konflikte bei mehreren Tabs behoben

### 📋 Breaking Changes

- **Alte Tabellen-UI** wurde durch Card-Layout ersetzt
- **Sidebar-Navigation** wurde durch Tab-Navigation ersetzt  
- **Direkte JSON-Manipulation** sollte vermieden werden (neue Validierung)

---

## [v1.5.3] - 2025-07-11

### ✨ Neue Funktionen

- Automatischer Volltextabruf bei zu kurzen Artikeln (< 50 Wörter)
  - Inhalte werden direkt von der Originalseite geladen (ähnlich wie bei der Bildextraktion)
  - Promobil, Camping-News und andere gängige WordPress-Seiten werden unterstützt

- Neue Verwaltungsseite `Feed-Verwaltung` unter `pages/01_feed_manager.py`
  - RSS-Feeds können nun über eine dedizierte Oberfläche hinzugefügt, bearbeitet und gelöscht werden
  - Anzahl verknüpfter Artikel pro Feed wird angezeigt
  - Änderungen werden protokolliert und per `st.rerun()` sofort sichtbar

### 🔧 Verbesserungen

- Feed-Filter in der Artikelübersicht zeigt jetzt die **korrekten Feed-Namen mit Artikelanzahl**
  - Beispiel: „Promobil News (12)“ statt nur „Alle (20)“
  - Basierend auf `source`-Feld im Artikelobjekt

- Verbesserte Logging-Ausgaben bei Feed-Aktionen (hinzufügen, ändern, löschen)

### 📁 Neue Dateien

- `utils/article_extractor.py` – Logik zum Abrufen vollständiger Artikeltexte von Originalseiten
- `pages/01_feed_manager.py` – Eigenständige Verwaltungsseite für RSS-Feeds

### 🛠 Interne Änderungen

- `main.py` erweitert: Automatischer Fallback auf `extract_full_article()` bei zu kurzem Text
- Logging konsolidiert und mit Feed-Aktionen ergänzt



## [v1.5.2] - 2025-07-09

- Fehlerbehandlung bei `CHANGELOG.md`-Doppelungen hinzugefügt
- Signaturlogik robuster (SSH, GPG, fallback)
- Farbige Terminalausgabe verbessert
- dry-run Argument hinzugefügt:
  * Versionsnummer wird berechnet ✅
  * Änderungen (Version, Changelog, Commit, Tag, Push) werden nur angezeigt, nicht ausgeführt ✅
  * Ausgabe erfolgt farbig und klar gegliedert ✅


## [1.5.1] - 2025-07-09

SSH-Commit-Signatur in versioning.py eingebaut
Automatischer Fallback auf GPG oder keine Signatur
Farbige Terminalausgabe zur Signaturmethode
Readme erweitert mit Setup-Anleitung


## [v1.5.0] – 2025-07-08

### 💡 Neue Funktionen
- 🪄 DALL·E-Bildgenerierung per Button direkt im Artikel-Expander
- Automatische Metadaten (Caption, Copyright, Quelle) für KI-generierte Bilder

### 🔧 Änderungen & Fixes
- 🔒 Kritischer Bugfix: Artikel gingen nach DALL·E oder Rewrite verloren → jetzt sichere `save_articles()`-Logik über alle Artikel
- Status-Änderungen, Rewrite und Bilderfassung überschreiben nicht mehr die Gesamtdatei
- Kein `st.rerun()` mehr nach jedem Klick – flüssiger Workflow 

### 📦 Internes
- Neue Datei `utils/dalle_generator.py` für DALL·E-Integration
- Erweiterung der Teststrategie um strukturierte `TEST-CHECKLIST.md`
- Verbesserte Update-Strategie für Einzelartikel bei Bearbeitung

## [v1.4.8] – 2025-07-07

### 💡 Neue Funktionen
- 

### 🔧 Änderungen & Fixes
- Fehlerbehebung bei neuen Release, CHANGELOG wurde nicht angehangen, es wird nun die gesamte Datei übernommen

### 📦 Internes
- 

## [v1.4.7] – 2025-07-07

### 💡 Neue Funktionen
- Automatischer Release-Workflow bei `git tag v*`
- Release-Text aus `CHANGELOG.md` wird extrahiert und als GitHub Release verwendet

### 🔧 Änderungen & Fixes
- Fehlerbehebung bei neuen Release, CHANGELOG wurde nicht angehangen

### 📦 Internes
- Erweiterte `release.yml` zur zuverlässigen Release-Erstellung
- GitHub Actions mit `softprops/action-gh-release`

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
