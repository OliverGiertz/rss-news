# KI-Verordnung: redaktionelle Freigabe vor der Veröffentlichung

Stand: 24.08.2026. Keine Rechtsberatung — die Umsetzung folgt der Auslegung, die
unten begründet ist. Bei wirtschaftlich kritischen Fällen juristisch prüfen.

## Warum das Gate existiert

Die Pipeline lässt ein Sprachmodell (OpenAI) Nachrichtentexte **neu schreiben**,
verschlagwortet sie und bewertet ihre Relevanz. Das Ergebnis wird als Beitrag auf
`vanityontour.de` veröffentlicht — also ein KI-erzeugter Text, der die
Öffentlichkeit informiert.

Art. 50 Abs. 4 UAbs. 2 KI-VO (Verordnung (EU) 2024/1689, Transparenzpflichten
anwendbar seit dem 02.08.2026) verlangt für solche Texte die Offenlegung, dass
sie künstlich erzeugt oder manipuliert wurden. **Ausgenommen** sind Inhalte, die

- einer **menschlichen Überprüfung bzw. redaktionellen Kontrolle** unterzogen
  wurden **und**
- für die eine natürliche oder juristische Person die **redaktionelle
  Verantwortung** trägt.

Der KI-Transparenzhinweis auf dem Blog (Plugin `vot-ki-hinweis`) sagt genau das
zu: „Jeder Text wird von mir redaktionell geprüft, auf Fakten kontrolliert und
inhaltlich verantwortet." Bis zum 24.08.2026 lief die News-Pipeline jedoch
vollautomatisch: Rewrite, WordPress-Beitrag und geplante Veröffentlichung ohne
menschlichen Zwischenschritt. Die zugesagte Kontrolle fand faktisch nicht statt.

Das Freigabe-Gate schließt diese Lücke: Es macht die Aussage wahr und
dokumentiert sie nachprüfbar.

## Der Ablauf

```
N8N (2× täglich)  →  POST /api/n8n/pipeline
   ├── RSS-Ingestion
   ├── Relevanz-Score (GPT)
   │     ├── < 60  → abgelehnt
   │     ├── 60–79 → Telegram-Warnung, Übernahme per Button möglich
   │     └── ≥ 80  → Rewrite + Tags (GPT)
   │
   └── Status: pending_review  ──►  KEIN WordPress-Beitrag, KEIN Slot
                                     Telegram: Info + Link ins Portal
                                        │
                        Mensch öffnet den Artikel im Portal, liest ihn
                                        │
              ┌─────────────────────────┼──────────────────────────┐
              ▼                         ▼                          ▼
     „Redaktionell geprüft      „Rewrite ausführen"          „Verwerfen"
      & freigeben"                  (neu schreiben)          (Status close)
              │
              ▼
   Stempel: editorial_review_at / _by / _note (Systemzeit, nicht editierbar)
   Status: approved  →  Publish-Slot reservieren  →  WordPress-Beitrag (future)
                     →  WordPress veröffentlicht zum Slot
```

Wichtig an der Reihenfolge:

- **Kein WordPress-Beitrag vor der Freigabe.** Sonst läge dort ein
  `future`-Beitrag, der sich selbst veröffentlicht, bevor jemand hingesehen hat.
- **Kein Slot vor der Freigabe.** Es gibt vier feste Slots pro Tag; ein Artikel,
  der stundenlang auf die Prüfung wartet, darf keinen davon blockieren. Der Slot
  wird im Moment der Freigabe reserviert, der Scheduler füllt Lücken auf.

## Wo der Nachweis liegt

| Ort | Inhalt |
|-----|--------|
| `articles.editorial_review_at` | Zeitpunkt der Freigabe (UTC, ISO 8601), vom System gesetzt |
| `articles.editorial_review_by` | angemeldeter Benutzer, der freigegeben hat |
| `articles.editorial_review_note` | optionale Notiz zur Prüfung |
| `meta_json.review_events[]` | Ereignis `editorial_review` im Audit-Trail, zusätzlich der Statuswechsel |

Der Zeitstempel ist **nie** ein Eingabefeld. Er entsteht ausschließlich beim
Klick auf „Redaktionell geprüft & freigeben" (bzw. beim manuellen Statuswechsel
nach `publish`) und kann in der Oberfläche nicht nachträglich gesetzt werden.

## Kein Schlupfloch nach `publish`

Jeder Weg in den Status `approved` stempelt die Freigabe:

- `POST /admin/articles/{id}/approve` — der reguläre Button
- `POST /admin/articles/{id}/transition` mit Ziel `publish` — leitet auf denselben
  Weg um, wenn noch kein Stempel vorliegt
- `POST /api/articles/{id}/transition` mit Ziel `publish` — stempelt ebenfalls

Die Pipeline selbst erreicht `approved` nicht mehr, solange
`EDITORIAL_REVIEW_REQUIRED=true` gesetzt ist.

## Altbestand

Artikel, die vor dem 24.08.2026 freigegeben oder veröffentlicht wurden, haben
keinen Stempel und brauchen keinen: Sie durchlaufen die neue Pipeline nicht
erneut, und der Publisher blockiert sie nicht. Das Gate greift ausschließlich für
Artikel, die ab sofort neu verarbeitet werden.

## Konfiguration

| Variable | Default | Wirkung |
|----------|---------|---------|
| `EDITORIAL_REVIEW_REQUIRED` | `true` | Gate aktiv; `false` stellt den alten vollautomatischen Ablauf wieder her |
| `PORTAL_BASE_URL` | `https://news.vanityontour.de` | Basis für die Deep-Links in Telegram |

Wird das Gate abgeschaltet, ist der KI-Hinweistext auf dem Blog anzupassen — die
Zusage der redaktionellen Prüfung träfe dann nicht mehr zu.

## Was bewusst nicht umgesetzt ist

- **Maschinenlesbare Markierung der KI-Ausgabe** (Art. 50 Abs. 2) ist eine
  Pflicht des Anbieters des KI-Systems, nicht des Betreibers. Sie liegt bei
  OpenAI.
- **Ein zweiter, abweichender Hinweistext für vollautomatische Beiträge** wird
  nicht gebraucht, solange das Gate aktiv ist: Es gibt dann keine
  vollautomatischen Beiträge mehr.

## Referenzen

- Verordnung (EU) 2024/1689 (KI-VO), Art. 50: https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=OJ:L_202401689
- Plugin `vot-ki-hinweis` (Hinweistext auf dem Blog): eigenes Repository `VoT-KI-Hinweis`
