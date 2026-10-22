# Interview Starter Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task.

**Goal:** A runnable backend interview starter with automatic sample ingestion.

**Architecture:** FastAPI routes call an ingestion service with explicit database,
vector-store, and embedding adapters. Startup owns clients and seeds sample data.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, psycopg, Weaviate v4, OpenAI,
pytest, Ruff, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-18-interview-starter-design.md`

## Global Constraints

- No credentials or external services needed for unit tests or demo embeddings.
- Real OpenAI mode requires an explicit key and never falls back silently.
- Repeated seed ingestion must not add duplicate documents or vectors.
- Keep the implementation small enough to explain and modify in an interview.

## Review Focus

- Repeat ingestion after a partially failed vector write repairs the index.
- Blank/oversized documents and invalid pagination fail validation.
- Switching embedding providers/models never shares a vector collection.
- Resource cleanup works on normal shutdown and failed startup.
- Integration tests exercise real PostgreSQL and Weaviate, not adapter mocks.

## Task 1: Ingestion and embeddings

Files: `app/config.py`, `app/schemas.py`, `app/service.py`, `app/embeddings.py`,
`app/database.py`, `app/vector_store.py`, `tests/test_service.py`,
`tests/test_embeddings.py`.

- [x] Write tests for idempotence, index failure recovery, and OpenAI HTTP behavior.
- [x] Run pytest and confirm the missing implementation fails.
- [x] Implement `DocumentService.ingest(documents)`, `list_documents(limit, offset)`,
  `get_document(id)`, and `search(query, limit)`, plus the adapters they consume.
- [x] Run the unit tests and verify they pass.

## Task 2: API and lifecycle

Files: `app/main.py`, `app/bootstrap.py`, `data/sample_documents.json`,
`tests/test_api.py`, `tests/test_config.py`.

- [x] Test GET/POST contracts, validation, 404/503 responses, and readiness.
- [x] Implement `create_app()` with dependency injection and lifecycle cleanup.
- [x] Add startup schema creation and repeatable seed ingestion.
- [x] Run the complete unit suite.

## Task 3: Runnable environment and handoff

Files: `pyproject.toml`, `uv.lock`, `.python-version`, `Dockerfile`, `docker-compose.yml`,
`.env.example`, `.gitignore`, `.dockerignore`, `Makefile`, `README.md`, `AGENTS.md`,
`.github/workflows/ci.yml`, `tests/integration/test_stack.py`.

- [x] Add reproducible dependencies, Docker health checks, and startup ordering.
- [x] Add integration tests and documentation with executable examples.
- [x] Run pytest, Ruff lint/format, Compose validation, and available stack checks.
- [x] Record verified results and any environment limitations in the handoff.

## Verification results

- Editable installation and dependency checks passed on Python 3.11.
- `make check`: 27 offline tests passed; Ruff lint and formatting passed.
- Docker build and Compose validation passed; all three services are healthy.
- Full pytest suite inside Docker: 28 passed, including real-store integration.
- API restart plus integration rerun passed; PostgreSQL and Weaviate each retain
  three sample documents.
- Independent read-only review found no critical or important issues.
- Local `.env` uses port 8001 because 8000 was occupied, and the verified
  `OPENSSL_armcap=0` workaround for this older Docker/Apple Silicon runtime.
  The example configuration leaves this workaround disabled.
- Two upstream HTTPX deprecation warnings remain in Starlette/Authlib; checks pass.
  Live OpenAI requests were not made; the official SDK was tested with HTTP stubs.
