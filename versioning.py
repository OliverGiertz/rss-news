import re
import subprocess
from pathlib import Path
from datetime import datetime
import typer
import os

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

def update_changelog(version: str):
    date = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"## [{version}] - {date}\n\n- Beschreibung...\n\n"
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    CHANGELOG_FILE.write_text(new_entry + content, encoding="utf-8")

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

def create_git_tag(version: str, sign: bool):
    if sign:
        subprocess.run(["git", "tag", "-s", f"v{version}", "-m", f"Release v{version}"], check=True)
    else:
        subprocess.run(["git", "tag", "-a", f"v{version}", "-m", f"Release v{version} (unsigned)"], check=True)

def push_git_tag(version: str):
    subprocess.run(["git", "push"], check=True)
    subprocess.run(["git", "push", "origin", f"v{version}"], check=True)

@app.command()
def create(level: str = "patch", push: bool = False, no_sign: bool = False):
    current = get_latest_version()
    new_version = bump_version(current, level)
    write_version_file(new_version)
    update_changelog(new_version)
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

    create_git_tag(new_version, sign=use_signing)

    if push:
        push_git_tag(new_version)

    if use_signing:
        if signing_method == "ssh":
            typer.secho(f"✅ Version {new_version} erstellt und signiert mit SSH 🔐", fg=typer.colors.GREEN)
        elif signing_method == "gpg":
            typer.secho(f"✅ Version {new_version} erstellt und signiert mit GPG 🔏", fg=typer.colors.CYAN)
    else:
        typer.secho(f"⚠️  Version {new_version} wurde ohne Signatur erstellt", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
