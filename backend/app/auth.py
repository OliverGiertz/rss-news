import hmac
from typing import Optional

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from .config import get_settings


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.app_secret_key, salt="rss-news-session")


def verify_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    user_ok = hmac.compare_digest(username, settings.app_admin_username)
    pw_ok = hmac.compare_digest(password, settings.app_admin_password)
    return user_ok and pw_ok


def create_session_token(username: str) -> str:
    return _serializer().dumps({"username": username})


def verify_session_token(token: str) -> Optional[str]:
    settings = get_settings()
    try:
        payload = _serializer().loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return payload.get("username")
