from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .auth import create_session_token, verify_credentials, verify_session_token
from .config import get_settings
from .ingestion import run_ingestion
from .policy import evaluate_source_policy
from .repositories import (
    FeedCreate,
    SourceCreate,
    create_feed,
    create_source,
    get_article_by_id,
    list_articles,
    list_feeds,
    list_runs,
    list_sources,
    update_article_status,
)

settings = get_settings()
router = APIRouter(tags=["admin-ui"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "new": ("review", "rewrite", "error"),
    "rewrite": ("review", "error"),
    "review": ("approved", "rewrite", "error"),
    "approved": ("published", "error"),
    "published": ("error",),
    "error": ("review", "rewrite"),
}


def _admin_user(request: Request) -> str | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    return verify_session_token(token)


def _to_optional_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = raw.strip()
    if value == "":
        return None
    return int(value)


def _dashboard_redirect(
    *,
    msg: str | None = None,
    msg_type: str = "success",
    status_filter: str | None = None,
) -> RedirectResponse:
    query: dict[str, str] = {}
    if msg:
        query["msg"] = msg
        query["type"] = msg_type
    if status_filter:
        query["status_filter"] = status_filter
    suffix = f"?{urlencode(query)}" if query else ""
    return RedirectResponse(url=f"/admin/dashboard{suffix}", status_code=303)


def _parse_meta_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


@router.get("/admin", response_class=HTMLResponse)
def admin_index(request: Request):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {"request": request, "title": "Admin Login", "error": request.query_params.get("error")},
    )


@router.post("/admin/login")
def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not verify_credentials(username, password):
        return RedirectResponse(url="/admin/login?error=1", status_code=303)

    token = create_session_token(username)
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return response


@router.post("/admin/logout")
def admin_logout():
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response


@router.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    sources = list_sources()
    source_policy = {s["id"]: evaluate_source_policy(s) for s in sources}
    feeds = list_feeds()
    runs = list_runs(limit=30)
    status_filter = request.query_params.get("status_filter")
    if status_filter in {"new", "rewrite", "review", "approved", "published", "error"}:
        articles = list_articles(limit=100, status_filter=status_filter)
    else:
        status_filter = ""
        articles = list_articles(limit=100)
    for article in articles:
        meta = _parse_meta_json(article.get("meta_json"))
        extraction = meta.get("extraction") if isinstance(meta.get("extraction"), dict) else {}
        article["meta"] = meta
        article["extracted_images"] = extraction.get("images") if isinstance(extraction.get("images"), list) else []
        article["press_contact"] = extraction.get("press_contact") if isinstance(extraction.get("press_contact"), str) else None
        article["extraction_error"] = extraction.get("extraction_error") if isinstance(extraction.get("extraction_error"), str) else None

    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            "request": request,
            "title": "Admin Dashboard",
            "user": user,
            "sources": sources,
            "source_policy": source_policy,
            "feeds": feeds,
            "runs": runs,
            "articles": articles,
            "status_options": ["new", "rewrite", "review", "approved", "published", "error"],
            "allowed_transitions": ALLOWED_TRANSITIONS,
            "status_filter": status_filter,
            "flash_msg": request.query_params.get("msg", ""),
            "flash_type": request.query_params.get("type", "success"),
        },
    )


@router.post("/admin/sources/create")
def admin_create_source(
    request: Request,
    name: str = Form(...),
    base_url: str = Form(""),
    terms_url: str = Form(""),
    license_name: str = Form(""),
    risk_level: str = Form("yellow"),
    last_reviewed_at: str = Form(""),
):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    try:
        create_source(
            SourceCreate(
                name=name,
                base_url=base_url or None,
                terms_url=terms_url or None,
                license_name=license_name or None,
                risk_level=risk_level,
                is_enabled=True,
                notes=None,
                last_reviewed_at=last_reviewed_at or None,
            )
        )
    except Exception as exc:
        return _dashboard_redirect(msg=f"Quelle konnte nicht gespeichert werden: {exc}", msg_type="error")
    return _dashboard_redirect(msg="Quelle gespeichert")


@router.post("/admin/feeds/create")
def admin_create_feed(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    source_id: str = Form(""),
):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    try:
        create_feed(
            FeedCreate(
                name=name,
                url=url,
                source_id=_to_optional_int(source_id),
                is_enabled=True,
            )
        )
    except Exception as exc:
        return _dashboard_redirect(msg=f"Feed konnte nicht gespeichert werden: {exc}", msg_type="error")
    return _dashboard_redirect(msg="Feed gespeichert")


@router.post("/admin/ingestion/run")
def admin_run_ingestion(request: Request, feed_id: str = Form("")):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)
    try:
        stats = run_ingestion(feed_id=_to_optional_int(feed_id))
    except Exception as exc:
        return _dashboard_redirect(msg=f"Ingestion fehlgeschlagen: {exc}", msg_type="error")
    return _dashboard_redirect(msg=f"Ingestion: {stats.status}, upserts={stats.articles_upserted}")


@router.post("/admin/articles/{article_id}/review")
def admin_review_article(request: Request, article_id: int, decision: str = Form(...), note: str = Form("")):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    article = get_article_by_id(article_id)
    if article and article.get("status") == "review" and decision in {"approve", "reject"}:
        target = "approved" if decision == "approve" else "rewrite"
        update_article_status(article_id, target, actor=user, note=note or None, decision=decision)
        return _dashboard_redirect(msg=f"Artikel #{article_id}: {decision}")
    return _dashboard_redirect(msg=f"Review-Aktion ungueltig fuer Artikel #{article_id}", msg_type="error")


@router.post("/admin/articles/{article_id}/transition")
def admin_transition_article(request: Request, article_id: int, target_status: str = Form(...), note: str = Form("")):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    article = get_article_by_id(article_id)
    if article:
        current = article.get("status")
        if target_status in ALLOWED_TRANSITIONS.get(current, ()):
            update_article_status(article_id, target_status, actor=user, note=note or None)
            return _dashboard_redirect(msg=f"Artikel #{article_id}: {current} -> {target_status}")
    return _dashboard_redirect(msg=f"Ungueltiger Statuswechsel fuer Artikel #{article_id}", msg_type="error")
