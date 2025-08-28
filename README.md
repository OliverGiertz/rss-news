# 📰 RSS News Bot

Ein intelligentes Tool zum Einlesen, Umschreiben und Veröffentlichen von Artikeln aus RSS-Feeds – mit automatischer Tag-Erkennung, KI-unterstütztem Rewrite via GPT-4, Bildextraktion aus Originalartikeln und optionaler DALL·E-Bildgenerierung.

![Version](https://img.shields.io/badge/version-1.5.2-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-yellow)
![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b)

---

## 🚀 Features

- 📡 **RSS-Feeds verwalten** (hinzufügen, aktualisieren)
- ✍️ **Artikel automatisch umschreiben** mit GPT-4
- 🏷️ **Tags automatisch generieren**
- 🖼️ **Bilder aus Originalartikeln extrahieren**
- 🪄 **Optionales DALL·E-Bild generieren**
- 🔧 **Bearbeiten von Bildmetadaten**
- 🗂️ **Statusverwaltung der Artikel (New, Rewrite, Process, etc.)**
- 📜 **Log-Viewer-Seite integriert**
- 📥 **Export zur Veröffentlichung auf WordPress vorbereitet**
- 📋 Artikeltabelle mit Status-Filter
- 🔍 Artikel-Expander mit Rewrite, Tags & Bildern
- 🪄 Button für KI-Bildgenerierung


---

## 🧱 Projektstruktur

ss-news/
├── app.py # Haupt-UI mit Streamlit
├── main.py # Logik für Feed-Import und Verarbeitung
├── utils/
│ └── image_extractor.py # Bilder aus Originalartikeln extrahieren
│ └── dalle_generator.py # DALL·E-Integration (KI-Bild)
├── pages/
│ └── log_viewer.py # UI zur Anzeige der Logs
├── data/
│ └── articles.json # Gespeicherte Artikel
│ └── feeds.json # Gespeicherte Feed-URLs
├── logs/
│ └── rss_tool.log # Logging der Verarbeitung
├── versioning.py # CLI-Tool zur Versionierung & Release
├── TEST-CHECKLIST.md # Manuelle Prüfliste für Releases
├── version.py # Aktuelle Version
└── CHANGELOG.md # Änderungsprotokoll


---

## ⚙️ Installation

```bash
git clone https://github.com/OliverGiertz/rss-news.git
cd rss-news
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Update
Ein Update Script findest du hier: https://gist.github.com/OliverGiertz/ad33ae3de9aa1c1163dad5fe8affb6ca

```bash
bash update.sh
```


## ▶️ Starten der App

streamlit run app.py

---

## 🔐 Konfiguration (.env)

Lege eine `.env` im Projekt an (siehe `.env.example`). Erforderliche Variablen:

- `WP_BASE_URL`: Basis-URL deiner WordPress-Seite (z. B. https://example.com)
- Authentifizierung (eine Option wählen):
  - `WP_AUTH_BASE64`: Bevorzugt. Base64 von `username:application_password`
  - oder `WP_USERNAME` und `WP_PASSWORD`: Benutzer + Anwendungspasswort
- Optional: `OPENAI_API_KEY` für das Umschreiben von Artikeln

Hinweis: Der Code liest ausschließlich aus `.env`. Es gibt keine hartkodierten Standard-Credentials.
