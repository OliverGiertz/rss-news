# Security und Auth

## Mindestanforderungen
- Zugriff auf die WebApp nur mit Login
- Ein aktiver Admin-User (kein Rollenmodell im MVP)
- Passwort nicht im Repo, nur als Secret auf Server

## Empfohlene Umsetzung
- Session-basierte Auth (HTTP-only Cookies)
- Passwort gehasht (Argon2 oder bcrypt)
- Rate Limiting auf Login-Endpunkt
- CSRF-Schutz fuer Form-Aktionen

## Spaeter (optional)
- Passkey/WebAuthn als zusaetzlicher Login-Faktor
- IP-Allowlist fuer Admin-Zugang
