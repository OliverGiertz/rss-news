from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .auth import create_session_token, verify_credentials, verify_session_token
from .config import get_settings
from .ingestion import run_ingestion
from .policy import evaluate_source_policy
from .publisher import enqueue_publish, run_publisher
from .relevance import article_age_days, article_relevance
from .repositories import (
    FeedCreate,
    SourceCreate,
    create_feed,
    create_source,
    get_article_by_id,
    get_feed_by_id,
    list_articles,
    list_feeds,
    list_publish_jobs,
    list_runs,
    list_sources,
    set_article_image_decision,
    set_article_legal_review,
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
IMAGE_PROXY_USER_AGENT = "rss-news-admin/1.0"


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


def _read_article_images(article: dict, extraction: dict) -> list[str]:
    images: list[str] = []
    if article.get("image_urls_json"):
        try:
            parsed_images = json.loads(article["image_urls_json"])
            if isinstance(parsed_images, list):
                images = [str(item) for item in parsed_images if item]
        except Exception:
            images = []
    if not images and isinstance(extraction.get("images"), list):
        images = [str(item) for item in extraction.get("images") if item]
    # deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for image in images:
        if image not in seen:
            seen.add(image)
            deduped.append(image)
    return deduped


def _is_probably_irrelevant_image(url: str) -> bool:
    lowered = url.lower()
    patterns = (
        r"logo",
        r"icon",
        r"sprite",
        r"avatar",
        r"favicon",
        r"/ads/",
        r"tracking",
        r"pixel",
        r"banner",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def _is_http_image_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _build_image_entries(article: dict, extraction: dict, meta: dict) -> list[dict[str, object]]:
    all_images = _read_article_images(article, extraction)
    image_review = meta.get("image_review") if isinstance(meta.get("image_review"), dict) else {}
    selected_url = image_review.get("selected_url") if isinstance(image_review.get("selected_url"), str) else None
    excluded_urls = image_review.get("excluded_urls") if isinstance(image_review.get("excluded_urls"), list) else []
    excluded_set = {str(item) for item in excluded_urls if item}

    entries: list[dict[str, object]] = []
    for url in all_images:
        entries.append(
            {
                "url": url,
                "proxy_url": f"/admin/images/proxy?{urlencode({'url': url})}",
                "is_selected": selected_url == url,
                "is_excluded": url in excluded_set,
                "is_irrelevant_hint": _is_probably_irrelevant_image(url),
            }
        )
    return entries


def _legal_checklist(article: dict, feed: dict | None) -> list[dict[str, str]]:
    meta = article.get("meta", {})
    extraction = meta.get("extraction") if isinstance(meta.get("extraction"), dict) else {}
    attribution = meta.get("attribution") if isinstance(meta.get("attribution"), dict) else {}

    checks: list[dict[str, str]] = []
    checks.append(
        {
            "label": "Original-Link vorhanden",
            "status": "ok" if article.get("source_url") else "missing",
            "value": article.get("source_url") or "-",
        }
    )
    checks.append(
        {
            "label": "Autor vorhanden",
            "status": "ok" if article.get("author") else "missing",
            "value": article.get("author") or "-",
        }
    )
    checks.append(
        {
            "label": "Bilder extrahiert",
            "status": "ok" if article.get("image_urls_json") else "missing",
            "value": str(len(extraction.get("images", []))) if isinstance(extraction.get("images"), list) else "0",
        }
    )
    checks.append(
        {
            "label": "Pressekontakt",
            "status": "ok" if article.get("press_contact") else "missing",
            "value": article.get("press_contact") or extraction.get("press_contact") or "-",
        }
    )
    checks.append(
        {
            "label": "Lizenz/Terms",
            "status": "ok" if article.get("source_license_name_snapshot") and article.get("source_terms_url_snapshot") else "missing",
            "value": f"{article.get('source_license_name_snapshot') or attribution.get('source_license_name') or '-'} | {article.get('source_terms_url_snapshot') or attribution.get('source_terms_url') or '-'}",
        }
    )
    checks.append(
        {
            "label": "Risiko-Status Quelle",
            "status": "ok" if (feed and feed.get("source_risk_level") == "green") else "missing",
            "value": feed.get("source_risk_level") if feed else "-",
        }
    )
    checks.append(
        {
            "label": "Manuelle Rechtsfreigabe",
            "status": "ok" if int(article.get("legal_checked", 0)) == 1 else "missing",
            "value": article.get("legal_checked_at") or "-",
        }
    )
    image_review = meta.get("image_review") if isinstance(meta.get("image_review"), dict) else {}
    selected_image = image_review.get("selected_url") if isinstance(image_review.get("selected_url"), str) else None
    checks.append(
        {
            "label": "Hauptbild ausgewählt",
            "status": "ok" if selected_image else "missing",
            "value": selected_image or "-",
        }
    )
    return checks


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
    publish_jobs = list_publish_jobs(limit=30)
    status_filter = request.query_params.get("status_filter")
    if status_filter in {"new", "rewrite", "review", "approved", "published", "error"}:
        articles = list_articles(limit=100, status_filter=status_filter)
    else:
        status_filter = ""
        articles = list_articles(limit=100)
    for article in articles:
        meta = _parse_meta_json(article.get("meta_json"))
        extraction = meta.get("extraction") if isinstance(meta.get("extraction"), dict) else {}
        images = _read_article_images(article, extraction)
        article["meta"] = meta
        article["extracted_images"] = images
        article["image_entries"] = _build_image_entries(article, extraction, meta)
        image_review = meta.get("image_review") if isinstance(meta.get("image_review"), dict) else {}
        article["selected_image_url"] = image_review.get("selected_url") if isinstance(image_review.get("selected_url"), str) else None
        article["selected_image_proxy_url"] = (
            f"/admin/images/proxy?{urlencode({'url': article['selected_image_url']})}" if article.get("selected_image_url") else None
        )
        if not article.get("press_contact") and isinstance(extraction.get("press_contact"), str):
            article["press_contact"] = extraction.get("press_contact")
        article["extraction_error"] = extraction.get("extraction_error") if isinstance(extraction.get("extraction_error"), str) else None
        article["days_old"] = article_age_days(article.get("published_at"))
        article["relevance"] = article_relevance(article.get("published_at"))

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
            "publish_jobs": publish_jobs,
            "articles": articles,
            "status_options": ["new", "rewrite", "review", "approved", "published", "error"],
            "allowed_transitions": ALLOWED_TRANSITIONS,
            "status_filter": status_filter,
            "flash_msg": request.query_params.get("msg", ""),
            "flash_type": request.query_params.get("type", "success"),
        },
    )


