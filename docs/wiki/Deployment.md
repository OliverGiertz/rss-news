# Deployment (Hetzner + CloudPanel)

## Umgebung
- Host: Hetzner
- Reverse Proxy: Nginx via CloudPanel
- Ziel-Domain: `news.vanityontour.de`

## Aktueller Zustand
- Domain ist bis zum Go-Live auf `https://vanityontour.de` umgeleitet.

## Zielzustand
- `news.vanityontour.de` zeigt auf neue App (interner Port, z. B. `127.0.0.1:8501`)
- API/Worker laufen als systemd-Services
- TLS bleibt ueber CloudPanel/Nginx

## Mindest-Checks nach Deployment
- `curl -I https://news.vanityontour.de`
- Login erreichbar
- Feed-Import laeuft
- WordPress-Testpublikation (pending) erfolgreich
