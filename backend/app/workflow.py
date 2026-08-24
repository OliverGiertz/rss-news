from __future__ import annotations

UI_STATUSES = ("new", "rewrite", "freigabe", "publish", "published", "close", "no_image")

# Menschenlesbare Beschriftungen fuer die Admin-UI.
UI_STATUS_LABELS: dict[str, str] = {
    "new": "Neu",
    "rewrite": "Rewrite",
    "freigabe": "Wartet auf Freigabe",
    "publish": "Freigegeben / eingeplant",
    "published": "Veroeffentlicht",
    "close": "Verworfen",
    "no_image": "Kein Bild",
}


def internal_to_ui_status(status: str | None) -> str:
    value = (status or "").strip()
    if value == "approved":
        return "publish"
    if value == "error":
        return "close"
    if value == "pending_review":
        return "freigabe"
    if value == "review":
        return "rewrite"
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
    if value in {"new", "rewrite", "published", "no_image"}:
        return value
    if value in {"approved", "error", "review", "pending_review"}:
        return value
    return value


def ui_status_label(status: str | None) -> str:
    value = (status or "").strip()
    return UI_STATUS_LABELS.get(value, value or "new")


# `freigabe` ist das Tor zur Veroeffentlichung: nur ueber diesen Zustand (oder
# einen bewussten manuellen Wechsel) erreicht ein Artikel `publish`, und beides
# stempelt die redaktionelle Freigabe (Art. 50 Abs. 4 KI-VO).
ALLOWED_UI_TRANSITIONS: dict[str, set[str]] = {
    "new": {"rewrite", "close"},
    "rewrite": {"freigabe", "publish", "close"},
    "freigabe": {"publish", "rewrite", "close"},
    "publish": {"published", "close"},
    "published": {"rewrite", "close"},
    "close": {"rewrite"},
    "no_image": {"rewrite", "close"},
}
