# rss-news (Rebuild)

`rss-news` wird als bestehendes Repository weitergefuehrt und schrittweise zu einer robusten, rechtssicheren News-Pipeline neu aufgebaut.

Aktueller Stand:
- Alte Streamlit-App wird nicht produktiv genutzt.
- `news.vanityontour.de` wird bis zum Go-Live der neuen App auf `https://vanityontour.de` umgeleitet.
- Planung, Doku und Wiki werden als Grundlage fuer den Neuaufbau gepflegt.

## Ziele
- RSS-gestuetzte Artikelverarbeitung mit klaren Quellregeln
- Rechtssichere Nutzung (Quellen, Attribution, Lizenzinformationen)
- Zuverlaessige Automatisierung auf Hetzner
- Publikation nach WordPress (IONOS aktuell, spaeter offen)
- Zugriff nur nach Login (zunaechst User/Password)

## Architektur-Richtung (MVP)
- Backend: `Python + FastAPI`
- Jobs: Queue-Worker (z. B. Redis + RQ/Celery)
- Daten: SQLite fuer MVP, spaeter optional PostgreSQL
- Auth: Session-Login mit einem Admin-User
- Publishing: WordPress REST API (Status zunaechst `pending`)

Details: `docs/PROJECT_PLAN.md`

## Projektsteuerung
- GitHub Project: `https://github.com/users/OliverGiertz/projects/3/views/1`
- Dieses Board ist die zentrale Steuerung fuer ToDos, Bugs, Verbesserungen.
- Wiki-Struktur liegt unter `docs/wiki/`.

## Dokumentation
- Projektplan: `docs/PROJECT_PLAN.md`
- ToDo-Liste: `docs/TODO.md`
- Quell- und Lizenzpolicy: `docs/SOURCE_POLICY.md`
- Wiki Home: `docs/wiki/Home.md`

## Lokale Entwicklung (Legacy-Code)
Der vorhandene Legacy-Stand kann weiterhin lokal gestartet werden:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Hinweis: Diese App ist funktional historisch und wird durch die neue Architektur ersetzt.

## Deployment-Zielbild
- Betrieb auf Hetzner
- Reverse Proxy via CloudPanel/Nginx
- Produktive Domain: `news.vanityontour.de`
- Bis zur Fertigstellung: Redirect auf `https://vanityontour.de`

## Sicherheit
- Keine Secrets im Repository
- `.env` lokal/auf Server, nie committen
- Auth-Pflicht fuer die neue WebApp
- spaeter optional: Passkeys/WebAuthn

## Rechtlicher Hinweis
Dieses Projekt verarbeitet nur Quellen mit dokumentierter Nutzungsgrundlage. Vor produktiver Nutzung ist eine finale rechtliche Pruefung der ausgewaehlten Feeds notwendig.

