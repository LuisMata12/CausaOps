# CausaOps

**Find the cause. Verify the fix.**

CausaOps is a portfolio-grade incident observability and response platform. The MVP will ingest telemetry from a controlled demo service, detect a timeout regression, correlate it with a deployment, generate an evidence-bound diagnosis, require human approval for a simulated rollback, and verify recovery.

## Current status

Phase 1 establishes the local development foundation:

- Next.js/TypeScript web application with a responsive system-status page.
- FastAPI service with liveness and PostgreSQL readiness checks.
- SQLAlchemy model foundation and Alembic migrations.
- Docker Compose development stack and container health checks.
- Unit tests and CI checks.

Telemetry ingestion, incident detection, LLM providers, remediation, and the Demo Service intentionally belong to later phases.

## Architecture

```text
Browser -> Next.js web -> FastAPI API -> PostgreSQL
                         /health/live
                         /health/ready -> SELECT 1
```

The repository is a small monorepo without an additional build orchestrator. Each app owns its dependencies and tests. The API remains a modular monolith: future domain modules will live under `app/` and share one database transaction boundary. This keeps the MVP easy to run and leaves clean seams for telemetry, incidents, evidence, providers, and actions.

See [docs/architecture/mvp.md](docs/architecture/mvp.md) and [docs/decisions/0001-modular-monolith.md](docs/decisions/0001-modular-monolith.md).

## Run locally with Docker

Prerequisites: Docker with Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open <http://localhost:3000>. API docs are at <http://localhost:8000/docs>.

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

The API container applies migrations before starting. Stop the stack with `docker compose down`; add `-v` only when you deliberately want to delete local database data.

## Run without Docker

Start a PostgreSQL database and set `DATABASE_URL`, then:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd apps/web
npm install
API_INTERNAL_URL=http://localhost:8000 npm run dev
```

## Verification

```bash
cd apps/api && pytest && ruff check .
cd apps/web && npm run lint && npm run typecheck && npm run build
docker compose config
```

Docker verification requires Docker to be installed. CI runs API tests/lint and web lint/typecheck/build on every push and pull request.

## Phase 1 completion criteria

- The Compose stack starts PostgreSQL, API, and web services.
- PostgreSQL and the API report healthy; readiness executes a real database query.
- The initial migration applies successfully.
- The dashboard renders and distinguishes API liveness from database readiness.
- API tests and lint pass; web lint, type checking, and production build pass.
- No secrets are committed and setup is reproducible from this README.

## Roadmap

1. Foundation and health checks (current).
2. Demo Service and telemetry persistence.
3. Deterministic detection and incident UI.
4. Evidence collection and validated Ollama/Groq diagnoses.
5. Human approval, simulated recovery, verification, and reports.
6. Evaluation, E2E testing, observability, security, and documentation.
7. Visual polish and public portfolio demo.

