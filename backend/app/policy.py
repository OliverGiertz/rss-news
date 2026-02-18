from __future__ import annotations

from typing import Any


def evaluate_source_policy(source: dict[str, Any] | None) -> list[str]:
    issues: list[str] = []
    if not source:
        issues.append("Keine Quelle zugeordnet")
        return issues

    risk_level = (source.get("risk_level") or "").strip().lower()
    if risk_level != "green":
        issues.append(f"Quelle nicht freigegeben (risk_level={risk_level or 'unset'})")

    terms_url = (source.get("terms_url") or "").strip()
    if not terms_url:
        issues.append("terms_url fehlt")

    license_name = (source.get("license_name") or "").strip()
    if not license_name:
        issues.append("license_name fehlt")

    last_reviewed_at = (source.get("last_reviewed_at") or "").strip()
    if not last_reviewed_at:
        issues.append("last_reviewed_at fehlt")

    if int(source.get("is_enabled", 0) or 0) != 1:
        issues.append("Quelle ist deaktiviert")

    return issues


def is_source_allowed(source: dict[str, Any] | None) -> bool:
    return len(evaluate_source_policy(source)) == 0
