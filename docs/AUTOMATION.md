# Automatischer Pipeline-Betrieb

## Überblick

Import, Bewertung und Rewrite laufen automatisch. **Veröffentlicht wird erst nach
deiner redaktionellen Freigabe im Portal** — siehe `docs/KI-VO.md` für den
rechtlichen Hintergrund (Art. 50 Abs. 4 KI-VO).

```
N8N (2× täglich, 08:00 + 16:00 Uhr)
  └─► POST /api/n8n/pipeline  (X-API-Key Header)
        ├── RSS Ingestion (alle aktivierten Feeds)
        ├── Relevanz-Score per GPT (0–100)
        │     ├── Score ≥ 80 → Rewrite + Tags → Status "Wartet auf Freigabe"
        │     ├── Score 60–79 → Telegram-Warnung + manueller Override möglich
        │     └── Score < 60 → Abgelehnt + tägliche Telegram-Liste
        └── Pipeline-Zusammenfassung via Telegram

Danach, manuell im Portal (news.vanityontour.de/admin/freigabe):
  Artikel lesen → [✅ Freigeben] / [✏️ Neu schreiben] / [❌ Verwerfen]
        ├── Stempel: Prüfer + Systemzeit (nicht editierbar)
        ├── Publish-Slot reservieren
        └── WordPress-Beitrag anlegen (Status "future" zum Slot)
```

Vor der Freigabe existiert **kein** WordPress-Beitrag und **kein** belegter
Publish-Slot. Wer das Gate abschalten will: `EDITORIAL_REVIEW_REQUIRED=false` —
dann gilt wieder der alte, vollautomatische Ablauf, und der KI-Hinweistext auf
dem Blog muss angepasst werden.

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

### Artikel wartet auf Freigabe
Wenn ein Artikel umgeschrieben wurde und geprüft werden muss:

```
📝 Neuer Artikel wartet auf Freigabe
📰 [Artikel-Titel]
🟢 Relevanz-Score: 87/100
📄 312 Wörter
🏷 #VanLife #Camping #Wohnmobil
🔗 Diesen Artikel prüfen
📋 Alle wartenden Artikel
Erst nach der Freigabe geht der Beitrag nach WordPress und wird eingeplant.
```

Zwei Links: der erste springt direkt in den gemeldeten Artikel, der zweite auf
die Freigabe-Warteschlange `/admin/freigabe`, wenn mehrere Artikel anstehen.

Diese Nachricht trägt **bewusst keinen Freigabe-Button**: Der Sinn des Gates ist,
dass der Artikel gelesen wurde. Freigeben, neu schreiben und verwerfen passiert
auf der Artikelseite im Portal, einen Tipp auf den Link entfernt.

### Freigegeben und eingeplant
Bestätigung nach der Freigabe im Portal:

