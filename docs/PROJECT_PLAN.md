# Projektplan (Neustart)

## Leitentscheidungen
- Bestehendes Repository wird weiterverwendet.
- Kein harter Endtermin: lauffaehig werden, dann iterativ verbessern.
- Hetzner bleibt Laufzeitplattform.
- WordPress (IONOS) bleibt vorerst Ziel fuer Publikation.
- Auth initial nur mit einem User/Password.

## Zielbild
Eine modulare News-Pipeline mit klaren Stufen:
1. Feed-Ingestion
2. Inhaltsanalyse und Normalisierung
3. Rewrite/Anreicherung
4. Legal- und Qualitaetschecks
5. WordPress-Publikation (`pending`)
6. Monitoring/Logging

## Grobe Zeitplanung (ohne Fixtermine)
- Phase 0: ca. 1 Woche
- Phase 1: ca. 2-4 Wochen
- Phase 2: ca. 2-3 Wochen
- Phase 3: fortlaufend

## Phasen

### Phase 0 - Grundlagen (jetzt)
- Doku und Wiki strukturieren
- Source-Policy definieren
- Redirect fuer `news.vanityontour.de` setzen
- GitHub Project als zentrale Planung scharfstellen

### Phase 1 - MVP Core
- Neues FastAPI-Projektgeruest
- SQLite-Datenmodell (feeds, articles, runs, source_policy)
- Feed-Import mit Duplikaterkennung
- Admin-Login (ein User)
- Manuelle Review vor Publish

### Phase 2 - Automation
- Job-Queue (asynchron)
- Regelbasierte Scheduler
- Retry/Dead-Letter-Handling
- Robustes Error-Reporting

### Phase 3 - Compliance und Skalierung
- Source-Whitelisting mit Pflichtfeldern
- Pflicht-Attribution pro Artikel
- Qualitaetsmetriken und Audit-Logs
- Optional: Passkey/WebAuthn

## Architekturprinzipien
- Idempotente Jobs
- Trennung von UI, API, Worker
- Strikte Validierung bei Quell-/Lizenzdaten
- Expliziter Publish-Schritt, kein blindes Autoposting

## Risiken
- Lizenz-/Nutzungsbedingungen je Quelle variieren stark
- Feeds aendern Struktur/Verfuegbarkeit
- WordPress-API und Auth koennen regressionsanfaellig sein

## Erfolgsmetriken
- Zeit von Feed-Eingang bis Review-Ready
- Quote sauber attribuierter Artikel
- Fehlerrate pro Pipeline-Stufe
- Anzahl manueller Eingriffe pro Woche
