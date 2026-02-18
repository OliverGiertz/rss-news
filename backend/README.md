# Backend Skeleton (FastAPI)

Dieses Verzeichnis enthaelt das technische Grundgeruest fuer den Rebuild von `rss-news`.

## Start (lokal)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8501
```

## Admin UI
- Login: `http://127.0.0.1:8501/admin/login`
- Dashboard: `http://127.0.0.1:8501/admin/dashboard`

## Environment
- Datei: `backend/.env`
- Vorlage: `backend/.env.example`

## Endpoints
- `GET /health` - Healthcheck
- `POST /auth/login` - Login mit Admin-User
- `POST /auth/logout` - Logout
- `GET /auth/me` - Aktiver User
- `GET /api/protected` - Geschuetzter Test-Endpoint
- `GET /api/pipeline/status` - Basisstatus inkl. Datensatzzaehler
- `GET /api/sources` - Quellenliste
- `POST /api/sources` - Quelle anlegen
- `GET /api/sources/{source_id}/policy-check` - Policy-Pruefung fuer Quelle
- `GET /api/feeds` - Feedliste
- `POST /api/feeds` - Feed anlegen
- `GET /api/feeds/{feed_id}/policy-check` - Policy-Pruefung fuer Feed
- `GET /api/runs` - Import-/Job-Runs anzeigen
- `GET /api/runs/{run_id}` - Detailansicht eines Runs
- `POST /api/runs` - Run starten
- `POST /api/runs/{run_id}/finish` - Run abschliessen
- `GET /api/articles` - Artikel anzeigen
- `GET /api/articles/{article_id}` - Artikeldetail
- `POST /api/articles/upsert` - Artikel idempotent anlegen/aktualisieren
- `POST /api/articles/{article_id}/transition` - Statuswechsel nach Workflow-Regeln
- `POST /api/articles/{article_id}/review` - Review-Entscheidung (approve/reject)
- `POST /api/ingestion/run` - Feed-Ingestion starten (optional pro Feed)

## Datenbank
- SQLite-Datei unter `backend/data/rss_news.db`
- Tabellen werden beim App-Start initialisiert.
- Tabellen: `sources`, `feeds`, `runs`, `articles`
- Dedupe-Strategie Artikel: `source_url` -> `(feed_id, source_article_id)` -> `source_hash`

## Policy-Enforcement
- Ingestion blockiert Feeds automatisch, wenn die zugeordnete Quelle nicht policy-konform ist.
- Mindestanforderungen: `risk_level=green`, `terms_url`, `license_name`, `last_reviewed_at`, `is_enabled=1`.
- Pro importiertem Artikel wird ein `attribution`-Block in `meta_json` gespeichert.

## Review-Workflow
- Statuskette: `new -> review -> approved -> published`
- Ablehnung im Review setzt auf `rewrite`
- Ungueltige Statuswechsel werden per API blockiert

## Verifikation
```bash
python -m unittest backend.tests.test_db_repositories
python -m unittest backend.tests.test_ingestion
python -m unittest backend.tests.test_api_auth
```

## CI / Online-Auswertung
- GitHub Actions Workflow: `.github/workflows/test.yml`
- Fuehrt Tests inkl. Coverage auf Push/PR gegen `main` aus.

## Hetzner Smoketest
```bash
BASE_URL="https://news.vanityontour.de" \
APP_ADMIN_USERNAME="admin" \
APP_ADMIN_PASSWORD="..." \
bash scripts/smoke_backend.sh
```

## Hinweis
Passwort-Hashing und CSRF/Rate-Limit sind als naechste Ausbaustufe vorgesehen.
