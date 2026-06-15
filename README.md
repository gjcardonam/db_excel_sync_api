# db-excel-sync-api

Internal API to sync **well configuration** and **wellheader** data from Excel
files into per-company Postgres databases. Built with FastAPI.

> Internal service for trusted, internal users. It has no end-user
> authentication by design.

## Features

- Upload an `.xlsx` and update a company's well-configuration tables
  (`dbesp` / `dbgl`, plus `installrecordgl` and `welltest`) atomically.
- Upload an `.xlsx` to update the `wellheader` table.
- Minimal HTML UI for manual uploads.
- Structured JSON logging to stdout, plus optional asynchronous audit logging
  to a Postgres table.

## Requirements

- Python 3.11+
- PostgreSQL (per-company operational databases, and optionally a log database)

## Setup

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt               # runtime + test deps
cp .env.example .env                              # then edit .env
```

## Running

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8484 --reload
```

- Interactive docs: `http://localhost:8484/docs`
- Liveness probe: `GET /api/v1/health`

## Configuration

All configuration is via environment variables (loaded from `.env`). See
[`.env.example`](.env.example) for the full list. Key groups:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Root log level |
| `LOG_TO_FILE` | `false` | Also write rotating log files |
| `CORS_ALLOW_ORIGINS` | `*` | Comma-separated allowed origins |
| `MAX_UPLOAD_BYTES` | `52428800` | Max request body size (50 MB) |
| `LOG_DB_*` | — | Async audit logging to Postgres (enabled when `LOG_DB_HOST` is set) |

**Per-company databases.** For each company, define `<COMPANY>_HOST`,
`<COMPANY>_DATABASE`, `<COMPANY>_USER`, `<COMPANY>_PASSWORD`, `<COMPANY>_PORT`,
`<COMPANY>_SCHEMA`. The company name from the request is upper-cased and spaces
become underscores to form the prefix (e.g. `ACME` → `ACME_HOST`).

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness probe |
| `GET` | `/api/v1/ping-db?company=ACME` | Check a company's DB connection |
| `POST` | `/api/v1/well-configuration/` | Upload well configuration (`company`, `lift_method`, `file`) |
| `POST` | `/api/v1/wellheader/upload` | Upload wellheader (`company`, `sheet_name`, `file`) |
| `GET` | `/`, `/well-configuration`, `/wellheader` | HTML upload UI |

## Testing & linting

```bash
python -m pytest          # run the test suite
python -m ruff check .     # lint
python -m ruff format .    # format
pre-commit install        # enable git hooks (optional)
```

## Docker

```bash
docker build -t excel-api:latest .
docker run -d --name excel-api -p 8484:8484 --env-file .env excel-api:latest
```

The image runs as a non-root user, serves with multiple uvicorn workers
(`UVICORN_WORKERS`, default 2), and ships a `HEALTHCHECK` against
`/api/v1/health`.

## CI/CD

`Jenkinsfile` defines a pipeline (SCM polling every ~2 min) that runs the test
suite, builds the image, and deploys it as a container with a health-gated swap.