@router.get("/admin/articles/{article_id}", response_class=HTMLResponse)
def admin_article_detail(request: Request, article_id: int):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    article = get_article_by_id(article_id)
    if not article:
        return _dashboard_redirect(msg=f"Artikel #{article_id} nicht gefunden", msg_type="error")

    meta = _parse_meta_json(article.get("meta_json"))
    article["meta"] = meta
    extraction = meta.get("extraction") if isinstance(meta.get("extraction"), dict) else {}
    extraction["images"] = _read_article_images(article, extraction)
    if not article.get("press_contact") and isinstance(extraction.get("press_contact"), str):
        article["press_contact"] = extraction.get("press_contact")
    article["extraction"] = extraction
    article["image_selection"] = extraction.get("image_selection") if isinstance(extraction.get("image_selection"), dict) else {}
    article["image_entries"] = _build_image_entries(article, extraction, meta)
    image_review = meta.get("image_review") if isinstance(meta.get("image_review"), dict) else {}
    article["selected_image_url"] = image_review.get("selected_url") if isinstance(image_review.get("selected_url"), str) else None
    article["selected_image_proxy_url"] = (
        f"/admin/images/proxy?{urlencode({'url': article['selected_image_url']})}" if article.get("selected_image_url") else None
    )
    article["days_old"] = article_age_days(article.get("published_at"))
    article["relevance"] = article_relevance(article.get("published_at"))
    feed = get_feed_by_id(int(article["feed_id"])) if article.get("feed_id") else None
    checklist = _legal_checklist(article, feed)

    return templates.TemplateResponse(
        request,
        "admin_article_detail.html",
        {
            "request": request,
            "title": f"Artikel #{article_id}",
            "user": user,
            "article": article,
            "feed": feed,
            "checklist": checklist,
            "allowed_transitions": ALLOWED_TRANSITIONS.get(article.get("status"), ()),
            "flash_msg": request.query_params.get("msg", ""),
            "flash_type": request.query_params.get("type", "success"),
        },
    )


