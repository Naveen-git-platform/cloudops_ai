# CloudOps AI — Backend

FastAPI service for the CloudOps AI platform. It stores a registry of services and integrations, and ingests OpenTelemetry traces, metrics and logs over OTLP/HTTP. All data is kept in PostgreSQL.

## Requirements

- Python 3.12+
- PostgreSQL 14+ (local install or container)

## Setup

From the `backend/` directory:

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Local PostgreSQL

Create a database and a user for local development. With `psql` connected as a superuser:

```sql
CREATE USER cloudops WITH PASSWORD 'choose-a-local-password' CREATEDB;
CREATE DATABASE cloudops OWNER cloudops;
-- Optional, for running the tests against PostgreSQL:
CREATE DATABASE cloudops_test OWNER cloudops;
```

Or run PostgreSQL in a container:

```bash
docker run --name cloudops-postgres -d -p 5432:5432 \
  -e POSTGRES_USER=cloudops -e POSTGRES_PASSWORD=choose-a-local-password -e POSTGRES_DB=cloudops \
  postgres:16
```

Then create the tables with Alembic (see [Database migrations](#database-migrations)):

```bash
export DATABASE_URL=postgresql+psycopg://cloudops:<password>@localhost:5432/cloudops   # or put it in .env
alembic upgrade head
```

## Database migrations

[Alembic](https://alembic.sqlalchemy.org/) manages the database schema. **PostgreSQL is the migration target**; migrations are written and tested for PostgreSQL only. Run every command from the `backend/` directory. Alembic reads the same `DATABASE_URL` as the API (environment or `.env`); no URL is stored in `alembic.ini`.

| Task | Command |
| ---- | ------- |
| Create or update the schema | `alembic upgrade head` |
| Show the database's revision | `alembic current` |
| Show all revisions | `alembic history --verbose` |
| Preview the SQL without running it | `alembic upgrade head --sql` |
| Step back one revision | `alembic downgrade -1` |

**Fresh database.** Create an empty database (see above), then `alembic upgrade head`.

**Database created before Alembic** (by the API's old automatic table creation). Its schema is already identical to revision `0001`, so record that instead of re-creating tables, then upgrade as usual:

```bash
alembic stamp 0001
alembic upgrade head
```

The API refuses to start if the tables don't match the models, and logs a warning if a PostgreSQL schema has no Alembic version yet.

**Changing the schema.** After editing a model in `app/db/models.py` or `app/telemetry/models.py`:

1. Generate a revision against a database that is at `head`:
   `alembic revision --autogenerate -m "add owner team to services"`
2. Review the file in `alembic/versions/`. Autogenerate is a draft: check types, server defaults for new `NOT NULL` columns on existing rows, constraint names and data migrations. Don't import application code (models, custom types) in a migration; spell types out so the revision keeps working as the models change.
3. Format it: `ruff format alembic/versions`
4. Apply it with `alembic upgrade head`, check `alembic downgrade -1` works, and run the tests against PostgreSQL (`TEST_DATABASE_URL`).

**Deployments run migrations before starting the API**, e.g. as a release step or init container:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run the migration once per deployment (not in every replica at the same time), and make schema changes backwards compatible with the version still running during a rolling deploy.

## Configuration

Settings come from environment variables. For local development, copy `.env.example` to `.env` (it is git-ignored) and fill in your values. Credentials are never hardcoded; the API refuses to start without `DATABASE_URL`.

| Variable               | Required | Default | Description                                                                                                     |
| ---------------------- | -------- | ------- | --------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`         | Yes      | —       | SQLAlchemy URL, e.g. `postgresql+psycopg://cloudops:<password>@localhost:5432/cloudops`                          |
| `DATABASE_ECHO`        | No       | `false` | Log every SQL statement                                                                                         |
| `DATABASE_AUTO_CREATE` | No       | `false` | Create missing tables directly from the models on startup, bypassing Alembic. For SQLite and throwaway databases only; never for a PostgreSQL database you will migrate later (tables created this way need `alembic stamp 0001`). Independently of this, the API always checks the schema at startup and refuses to start if tables are missing columns or indexes |
| `DATABASE_CONNECT_TIMEOUT` | No  | `5`     | Seconds to wait for a database connection before failing the request with a retryable 503                        |
| `OTLP_MAX_BODY_BYTES`  | No       | `10485760` | Largest accepted OTLP request body in bytes (10 MiB), checked before and after gzip decompression |
| `TEST_DATABASE_URL`    | No       | —       | Database for the test suite (see below)                                                                         |

## Run the API

```bash
uvicorn app.main:app --reload
```

The API starts at http://127.0.0.1:8000. Interactive docs are at http://127.0.0.1:8000/docs.

### Health check

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{"status": "healthy", "service": "cloudops-api", "version": "0.1.0"}
```

## Service registry

| Method | Path                              | Description                                         |
| ------ | --------------------------------- | --------------------------------------------------- |
| GET    | `/services`                       | List services (oldest first)                        |
| GET    | `/services/{service_id}`          | Get one service (404 if unknown)                    |
| POST   | `/services`                       | Create a service (201; 409 if the ID exists)        |
| GET    | `/integrations?service_id=...`    | List integrations, optionally for one service       |
| GET    | `/integrations/{integration_id}`  | Get one integration (404 if unknown)                |
| POST   | `/integrations`                   | Create an integration (201; 422 if service unknown) |

IDs are lowercase slugs. If `id` is omitted, one is generated: from the name for services (`Payment Service` → `payment-service`), and from the service and type for integrations (`payment-service-stripe`).

```bash
curl -X POST http://127.0.0.1:8000/services \
  -H "Content-Type: application/json" \
  -d '{"name": "Payment Service", "description": "Handles customer payment processing", "environment": "production", "status": "healthy"}'

curl -X POST http://127.0.0.1:8000/integrations \
  -H "Content-Type: application/json" \
  -d '{"name": "Stripe", "type": "stripe", "service_id": "payment-service"}'
```

Allowed values:

- `environment`: `production`, `staging`, `development`
- service `status`: `healthy`, `degraded`, `down`, `unknown` (default)
- integration `type`: `github`, `aws`, `kubernetes`, `stripe`, `postgresql`, `redis`, `opentelemetry`, `other`
- integration `status`: `pending` (default), `connected`, `degraded`, `disconnected`

Integrations store metadata only; no credentials or live connections yet.

## Telemetry ingestion (OTLP/HTTP)

The API is an OTLP/HTTP receiver. Point any OpenTelemetry SDK or the OpenTelemetry Collector at it:

| Method | Path                 | Description                                                    |
| ------ | -------------------- | -------------------------------------------------------------- |
| POST   | `/v1/traces`         | Export spans                                                   |
| POST   | `/v1/metrics`        | Export metric data points                                      |
| POST   | `/v1/logs`           | Export log records                                             |
| GET    | `/telemetry/records` | Query stored telemetry by service, signal, time range or trace |

Both OTLP/HTTP encodings are accepted, optionally with `Content-Encoding: gzip`:

- `Content-Type: application/x-protobuf` (the SDK and Collector default)
- `Content-Type: application/json` (OTLP/JSON: trace and span IDs as hex, timestamps as nanoseconds since the epoch)

Responses are OTLP `Export*ServiceResponse` messages in the same encoding as the request.

### Sending telemetry from an application

Any OpenTelemetry SDK works with the standard environment variables, for example:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:8000
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_SERVICE_NAME=checkout-api
export OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=production,service.version=3.8.1
```

Or forward from an OpenTelemetry Collector:

```yaml
exporters:
  otlphttp/cloudops:
    endpoint: http://127.0.0.1:8000
    compression: gzip
service:
  pipelines:
    traces: { receivers: [otlp], exporters: [otlphttp/cloudops] }
    metrics: { receivers: [otlp], exporters: [otlphttp/cloudops] }
    logs: { receivers: [otlp], exporters: [otlphttp/cloudops] }
```

### Sending OTLP/JSON with curl

```bash
curl -X POST http://127.0.0.1:8000/v1/logs \
  -H "Content-Type: application/json" \
  -d '{
    "resourceLogs": [{
      "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "checkout-api"}}]},
      "scopeLogs": [{"logRecords": [{
        "timeUnixNano": "1792065601230000000",
        "severityNumber": 17,
        "severityText": "ERROR",
        "body": {"stringValue": "Payment authorization failed"},
        "traceId": "5b8efff798038103d269b633813fc60c",
        "spanId": "eee19b7ec3c1b174"
      }]}]
    }]
  }'
```

Response: `{}`. Complete example payloads for all three signals are in `tests/fixtures/otlp/`:

```bash
curl -X POST http://127.0.0.1:8000/v1/traces \
  -H "Content-Type: application/json" --data-binary @tests/fixtures/otlp/traces.json
```

### What is stored

Each span, metric data point and log record becomes one row in `telemetry_records`:

| Field | Source |
| ----- | ------ |
| `signal` | `traces`, `metrics` or `logs` |
| `service_name` | `service.name` resource attribute (`unknown_service` if missing) |
| `service_namespace`, `service_version`, `environment`, `host_name` | `service.namespace`, `service.version`, `deployment.environment.name` (or legacy `deployment.environment`), `host.name` |
| `timestamp` | Span start, data point time, or log time (falling back to observed time, then receive time). Microsecond precision; exact nanoseconds stay in `raw` |
| `end_timestamp` | Span end |
| `trace_id`, `span_id`, `parent_span_id` | Lowercase hex, when present (spans, and logs with trace context) |
| `span_kind`, `status_code` | Spans: `server`, `client`, ...; `unset`, `ok`, `error` |
| `severity_number`, `severity_text` | Logs; text is derived from the number (e.g. 17 → `ERROR`) when not sent |
| `body` | Logs; structured bodies are stored as JSON text |
| `name` | Span name, metric name, or log event name |
| `metric_type`, `unit`, `value` | Metrics: the `gauge`/`sum` value, or the sum for `histogram`, `exponential_histogram` and `summary` |
| `resource_attributes`, `attributes` | All attributes as JSON |
| `raw` | The original OTLP record (JSON), including events, links, buckets, exemplars, flags, trace state and unknown fields |
| `fingerprint` | SHA-256 of signal, resource, scope and raw record, used for de-duplication |

Indexes cover `(service_name, timestamp)`, `(service_name, signal, timestamp)` and `trace_id`, plus a unique index on `fingerprint`.

Values are made storable before saving:

- Text longer than its column (e.g. a `service.name` over 255 characters, a span name over 1024) is clipped in that column; the full value stays in `raw` and the attributes.
- NUL characters are removed and lone UTF-16 surrogates become U+FFFD (PostgreSQL can't store either).
- Non-finite numbers (`1e400` in JSON) are stored as `"Infinity"`, `"-Infinity"` or `"NaN"`, as protobuf's JSON mapping does.

### Duplicates and retries

Ingestion is idempotent for exact resends: a record whose signal, resource, scope and OTLP content all match a stored record is skipped, within a batch and across requests. OTLP exporters resend whole batches after timeouts and 503s, so retries don't create duplicate rows.

Records that differ in any way are kept, for example the same span reported by two services, or a cumulative metric re-exported with a new timestamp. Two genuinely separate records that are identical in every field (same timestamp to the nanosecond, same attributes) are stored once.

### Validation and errors

| Status | When |
| ------ | ---- |
| 200 | Accepted. If some records were invalid (bad or all-zero trace/span ID, missing or out-of-range timestamp, malformed attribute, metric without a name or supported data type), the rest are stored and the response carries `partialSuccess` with the rejected count and up to five reasons |
| 400 | Body isn't valid JSON, protobuf or gzip (including truncated gzip or trailing data), the request structure is wrong, or JSON is nested more than 128 levels deep |
| 413 | Body larger than `OTLP_MAX_BODY_BYTES` (before or after decompression) |
| 415 | Missing or unsupported `Content-Type`, or unsupported `Content-Encoding` |
| 503 | The database is unreachable or saturated. Includes `Retry-After: 5`; OTLP exporters retry these, so no data is lost while the database recovers |
| 500 | Unexpected server error (details are logged, not returned) |

As OTLP/HTTP requires, error bodies are a `google.rpc.Status` message in the request's encoding: protobuf for `application/x-protobuf` requests, JSON (`{"code": 3, "message": "..."}`) for `application/json` requests or when the Content-Type isn't supported. Exporters act on the status code; the message is for troubleshooting.

Following the OTLP/JSON specification, keys must be lowerCamelCase (`resourceSpans`, not `resource_spans`) and enums must be integers (`"kind": 2`, not `"SPAN_KIND_SERVER"`). Unknown keys are ignored, so a snake_case payload is accepted but stores nothing; a record with an enum name is rejected.

gzip bodies may contain several concatenated members; all are read.

The rest of the API (`/services`, `/integrations`, `/telemetry/records`) also returns `503` with `Retry-After` when the database is unavailable, with a JSON `{"detail": "..."}` body. `/health` doesn't use the database and keeps answering.

### Querying stored telemetry

`GET /telemetry/records` returns records newest first. All filters are optional:

| Parameter  | Description |
| ---------- | ----------- |
| `service`  | Exact `service.name` |
| `signal`   | `traces`, `metrics` or `logs` |
| `start`    | Inclusive lower bound on `timestamp` (ISO 8601; UTC if no offset) |
| `end`      | Exclusive upper bound on `timestamp` |
| `trace_id` | 32 hex characters; returns spans and logs across services |
| `limit`    | 1–1000, default 100 |

```bash
curl "http://127.0.0.1:8000/telemetry/records?service=checkout-api&signal=logs&start=2026-10-15T12:00:00Z&end=2026-10-15T13:00:00Z"
```

Telemetry is stored separately from the service registry: a `service.name` doesn't have to match a registered service.

## Project structure

```
app/
  main.py          App factory: database lifecycle, routers, error handlers
  config.py        Settings loaded from environment variables
  dependencies.py  Per-request database session and registry
  db/              SQLAlchemy engine/session (session.py) and tables (models.py)
  models/          Enums and API response models
  schemas/         Request bodies and validation rules
  routes/          HTTP endpoints (health, services, integrations)
  services/        Business logic; registry.py reads and writes the database
  errors.py        Error responses: OTLP google.rpc.Status bodies, retryable 503 when the database is down
  telemetry/       OTLP/HTTP ingestion: decoding (otlp.py), wire schemas (schemas.py),
                   normalisation (normalize.py), table (models.py), queries (repository.py), routes (router.py)
alembic/           Migration environment (env.py) and revisions (versions/)
alembic.ini        Alembic configuration (no credentials; the URL comes from DATABASE_URL)
tests/
  fixtures/otlp/   Representative OTLP/JSON payloads for traces, metrics and logs
```

## Run the tests

From the `backend/` directory:

```bash
pytest
```

By default the tests use a temporary SQLite file, so they run without a database server. To run them against PostgreSQL, set `TEST_DATABASE_URL` to a **dedicated test database**. Every test drops and recreates the tables, so never point it at real data.

```bash
# macOS / Linux
TEST_DATABASE_URL=postgresql+psycopg://cloudops:<password>@localhost:5432/cloudops_test pytest
# Windows (PowerShell)
$env:TEST_DATABASE_URL = "postgresql+psycopg://cloudops:<password>@localhost:5432/cloudops_test"; pytest
```

The migration tests (`tests/test_migrations.py`) run only against PostgreSQL. They create and drop their own temporary databases on the `TEST_DATABASE_URL` server, so that user needs the `CREATEDB` privilege (the CI service user has it). With SQLite they are skipped.


## Run the ShopStack demo prototype

The repository includes a fictional **ShopStack Demo** workload so you can exercise the dashboard without connecting a real cloud account. It seeds four registered services and five integration metadata records into a local SQLite database. The dashboard's incident, deployment, activity, and chart panels remain explicitly marked demo data; seeded integrations are metadata only and do not connect to Stripe, AWS, Redis, Kubernetes, or PostgreSQL.

From the repository root, open a terminal:

**1. Start the backend and seed a local database (Windows PowerShell):**

```powershell
cd backend
python -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./cloudops_demo.db"
python -m scripts.seed_demo
uvicorn app.main:app --reload
```

On macOS/Linux, activate the virtual environment with `source .venv/bin/activate` instead. Keep this terminal open. The seed command is safe to run more than once: it inserts missing sample records and does not delete or overwrite existing records.

**2. Start the frontend in a second terminal:**

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Ensure `.env.local` contains `CLOUDOPS_API_URL=http://127.0.0.1:8000`, then open the local URL printed by Next.js (normally http://localhost:3000). The API docs are at http://127.0.0.1:8000/docs.

**3. Try the sample workload:**

- The Services panel should show ShopStack Checkout API, ShopStack Search, ShopStack Order Worker, and ShopStack Edge Gateway.
- Checkout and search are intentionally marked degraded to demonstrate a mixed-health project.
- The existing demo incident list includes checkout 5xx errors and search latency; open an incident to inspect the details and use Resolve to test the local UI interaction.
- Try the dashboard search to filter services/incidents.
- Inspect `GET /services` and `GET /integrations` in the API docs to see persisted sample records.

This is a local prototype, not a live cloud monitoring deployment. The sample incidents and telemetry are illustrative and are not generated from actual infrastructure signals. For PostgreSQL, run `alembic upgrade head` first and use a dedicated development database; never run demo seeding against production.
