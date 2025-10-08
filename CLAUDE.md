# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Install development tools (linting, formatting, testing)
pip install -r requirements-dev.txt

# Configure environment (required)
cp env.example .env
# Edit .env and set SECRET_KEY (mandatory)

# Setup pre-commit hooks (recommended)
pre-commit install

# Run REST API (development)
uvicorn main:app --reload
# or
python main.py

# Run gRPC service (requires GRPC__ENABLED=true in .env)
python grpc_main.py

# Start with Docker Compose (includes PostgreSQL)
docker-compose up -d

# Start gRPC service with Docker
docker-compose up -d grpc
```

### Database Migrations
```bash
# Create new migration (after modifying ORM models)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# View migration history
alembic history
```

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_payments_skeleton.py

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run tests in parallel
pytest tests/ -n auto

# Run only unit tests
pytest tests/ -m unit
```

### Code Quality
```bash
# Format code
black .
isort .

# Check linting
flake8 .

# Type checking
mypy .

# Security check
bandit -r . -c pyproject.toml

# Run all pre-commit checks manually
pre-commit run --all-files
```

### gRPC Protocol Generation
```bash
# Generate Python stubs from .proto files
bash scripts/gen_protos.sh
```

## Architecture Overview

This is a **DDD (Domain-Driven Design) + Hexagonal Architecture** FastAPI project with strict layered boundaries.

### Dependency Direction (Critical)
**API → Application → Domain ← Infrastructure**

- Domain layer NEVER imports from infrastructure, application, or API
- Infrastructure implements interfaces defined in domain
- Application orchestrates domain services and infrastructure through interfaces (ports/adapters)
- API layer only handles HTTP I/O and dependency injection

### Layer Responsibilities

**`domain/`** - Pure business logic
- Entities with business rules (e.g., `domain/user/entity.py`)
- Repository interfaces (contracts only, no implementation)
- Domain services for complex cross-entity logic
- Domain events
- **No framework imports, no DB code, no HTTP**

**`application/`** - Use case orchestration
- Services that coordinate domain logic and infrastructure (`application/services/`)
- DTOs for data transfer (`application/dtos/`)
- Ports (interfaces) for external capabilities (`application/ports/`)
- Transaction boundaries via UnitOfWork
- JWT generation/verification
- **No direct DB/ORM imports; uses repositories through interfaces**

**`infrastructure/`** - Technical implementation
- ORM models (`infrastructure/models/`)
- Repository implementations (`infrastructure/repositories/`)
- UnitOfWork implementation (`infrastructure/unit_of_work.py`)
- External service clients: Redis, storage (S3/OSS/local), payment gateways, Kafka, RocketMQ
- Adapters that implement application ports
- Database session management

**`api/`** - Presentation layer
- FastAPI routes (`api/routes/`)
- Request/response models (if not using application DTOs)
- Middleware (`api/middleware/`)
- Dependencies for authentication (`api/dependencies.py`)
- **Only does I/O binding, no business logic**

**`core/`** - Shared infrastructure
- Configuration (`core/config.py`, `core/settings.py`)
- Logging setup (`core/logging_config.py`)
- Exception handlers (`core/exceptions.py`)
- Response models (`core/response.py`)

**`shared/`** - Cross-cutting utilities
- Business codes (`shared/codes.py`)
- Common constants

### Key Architectural Patterns

1. **Repository Pattern**: Domain defines interfaces, infrastructure implements them
2. **Unit of Work**: Transaction management abstracted via `domain/common/unit_of_work.py`
3. **Ports & Adapters**: Application defines ports (e.g., `application/ports/storage.py`), infrastructure provides adapters
4. **Domain Events**: Entities emit events for important state changes (e.g., user activated/deactivated)

## Critical Design Decisions

### When to use Domain Service vs Application Service

**Domain Service** (`domain/*/service.py`) - Use when:
- Pure business rules involving multiple entities/aggregates
- Business validation requiring repository queries (e.g., username uniqueness)
- Complex domain logic/strategies (pricing, discount rules)
- Maintaining business invariants (e.g., "superuser cannot be deactivated")
- **No external system dependencies (HTTP, SDK, cache, JWT)**

**Application Service** (`application/services/*_service.py`) - Use when:
- Orchestrating domain services with external systems
- Technical concerns: HTTP calls, SDK integration, caching, distributed locks
- DTO mapping between API and domain
- JWT token operations
- Transaction boundary management (UoW)
- Coordinating multiple domain aggregates with external state

**Examples in this codebase:**
- `domain/user/service.py` - Pure business: password validation, uniqueness checks, first superuser logic
- `application/services/user_service.py` - Orchestration: JWT generation, Redis locks, DTO conversion
- `application/services/payment_service.py` - Technical: payment gateway SDK calls, idempotency keys
- `application/services/file_asset_service.py` - Technical: storage SDK integration, presigned URLs

