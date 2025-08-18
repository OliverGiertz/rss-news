#!/usr/bin/env python3
"""
image_deduper.py — Finde und bereinige Bild-Dubletten sicher & reversibel.

Neu:
- collect: Bild-URLs aus JSON/HTML/Markdown/Text sammeln und lokal in .media_cache/ speichern
- scan/report/apply: wie gehabt (Hardlink/Delete), jetzt standardmäßig mit Cache nutzbar

Workflows:
  # A) Nur remote-Referenzen vorhanden → erst sammeln, dann deduplizieren
  python tools/image_deduper.py collect --sources processed_articles.json,content/ --cache .media_cache
  python tools/image_deduper.py scan --roots .media_cache --out-dir .dedupe --phash
  python tools/image_deduper.py apply --report .dedupe/report.csv --mode hardlink --dry-run
  python tools/image_deduper.py apply --report .dedupe/report.csv --mode hardlink

  # B) Lokale Bild-Ordner vorhanden
  python tools/image_deduper.py scan --roots ./media,./static/images --out-dir .dedupe --phash

Hinweise:
- "collect" speichert Bilder content-addressed (<sha256>.<ext>) und lädt identische Dateien nicht doppelt.
- Für HTML/Markdown werden Bild-URLs geparst; für JSON werden alle Stringwerte mit Bild-URL-Muster extrahiert.
"""

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Set
from urllib.parse import urlparse

# Optionale Parser/Helpers
try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import imagehash  # type: ignore
except ImportError:
    imagehash = None

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DEFAULT_INDEX = ".dedupe/index.sqlite"
DEFAULT_REPORT = ".dedupe/report.csv"
DEFAULT_CACHE = ".media_cache"

URL_RE = re.compile(
    r"""https?://[^\s"'<>]+?\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\s"'<>]*)?""",
    re.IGNORECASE,
)

def human_mb(nbytes: int) -> str:
    return f"{nbytes/1_000_000:.2f} MB"


# ---------------------------
# Hashing & pHash
# ---------------------------
def sha256_file(path: Path, bufsize: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def calc_phash(path: Path) -> Optional[str]:
    if Image is None or imagehash is None:
        return None
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            ph = imagehash.phash(im, hash_size=16)  # 16x16 → 256-bit
            return str(ph)
    except Exception:
        return None


# ---------------------------
# Index (SQLite)
# ---------------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def init_index(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            sha256 TEXT NOT NULL,
            phash TEXT,
            ext TEXT NOT NULL
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sha256 ON files (sha256);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_phash ON files (phash);")
    conn.commit()
    conn.close()


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def walk_images(roots: List[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            # Skip silently to be more forgiving; user might pass multiple roots
            continue
        for p in root.rglob("*"):
            if p.is_file() and is_image(p):
                yield p


def upsert_file(db_path: Path, path: Path, sha256: str, phash: Optional[str]):
    st = path.stat()
    row = (str(path), st.st_size, st.st_mtime, sha256, phash, path.suffix.lower())
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO files (path, size, mtime, sha256, phash, ext)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            size=excluded.size,
            mtime=excluded.mtime,
            sha256=excluded.sha256,
            phash=excluded.phash,
            ext=excluded.ext;
    """, row)
    conn.commit()
    conn.close()


def group_by_sha256(db_path: Path) -> List[List[Tuple[int, str, int]]]:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT sha256 FROM files GROUP BY sha256 HAVING COUNT(*) > 1;")
    hashes = [r[0] for r in cur.fetchall()]
    groups = []
    for h in hashes:
        cur.execute("SELECT id, path, size FROM files WHERE sha256=?", (h,))
        rows = cur.fetchall()
        groups.append([(rid, rpath, rsize) for rid, rpath, rsize in rows])
    conn.close()
    return groups


def write_csv_report(db_path: Path, csv_path: Path) -> Tuple[int, int]:
    groups = group_by_sha256(db_path)
    ensure_dir(csv_path.parent)
    total_dups = 0
    total_savings = 0
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group_id", "canonical_path", "dup_path", "dup_size_bytes"])
        gid = 0
        for g in groups:
            if not g:
                continue
            canonical = max(g, key=lambda x: x[2])  # größte Datei als Kanon
            for rid, path, size in g:
                if path == canonical[1]:
                    continue
                total_dups += 1
                total_savings += size
                w.writerow([gid, canonical[1], path, size])
            gid += 1
    return total_dups, total_savings


# ---------------------------
# Apply (Hardlink/Delete)
# ---------------------------
def apply_hardlink(canonical: Path, dup: Path, dry_run: bool) -> None:
    if dry_run:
        return
    tmp = dup.with_suffix(dup.suffix + ".dedupe.tmp")
    dup.unlink(missing_ok=False)
    os.link(canonical, tmp)  # gleicher FS notwendig
    tmp.replace(dup)


def apply_delete(dup: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dup.unlink(missing_ok=False)


@dataclass
class ApplyStats:
    processed: int = 0
    errors: int = 0
    saved_bytes: int = 0


def apply_changes(csv_report: Path, mode: str, dry_run: bool) -> ApplyStats:
    stats = ApplyStats()
    with csv_report.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            canonical = Path(row["canonical_path"])
            dup = Path(row["dup_path"])
            size = int(row["dup_size_bytes"])
            try:
                if mode == "hardlink":
                    apply_hardlink(canonical, dup, dry_run)
                elif mode == "delete":
                    apply_delete(dup, dry_run)
                else:
                    raise ValueError("mode must be 'hardlink' or 'delete'")
                stats.processed += 1
                stats.saved_bytes += size
            except Exception as e:
                stats.errors += 1
                print(f"[ERROR] {dup}: {e}", file=sys.stderr)
    return stats


# ---------------------------
# Collect (URLs -> Cache)
# ---------------------------
def is_image_url(url: str) -> bool:
    if URL_RE.search(url):
        return True
    # Fallback: Extension anhand des Pfads
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    return ext in IMAGE_EXTS


def extract_urls_from_text(text: str) -> Set[str]:
    urls = set(URL_RE.findall(text))
    return urls


def extract_urls_from_html(text: str) -> Set[str]:
    urls = set()
    if BeautifulSoup is None:
        return extract_urls_from_text(text)
    try:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup.find_all(["img", "source"]):
            src = tag.get("src") or tag.get("data-src")
            if src and is_image_url(src):
                urls.add(src)
        # Fallback auf nackte URLs
        urls |= extract_urls_from_text(text)
    except Exception:
        urls |= extract_urls_from_text(text)
    return urls


def extract_urls_from_json(obj) -> Set[str]:
    urls = set()
    if isinstance(obj, dict):
        for v in obj.values():
            urls |= extract