```
✅ Freigegeben und eingeplant
📰 [Artikel-Titel]
👤 Geprüft von: admin
📅 Veröffentlichung: Mo, 24.08.2026 um 09:00 Uhr
🔗 Beitrag in WordPress
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
| 80–100 | Rewrite, danach Warteschlange „Wartet auf Freigabe" |
| 60–79 | Telegram-Warnung, manueller Override (führt ebenfalls in die Warteschlange) |
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

- Standardmäßig **09:00, 12:00, 15:00 und 18:00 Uhr**
- Maximal **4 Beiträge pro Tag** im Standard-Setup
- Zwischen den Slots liegen jeweils **3 Stunden Abstand**
- Veröffentlichungsfenster: **09:00 bis 19:00 Uhr** (`Europe/Berlin`)
- Gleichmäßig über die Woche verteilt
- Der Slot wird **im Moment der Freigabe** reserviert, nicht schon beim Rewrite —
  ein wartender Artikel blockiert also keinen Sendeplatz
- Der zugeteilte Slot erscheint in der Freigabe-Bestätigung per Telegram
- WordPress veröffentlicht den Beitrag zum Slot selbst (Status `future`)

### Termin bei der Freigabe wählen

Der Standard bleibt „Nächster freier Termin" — der Artikel hängt sich hinten an
die Warteschlange. Für Themen, die nicht acht Wochen warten können (Messeberichte
etwa), gibt es daneben:

| Auswahl | Was passiert |
|---------|--------------|
| Nächster freier Termin | Erster freier Rastertermin ab morgen (Standard) |
| Heute | Nächste freie Rasterzeit heute, mindestens 20 Minuten voraus |
| Morgen | Erste freie Rasterzeit morgen |
| Sofort veröffentlichen | Geht direkt live, WordPress-Status `publish` |
| Datum und Uhrzeit wählen | Frei wählbar, wird genau so übernommen |

**Es wird nie etwas verschoben.** Ist die gewünschte Rasterzeit belegt, bekommt
der Artikel einen **Sondertermin** auf der halben Stunde zwischen zwei
Rasterzeiten (also 10:30, 13:30, 16:30). An dem Tag erscheinen dann fünf statt
vier Beiträge; alle anderen Termine bleiben, wo sie sind. Ein Sondertermin hält
mindestens 45 Minuten Abstand zu jedem anderen Beitrag, deshalb kommen 09:30 oder
11:30 neben einem 09:00/12:00-Raster nicht in Frage.

Ist heute keine Zeit mehr frei, wird „Heute" zu „Sofort" — mit entsprechendem
Hinweis in der Bestätigung.

Wird ein bereits eingeplanter Artikel vorgezogen, fällt sein alter Rastertermin
einfach frei und der nächste Pipeline-Lauf setzt den nächsten Artikel hinein. Die
Warteschlange wird dadurch nicht länger.

Termine ändern lassen sich an zwei Stellen:

- **Artikel-Detailseite** — Kasten „Veröffentlichungstermin" bei freigegebenen Artikeln
- **`/admin/schedule`** — freier Rastertermin im Kalender ist anklickbar und
  führt auf eine Liste der eingeplanten Artikel („Hierhin setzen"); Sondertermine
  stehen in einer eigenen Spalte

Scheitert das Umdatieren in WordPress, bleibt der alte Termin stehen — DB und
WordPress laufen nicht auseinander.

Einstellbar via:
```
PIPELINE_MAX_DRAFTS_PER_DAY=4
PIPELINE_PUBLISH_HOURS=9,12,15,18
PIPELINE_PUBLISH_START_HOUR=9
PIPELINE_PUBLISH_END_HOUR=19
PIPELINE_PUBLISH_MIN_GAP_HOURS=3
```

---

## API-Endpunkte (N8N / extern)

Alle externen Endpunkte benötigen den Header `X-API-Key: <N8N_API_KEY>`.

| Methode | Endpunkt | Funktion |
|---------|----------|----------|
| `POST` | `/api/n8n/pipeline` | Komplette Pipeline starten |
| `POST` | `/api/n8n/ingest` | Nur RSS-Import (ohne Rewrite) |

---

## Deployment (Hetzner)

**Achtung: Das Deployment läuft derzeit NICHT automatisch.** Stand 24.08.2026
geprüft — `.github/workflows/deploy.yml` ist GitHub-Actions-Syntax, das Remote
ist aber Forgejo (`git.giertz.biz`), und es greift kein Runner. Zusätzlich hat
der Server keinen Deploy-Key für das Repo: `git pull origin main` scheitert dort
mit `Permission denied (publickey)`. Ein Push auf `main` bewirkt also nichts.

Bis das repariert ist, wird von Hand deployt. Weg über ein Git-Bundle, damit die
Historie auf dem Server korrekt bleibt (statt Dateien zu kopieren und die Stände
unbemerkt auseinanderdriften zu lassen):

```bash
# lokal, <alt> = Commit, auf dem der Server steht
git bundle create /tmp/deploy.bundle <alt>..main
scp /tmp/deploy.bundle hetzner:/root/deploy.bundle

# auf dem Server
cd /opt/rss-news
git pull /root/deploy.bundle main
systemctl restart rss-news-api      # zieht die DB-Migration automatisch nach
```

`pip install` nur, wenn sich `requirements.txt` oder `backend/requirements.txt`
tatsächlich geändert haben.

Dienst: `rss-news-api` (systemd), `WorkingDirectory=/opt/rss-news`,
uvicorn auf `127.0.0.1:8790`, davor der Reverse Proxy.

**Vor jedem Deploy die Datenbank sichern:**

```bash
ssh hetzner "cp -a /opt/rss-news/backend/data/rss_news.db \
  /root/rss-news-backups/rss_news.db.$(date +%F-%H%M)"
```

Dauerhafte Reparatur (offen): entweder einen Deploy-Key auf dem Server
hinterlegen und in Forgejo eintragen, oder den Workflow nach
`.forgejo/workflows/` umziehen und einen Runner registrieren.

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