### Distributed Lock Pattern for First Superuser

When registering the first user (who becomes superuser), concurrent requests could create multiple superusers. Solution:
- Check user count (read-only)
- If potentially zero, acquire Redis lock `first_superuser_init`
- Re-check count inside lock before proceeding
- Fallback to best-effort without Redis (small race condition acceptable)

Configuration: `REDIS__URL`, `FIRST_SUPERUSER_LOCK_TIMEOUT`, `FIRST_SUPERUSER_LOCK_BLOCKING_TIMEOUT`

## Configuration

All settings use **nested environment variables** with `__` separator (Pydantic Settings v2):
```bash
DATABASE__URL=postgresql+asyncpg://user:password@localhost/userdb
REDIS__URL=redis://localhost:6379/0
STORAGE__TYPE=s3
STORAGE__BUCKET=my-bucket
GRPC__ENABLED=true
GRPC__PORT=50051
KAFKA__BOOTSTRAP_SERVERS=localhost:9092
```

**Mandatory**: `SECRET_KEY` must be set in all environments (app fails fast if missing)

See `env.example` for full reference.

## Logging

**Always use structured logging**:
```python
from core.logging_config import get_logger

logger = get_logger(__name__)
logger.info("user_registered", user_id=user.id, username=user.username)
```

- Never use `print()` or `logging.getLogger()` directly
- Development: console-friendly output
- Production: JSON format
- Request ID automatically propagated via contextvars

### Request Body Logging
- Controlled by `LOG_REQUEST_BODY_ENABLE_BY_DEFAULT` (default: true in DEBUG)
- Override per-request with header: `X-Log-Body: true|false`
- Sensitive fields auto-redacted: `password`, `token`, `access_token`, `secret`, `api_key`, etc.
- Limited to first 2048 bytes (configurable via `LOG_REQUEST_BODY_MAX_BYTES`)
- multipart/form-data not logged by default

## Authentication & Authorization

- JWT-based with `access_token` (short-lived) and `refresh_token`
- Dependencies in `api/dependencies.py`:
  - `get_current_user` - any authenticated user
  - `get_current_active_user` - active users only
  - `get_current_superuser` - superuser only
- gRPC: pass token in metadata as `authorization: Bearer <token>` or `access_token: <token>`

## Storage (File Upload)

Supports local filesystem, AWS S3, and Alibaba OSS via unified interface:
- Configuration: `STORAGE__TYPE`, `STORAGE__BUCKET`, `STORAGE__REGION`, etc.
- Two upload modes:
  1. **Direct upload**: Client uploads to presigned URL, API records metadata
  2. **Proxied upload**: API receives file and uploads to storage
- Presigned URLs generated on-demand (never stored in database)
- File state machine: `pending` → `active` → `deleted`

## Payments

Unified payment gateway interface supporting Stripe, Alipay, WeChat Pay:
- Provider selection via `PAYMENT__DEFAULT_PROVIDER`
- Idempotency keys automatically generated (order_id-based)
- Webhook signature verification required
- Event deduplication via Redis (hash of webhook body + event ID)
- See `docs/payments.md` for integration details

## Real-time WebSocket

Abstracted broker interface with multiple backends:
- In-memory (default, single-instance only)
- Redis Pub/Sub (recommended for multi-instance)
- Kafka (high throughput)
- RocketMQ (alternative MQ)

Configuration: `REALTIME_BROKER` (auto/redis/kafka/rocketmq)

Connection management at `api/routes/ws.py`; business logic in `application/services/realtime_service.py`

## gRPC Service

Parallel to REST API, reusing same application/domain layers:
- Protos: `grpc_app/protos/forge/v1/*.proto`
- Generated stubs: `grpc_app/generated/forge/v1/`
- Server implementation: `grpc_app/server.py`, `grpc_app/services/`
- Entry: `grpc_main.py`

**Anonymous RPCs**: `Register`, `Login`, `Refresh`, `Health`
**Authenticated RPCs**: all others (require token in metadata)

## Testing Strategy

- Unit tests with pytest + pytest-asyncio
- API tests use `httpx.AsyncClient`
- Mock external dependencies (storage, payment gateways) at port/adapter boundaries
- Existing coverage: payment service idempotency, webhook parsing, gRPC user service
- **Gaps**: Full user registration/login flow, file upload scenarios (good areas to add tests)

## Common Development Patterns

### Adding a New Entity/Aggregate

