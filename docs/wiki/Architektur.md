# Architektur

## Zielarchitektur
- API: FastAPI
- Worker: Queue-basierte Hintergrundjobs
- DB: SQLite (MVP), spaeter optional PostgreSQL
- Publisher: WordPress REST API
- Frontend/Admin: schlanke Web-UI mit Login

## Pipeline
1. Feed Fetch
2. Parse + Normalize
3. Deduplicate
4. Enrichment (Rewrite/Tags)
5. Legal/Policy Check
6. Publish (pending)

## Datenobjekte (MVP)
- `sources`
- `feeds`
- `articles`
- `article_versions`
- `runs`
- `policy_checks`

## Nichtziele (MVP)
- Multi-User und Rollen
- Vollautomatische Freigabe ohne Review
- Komplexe externe SSO-Integration
