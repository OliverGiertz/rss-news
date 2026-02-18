from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles

from .admin_ui import router as admin_router
from .auth import create_session_token, verify_credentials, verify_session_token
from .config import get_settings
from .db import init_db
from .ingestion import run_ingestion
from .policy import evaluate_source_policy, is_source_allowed
from .repositories import (
    ArticleUpsert,
    FeedCreate,
    RunCreate,
    SourceCreate,
    create_feed as repo_create_feed,
    create_run,
    create_source as repo_create_source,
    finish_run,
    get_article_by_id,
    get_feed_by_id,
    get_run_by_id,
    get_source_by_id,
    list_articles as repo_list_articles,
    list_feeds as repo_list_feeds,
    list_runs,
    list_sources as repo_list_sources,
    set_article_legal_review,
    update_article_status,
    upsert_article as repo_upsert_article,
)

settings = get_settings()


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=app_lifespan)
app.include_router(admin_router)
app.mount(
    "/admin/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")),
    name="admin-static",
)


class LoginRequest(BaseModel):
    username: str
    password: str


class SourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_url: str | None = None
    terms_url: str | None = None
    license_name: str | None = None
    risk_level: str = Field(default="yellow", pattern="^(green|yellow|red)$")
    is_enabled: bool = False
    notes: str | None = None
    last_reviewed_at: str | None = None


class FeedCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=5, max_length=1000)
    source_id: int | None = None
    is_enabled: bool = True


class RunCreateRequest(BaseModel):
    run_type: str = Field(min_length=2, max_length=100)
    status: str = Field(default="queued", pattern="^(queued|running|success|failed)$")
    details: str | None = None


class RunFinishRequest(BaseModel):
    status: str = Field(pattern="^(success|failed)$")
    details: str | None = None


class ArticleUpsertRequest(BaseModel):
    feed_id: int | None = None
    source_article_id: str | None = None
    source_hash: str | None = None
    title: str = Field(min_length=1, max_length=500)
    source_url: str = Field(min_length=5, max_length=2000)
    canonical_url: str | None = None
    published_at: str | None = None
    author: str | None = None
    summary: str | None = None
    content_raw: str | None = None
    content_rewritten: str | None = None
    image_urls_json: str | None = None
    press_contact: str | None = None
    source_name_snapshot: str | None = None
    source_terms_url_snapshot: str | None = None
    source_license_name_snapshot: str | None = None
    legal_checked: bool = False
    legal_checked_at: str | None = None
    legal_note: str | None = None
    word_count: int = 0
    status: str = Field(default="new", pattern="^(new|rewrite|review|approved|published|error)$")
    meta_json: str | None = None


class IngestionRunRequest(BaseModel):
    feed_id: int | None = None


class ArticleTransitionRequest(BaseModel):
    target_status: str = Field(pattern="^(new|rewrite|review|approved|published|error)$")
    note: str | None = None


class ArticleReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str | None = None


class ArticleLegalReviewRequest(BaseModel):
    approved: bool
    note: str | None = None


ALLOWED_ARTICLE_TRANSITIONS: dict[str, set[str]] = {
    "new": {"review", "rewrite", "error"},
    "rewrite": {"review", "error"},
    "review": {"approved", "rewrite", "error"},
    "approved": {"published", "error"},
    "published": {"error"},
    "error": {"review", "rewrite"},
}


def require_auth(request: Request) -> str:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")

    username = verify_session_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session ungueltig oder abgelaufen")

    return username


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "db_path": settings.app_db_path}


@app.post("/auth/login")
def login(payload: LoginRequest, response: Response) -> dict:
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungueltige Zugangsdaten")

    token = create_session_token(payload.username)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return {"ok": True, "username": payload.username}


@app.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}


@app.get("/auth/me")
def me(username: str = Depends(require_auth)) -> dict:
    return {"authenticated": True, "username": username}


@app.get("/api/protected")
def protected(username: str = Depends(require_auth)) -> dict:
    return {"ok": True, "message": "Protected endpoint", "username": username}


