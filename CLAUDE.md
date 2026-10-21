# ADB Glue Service

Take-home assignment: a glue service for an electronics reseller that sells on its own shop (Electronic Market, shaped like Adobe Commerce) and on the eMAG Marketplace from one warehouse. It routes orders from both channels to the warehouse, pushes true stock back to both channels, and handles duplicates, retries, partial failures and cross-channel oversell. Due 2026-10-26. Design in `docs/architecture.md`.

The full implementation plan is kept outside the repo on purpose.

## Scope

- POC, not production. Python 3.12, FastAPI, Jinja2 + HTMX, httpx, SQLite (stdlib), Docker Compose. Nothing else unless agreed.
- Depth over breadth: the sync core must work end to end before anything is added.
- Tests and logging are required here. This overrides the global "add tests only where a suite exists" rule.

## Code style

- Type hints on public functions. No docstrings or comments unless the *why* is non-obvious.
- No base classes, no `utils.py`, no configuration nobody asked for. Modules under ~150 lines; functions fit on a screen.
- All SQL lives in `glue/db.py`. Only `glue/router.py` changes an order's status.
- `ruff check . && ruff format .` before every commit.

## Repo hygiene

- Never commit: the assignment PDF, `.env`, `research/`, anything from other projects or employers.
- Commit author is the repo-local identity already configured. **Never add AI attribution lines** (no `Co-Authored-By`, no "Generated with"). Ask before each commit. Push only when asked.

## Working with the user

- Short, focused replies. Lead with the answer.
- Explain unfamiliar terms in plain words the first time they come up.
