# CloudOps AI

**Evidence-first cloud incident intelligence for developers and small engineering teams.**

CloudOps AI is an open-source platform in active development that brings service health, telemetry, deployments, and incident investigation into one operational workspace. The goal is to help engineers answer three questions quickly: **What is broken? What changed? What evidence supports the likely cause?**

> Project status: early development. Some dashboard panels currently use clearly identified demo data; do not treat the UI as a production monitoring source until the relevant integrations are connected.

## Current capabilities

- **Service registry API** — register services and track their environment and reported status.
- **Integration registry API** — associate integrations with services.
- **OpenTelemetry ingestion** — accept and normalize supported OTLP telemetry.
- **PostgreSQL persistence** — persist service and telemetry records with schema migrations managed by Alembic.
- **Health checks** — separate process liveness from database readiness.
- **Responsive dashboard** — Next.js and React UI with service health, incident/deployment panels, accessible navigation, and loading/error states.
- **Automated validation** — GitHub Actions runs backend tests and frontend lint/build checks on pull requests.

## Health endpoints

| Endpoint | Purpose | Success |
|---|---|---|
| `GET /health` | Liveness: the API process can respond | `200` |
| `GET /ready` | Readiness: the API can execute a database query | `200` |

If the database is unavailable, `/ready` returns `503` with a safe `database: unavailable` status. It does not return database URLs or driver error details. Use `/health` for process liveness and `/ready` for readiness probes in deployment platforms.

Example:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
```

## Project history

See the [day-by-day development log](docs/DEVELOPMENT_LOG.md) for implemented milestones, major changes, CI evidence, and remaining limitations.

## Architecture

- `frontend/` — Next.js, React, TypeScript, Tailwind CSS, Motion, and Lucide icons.
- `backend/` — FastAPI, SQLAlchemy, Pydantic Settings, Alembic, and OpenTelemetry protocol support.
- `.github/workflows/` — separate backend test and frontend lint/build workflows.

The frontend's server-side API client reads `CLOUDOPS_API_URL`. Keep server-only environment variables on the server; never commit credentials or expose secret keys to browser code.

## Local development

### Backend

1. Create a Python 3.12 virtual environment.
2. Install dependencies with `python -m pip install -r backend/requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env` and set a local `DATABASE_URL`.
4. From `backend/`, run database migrations with `alembic upgrade head` for PostgreSQL.
5. Start the API with `uvicorn app.main:app --reload` from `backend/`.

See [backend setup and API documentation](backend/README.md) for database, migration, telemetry, and test details.

### Frontend

1. Install Node.js 22 or a compatible supported release.
2. From `frontend/`, run `npm ci`.
3. Set `CLOUDOPS_API_URL` in the local environment to the backend URL, for example `http://127.0.0.1:8000`.
4. Run `npm run dev` and open the local Next.js URL printed in the terminal.

### Tests

- Backend: from `backend/`, run `python -m pytest`. Set `TEST_DATABASE_URL` to use PostgreSQL; otherwise the suite uses a temporary SQLite database where supported.
- Frontend: from `frontend/`, run `npm run lint` and `npm run build`.

GitHub Actions runs these checks for pull requests targeting `main`.

## Roadmap

- Complete secure authentication and server-side API authorization.
- Connect real deployment and incident data sources.
- Improve alerting, incident timelines, and evidence-linked root-cause investigation.
- Add end-to-end tests for critical dashboard flows.
- Keep the UI responsive, accessible, and explicit about live versus demo data.

## Contributing

Open an issue before large changes. Prefer focused pull requests with tests, clear acceptance criteria, and a short code-review checklist. Never commit secrets, production data, or real credentials.

## License

[MIT](LICENSE).
