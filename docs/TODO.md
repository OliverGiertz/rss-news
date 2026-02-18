# ToDo (Ein-Entwickler Setup)

## Jetzt
- [ ] GitHub Project #3 Felder/Views fuer Neustart vereinheitlichen
- [ ] Alte/obsolet gewordene Issues kennzeichnen (z. B. User-Verwaltung)
- [ ] Redirect `news.vanityontour.de -> vanityontour.de` aktiv halten
- [ ] Wiki-Basis fertigstellen und verlinken

## MVP
- [x] Neues Backend-Skelett (`backend/`) aufsetzen (FastAPI)
- [x] Datenmodell in SQLite anlegen
- [x] Feed-Ingestion Service bauen (ETag/Last-Modified)
- [x] Duplikaterkennung ueber `source_url`, `guid`, Hash
- [x] Login mit 1 Admin-Account implementieren
- [ ] Artikel-Review-Maske mit Statusworkflow
- [ ] WordPress-Publisher als separaten Service implementieren

## Recht/Qualitaet
- [ ] Source-Policy in DB + Admin-UI abbilden
- [ ] Pflichtfelder je Quelle erzwingen (Autor, URL, Lizenz, Hinweise)
- [ ] Auto-Block bei fehlender Lizenzinfo
- [ ] Pro Artikel Attribution-Block generieren

## Betrieb
- [ ] Systemd-Service(s) fuer API/Worker erstellen
- [ ] Nginx-Routing fuer neue App einrichten
- [ ] Healthcheck-Endpunkte + Monitoring einrichten
- [ ] Backup/Restore fuer DB dokumentieren

## Spaeter
- [ ] Passkey/WebAuthn evaluieren und optional einfuehren
- [ ] Migration auf PostgreSQL bewerten
- [ ] Teilautomatische Freigabe-Regeln definieren