@router.post("/admin/articles/{article_id}/images/decision")
def admin_article_image_decision(
    request: Request,
    article_id: int,
    image_url: str = Form(...),
    action: str = Form(...),
):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    ok = set_article_image_decision(article_id=article_id, image_url=image_url, action=action, actor=user)
    if not ok:
        return _dashboard_redirect(msg=f"Bildaktion fehlgeschlagen fuer Artikel #{article_id}", msg_type="error")
    return RedirectResponse(url=f"/admin/articles/{article_id}", status_code=303)


@router.post("/admin/articles/{article_id}/publish-enqueue")
def admin_enqueue_publish(request: Request, article_id: int, max_attempts: str = Form("3")):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)
    try:
        job_id = enqueue_publish(article_id=article_id, max_attempts=max(1, int(max_attempts)))
    except Exception as exc:
        return _dashboard_redirect(msg=f"Publish Queue Fehler fuer Artikel #{article_id}: {exc}", msg_type="error")
    return RedirectResponse(url=f"/admin/articles/{article_id}?msg=Publish-Job%20#{job_id}%20erstellt&type=success", status_code=303)


@router.post("/admin/publisher/run")
def admin_run_publisher(request: Request, max_jobs: str = Form("10")):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)
    try:
        stats = run_publisher(max_jobs=max(1, int(max_jobs)))
    except Exception as exc:
        return _dashboard_redirect(msg=f"Publisher Fehler: {exc}", msg_type="error")
    return _dashboard_redirect(
        msg=f"Publisher: processed={stats.processed}, success={stats.success}, failed={stats.failed}, requeued={stats.requeued}"
    )


@router.get("/admin/images/proxy")
def admin_image_proxy(request: Request, url: str):
    if not _is_http_image_url(url):
        return Response(status_code=400)

    try:
        referer = request.headers.get("referer", "")
        req = UrlRequest(
            url=url,
            headers={
                "User-Agent": IMAGE_PROXY_USER_AGENT,
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": referer or url,
            },
        )
        with urlopen(req, timeout=10) as resp:
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
    except Exception:
        return Response(status_code=404)

    if not content_type.lower().startswith("image/"):
        return Response(status_code=415)
    return Response(content=body, media_type=content_type)


@router.post("/admin/articles/{article_id}/legal-review")
def admin_article_legal_review(request: Request, article_id: int, approved: str = Form("0"), note: str = Form("")):
    user = _admin_user(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=303)

    is_approved = approved == "1"
    ok = set_article_legal_review(article_id, approved=is_approved, note=note or None, actor=user)
    if not ok:
        return _dashboard_redirect(msg=f"Artikel #{article_id} nicht gefunden", msg_type="error")
    return RedirectResponse(url=f"/admin/articles/{article_id}", status_code=303)


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
            if target_status == "published" and int(article.get("legal_checked", 0)) != 1:
                return _dashboard_redirect(msg=f"Publish blockiert fuer Artikel #{article_id}: Rechtsfreigabe fehlt", msg_type="error")
            update_article_status(article_id, target_status, actor=user, note=note or None)
            return _dashboard_redirect(msg=f"Artikel #{article_id}: {current} -> {target_status}")
    return _dashboard_redirect(msg=f"Ungueltiger Statuswechsel fuer Artikel #{article_id}", msg_type="error")
