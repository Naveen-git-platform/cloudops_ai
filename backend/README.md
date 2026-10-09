# CloudOps AI — Backend

FastAPI service for the CloudOps AI platform. Services and integrations are stored in PostgreSQL.

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
| `DATABASE_AUTO_CREATE` | No       | `true`  | Create missing tables on startup. Existing tables are not altered; schema migrations will come in a later issue |
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
tests/
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
