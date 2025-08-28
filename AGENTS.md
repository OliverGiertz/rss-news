# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: Streamlit UI (entry point for the app).
- `main.py`: RSS fetching, rewrite, and WordPress upload logic.
- `utils/`: Helpers (image/article extraction, WP uploader, UI helpers).
- `pages/`: Streamlit pages (e.g., `01_feed_manager.py`, `log_viewer.py`).
- `data/`: JSON state (`articles.json`, `feeds.json`).
- `logs/`: Runtime logs (`rss_tool.log`).
- `docs/`: Project notes (e.g., roadmap).
- `__version__.py`: Version string written by `versioning.py`.

## Build, Test, and Development Commands
- Create env: `python -m venv .venv && source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run app: `streamlit run app.py`
- Version bump: `python versioning.py --level patch --push` (updates `__version__.py`, prepares `CHANGELOG.md`, creates tag; see `--help`).

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8, 4-space indentation, type hints where practical.
- Modules and functions: `snake_case`; classes: `PascalCase`.
- Streamlit pages: numeric prefix for order, e.g., `pages/01_feature.py`.
- Keep functions small and pure in `utils/`; isolate I/O in app layers.
- Suggested tools (optional): Black (`black .`) and Ruff (`ruff check .`).

## Testing Guidelines
- Framework: pytest (recommended). Place tests under `tests/` with `test_*.py`.
- Unit tests for `utils/*`; light integration checks for `main.py` with temporary files.
- Run: `pytest -q`. Add coverage if needed (e.g., `pytest --cov=utils`).
- Test data: avoid mutating files in `data/`; use temp dirs or fixtures.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise; examples: `Add feed dedupe`, `Fix WP upload retry`, `Bump version to v1.7.0`.
- PRs: clear description, linked issue, screenshots/GIFs for UI changes, note env variables touched.
- Update `CHANGELOG.md` and bump version via `versioning.py` before release PRs.

## Security & Configuration Tips
- Required env: `OPENAI_API_KEY`, `WP_BASE_URL`, `WP_USERNAME`, `WP_PASSWORD` or `WP_AUTH_BASE64` (see `.env`).
- Never commit secrets; `.env` is git-ignored. Avoid hardcoded credentials; prefer `os.getenv`.
- Logs and data may contain content; do not commit `logs/` or large `data/` snapshots.
