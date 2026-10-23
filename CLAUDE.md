# ADB Glue Service

Take-home assignment: a glue service for an electronics reseller that sells on its own shop (Electronic Market, shaped like Adobe Commerce) and on the eMAG Marketplace from one Bucharest warehouse. It routes orders from both channels to the warehouse, pushes true stock back to both channels, and handles duplicates, retries, partial failures and cross-channel oversell. Due 2026-10-26. Design in `docs/architecture.md`, customer note in `docs/customer-context.md`.

The full implementation plan is kept outside the repo on purpose.

## Stack

- Glue and mocks: Python 3.12, FastAPI, pydantic, httpx, SQLite (stdlib, migrations by `PRAGMA user_version` in `glue/db.py`). The mocks are server-rendered Jinja.
- Dashboard: React 18, TypeScript, Vite, TanStack Query, React Router, Recharts, cmdk, CSS Modules, in `frontend/`.
- AI helpers: Ollama (`qwen2.5:3b`) through the openai SDK, in `glue/ai/`.
- Docker Compose with a multi-stage build. Tests: pytest and Vitest. Lint: ruff, ESLint, tsc.
- Nothing else unless agreed.

## Scope

- POC, not production. Depth over breadth: the sync core comes first.
- Core vs the rest: the top-level `glue/` modules are the sync core and its read models; `glue/api/` and `frontend/` are the operator console; `glue/ai/` and `glue/demo/` are optional layers. `glue/main.py` wires them together; keep their logic out of the core modules.
- Tests and logging are required here. This overrides the global "add tests only where a suite exists" rule.

## Code style

- Type hints on public functions. No docstrings or comments unless the *why* is non-obvious.
- No base classes, no `utils.py`, no configuration nobody asked for. Modules aim for about 150 lines; functions fit on a screen. `glue/db.py` is the deliberate exception, because all SQL lives there.
- Only `glue/router.py` changes an order's status. `glue/schema.sql` is migration 1 and never changes; schema changes are new steps in `MIGRATIONS`.
- `ruff check . && ruff format .` before every commit; in `frontend/`, `npm run lint && npm run typecheck && npm test`.

## Repo hygiene

- Never commit: the assignment PDF, `.env`, `research/`, anything from other projects or employers.
- Commit author is the repo-local identity already configured. **Never add AI attribution lines** (no `Co-Authored-By`, no "Generated with"). Ask before each commit. Push only when asked.

## Working with the user

- Short, focused replies. Lead with the answer.
- Explain unfamiliar terms in plain words the first time they come up.
