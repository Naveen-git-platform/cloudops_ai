# CloudOps AI — Backend

FastAPI service for the CloudOps AI platform.

## Requirements

- Python 3.10+

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

Services and their integrations (Stripe, PostgreSQL, GitHub, ...) are stored **in memory** for now, so data resets when the server restarts. PostgreSQL storage comes in a later issue.

| Method | Path                              | Description                                         |
| ------ | --------------------------------- | --------------------------------------------------- |
| GET    | `/services`                       | List services                                       |
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

Full interactive docs are at http://127.0.0.1:8000/docs.

## Project structure

```
app/
  main.py          App factory: routers and error handlers
  config.py        Service name and version
  dependencies.py  FastAPI dependency that provides the registry
  models/          Enums and stored resource models (also used as response models)
  schemas/         Request bodies and validation rules
  routes/          HTTP endpoints (health, services, integrations)
  services/        Business logic; registry.py holds the in-memory store
tests/
```

## Run the tests

From the `backend/` directory:

```bash
pytest
```
