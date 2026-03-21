# Automatischer Pipeline-Betrieb

## Überblick

Das System läuft vollautomatisch und benötigt nur noch gelegentliche Telegram-Interaktion.

```
N8N (2× täglich, 08:00 + 16:00 Uhr)
  └─► POST /api/n8n/pipeline  (X-API-Key Header)
        ├── RSS Ingestion (alle aktivierten Feeds)
        ├── Relevanz-Score per GPT (0–100)
        │     ├── Score ≥ 80 → Rewrite + WP-Draft + Telegram
        │     ├── Score 60–79 → Telegram-Warnung + manueller Override möglich
        │     └── Score < 60 → Abgelehnt + tägliche Telegram-Liste
        └── Pipeline-Zusammenfassung via Telegram
```

---

## Einrichtung

### 1. Umgebungsvariablen setzen

Kopiere `backend/.env.example` nach `backend/.env` und fülle alle Felder aus:

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Wichtige Variablen:

| Variable | Beschreibung |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot-Token von @BotFather |
| `TELEGRAM_CHAT_ID` | Deine persönliche Chat-ID |
| `TELEGRAM_WEBHOOK_SECRET` | Zufälliger String (≥ 20 Zeichen) |
| `N8N_API_KEY` | Starker zufälliger API-Key |
| `OPENAI_API_KEY` | OpenAI API-Key |
| `WP_BASE_URL` | WordPress-URL |
| `WP_USERNAME` | WordPress-Benutzername |
| `WP_PASSWORD` | WordPress App-Passwort |

### 2. Telegram-Webhook registrieren

Nach dem Deployment einmalig aufrufen:

```bash
curl -X POST https://news.vanityontour.de/api/telegram/setup-webhook \
  -H "Cookie: rss_news_session=<dein-session-token>"
```

Oder über die Admin-UI: Settings → Telegram Webhook einrichten.

### 3. N8N Workflow einrichten

In N8N einen neuen Workflow erstellen:

**Trigger:** Cron
- Zeitplan 1: `0 8 * * *` (täglich 08:00)
- Zeitplan 2: `0 16 * * *` (täglich 16:00)

**Aktion:** HTTP Request
- Method: `POST`
- URL: `https://news.vanityontour.de/api/n8n/pipeline`
- Header: `X-API-Key: <dein-n8n-api-key>`

**Fehlerbehandlung:** Bei HTTP-Fehler → E-Mail/Telegram-Alert

---

## Telegram-Befehle

| Befehl | Funktion |
|--------|----------|
| `/run` | Pipeline manuell starten |
| `/rejected` | Abgelehnte Artikel der letzten 3 Tage anzeigen |
| `/status` | Aktuellen Pipeline-Status |
| `/help` | Alle Befehle anzeigen |

---

## Telegram-Benachrichtigungen

### Neuer Draft erstellt
Wenn ein Artikel erfolgreich verarbeitet wurde:

```
✅ Neuer Draft erstellt
📰 [Artikel-Titel]
🟢 Relevanz-Score: 87/100
📅 Vorgeschlagene Veröffentlichung: Mo, 24.03.2026 um 09:00 Uhr
🏷 #VanLife #Camping #Wohnmobil
🔗 Draft in WordPress öffnen

  [✏️ Neu schreiben]  [❌ Verwerfen]
```

### Relevanz-Warnung (Score 60–79)
```
⚠️ Artikel mit niedrigem Relevanz-Score
📰 [Artikel-Titel]
🟡 Score: 72/100
💬 Artikel behandelt hauptsächlich...
🔗 Originalartikel

  [➕ Trotzdem verarbeiten]  [❌ Ablehnen]
```

### Abgelehnte Artikel (Ende jedes Runs)
Liste aller abgelehnten Artikel mit Override-Buttons für jeden einzelnen.

---

## Relevanz-Score

Der GPT-basierte Score bewertet die Themenrelevanz für den VanLife/Camping-Blog:

| Score | Aktion |
|-------|--------|
| 80–100 | Automatisch verarbeiten |
| 60–79 | Telegram-Warnung, manueller Override |
| 0–59 | Automatisch abgelehnt |

Themen die hoch scored werden: Campingplätze, Stellplätze, Wohnmobile, Van-Ausbau,
Outdoor-Equipment, Wandern, Naturreisen, Roadtrips, Camping-Tipps.

Schwellwerte sind in `.env` konfigurierbar:
```
PIPELINE_RELEVANCE_AUTO=80
PIPELINE_RELEVANCE_WARN=60
```

---

## Veröffentlichungsplan

- Maximal **2 Beiträge pro Tag**
- Bevorzugte Zeiten: **09:00 und 14:00 Uhr** (CET)
- Gleichmäßig über die Woche verteilt
- Der Vorschlag erscheint in der Telegram-Nachricht
- Manuell in WordPress setzen oder über WP Scheduling-Plugin automatisieren

Einstellbar via:
```
PIPELINE_MAX_DRAFTS_PER_DAY=2
PIPELINE_PUBLISH_HOURS=9,14
```

---

## API-Endpunkte (N8N / extern)

Alle externen Endpunkte benötigen den Header `X-API-Key: <N8N_API_KEY>`.

| Methode | Endpunkt | Funktion |
|---------|----------|----------|
| `POST` | `/api/n8n/pipeline` | Komplette Pipeline starten |
| `POST` | `/api/n8n/ingest` | Nur RSS-Import (ohne Rewrite) |

---

## Deployment (Hetzner via GitHub)

Das Deployment läuft automatisch über GitHub Actions beim Push auf `main`:

1. GitHub Action führt Tests aus
2. Bei Erfolg: SSH-Deploy auf Hetzner
3. `pip install -r requirements.txt`
4. Systemd-Dienst `rss-app` neu starten

Workflow-Dateien: `.github/workflows/test.yml` und `.github/workflows/deploy.yml`

---

## Troubleshooting

**Pipeline läuft, aber keine Telegram-Nachrichten:**
- `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` prüfen
- Webhook-Status prüfen: `GET https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

**N8N bekommt 401:**
- `N8N_API_KEY` in `.env` und N8N-Workflow-Header müssen übereinstimmen

**Alle Artikel werden abgelehnt:**
- `PIPELINE_RELEVANCE_WARN` temporär auf 40 senken zum Testen
- Über `/rejected` + Override-Button manuell testen

**Artikel werden doppelt importiert:**
- Deduplication läuft über `source_url` (eindeutig). Bereits verarbeitete Artikel werden nie erneut als Draft angelegt.
