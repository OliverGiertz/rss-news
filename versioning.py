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

def update_changelog(version: str):
    date = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"## [{version}] - {date}\n\n- Beschreibung...\n\n"
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    CHANGELOG_FILE.write_text(new_entry + content, encoding="utf-8")

def create_git_tag(version: str, signed: bool = True):
    tag_args = ["git", "tag"]
    if signed:
        tag_args.append("-s")  # signierter Tag
    else:
        tag_args.append("-a")  # un-signierter, annotierter Tag
    tag_args += [f"v{version}", "-m", f"Release v{version}"]
    subprocess.run(tag_args, check=True)

def push_git_tag(version: str):
    subprocess.run(["git", "push"], check=True)
    subprocess.run(["git", "push", "origin", f"v{version}"], check=True)

@app.command()
def create(level: str = "patch", push: bool = False, unsigned: bool = False):
    current = get_latest_version()
    new_version = bump_version(current, level)
    write_version_file(new_version)
    update_changelog(new_version)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", f"Bump version to v{new_version}"], check=True)
    create_git_tag(new_version, signed=not unsigned)
    if push:
        push_git_tag(new_version)
    typer.echo(f"✅ Version {new_version} erstellt und getaggt{' (unsigned)' if unsigned else ' (signed)'}.")

if __name__ == "__main__":
    app()