1. Define entity in `domain/<aggregate>/entity.py`
2. Define repository interface in `domain/<aggregate>/repository.py`
3. Create ORM model in `infrastructure/models/<aggregate>.py`
4. Implement repository in `infrastructure/repositories/<aggregate>_repository.py`
5. Generate migration: `alembic revision --autogenerate -m "add <aggregate>"`
6. Apply: `alembic upgrade head`
7. Create application service in `application/services/<aggregate>_service.py`
8. Add API routes in `api/routes/<aggregate>.py`
9. Register routes in `main.py`

### Adding External Service Integration

1. Define port interface in `application/ports/<service>.py`
2. Implement client in `infrastructure/external/<service>/<provider>.py`
3. Create adapter in `infrastructure/adapters/<service>_port.py` (if needed)
4. Initialize in `main.py` lifespan
5. Inject via dependency in API routes

### Extending Payment Gateway

1. Implement `application.ports.payment_gateway.PaymentGateway` protocol
2. Add client in `infrastructure/external/payments/<provider>_client.py`
3. Register in `infrastructure/external/payments/__init__.py:get_payment_gateway()`
4. Add provider config to `core/settings.py:PaymentSettings`
5. Set credentials in `.env`

## Important Files Reference

- Entry: `main.py:44` (lifespan), `main.py:148` (app creation)
- Config: `core/config.py:98`, `core/settings.py` (payments)
- Logging: `core/logging_config.py:22`
- Middleware: `api/middleware/request_id.py`, `api/middleware/logging.py`
- Exceptions: `core/exceptions.py:55` (handlers)
- Response: `core/response.py:34`
- Auth: `api/dependencies.py:20` (get_current_user)
- UoW: `infrastructure/unit_of_work.py:23`
- Database: `infrastructure/database.py:15` (session), `infrastructure/database.py:47` (create_tables)

## Known Issues & Gotchas

1. **Initial migration only includes `file_assets`**: Run `alembic revision --autogenerate` to capture `users` table for production
2. **Storage health check**: Small undefined variable issue in `infrastructure/external/storage/__init__.py` (non-blocking in DEBUG)
3. **Alipay SDK**: Not in requirements by default (add `alipay-sdk-python` if needed)
4. **SECRET_KEY**: Must be stable across restarts (avoid random generation in production)
5. **Async everywhere**: All DB operations, external calls, and file I/O are async; don't mix sync code without `asyncio.to_thread`

## Development Workflow

1. Create feature branch from `master`
2. Make changes following DDD boundaries
3. Add/update tests
4. Generate migration if DB schema changed
5. Run code quality checks: `pre-commit run --all-files`
6. Test locally with Docker Compose
7. Commit (pre-commit hooks run automatically)
   - Use Conventional Commits format: `feat:`, `fix:`, `docs:`, etc.
   - Example: `feat: add payment refund endpoint`
8. Create PR with description, test steps, and migration notes

### Pre-commit Hooks

Automatically run on every commit:
- **black**: Code formatting (100 char line length)
- **isort**: Import sorting
- **flake8**: Linting with bugbear, comprehensions, simplify plugins
- **mypy**: Static type checking
- **bandit**: Security vulnerability scanning
- **trailing-whitespace**: Remove trailing spaces
- **end-of-file-fixer**: Ensure newline at EOF
- **check-yaml/json/toml**: Syntax validation
- **detect-private-key**: Prevent committing secrets

Configuration files:
- `.pre-commit-config.yaml`: Hook definitions
- `pyproject.toml`: Tool-specific settings (black, isort, mypy, pytest, bandit)

Skip hooks only when necessary:
```bash
git commit --no-verify  # Skip all hooks (emergency only)
SKIP=mypy git commit    # Skip specific hook
```

## Docker Multi-stage Build

Optimized production-ready Dockerfile with three stages:

1. **Builder stage**: Installs build dependencies and compiles packages to virtual environment
2. **Runtime stage**: Minimal production image (~200MB smaller)
   - Copies only venv from builder
   - Runs as non-root user `appuser`
   - Includes health check
   - No dev tools or test files
3. **Development stage**: Extends runtime with dev tools
   - Includes `requirements-dev.txt`
   - Enables hot reload
   - Git for pre-commit hooks

Build commands:
```bash
# Production image (default, minimal size)
docker build -t fastapi-forge:latest .

# Development image (with dev tools)
docker build --target development -t fastapi-forge:dev .

# Check image size
docker images fastapi-forge
```

`.dockerignore` excludes:
- Tests, docs, examples
- Dev configs (.pre-commit-config.yaml, pyproject.toml)
- Git history, IDE files
- Local storage, logs, cache

## Documentation

See `docs/` directory for deep dives:
- `development.md` - **development workflow, pre-commit, Docker, testing**
- `architecture.md` - comprehensive architecture guide
- `application.md`, `domain.md`, `infrastructure.md` - layer-specific details
- `payments.md`, `messaging.md`, `realtime.md` - subsystem guides
- `alembic.md`, `tests.md` - operational guides
