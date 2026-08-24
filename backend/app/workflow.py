from __future__ import annotations

UI_STATUSES = ("new", "relevanz", "rewrite", "freigabe", "publish", "published", "close", "no_image")

# Menschenlesbare Beschriftungen fuer die Admin-UI. Interne Kuerzel tauchen in
# der Oberflaeche nirgends mehr auf.
UI_STATUS_LABELS: dict[str, str] = {
    "new": "Neu",
    "relevanz": "Niedrige Relevanz",
    "rewrite": "Rewrite nötig",
    "freigabe": "Wartet auf Freigabe",
    "publish": "Freigegeben / eingeplant",
    "published": "Veröffentlicht",
    "close": "Verworfen",
    "no_image": "Kein Bild",
}

# Reihenfolge fuer Status-Filter: entlang des Ablaufs, nicht alphabetisch.
INTERNAL_STATUSES = (
    "new",
    "review",
    "rewrite",
    "pending_review",
    "approved",
    "published",
    "error",
    "no_image",
)


def internal_to_ui_status(status: str | None) -> str:
    value = (status or "").strip()
    if value == "approved":
        return "publish"
    if value == "error":
        return "close"
    if value == "pending_review":
        return "freigabe"
    if value == "review":
        # Relevanz-Warnzone (Score zwischen WARN und AUTO): wartet auf die
        # Entscheidung, ob der Artikel ueberhaupt verarbeitet wird. Wurde frueher
        # als "rewrite" angezeigt, was etwas anderes bedeutet.
        return "relevanz"
    if value in {"new", "rewrite", "published", "no_image"}:
        return value
    return value or "new"


def ui_to_internal_status(status: str | None) -> str:
    value = (status or "").strip()
    if value == "publish":
        return "approved"
    if value == "close":
        return "error"
    if value == "freigabe":
        return "pending_review"
    if value == "relevanz":
        return "review"
    if value in {"new", "rewrite", "published", "no_image"}:
        return value
    if value in {"approved", "error", "review", "pending_review"}:
        return value
    return value


def ui_status_label(status: str | None) -> str:
    value = (status or "").strip()
    return UI_STATUS_LABELS.get(value, value or "new")


# `freigabe` ist das einzige Tor zur Veroeffentlichung: der Wechsel nach
# `publish` stempelt die redaktionelle Freigabe (Art. 50 Abs. 4 KI-VO).
# Der frueher moegliche Sprung `rewrite -> publish` ist bewusst entfernt - er war
# ein zweiter Weg an der Freigabe vorbei und im Menue nur verwirrend.
# `published` setzt WordPress bzw. der Publisher, nicht die Hand.
ALLOWED_UI_TRANSITIONS: dict[str, set[str]] = {
    "new": {"rewrite", "close"},
    "relevanz": {"rewrite", "close"},
    "rewrite": {"freigabe", "close"},
    "freigabe": {"publish", "rewrite", "close"},
    "publish": {"close"},
    "published": {"rewrite", "close"},
    "close": {"rewrite"},
    "no_image": {"rewrite", "close"},
}
