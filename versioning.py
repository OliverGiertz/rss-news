# versioning.py

import re
import subprocess
from pathlib import Path
from datetime import datetime
import typer

app = typer.Typer()

CHANGELOG_FILE = Path("CHANGELOG.md")
VERSION_FILE = Path("__version__.py")
VERSION_PATTERN = r"## \[v?(\d+\.\d+\.\d+)\]"


def get_latest_version():
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    matches = re.findall(VERSION_PATTERN, content)
    return matches[0] if matches else "0.0.0"


def bump_version(version: str, level: str = "patch") -> str:
    major, minor, patch = map(int, version.split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    elif level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_version_file(version: str):
    VERSION_FILE.write_text(f"VERSION = \"{version}\"\n", encoding="utf-8")
    typer.echo(f"🔢 __version__.py aktualisiert auf {version}")


def prepend_changelog(version: str):
    today = datetime.today().strftime("%Y-%m-%d")
    new_entry = f"\n\n## [v{version}] – {today}\n\n### 💡 Neue Funktionen\n- \n\n### 🔧 Änderungen & Fixes\n- \n\n### 📦 Internes\n- "
    original = CHANGELOG_FILE.read_text(encoding="utf-8")
    CHANGELOG_FILE.write_text(new_entry + original, encoding="utf-8")
    typer.echo(f"📝 Neuer Eintrag für v{version} zu CHANGELOG.md hinzugefügt")


def validate_changelog(version: str) -> bool:
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    pattern = rf"## \[v?{re.escape(version)}\](.*?)^## \["
    match = re.search(pattern, content + "\n## [", re.DOTALL | re.MULTILINE)
    if match:
        section = match.group(1).strip()
        if any(line.strip() != "-" for line in section.splitlines() if line.strip()):
            return True
    typer.echo("⚠️ CHANGELOG-Eintrag ist noch leer oder unvollständig.")
    return False


def create_git_tag(version: str):
    try:
        subprocess.run(["git", "add", str(CHANGELOG_FILE), str(VERSION_FILE)], check=True)
        subprocess.run(["git", "commit", "-m", f"🔖 Release v{version}"], check=True)
        subprocess.run(["git", "tag", f"v{version}"], check=True)
        typer.echo(f"🏷️ Git-Tag 'v{version}' erstellt und commit durchgeführt.")
    except subprocess.CalledProcessError:
        typer.echo("⚠️ Git-Fehler beim Taggen oder Committen. Bitte manuell prüfen.")


def push_to_github():
    try:
        subprocess.run(["git", "push"], check=True)
        subprocess.run(["git", "push", "--tags"], check=True)
        typer.echo("🚀 Änderungen und Tags an GitHub gepusht.")
    except subprocess.CalledProcessError:
        typer.echo("⚠️ Fehler beim Pushen zu GitHub. Bitte Zugang oder Netzwerk prüfen.")


@app.command()
def list():
    "Listet alle verfügbaren Versionen aus dem CHANGELOG"
    typer.echo("\n📚 Verfügbare Versionen im CHANGELOG:")
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    versions = re.findall(VERSION_PATTERN, content)
    for v in versions:
        typer.echo(f"- v{v}")


@app.command()
def rollback():
    "Letzte Version zurückrollen (Tag löschen + Commit zurücknehmen)"
    last_version = get_latest_version()
    if typer.confirm(f"⚠️ Letzte Version 'v{last_version}' wirklich zurücknehmen?"):
        try:
            subprocess.run(["git", "tag", "-d", f"v{last_version}"], check=True)
            subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True)
            typer.echo(f"🔙 Version 'v{last_version}' wurde zurückgerollt.")
        except subprocess.CalledProcessError:
            typer.echo("❌ Rollback fehlgeschlagen.")
    else:
        typer.echo("⛔ Abgebrochen.")


@app.command()
def create(level: str = typer.Option("patch", help="Versionstyp: patch, minor oder major"),
           push: bool = typer.Option(False, help="Änderungen direkt an GitHub pushen")):
    "Neue Version erstellen inkl. CHANGELOG, Git-Tag und optional Push"
    current_version = get_latest_version()
    next_version = bump_version(current_version, level)

    typer.echo(f"💡 Aktuelle Version: {current_version}")
    typer.echo(f"🚀 Neue Version: {next_version}")

    if typer.confirm("Version übernehmen und eintragen?"):
        write_version_file(next_version)
        prepend_changelog(next_version)

        typer.echo("\nBitte CHANGELOG.md bearbeiten und danach fortfahren.")
        typer.prompt("Drücke Enter, sobald du den neuen Abschnitt ausgefüllt hast")

        if not validate_changelog(next_version):
            typer.echo("❌ Release abgebrochen: Bitte fülle den CHANGELOG-Eintrag aus.")
            raise typer.Exit(code=1)

        create_git_tag(next_version)

        if push:
            push_to_github()

        typer.echo(f"✅ Version {next_version} erfolgreich erstellt.")
    else:
        typer.echo("❌ Abgebrochen.")


if __name__ == "__main__":
    app()
