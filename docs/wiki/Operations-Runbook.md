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

## Incident: Telegram-Buttons reagieren nicht / Befehle ignoriert

**Ursache:** N8N "App Release - Telegram Bot"-Workflow hat den Webhook überschrieben.

**Prüfen:**
```bash
curl -s "https://api.telegram.org/bot8403822424:AAGp8gZoNIGZv3IIan45q7P9HfM868qzXi4/getWebhookInfo" | python3 -m json.tool
```
→ `url` muss auf `https://news.vanityontour.de/telegram/webhook` zeigen
→ `allowed_updates` muss `["message", "callback_query"]` enthalten

**Webhook zurücksetzen:**
```bash
curl -s -X POST "https://api.telegram.org/bot8403822424:AAGp8gZoNIGZv3IIan45q7P9HfM868qzXi4/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://news.vanityontour.de/telegram/webhook","allowed_updates":["message","callback_query"],"secret_token":"RWWAaBwfCUX9Y573JVkB9zAeloHsZZoruXOBBgUtsvU"}'
```

Vollständige Dokumentation: `projects/webhook/telegram-webhook-reset.md`

## Backups
- SQLite-Dump taeglich
- Konfiguration und `.env` sicher sichern
