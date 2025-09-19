# Repository Guidelines

## Project Structure & Module Organization
- `api/` REST routes and middleware (RequestID, Logging); expose under `/api/v1`.
- `application/` use‑case orchestration and DTOs (no DB code).
- `domain/` pure business logic: entities, services, events (no infra imports).
- `infrastructure/` persistence, models, DB session, external clients (cache, storage, messaging), Celery tasks.
- `core/` settings, exceptions, responses, structlog config.
- `shared/` common utilities and business codes.
- `alembic/` migrations (`versions/`), `alembic.ini`.
- `tests/` for unit/integration; `docs/`, `examples/` for demos.
- `main.py` FastAPI entrypoint.

## Build, Test, and Development Commands
- Python 3.11. Install: `pip install -r requirements.txt`.
- Configure env: `cp .env.example .env` and set `SECRET_KEY`.
- Run DB+API via Docker: `docker-compose up -d`.
- Run locally: `uvicorn main:app --reload` or `python main.py`.
- Migrations (set `DATABASE__URL`): `alembic revision --autogenerate -m "msg"` then `alembic upgrade head`.
- Tests: `pytest tests/` (supports `pytest-asyncio`).

## Coding Style & Naming Conventions
- PEP 8, 4‑space indent, type hints required for public functions.
- Names: files/modules `snake_case`; classes `CapWords`; functions/vars `snake_case`.
- DTOs use Pydantic v2 models; validate at boundaries.
- Logging: never `print`; use `core.logging_config.get_logger(__name__)`.
- Exceptions: domain raises `BusinessException`; API may translate to `HTTPException` via handlers in `core.exceptions`.
- Respect DDD boundaries: API → application → domain; infrastructure only behind interfaces.

## Testing Guidelines
- Place tests under `tests/` as `test_*.py`; one assertion per behavior.
- Async tests: mark with `pytest-asyncio`; prefer `httpx.AsyncClient` for API.
- Isolate side effects; clean DB state or use transactional fixtures.

## Commit & Pull Request Guidelines
- Commits: imperative, present tense, concise (e.g., "add user routes").
- PRs: clear description, linked issues, steps to test, migration notes, and screenshots or curl examples for new endpoints.

## Security & Configuration Tips
- Do not commit secrets; env uses nested keys (e.g., `DATABASE__URL`, `REDIS__URL`).
- `SECRET_KEY` is mandatory (app fails fast if missing). Keep default CORS/dev settings out of production.
