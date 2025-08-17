# Roadmap: Bild-Deduplizierung & Medien-Hygiene

## Ziele
- Speicherverbrauch reduzieren
- Medienbestand konsistent halten
- Pipeline stabilisieren (keine Mehrfach-Uploads und -Speicherungen)

## Vorgehen (sicher und reversibel)
1. **Index aufbauen (Read-Only):**
   - Alle Bilder (`.jpg/.jpeg/.png/.webp/.gif`) in definierten Verzeichnissen scannen
   - Für jede Datei: `sha256` (Byte-Hash) + `pHash` (perzeptuell) berechnen
   - Ergebnis als SQLite-Index + CSV-Report speichern

2. **Kanonisierung & Referenzen prüfen:**
   - Pro Duplikatgruppe genau **eine** kanonische Datei wählen (größte/neueste)
   - Alle internen Referenzen (DB/JSON) testweise auf Kanon aktualisieren (Dry-Run)

3. **Speicher sparen ohne Risiko:**
   - Nicht-kanonische Dateien durch **Hardlinks** auf den Kanon ersetzen (gleiches FS)
   - Alternativ: nur löschen, wenn Referenzen **sicher** auf Kanon zeigen

4. **Prävention für die Zukunft:**
   - Beim Speichern: **Content-Addressed Storage** (`<sha256>.<ext>`)
   - In DB ein `content_hash`-Feld mit **Unique-Constraint**
   - Vor jedem Speichern/Upload: Hash lookup → vorhandene Datei wiederverwenden

## Akzeptanzkriterien
- Report listet alle Duplikatgruppen mit Pfaden und Größenersparnis
- Dry-Run zeigt geplante Änderungen ohne Schreibzugriff
- Nach „Anwenden“ verweisen alle Referenzen auf die kanonische Datei
- Re-Run findet **keine** Duplikate mehr (idempotent)
- Rollback möglich via Backup der Reports/Indexdatei

## Metriken
- Anzahl Bilder vorher/nachher
- Ersparter Speicher (MB/GB)
- Anzahl gruppierter Duplikate
