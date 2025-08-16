import re
import subprocess
from pathlib import Path
from datetime import datetime
import click

CHANGELOG_FILE = Path("CHANGELOG.md")
VERSION_FILE = Path("__version__.py")
VERSION_PATTERN = r"## \[v?(\d+\.\d+\.\d+)\]"

def get_latest_version():
    try:
        # Zuerst versuchen, Git-Tag auszulesen
        tag = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"], stderr=subprocess.DEVNULL)
        return tag.decode("utf-8").strip().lstrip("v")
    except subprocess.CalledProcessError:
        # Fallback auf CHANGELOG.md
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

def is_ssh_signing_available() -> bool:
    return Path("~/.ssh/id_ed25519").expanduser().exists()

def is_gpg_available() -> bool:
    try:
        output = subprocess.check_output(["gpg", "--list-secret-keys"], stderr=subprocess.DEVNULL)
        return bool(output.strip())
    except Exception:
        return False

def configure_signing(use_ssh: bool):
    if use_ssh:
        subprocess.run(["git", "config", "--global", "gpg.format", "ssh"], check=True)
        subprocess.run(["git", "config", "--global", "user.signingkey", "~/.ssh/id_ed25519.pub"], check=True)
    else:
        subprocess.run(["git", "config", "--global", "gpg.format", "openpgp"], check=True)
    subprocess.run(["git", "config", "--global", "commit.gpgsign", "true"], check=True)

@click.command()
@click.option("--level", default="patch", help="Version bump level: patch, minor, major")
@click.option("--version", "specific_version", help="Set specific version (e.g., 2.1.0) instead of auto-bumping")
@click.option("--push", is_flag=True, help="Push to GitHub after creating version")
@click.option("--no-sign", is_flag=True, help="Skip signing of commits and tags")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
def create(level, specific_version, push, no_sign, dry_run):
    """
    Erstellt eine neue Version mit optional signiertem Commit & Tag.
    Optional: --push, --no-sign, --dry-run, --version
    """
    current = get_latest_version()
    
    # Validierung und Festlegung der neuen Version
    if specific_version:
        # Validiere das Format der vorgegebenen Version
        version_pattern = r"^\d+\.\d+\.\d+$"
        if not re.match(version_pattern, specific_version):
            click.secho("❌ Fehler: Version muss im Format X.Y.Z sein (z.B. 2.1.0)", fg="red")
            return
        
        # Prüfe, ob die vorgegebene Version höher als die aktuelle ist
        def version_tuple(v):
            return tuple(map(int, v.split('.')))
        
        if version_tuple(specific_version) <= version_tuple(current):
            click.secho(f"❌ Fehler: Neue Version {specific_version} muss höher sein als aktuelle Version {current}", fg="red")
            return
        
        new_version = specific_version
        click.secho(f"📌 Verwende vorgegebene Version: {new_version}", fg="blue")
    else:
        new_version = bump_version(current, level)
        click.secho(f"🔄 Auto-Bump ({level}): {current} → {new_version}", fg="green")

    if dry_run:
        click.secho("🔍 Dry-Run aktiviert – keine Dateien oder Git-Kommandos werden ausgeführt.\n", fg="yellow")
        click.echo(f"➡️  Aktuelle Version: {current}")
        click.echo(f"➡️  Neue Version:     {new_version}")
        click.echo(f"➡️  Commit-Level:     {level}")
        click.echo(f"➡️  Push nach GitHub: {'Ja' if push else 'Nein'}")
        click.echo(f"➡️  Signieren:        {'Nein' if no_sign else 'Automatisch (SSH > GPG)'}")

        date = datetime.now().strftime("%Y-%m-%d")
        click.echo("\n📄 Vorschlag für CHANGELOG-Eintrag:")
        click.echo(f"\n## [{new_version}] - {date}\n\n- Beschreibung...\n")
        click.secho("🚫 Dry-Run beendet.\n", fg="yellow")
        return

    # Update version file
    write_version_file(new_version)

    # Prepare or check changelog entry
    date = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"## [{new_version}] - {date}\n\n- Beschreibung...\n\n"
    content = CHANGELOG_FILE.read_text(encoding="utf-8")

    if f"## [{new_version}]" in content:
        click.secho(f"ℹ️  Version {new_version} ist bereits im CHANGELOG.md vorhanden. Kein Eintrag hinzugefügt.", fg="blue")
    else:
        CHANGELOG_FILE.write_text(new_entry + content, encoding="utf-8")
        click.secho(f"📄 CHANGELOG.md wurde vorbereitet für Version {new_version}.", fg="magenta")

    click.echo("")
    click.secho("✏️  Bitte jetzt den Eintrag in CHANGELOG.md überprüfen oder anpassen.", fg="cyan")
    input("⏸️  Drücke [Enter], um fortzufahren...")

    subprocess.run(["git", "add", "."], check=True)

    use_signing = False
    signing_method = "none"

    if not no_sign:
        if is_ssh_signing_available():
            configure_signing(use_ssh=True)
            use_signing = True
            signing_method = "ssh"
        elif is_gpg_available():
            configure_signing(use_ssh=False)
            use_signing = True
            signing_method = "gpg"

    commit_cmd = ["git", "commit", "-m", f"Bump version to v{new_version}"]
    if use_signing:
        commit_cmd.append("-S")
    subprocess.run(commit_cmd, check=True)

    if use_signing:
        subprocess.run(["git", "tag", "-s", f"v{new_version}", "-m", f"Release v{new_version}"], check=True)
    else:
        subprocess.run(["git", "tag", "-a", f"v{new_version}", "-m", f"Release v{new_version} (unsigned)"], check=True)

    if push:
        subprocess.run(["git", "push"], check=True)
        subprocess.run(["git", "push", "origin", f"v{new_version}"], check=True)

    if use_signing:
        if signing_method == "ssh":
            click.secho(f"✅ Version {new_version} erstellt und signiert mit SSH 🔐", fg="green")
        elif signing_method == "gpg":
            click.secho(f"✅ Version {new_version} erstellt und signiert mit GPG 🔏", fg="cyan")
    else:
        click.secho(f"⚠️  Version {new_version} wurde ohne Signatur erstellt", fg="yellow")

if __name__ == "__main__":
    create()