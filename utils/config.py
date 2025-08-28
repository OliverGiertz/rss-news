import os
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()


def validate_env() -> Dict:
    """Validiert sicherheitsrelevante .env-Variablen.

    Returns dict with: ok: bool, errors: List[str], warnings: List[str], summary: Dict[str, bool]
    """
    errors: List[str] = []
    warnings: List[str] = []

    wp_base_url = os.getenv("WP_BASE_URL", "").strip()
    wp_user = os.getenv("WP_USERNAME", "").strip()
    wp_pass = os.getenv("WP_PASSWORD", "").strip()
    wp_b64 = os.getenv("WP_AUTH_BASE64", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    # WP_BASE_URL Pflicht
    if not wp_base_url:
        errors.append("WP_BASE_URL fehlt in .env")
    elif not (wp_base_url.startswith("http://") or wp_base_url.startswith("https://")):
        errors.append("WP_BASE_URL muss mit http:// oder https:// beginnen")

    # Auth-Creds: entweder Base64 ODER Username+Password
    if not wp_b64 and not (wp_user and wp_pass):
        errors.append("Entweder WP_AUTH_BASE64 oder WP_USERNAME + WP_PASSWORD in .env setzen")

    # Empfehlungen
    if not wp_b64 and (wp_user and wp_pass):
        warnings.append("WP_AUTH_BASE64 nicht gesetzt – Empfehlung: Base64 nutzen (Application Password)")

    if not openai_key:
        warnings.append("OPENAI_API_KEY ist nicht gesetzt – Umschreibungsfunktion ist deaktiviert")

    summary = {
        "WP_BASE_URL": bool(wp_base_url),
        "WP_USERNAME": bool(wp_user),
        "WP_PASSWORD": bool(wp_pass),
        "WP_AUTH_BASE64": bool(wp_b64),
        "OPENAI_API_KEY": bool(openai_key),
    }

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "summary": summary}


__all__ = ["validate_env"]

