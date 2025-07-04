# 📰 RSS Artikel Manager

Ein Python-Webtool, das RSS-Artikel automatisch einliest, per ChatGPT umschreibt und mit Tags versieht. Die Artikel lassen sich nach Status filtern und über eine tabellarische Streamlit-Oberfläche verwalten.

---

## 🚀 Features

- Verwaltung von RSS-Feeds direkt in der Weboberfläche
- Artikel laden, duplikatfrei speichern und anzeigen
- Artikelstatus: `New`, `Rewrite`, `Process`, `Online`, `On Hold`, `Trash`
- Artikel per ChatGPT umformulieren und automatisch taggen
- Filterbare und editierbare Artikelübersicht in Tabellenform
- Speicherung in `articles.json` (lokale JSON-Datei)

---

## 🛠️ Installation

```bash
git clone https://github.com/dein-user/rss-artikel-manager.git
cd rss-artikel-manager
python -m venv .venv
source .venv/bin/activate  # oder .venv\\Scripts\\activate auf Windows
pip install -r requirements.txt
