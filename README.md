# 📰 RSS News Bot

Ein intelligentes Tool zum Einlesen, Umschreiben und Veröffentlichen von Artikeln aus RSS-Feeds – mit automatischer Tag-Erkennung, KI-unterstütztem Rewrite via GPT-4, Bildextraktion aus Originalartikeln und optionaler DALL·E-Bildgenerierung.

![Version](https://img.shields.io/badge/version-1.5.0-blue)
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

## 🔐 Signierte Commits und Tags

Dieses Projekt unterstützt **signierte Commits und Tags über SSH** (alternativ GPG). GitHub zeigt für signierte Beiträge ein ✅ **Verified**-Badge an.

### 🛠 Voraussetzungen

1. Ein SSH-Key (z. B. `~/.ssh/id_ed25519`) ist generiert:
   
   ```bash
   ssh-keygen -t ed25519 -C "deine@email.de"
    ```

2. Key bei GitHub an zwei Stellen hinterlegen:
    * 🔏 Signing Keys (für Commit-Signatur)
    * 🔐 SSH Keys (für Git-Push/Pull)

3. Git-Konfiguration

    ```bash
    git config --global gpg.format ssh
    git config --global user.signingkey ~/.ssh/id_ed25519.pub
    git config --global commit.gpgsign true
    ```

4. Optional: SSH config zur Sicherheit:
    
    ```bash
    # ~/.ssh/config
    Host github.com
        HostName github.com
        User git
        IdentityFile ~/.ssh/id_ed25519
        IdentitiesOnly yes
    ```
---

🧰 Nutzung von versioning.py
Die Datei versioning.py automatisiert:

    * ⬆️ Versionsnummer erhöhen
    * 📄 CHANGELOG.md und __version__.py aktualisieren
    * 🔒 Commit signieren (SSH oder GPG)
    * 🏷 Git-Tag signieren
    * ⬆️ Push zu GitHub

Beispiel:

    ```bash
    python versioning.py create --level minor --push
    ```

* Wählt automatisch SSH oder GPG zur Signatur
* Optional --no-sign, um ohne Signatur zu arbeiten
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

## ▶️ Starten der App

streamlit run app.py