@app.get("/api/pipeline/status")
def pipeline_status(username: str = Depends(require_auth)) -> dict:
    feeds_total = len(repo_list_feeds())
    sources_total = len(repo_list_sources())
    articles_total = len(repo_list_articles(limit=500))
    return {
        "ok": True,
        "stage": "skeleton+db",
        "requested_by": username,
        "counts": {
            "sources": sources_total,
            "feeds": feeds_total,
            "articles": articles_total,
        },
    }


@app.get("/api/sources")
def list_sources(username: str = Depends(require_auth)) -> dict:
    return {"ok": True, "items": repo_list_sources(), "requested_by": username}


@app.get("/api/sources/{source_id}/policy-check")
def source_policy_check(source_id: int, username: str = Depends(require_auth)) -> dict:
    source = get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quelle nicht gefunden")
    issues = evaluate_source_policy(source)
    return {
        "ok": True,
        "source_id": source_id,
        "allowed": is_source_allowed(source),
        "issues": issues,
        "requested_by": username,
    }


@app.post("/api/sources")
def create_source(payload: SourceCreateRequest, username: str = Depends(require_auth)) -> dict:
    source_id = repo_create_source(
        SourceCreate(
            name=payload.name,
            base_url=payload.base_url,
            terms_url=payload.terms_url,
            license_name=payload.license_name,
            risk_level=payload.risk_level,
            is_enabled=payload.is_enabled,
            notes=payload.notes,
            last_reviewed_at=payload.last_reviewed_at,
        )
    )
    return {"ok": True, "id": source_id, "requested_by": username}


@app.get("/api/feeds")
def list_feeds(username: str = Depends(require_auth)) -> dict:
    return {"ok": True, "items": repo_list_feeds(), "requested_by": username}


@app.get("/api/feeds/{feed_id}/policy-check")
def feed_policy_check(feed_id: int, username: str = Depends(require_auth)) -> dict:
    feed = get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed nicht gefunden")

    source_snapshot = {
        "id": feed.get("source_id"),
        "name": feed.get("source_name"),
        "base_url": feed.get("source_base_url"),
        "terms_url": feed.get("source_terms_url"),
        "license_name": feed.get("source_license_name"),
        "risk_level": feed.get("source_risk_level"),
        "last_reviewed_at": feed.get("source_last_reviewed_at"),
        "is_enabled": feed.get("source_is_enabled"),
    }
    issues = evaluate_source_policy(source_snapshot)
    return {
        "ok": True,
        "feed_id": feed_id,
        "allowed": len(issues) == 0,
        "issues": issues,
        "requested_by": username,
    }


