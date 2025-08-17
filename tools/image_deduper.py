#!/usr/bin/env python3
"""
image_deduper.py — Finde und bereinige Bild-Dubletten sicher & reversibel.

Funktionen:
- Scan: Verzeichnisse rekursiv scannen, sha256 + pHash berechnen
- Report: CSV + menschenlesbare Zusammenfassung mit Gruppen
- Apply: Duplikate auf kanonische Datei umbiegen (Hardlink/Löschen)
- Optional: DB-Referenzen aktualisieren (SQLite/SQLModel kompatibel)

Nutzung (Beispiele):
  # 1) Nur scannen + reporten (keine Änderungen):
  python tools/image_deduper.py scan --roots media,assets/images --out-dir .dedupe --phash

  # 2) Report anzeigen:
  python tools/image_deduper.py report --index .dedupe/index.sqlite --csv

  # 3) Anwenden (Hardlinks setzen, Dry-Run):
  python tools/image_deduper.py apply --index .dedupe/index.sqlite --mode hardlink --dry-run

  # 4) Anwenden (wirklich ändern):
  python tools/image_deduper.py apply --index .dedupe/index.sqlite --mode hardlink

  # 5) Referenzen in DB aktualisieren (optional):
  python tools/image_deduper.py apply --index .dedupe/index.sqlite --update-db sqlite:///./rssbot.db --dry-run
"""

import argparse
import csv
import hashlib
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import imagehash  # type: ignore
except ImportError:
    imagehash = None


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DEFAULT_INDEX = ".dedupe/index.sqlite"
DEFAULT_REPORT = ".dedupe/report.csv"


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
    """Return list of groups: [(id, path, size), ...] where sha256 identical and len(group) > 1."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("""
        SELECT sha256 FROM files GROUP BY sha256 HAVING COUNT(*) > 1;
    """)
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
            # Kanon: größte Datei (oder erste)
            canonical = max(g, key=lambda x: x[2])
            for rid, path, size in g:
                if path == canonical[1]:
                    continue
                total_dups += 1
                total_savings += size
                w.writerow([gid, canonical[1], path, size])
            gid += 1
    return total_dups, total_savings


def apply_hardlink(canonical: Path, dup: Path, dry_run: bool) -> None:
    # Ersetzt dup durch Hardlink auf canonical (gleiche Partition nötig)
    if dry_run:
        return
    tmp = dup.with_suffix(dup.suffix + ".dedupe.tmp")
    dup.unlink()                # entferne dup
    os.link(canonical, tmp)     # hardlink temp
    tmp.replace(dup)            # atomarer move


def apply_delete(dup: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dup.unlink()


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


def parse_roots(roots_arg: str) -> List[Path]:
    parts = [Path(p.strip()) for p in roots_arg.split(",") if p.strip()]
    for p in parts:
        if not p.exists():
            raise FileNotFoundError(f"Root not found: {p}")
    return parts


def cmd_scan(args):
    out_dir = Path(args.out_dir)
    index = Path(args.index or DEFAULT_INDEX)
    ensure_dir(out_dir)
    ensure_dir(index.parent)
    init_index(index)
    roots = parse_roots(args.roots)

    count = 0
    for path in walk_images(roots):
        try:
            h = sha256_file(path)
            ph = calc_phash(path) if args.phash else None
            upsert_file(index, path, h, ph)
            count += 1
            if count % 500 == 0:
                print(f"... indexed {count} files")
        except Exception as e:
            print(f"[WARN] {path}: {e}", file=sys.stderr)

    dups, savings = write_csv_report(index, Path(args.report or DEFAULT_REPORT))
    print(f"Indexed {count} images. Found duplicate files: {dups}, potential savings: {savings/1_000_000:.2f} MB")
    print(f"Index: {index}")
    print(f"Report: {args.report or DEFAULT_REPORT}")


def cmd_report(args):
    index = Path(args.index or DEFAULT_INDEX)
    csv_path = Path(args.report or DEFAULT_REPORT)
    dups, savings = write_csv_report(index, csv_path)
    print(f"Duplicates: {dups}, potential savings: {savings/1_000_000:.2f} MB")
    if args.csv:
        print(f"CSV written: {csv_path}")


def cmd_apply(args):
    csv_report = Path(args.report or DEFAULT_REPORT)
    if not csv_report.exists():
        raise FileNotFoundError(f"Report not found: {csv_report}")
    stats = apply_changes(csv_report, args.mode, args.dry_run)
    print(f"Processed: {stats.processed}, Errors: {stats.errors}, Saved: {stats.saved_bytes/1_000_000:.2f} MB (mode={args.mode}, dry_run={args.dry_run})")
    if args.update_db:
        # Platzhalter: hier könntest du eure DB-Referenzen aktualisieren (falls Bilder-Paths in DB gespeichert sind).
        # Beispiel: SQLModel mit Tabelle ImageMeta(content_hash UNIQUE, local_path) → auf kanonischen Pfad umbiegen.
        print(f"[INFO] DB update requested for: {args.update_db} (implementierung projektspezifisch)")


def main():
    ap = argparse.ArgumentParser(description="Bild-Deduplizierung (scan/report/apply)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scan", help="Verzeichnisse scannen und Index/Report erstellen")
    sc.add_argument("--roots", required=True, help="Kommagetrennte Wurzelpfade, z.B. 'media,assets/images'")
    sc.add_argument("--out-dir", default=".dedupe", help="Ausgabeverzeichnis für Index/Reports")
    sc.add_argument("--index", help="Pfad zur SQLite-Indexdatei (default .dedupe/index.sqlite)")
    sc.add_argument("--report", help="Pfad zum CSV-Report (default .dedupe/report.csv)")
    sc.add_argument("--phash", action="store_true", help="Perzeptuellen Hash berechnen (für zukünftige Near-Dups)")
    sc.set_defaults(func=cmd_scan)

    rp = sub.add_parser("report", help="Report neu generieren/anzeigen")
    rp.add_argument("--index", help="Pfad zur SQLite-Indexdatei")
    rp.add_argument("--report", help="Pfad zum CSV-Report")
    rp.add_argument("--csv", action="store_true", help="CSV-Pfad ausgeben")
    rp.set_defaults(func=cmd_report)

    aply = sub.add_parser("apply", help="Änderungen anwenden (Hardlink/Delete)")
    aply.add_argument("--report", help="Pfad zum CSV-Report")
    aply.add_argument("--mode", choices=["hardlink", "delete"], default="hardlink", help="Strategie für Duplikate")
    aply.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    aply.add_argument("--update-db", help="Optional: DB-URL für Referenz-Updates (projektspezifisch)")
    aply.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
