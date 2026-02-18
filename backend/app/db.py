import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings


def _db_path() -> Path:
    settings = get_settings()
    path = Path(settings.app_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                base_url TEXT,
                terms_url TEXT,
                license_name TEXT,
                risk_level TEXT NOT NULL DEFAULT 'yellow' CHECK (risk_level IN ('green', 'yellow', 'red')),
                is_enabled INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                last_reviewed_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                etag TEXT,
                last_modified TEXT,
                last_checked_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'success', 'failed')),
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                finished_at TEXT,
                details TEXT
            );

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER,
                source_article_id TEXT,
                source_hash TEXT,
                title TEXT NOT NULL,
                source_url TEXT NOT NULL,
                canonical_url TEXT,
                published_at TEXT,
                author TEXT,
                summary TEXT,
                content_raw TEXT,
                content_rewritten TEXT,
                word_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'rewrite', 'review', 'approved', 'published', 'error')),
                meta_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(feed_id) REFERENCES feeds(id) ON DELETE SET NULL,
                UNIQUE(source_url)
            );

            CREATE INDEX IF NOT EXISTS idx_articles_source_article_id ON articles(source_article_id);
            CREATE INDEX IF NOT EXISTS idx_articles_source_hash ON articles(source_hash);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_articles_feed_source_article_id
              ON articles(feed_id, source_article_id)
              WHERE source_article_id IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS uq_articles_source_hash
              ON articles(source_hash)
              WHERE source_hash IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
            CREATE INDEX IF NOT EXISTS idx_feeds_source_id ON feeds(source_id);
            CREATE INDEX IF NOT EXISTS idx_runs_started_at ON runs(started_at);
            CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);

            CREATE TRIGGER IF NOT EXISTS trg_sources_updated_at
            AFTER UPDATE ON sources
            FOR EACH ROW
            BEGIN
                UPDATE sources SET updated_at = datetime('now') WHERE id = OLD.id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_feeds_updated_at
            AFTER UPDATE ON feeds
            FOR EACH ROW
            BEGIN
                UPDATE feeds SET updated_at = datetime('now') WHERE id = OLD.id;
            END;

            CREATE TRIGGER IF NOT EXISTS trg_articles_updated_at
            AFTER UPDATE ON articles
            FOR EACH ROW
            BEGIN
                UPDATE articles SET updated_at = datetime('now') WHERE id = OLD.id;
            END;
            """
        )

        # Lightweight migration for existing DBs created before source_hash was introduced.
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        if "source_hash" not in existing_columns:
            conn.execute("ALTER TABLE articles ADD COLUMN source_hash TEXT")


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]