@app.post("/api/feeds")
def create_feed(payload: FeedCreateRequest, username: str = Depends(require_auth)) -> dict:
    try:
        feed_id = repo_create_feed(
            FeedCreate(
                name=payload.name,
                url=payload.url,
                source_id=payload.source_id,
                is_enabled=payload.is_enabled,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Feed konnte nicht angelegt werden: {exc}") from exc

    return {"ok": True, "id": feed_id, "requested_by": username}


@app.get("/api/runs")
def api_list_runs(limit: int = 50, username: str = Depends(require_auth)) -> dict:
    return {"ok": True, "items": list_runs(limit=limit), "requested_by": username}


@app.get("/api/runs/{run_id}")
def api_get_run(run_id: int, username: str = Depends(require_auth)) -> dict:
    run = get_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run nicht gefunden")
    return {"ok": True, "item": run, "requested_by": username}


@app.post("/api/runs")
def api_create_run(payload: RunCreateRequest, username: str = Depends(require_auth)) -> dict:
    run_id = create_run(RunCreate(run_type=payload.run_type, status=payload.status, details=payload.details))
    return {"ok": True, "id": run_id, "requested_by": username}


@app.post("/api/runs/{run_id}/finish")
def api_finish_run(run_id: int, payload: RunFinishRequest, username: str = Depends(require_auth)) -> dict:
    finish_run(run_id=run_id, status=payload.status, details=payload.details)
    return {"ok": True, "id": run_id, "requested_by": username}


@app.get("/api/articles")
def api_list_articles(limit: int = 100, status_filter: str | None = None, username: str = Depends(require_auth)) -> dict:
    return {"ok": True, "items": repo_list_articles(limit=limit, status_filter=status_filter), "requested_by": username}


@app.get("/api/articles/{article_id}")
def api_get_article(article_id: int, username: str = Depends(require_auth)) -> dict:
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")
    return {"ok": True, "item": article, "requested_by": username}


@app.post("/api/articles/upsert")
def api_upsert_article(payload: ArticleUpsertRequest, username: str = Depends(require_auth)) -> dict:
    article_id = repo_upsert_article(
        ArticleUpsert(
            feed_id=payload.feed_id,
            source_article_id=payload.source_article_id,
            source_hash=payload.source_hash,
            title=payload.title,
            source_url=payload.source_url,
            canonical_url=payload.canonical_url,
            published_at=payload.published_at,
            author=payload.author,
            summary=payload.summary,
            content_raw=payload.content_raw,
            content_rewritten=payload.content_rewritten,
            image_urls_json=payload.image_urls_json,
            press_contact=payload.press_contact,
            source_name_snapshot=payload.source_name_snapshot,
            source_terms_url_snapshot=payload.source_terms_url_snapshot,
            source_license_name_snapshot=payload.source_license_name_snapshot,
            legal_checked=payload.legal_checked,
            legal_checked_at=payload.legal_checked_at,
            legal_note=payload.legal_note,
            word_count=payload.word_count,
            status=payload.status,
            meta_json=payload.meta_json,
        )
    )
    return {"ok": True, "id": article_id, "requested_by": username}


@app.post("/api/articles/{article_id}/transition")
def api_article_transition(article_id: int, payload: ArticleTransitionRequest, username: str = Depends(require_auth)) -> dict:
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")

    current_status = article.get("status")
    allowed_targets = ALLOWED_ARTICLE_TRANSITIONS.get(current_status, set())
    if payload.target_status not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ungueltiger Statuswechsel: {current_status} -> {payload.target_status}",
        )
    if payload.target_status == "published" and int(article.get("legal_checked", 0)) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Publish gesperrt: Rechtscheck wurde noch nicht freigegeben",
        )

    updated = update_article_status(article_id, payload.target_status, actor=username, note=payload.note)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")
    return {"ok": True, "id": article_id, "from_status": current_status, "to_status": payload.target_status}


@app.post("/api/articles/{article_id}/legal-review")
def api_article_legal_review(article_id: int, payload: ArticleLegalReviewRequest, username: str = Depends(require_auth)) -> dict:
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")

    updated = set_article_legal_review(article_id, approved=payload.approved, note=payload.note, actor=username)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")
    return {
        "ok": True,
        "id": article_id,
        "legal_checked": payload.approved,
    }


@app.post("/api/articles/{article_id}/review")
def api_article_review(article_id: int, payload: ArticleReviewRequest, username: str = Depends(require_auth)) -> dict:
    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")
    if article.get("status") != "review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Review nur fuer Status 'review' erlaubt (aktuell: {article.get('status')})",
        )

    target_status = "approved" if payload.decision == "approve" else "rewrite"
    updated = update_article_status(
        article_id,
        target_status,
        actor=username,
        note=payload.note,
        decision=payload.decision,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")
    return {
        "ok": True,
        "id": article_id,
        "decision": payload.decision,
        "to_status": target_status,
    }


@app.post("/api/ingestion/run")
def api_run_ingestion(payload: IngestionRunRequest, username: str = Depends(require_auth)) -> dict:
    stats = run_ingestion(feed_id=payload.feed_id)
    return {
        "ok": stats.status == "success",
        "run_id": stats.run_id,
        "status": stats.status,
        "message": stats.message,
        "stats": {
            "feeds_processed": stats.feeds_processed,
            "entries_seen": stats.entries_seen,
            "articles_upserted": stats.articles_upserted,
        },
        "requested_by": username,
    }
