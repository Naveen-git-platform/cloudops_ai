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

## Run the tests

From the `backend/` directory:

```bash
pytest
```
