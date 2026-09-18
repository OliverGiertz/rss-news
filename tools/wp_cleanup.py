#!/usr/bin/env python3
"""
wp_cleanup.py — Automatisch erzeugte Blogbeiträge samt Bildern aus WordPress entfernen.

Hintergrund: Nach einer Abmahnung wegen fremder Bilder werden alle vom
News-Portal erzeugten Beiträge und die dazu hochgeladenen Medien gelöscht.
Das Skript arbeitet in zwei getrennten Schritten, damit nichts verschwindet,
was vorher niemand gesehen hat:

  1) scan   — liest alles, löscht nichts, schreibt Listen in ein Verzeichnis
  2) apply  — löscht genau das, was der Scan aufgelistet hat, mit Protokoll

Gruppen:
  A  geplant/Entwurf mit Attributionsblock          -> löschen (Beitrag + Bild)
  B  veröffentlicht mit Attributionsblock           -> löschen (Beitrag + Bild)
  C  ohne Attributionsblock, aber ab 2026 oder      -> Liste zur Durchsicht; per --private
     nicht veröffentlicht                              auf privat, fremdes Bild wird gelöscht
  M  Medien: Beitragsbilder von A/B sowie Waisen     -> löschen
     mit "Quelle:"-Caption

Erkennungsmerkmal für Tool-Beiträge ist der Absatz mit der CSS-Klasse
`article-attribution`, den der Publisher unter jeden Beitrag schreibt.

Nutzung (auf dem Server, aus /opt/rss-news):
  .venv/bin/python tools/wp_cleanup.py scan  --out /root/wp-cleanup
  .venv/bin/python tools/wp_cleanup.py apply --from /root/wp-cleanup/<stempel>
  .venv/bin/python tools/wp_cleanup.py apply --from ... --private   # zusätzlich Gruppe C
  .venv/bin/python tools/wp_cleanup.py prune-tags                   # leere Schlagwörter
  .venv/bin/python tools/wp_cleanup.py portal-reset                 # Portal-DB leeren (mit Backup)

Vor `apply` die Liste c.csv durchsehen und Zeilen entfernen, die öffentlich
bleiben sollen — `apply --private` liest die (gekürzte) Datei.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import get_settings  # noqa: E402
from backend.app.wordpress import _auth_header  # noqa: E402

ATTRIBUTION_MARKER = "article-attribution"
FOREIGN_CAPTION_MARKER = "Quelle:"
# Eigene Beiträge ohne Attributionsblock aus diesem Jahr könnten trotzdem vom
# Tool stammen (ältere Version) — sie landen zur Durchsicht in Gruppe C.
REVIEW_FROM = "2026-01-01"
PER_PAGE = 100


# ---------------------------------------------------------------------------
# WordPress-Zugriff
# ---------------------------------------------------------------------------

class WP:
    def __init__(self) -> None:
        s = get_settings()
        if not (s.wordpress_base_url and s.wordpress_username and s.wordpress_app_password):
            sys.exit("WordPress-Zugangsdaten fehlen (WP_BASE_URL / WP_USERNAME / WP_PASSWORD).")
        self.base = s.wordpress_base_url.rstrip("/")
        self.auth = _auth_header(s.wordpress_username, s.wordpress_app_password)

    def call(self, method: str, endpoint: str, params: dict | None = None, payload: dict | None = None):
        url = f"{self.base}/wp-json/wp/v2/{endpoint.lstrip('/')}"
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(
            url=url,
            data=data,
            method=method,
            headers={
                "Authorization": self.auth,
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "rss-news-cleanup/1.0",
            },
        )
        with urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            total = resp.headers.get("X-WP-Total")
        body = json.loads(raw) if raw else {}
        return body, int(total) if total else None

    def paged(self, endpoint: str, params: dict) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            body, _ = self.call("GET", endpoint, {**params, "per_page": PER_PAGE, "page": page})
            if not body:
                break
            items.extend(body)
            if len(body) < PER_PAGE:
                break
            page += 1
        return items


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def _post_row(p: dict) -> dict:
    return {
        "id": p["id"],
        "status": p.get("status"),
        "date": p.get("date"),
        "title": (p.get("title") or {}).get("rendered") or (p.get("title") or {}).get("raw") or "",
        "link": p.get("link"),
        "featured_media": p.get("featured_media") or 0,
        "categories": p.get("categories") or [],
    }


def _media_row(m: dict, reason: str) -> dict:
    caption = m.get("caption") or {}
    return {
        "id": m["id"],
        "date": m.get("date"),
        "file": m.get("source_url"),
        "parent_post": m.get("post") or 0,
        "caption": (caption.get("raw") or caption.get("rendered") or "").strip()[:200],
        "reason": reason,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()})


def classify(posts: list[dict], media: list[dict]) -> dict[str, list[dict]]:
    """Beiträge und Medien in die Gruppen A/B/C/M einteilen (reine Funktion)."""
    group_a: list[dict] = []
    group_b: list[dict] = []
    group_c: list[dict] = []
    keep: list[dict] = []
    for p in posts:
        content = (p.get("content") or {})
        html = content.get("raw") or content.get("rendered") or ""
        row = _post_row(p)
        tool_made = ATTRIBUTION_MARKER in html
        published = p.get("status") == "publish"
        if tool_made and published:
            group_b.append(row)
        elif tool_made:
            group_a.append(row)
        elif not published or (p.get("date") or "") >= REVIEW_FROM:
            group_c.append(row)
        else:
            keep.append(row)

    def _caption(m: dict) -> str:
        c = m.get("caption") or {}
        return c.get("raw") or c.get("rendered") or ""

    doomed_posts = {r["id"] for r in group_a + group_b}
    featured = {r["featured_media"] for r in group_a + group_b if r["featured_media"]}
    # Ein Bild, das auch ein bleibender Beitrag nutzt, bleibt — egal woher es
    # stammt. Es taucht in shared.csv auf, damit es niemand vergisst.
    protected = {r["featured_media"] for r in keep + group_c if r["featured_media"]}
    post_ids = {p["id"] for p in posts}
    group_m: list[dict] = []
    shared: list[dict] = []
    for m in media:
        parent = m.get("post") or 0
        if m["id"] in featured:
            reason = "beitragsbild"
        elif parent in doomed_posts:
            reason = "an tool-beitrag angehängt"
        elif FOREIGN_CAPTION_MARKER in _caption(m) and parent not in post_ids:
            reason = "waise mit quelle-caption"
        else:
            continue
        if m["id"] in protected:
            shared.append(_media_row(m, f"{reason}, aber an behaltenem beitrag"))
            continue
        group_m.append(_media_row(m, reason))

    # Eigene Medien, die zufällig "Quelle:" tragen und an einem behaltenen
    # Beitrag hängen, bleiben unangetastet — sie tauchen nur zur Kenntnis auf.
    suspicious = [
        _media_row(m, "quelle-caption an behaltenem beitrag")
        for m in media
        if FOREIGN_CAPTION_MARKER in _caption(m)
        and (m.get("post") or 0) in post_ids
        and (m.get("post") or 0) not in doomed_posts
    ]

    # Gruppe C: bleibt der Beitrag privat, muss ein fremdes Bild trotzdem weg.
    foreign_media = {m["id"] for m in media if FOREIGN_CAPTION_MARKER in _caption(m)}
    for row in group_c:
        row["bild_fremd"] = "ja" if row["featured_media"] in foreign_media else "nein"

    return {"a": group_a, "b": group_b, "c": group_c, "m": group_m,
            "keep": keep, "suspicious": suspicious, "shared": shared}


def cmd_scan(args: argparse.Namespace) -> None:
    wp = WP()
    out = Path(args.out) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)

    print("Lese Beiträge (alle Status) …")
    posts = wp.paged("posts", {"status": "any", "context": "edit",
                               "_fields": "id,status,date,title,link,featured_media,categories,content"})
    print(f"  {len(posts)} Beiträge")
    print("Lese Mediathek …")
    media = wp.paged("media", {"context": "edit", "_fields": "id,date,source_url,post,caption"})
    print(f"  {len(media)} Medien")

    groups = classify(posts, media)
    for name, rows in groups.items():
        (out / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        _write_csv(out / f"{name}.csv", rows)

    summary = {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "posts_total": len(posts),
        "media_total": len(media),
        "A_geplant_loeschen": len(groups["a"]),
        "B_veroeffentlicht_loeschen": len(groups["b"]),
        "C_zur_durchsicht": len(groups["c"]),
        "M_medien_loeschen": len(groups["m"]),
        "behalten": len(groups["keep"]),
        "verdaechtig_behalten": len(groups["suspicious"]),
        "geteilt_behalten": len(groups["shared"]),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print()
    for k, v in summary.items():
        print(f"  {k:28} {v}")
    print(f"\nListen liegen in {out}")
    print("Nichts wurde verändert. Vor `apply` bitte c.csv durchsehen.")


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

class Protocol:
    def __init__(self, path: Path) -> None:
        self.fh = path.open("a")

    def log(self, **entry) -> None:
        entry["at"] = datetime.now().isoformat(timespec="seconds")
        self.fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.fh.flush()


def _delete(wp: WP, proto: Protocol, kind: str, row: dict) -> bool:
    endpoint = f"{'posts' if kind == 'post' else 'media'}/{row['id']}"
    try:
        wp.call("DELETE", endpoint, {"force": "true"})
        proto.log(action="delete", kind=kind, ok=True, **row)
        return True
    except HTTPError as exc:
        # 404 heißt: schon weg — für das Protokoll ist das ein Erfolg.
        ok = exc.code == 404
        proto.log(action="delete", kind=kind, ok=ok, http=exc.code, **row)
        if not ok:
            print(f"  FEHLER {kind} #{row['id']}: HTTP {exc.code}")
        return ok


def _privatize(wp: WP, proto: Protocol, row: dict) -> None:
    payload = {"status": "private"}
    if row.get("bild_fremd") == "ja":
        payload["featured_media"] = 0
    try:
        wp.call("POST", f"posts/{row['id']}", payload=payload)
        proto.log(action="private", kind="post", ok=True, **row)
    except HTTPError as exc:
        proto.log(action="private", kind="post", ok=False, http=exc.code, **row)
        print(f"  FEHLER privat #{row['id']}: HTTP {exc.code}")
        return
    # Ein fremdes Bild bleibt sonst unter seiner Datei-URL erreichbar.
    if row.get("bild_fremd") == "ja" and row.get("featured_media"):
        _delete(wp, proto, "media", {"id": row["featured_media"], "reason": "bild von privatem beitrag"})


def cmd_apply(args: argparse.Namespace) -> None:
    src = Path(args.src)
    if not (src / "summary.json").exists():
        sys.exit(f"{src} ist kein Scan-Verzeichnis (summary.json fehlt).")
    load = lambda n: json.loads((src / f"{n}.json").read_text())  # noqa: E731
    group_a, group_b, group_m = load("a"), load("b"), load("m")
    group_c = _read_c_csv(src / "c.csv") if args.private else []

    print(f"Zu löschen: {len(group_a)} geplante, {len(group_b)} veröffentlichte Beiträge, {len(group_m)} Medien")
    if args.private:
        print(f"Auf privat: {len(group_c)} Beiträge aus c.csv")
    if not args.yes:
        answer = input("Endgültig löschen? Tippe 'löschen': ")
        if answer.strip() != "löschen":
            sys.exit("Abgebrochen.")

    wp = WP()
    proto = Protocol(src / "protokoll.jsonl")
    proto.log(action="start", scan_dir=str(src), private=bool(args.private))

    ok = fail = 0
    for label, rows in (("A", group_a), ("B", group_b)):
        print(f"Gruppe {label}: {len(rows)} Beiträge")
        for i, row in enumerate(rows, 1):
            if _delete(wp, proto, "post", row):
                ok += 1
            else:
                fail += 1
            if i % 50 == 0:
                print(f"  … {i}/{len(rows)}")
            time.sleep(args.pause)

    print(f"Medien: {len(group_m)}")
    for i, row in enumerate(group_m, 1):
        if _delete(wp, proto, "media", row):
            ok += 1
        else:
            fail += 1
        if i % 50 == 0:
            print(f"  … {i}/{len(group_m)}")
        time.sleep(args.pause)

    for row in group_c:
        _privatize(wp, proto, row)
        time.sleep(args.pause)

    proto.log(action="end", ok=ok, failed=fail)
    print(f"\nFertig: {ok} gelöscht, {fail} fehlgeschlagen. Protokoll: {src / 'protokoll.jsonl'}")


def _read_c_csv(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text().strip():
        return []
    with path.open() as fh:
        return [{"id": int(r["id"]), "title": r.get("title", ""), "link": r.get("link", ""),
                 "featured_media": int(r.get("featured_media") or 0),
                 "bild_fremd": r.get("bild_fremd", "nein")}
                for r in csv.DictReader(fh)]


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

def cmd_prune_tags(args: argparse.Namespace) -> None:
    wp = WP()
    tags = wp.paged("tags", {"_fields": "id,name,count", "hide_empty": "false"})
    empty = [t for t in tags if not t.get("count")]
    print(f"{len(tags)} Schlagwörter, davon {len(empty)} ohne Beitrag")
    if args.dry_run:
        for t in empty[:40]:
            print(f"  #{t['id']} {t['name']}")
        if len(empty) > 40:
            print(f"  … und {len(empty) - 40} weitere")
        return
    for t in empty:
        try:
            wp.call("DELETE", f"tags/{t['id']}", {"force": "true"})
        except HTTPError as exc:
            print(f"  FEHLER tag #{t['id']} {t['name']}: HTTP {exc.code}")
    print("Leere Schlagwörter gelöscht.")


# ---------------------------------------------------------------------------
# Portal-Datenbank
# ---------------------------------------------------------------------------

PORTAL_TABLES = ("articles", "publish_jobs", "tag_proposals", "runs")


def cmd_portal_reset(args: argparse.Namespace) -> None:
    """Artikel und Verlauf des Portals löschen; Feeds und Quellen bleiben.

    Die Ingestion holt danach nur Meldungen der letzten
    `pipeline_max_article_age_days` Tage nach — alles Ältere bleibt draußen.
    """
    import shutil
    import sqlite3

    db_path = Path(get_settings().app_db_path)
    if not db_path.exists():
        sys.exit(f"Datenbank nicht gefunden: {db_path}")
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{db_path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{db_path.suffix}"

    conn = sqlite3.connect(db_path)
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in PORTAL_TABLES}
    print("Zu leeren:", ", ".join(f"{t}={n}" for t, n in counts.items()))
    if not args.yes:
        if input("Portal-Datenbank leeren? Tippe 'leeren': ").strip() != "leeren":
            sys.exit("Abgebrochen.")

    conn.close()
    shutil.copy2(db_path, backup)
    print(f"Backup: {backup}")

    conn = sqlite3.connect(db_path)
    with conn:
        for t in PORTAL_TABLES:
            conn.execute(f"DELETE FROM {t}")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN (%s)" % ",".join("?" * len(PORTAL_TABLES)), PORTAL_TABLES)
    conn.execute("VACUUM")
    conn.close()
    print("Portal-Datenbank geleert; Feeds und Quellen unverändert.")


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="nur lesen, Listen schreiben")
    s.add_argument("--out", default="/root/wp-cleanup", help="Basisverzeichnis für die Listen")
    s.set_defaults(func=cmd_scan)

    a = sub.add_parser("apply", help="löschen, was ein Scan aufgelistet hat")
    a.add_argument("--from", dest="src", required=True, help="Scan-Verzeichnis")
    a.add_argument("--private", action="store_true", help="Gruppe C aus c.csv auf privat stellen")
    a.add_argument("--yes", action="store_true", help="keine Rückfrage")
    a.add_argument("--pause", type=float, default=0.2, help="Sekunden zwischen Anfragen")
    a.set_defaults(func=cmd_apply)

    t = sub.add_parser("prune-tags", help="Schlagwörter ohne Beitrag löschen")
    t.add_argument("--dry-run", action="store_true")
    t.set_defaults(func=cmd_prune_tags)

    r = sub.add_parser("portal-reset", help="Artikel des Portals löschen, Feeds behalten")
    r.add_argument("--backup-dir", default="/root/rss-news-backups")
    r.add_argument("--yes", action="store_true", help="keine Rückfrage")
    r.set_defaults(func=cmd_portal_reset)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
