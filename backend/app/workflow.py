from __future__ import annotations

UI_STATUSES = ("new", "rewrite", "publish", "published", "close")


def internal_to_ui_status(status: str | None) -> str:
    value = (status or "").strip()
    if value == "approved":
        return "publish"
    if value == "error":
        return "close"
    if value == "review":
        return "rewrite"
    if value in {"new", "rewrite", "published"}:
        return value
    return value or "new"


def ui_to_internal_status(status: str | None) -> str:
    value = (status or "").strip()
    if value == "publish":
        return "approved"
    if value == "close":
        return "error"
    if value in {"new", "rewrite", "published"}:
        return value
    if value in {"approved", "error", "review"}:
        return value
    return value


ALLOWED_UI_TRANSITIONS: dict[str, set[str]] = {
    "new": {"rewrite", "close"},
    "rewrite": {"publish", "close"},
    "publish": {"published", "close"},
    "published": {"rewrite", "close"},
    "close": {"rewrite"},
}
