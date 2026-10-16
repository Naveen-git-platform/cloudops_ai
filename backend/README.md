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
CREATE USER cloudops WITH PASSWORD 'choose-a-local-password';
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

Tables are created automatically when the API starts (see `DATABASE_AUTO_CREATE`).

## Configuration

Settings come from environment variables. For local development, copy `.env.example` to `.env` (it is git-ignored) and fill in your values. Credentials are never hardcoded; the API refuses to start without `DATABASE_URL`.

| Variable               | Required | Default | Description                                                                                                     |
| ---------------------- | -------- | ------- | --------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`         | Yes      | —       | SQLAlchemy URL, e.g. `postgresql+psycopg://cloudops:<password>@localhost:5432/cloudops`                          |
| `DATABASE_ECHO`        | No       | `false` | Log every SQL statement                                                                                         |
| `DATABASE_AUTO_CREATE` | No       | `true`  | Create missing tables on startup. Existing tables are never altered: if one is missing columns or indexes (e.g. an older `telemetry_records` without `fingerprint`), the API refuses to start and names the problem; drop and recreate that table until migrations exist |
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
