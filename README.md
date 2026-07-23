# CausaOps

**Find the cause. Verify the fix.**

CausaOps is a portfolio-grade incident observability and response platform. The MVP will ingest telemetry from a controlled demo service, detect a timeout regression, correlate it with a deployment, generate an evidence-bound diagnosis, require human approval for a simulated rollback, and verify recovery.

## Current status

Phase 4 adds evidence-bound Groq diagnoses to the deterministic incident workflow:

- Next.js/TypeScript web application with a responsive system-status page.
- FastAPI service with liveness and PostgreSQL readiness checks.
- Validated ingestion APIs for services, events, metrics, and deployments.
- SQLAlchemy persistence and versioned Alembic migrations.
- Demo Payments service with `stable` and `timeout` modes.
- Configurable deterministic rules for error rate, p95 latency, and health failures.
- Incident grouping, deployment correlation, evidence, and verified recovery.
- Dashboard, filterable incident history, and incident detail pages.
- Strict JSON Schema diagnoses with backend evidence-reference validation.
- Groq GPT-OSS 20B development analysis and GPT-OSS 120B primary analysis.
- Persisted provider, model, latency, token usage, prompt snapshot, and rejection reason.
- A lightweight detector process; no Redis or task queue is required.
- Docker Compose development stack and container health checks.
- Unit tests and CI checks.

AI output is kept separate from deterministic facts and cannot execute remediation. Human approval
and simulated rollback intentionally belong to Phase 5.

## Architecture

```text
Browser -> Next.js web -> FastAPI API -> PostgreSQL
                         /health/live
                         /health/ready -> SELECT 1
Demo Payments ----------> ingestion API
Detector ---------------> PostgreSQL -> incidents/evidence
Incident detail --------> Groq -------> validated diagnoses
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

To enable diagnosis, create a Groq project key and keep it only in the untracked `.env` file:

```bash
GROQ_API_KEY=your_local_groq_key
GROQ_TEST_MODEL=openai/gpt-oss-20b
GROQ_PRIMARY_MODEL=openai/gpt-oss-120b
```

The key must never be placed in `.env.example` or committed. The incident detail page offers a
20B development run and a 120B primary run. Unit tests never call Groq or consume API quota.

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8100/health
```

## Run the controlled Phase 3 scenario

Process a healthy payment:

```bash
curl -X POST http://localhost:8100/payments \
  -H 'content-type: application/json' \
  -d '{"amount":25,"currency":"USD"}'
```

Activate the timeout deployment and generate at least five observable failures:

```bash
curl -X POST http://localhost:8100/admin/mode \
  -H 'content-type: application/json' \
  -d '{"mode":"timeout"}'
for i in 1 2 3 4 5; do
  curl -X POST http://localhost:8100/payments \
    -H 'content-type: application/json' \
    -d '{"amount":25,"currency":"USD"}'
done
curl -X POST http://localhost:8000/api/v1/detection/run
curl http://localhost:8000/api/v1/incidents
```

Open <http://localhost:3000/incidents> to inspect the grouped incident, deterministic metrics, related events, and correlated deployment. The detector also runs automatically every 30 seconds.

Restore stable behavior with `POST /admin/mode` and `{"mode":"stable"}`, then generate at least five successful requests after the original failures leave the five-minute window. The next detection run marks the incident resolved only after recovery telemetry exists. Each mode change is persisted as a deployment fact. Telemetry delivery is best-effort: CausaOps downtime does not break the Demo Service response.

Optional deterministic sample data can be added after migrations:

```bash
docker compose exec api python -m app.seed
```

The seed is idempotent and never contains an AI-generated diagnosis.

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
cd apps/demo-service && pytest && ruff check .
cd apps/web && npm run lint && npm run typecheck && npm run build
docker compose config
```

Docker verification requires Docker to be installed. CI runs API tests/lint and web lint/typecheck/build on every push and pull request.

## Phase 4 completion criteria

- The Compose stack starts PostgreSQL, API, Demo Service, detector, and web services.
- PostgreSQL and the API report healthy; readiness executes a real database query.
- All three migrations apply successfully on an empty database.
- Registering the same service twice returns the same identifier.
- Valid events, metrics, and deployments persist; unknown services are rejected.
- Stable traffic does not create an incident.
- Five timeout failures breach deterministic thresholds and create exactly one incident.
- Re-running detection updates the same incident and does not duplicate evidence.
- A recent deployment raises severity and appears as referenced evidence.
- A later healthy window resolves the existing incident.
- The dashboard, filterable history, and detail page expose only stored facts and backend calculations.
- Groq receives only the selected incident facts and evidence identifiers.
- GPT-OSS output must match a strict schema and cite only supplied incident evidence.
- Unknown evidence references are rejected and retained as an auditable rejected attempt.
- Provider errors do not alter detection or incident state.
- Each accepted diagnosis records model, latency, token usage, confidence, and human-review status.
- API and Demo Service tests/lint pass; web lint, type checking, and production build pass.
- No secrets are committed and setup is reproducible from this README.

## Roadmap

1. Foundation and health checks (complete).
2. Demo Service and telemetry persistence (complete).
3. Deterministic detection and incident UI (complete).
4. Evidence collection and validated Groq diagnoses (current).
5. Human approval, simulated recovery, verification, and reports.
6. Evaluation, E2E testing, observability, security, and documentation.
7. Visual polish and public portfolio demo.
