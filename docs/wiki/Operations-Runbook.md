# Operations Runbook

## Daily Checks
- App erreichbar
- Queue/Worker aktiv
- Letzte Feed-Laeufe erfolgreich
- Keine auffaelligen Fehler im Log

## Incident: Feed-Import faellt aus
1. RSS-Quelle erreichbar?
2. Parser-Fehler im Log?
3. Rate Limits oder Blockaden?
4. Retry-Queue pruefen

## Incident: WordPress Publish faellt aus
1. WP API erreichbar?
2. Credentials gueltig?
3. Payload-Validation/Tag-Fehler?
4. Artikel in `pending` statt `failed` markieren, wenn unklar

## Backups
- SQLite-Dump taeglich
- Konfiguration und `.env` sicher sichern
