from __future__ import annotations

from dataclasses import dataclass

from .repositories import (
    claim_next_publish_job,
    complete_publish_job,
    create_publish_job,
    fail_publish_job,
    get_article_by_id,
    mark_article_publish_result,
    PublishJobCreate,
)
from .wordpress import publish_article_draft, selected_image_exists


@dataclass(frozen=True)
class PublisherStats:
    processed: int
    success: int
    failed: int
    requeued: int


def enqueue_publish(article_id: int, max_attempts: int = 3) -> int:
    return create_publish_job(PublishJobCreate(article_id=article_id, max_attempts=max_attempts))


def _can_publish(article: dict) -> tuple[bool, str | None]:
    if article.get("status") not in {"approved", "published"}:
        return False, "Artikelstatus muss 'publish' sein"
    if not selected_image_exists(article):
        return False, "Hauptbild nicht gesetzt"
    return True, None


def run_publisher(max_jobs: int = 10) -> PublisherStats:
    processed = 0
    success = 0
    failed = 0
    requeued = 0

    for _ in range(max(1, max_jobs)):
        job = claim_next_publish_job()
        if not job:
            break
        processed += 1
        job_id = int(job["id"])
        article_id = int(job["article_id"])

        article = get_article_by_id(article_id)
        if not article:
            fail_publish_job(job_id, "Artikel nicht gefunden", requeue=False)
            failed += 1
            continue

        allowed, reason = _can_publish(article)
        if not allowed:
            fail_publish_job(job_id, reason or "Publish-Bedingungen nicht erfüllt", requeue=False)
            mark_article_publish_result(
                article_id,
                wp_post_id=article.get("wp_post_id"),
                wp_post_url=article.get("wp_post_url"),
                error=reason or "blocked",
                increment_attempts=True,
                set_published_status=False,
            )
            failed += 1
            continue

        try:
            wp_post_id, wp_post_url = publish_article_draft(article)
            complete_publish_job(job_id, wp_post_id=wp_post_id, wp_post_url=wp_post_url)
            mark_article_publish_result(
                article_id,
                wp_post_id=wp_post_id,
                wp_post_url=wp_post_url,
                error=None,
                increment_attempts=True,
                set_published_status=True,
            )
            success += 1
        except Exception as exc:
            attempts = int(job.get("attempts", 1))
            max_attempts = int(job.get("max_attempts", 3))
            should_requeue = attempts < max_attempts
            fail_publish_job(job_id, str(exc), requeue=should_requeue)
            mark_article_publish_result(
                article_id,
                wp_post_id=article.get("wp_post_id"),
                wp_post_url=article.get("wp_post_url"),
                error=str(exc),
                increment_attempts=True,
                set_published_status=False,
            )
            if should_requeue:
                requeued += 1
            else:
                failed += 1

    return PublisherStats(processed=processed, success=success, failed=failed, requeued=requeued)
