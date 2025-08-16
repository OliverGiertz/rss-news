# Aktuellen Stand vom main/master holen
git checkout main
git pull origin main

# Neuen Feature-Branch erstellen
git checkout -b feature/neue-funktion

# Entwickeln und committen
git add .
git commit -m "Neue Funktion implementiert"

# Branch auf Remote-Repository pushen
git push -u origin feature/neue-funktion


# Alle Branches anzeigen
git branch -a

# Aktuellen Branch anzeigen
git branch --show-current