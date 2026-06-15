# syntax=docker/dockerfile:1

# --- Build stage: install runtime dependencies into an isolated prefix ---
FROM python:3.11-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build tools are only needed if a dependency lacks a prebuilt wheel.
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# --- Test stage: install dev deps and run the suite. ---
# `docker build --target test` runs this and fails the build if tests fail.
# (Done inside the build because the CI runs Docker-in-Docker, where bind-mounting
# the workspace into a sibling container does not work.)
FROM python:3.11-slim AS test

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_DB_ENABLED=false \
    LOG_TO_FILE=false

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .
RUN python -m pytest -q

# --- Runtime stage: slim image with just what is needed to run ---
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UVICORN_WORKERS=2

# curl is used by the container HEALTHCHECK.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Bring in the installed Python packages from the build stage.
COPY --from=builder /install /usr/local

WORKDIR /app
# Copy only what the app needs at runtime (keeps tests/dev files out of the image).
COPY app/ ./app/
COPY requirements.txt ./

EXPOSE 8484

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8484/api/v1/health || exit 1

# Shell form so UVICORN_WORKERS is expanded at runtime.
CMD uvicorn app.main:app --host 0.0.0.0 --port 8484 --workers ${UVICORN_WORKERS}
