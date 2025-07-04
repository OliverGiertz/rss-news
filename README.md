# 📰 RSS Article Manager

Ein einfaches, modulares Webtool auf Basis von Streamlit, das RSS-Artikel automatisch einliest, umschreibt, zusammenfasst und mit Tags versieht – bereit zur Veröffentlichung auf WordPress.

## ✨ Funktionen

- 📥 RSS-Feeds direkt über die Oberfläche hinzufügen und verwalten
- 📝 Artikel automatisch umschreiben mit Hilfe von ChatGPT
- 🏷️ Tags und Zusammenfassungen automatisch generieren
- 🗂️ Übersicht in tabellarischer Form mit Filter nach Status
- 📋 Kopierbare Inhalte für manuelles Einfügen in WordPress
- 📎 Link zum Originalartikel zur einfachen Bildübernahme
- 💾 Speicherung in einer lokalen JSON-Datei (später SQLite möglich)
- 📦 Versionierung inkl. CHANGELOG und GitHub Releases

## 🔐 Voraussetzungen

- Python 3.8+
- OpenAI API Key (per `.env` eingebunden)

## 🚀 Loslegen

```bash
# Setup
git clone https://github.com/dein-benutzername/rss-article-manager.git
cd rss-article-manager
bash start.sh
