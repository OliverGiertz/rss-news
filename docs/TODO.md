# ToDo (Ein-Entwickler Setup)

## Jetzt
- [ ] WordPress Beitragsbild-Upload implementieren (`featured_media` aus ausgewaehltem Hauptbild)
- [ ] WordPress-HTML-Ausgabe pro Artikel weiter verbessern (sauberes Layout, Quellenblock, Shortcodes falls noetig)
- [ ] Publisher Fehlertexte fuer WP-Auth/Media/API in UI klarer darstellen
- [ ] End-to-end Publish Smoke-Test dokumentieren (lokal + Hetzner)

## MVP
- [x] Neues Backend-Skelett (`backend/`) aufsetzen (FastAPI)
- [x] Datenmodell in SQLite anlegen
- [x] Feed-Ingestion Service bauen (ETag/Last-Modified)
- [x] Duplikaterkennung ueber `source_url`, `guid`, Hash
- [x] Login mit 1 Admin-Account implementieren
- [x] Artikel-Review-Maske mit Statusworkflow
- [x] WordPress-Publisher als separaten Service implementieren (Queue + Retry + Mapping)
- [x] Bildvorschau + manuelle Bildauswahl im Admin-UI
- [x] Automatische Bildreduktion/Scoring fuer Presseportal-Quellen
- [x] Artikel-Datum + Relevanzscore im UI/Export

## Recht/Qualitaet
- [x] Source-Policy in DB + Admin-UI abbilden
- [x] Pflichtfelder je Quelle erzwingen (Autor, URL, Lizenz, Hinweise)
- [x] Auto-Block bei fehlender Lizenzinfo
- [x] Pro Artikel Attribution-Block generieren
- [x] Manuelle Rechtsfreigabe als Publish-Gate

## Betrieb
- [ ] Systemd-Service(s) fuer API/Worker erstellen
- [ ] Nginx-Routing fuer neue App einrichten
- [ ] Healthcheck-Endpunkte + Monitoring einrichten
- [ ] Backup/Restore fuer DB dokumentieren

## Spaeter
- [ ] Passkey/WebAuthn evaluieren und optional einfuehren
- [ ] Migration auf PostgreSQL bewerten
- [ ] Teilautomatische Freigabe-Regeln definieren
- [ ] KI-Rewrite mit Prompt-Versionierung + Qualitaetsmetriken wieder aktivieren
