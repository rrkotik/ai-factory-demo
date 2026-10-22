# Agent guide

## Purpose and stack

Keep this repository a small, understandable backend interview starter. It uses
Python 3.11+, FastAPI, PostgreSQL 17 with SQLAlchemy/psycopg, Weaviate with its v4
Python client, the official OpenAI Python SDK, uv, pytest, Ruff, and Docker Compose.
Do not introduce frameworks or infrastructure without a concrete requirement.

## Architecture

- `app/main.py`: synchronous GET/POST handlers, validation, dependency injection,
  and generic HTTP errors. Blocking clients belong in `def` handlers.
- `app/service.py`: ingestion/search orchestration and small adapter protocols.
- `app/database.py`: PostgreSQL is the source of truth. Use short-lived sessions;
  stable IDs and conflict-safe inserts prevent duplicates.
- `app/vector_store.py`: vectors use document UUIDs and
  `Configure.Vectors.self_provided()`. HTTP and gRPC must both be reachable.
- `app/embeddings.py`: use the official `OpenAI` client for real embeddings.
  `local` is an explicit deterministic demo mode, never a fallback for failures.
- `app/bootstrap.py`: acquire/close clients, create schemas, ingest
  `data/sample_documents.json` before startup completes. Preserve cleanup on errors.
- `app/config.py`: Pydantic Settings; `.env` stays untracked. Provider/model
  identity separates vector collections.

## API and ingestion contract

- `POST /ingest`: 1–100 documents; title 1–200 characters, content 1–4,000.
  Trim boundary whitespace and reject blank values.
- `GET /documents`: stable pagination, limit 1–100 and offset 0+.
- `GET /documents/{id}`: UUID lookup; 404 if absent.
- `GET /search`: nonblank q, limit 1–20, results with cosine distance.
- `/health` is liveness; `/ready` checks both stores without an OpenAI call.
- Bad requests return 422. Translate external failures to
  `DependencyUnavailable`/503 without credentials or raw vendor messages.
- Preserve stable IDs and idempotent startup/request ingestion. PostgreSQL commits
  before indexing; retries repair partial failures. Do not imply cross-store
  atomicity. Changed content creates a new document.
- Switching provider/model requires reingesting custom documents into the new
  collection. Never mix vector spaces in an existing collection.

## Commands and verification

```bash
make build
make check
make pre-commit
make start
make tests
make integration
make stop
docker compose config --quiet
```

Run the application and all Python tools inside Docker. Only Docker Compose and
make are required on the host; do not introduce local Python/uv setup commands.
Docker uses Python 3.11, `uv sync --locked` with the `dev` group during builds,
and `uv run --no-sync` at runtime. `make build` / `make install` builds the image.
Tests and lint use disposable API containers with `--no-deps`; they must work
while the databases and application are stopped. Formatting uses writable source
mounts and the host UID/GID. Keep the API's normal source mounts read-only.
`make start` enables Uvicorn live reload and debug logs inside Docker. Compose
bind-mounts `app/`, `data/`, and `tests/`; never mount the host `.venv` over the
container environment. Python and sample JSON edits reload only the API worker.
Polling is enabled for Docker Desktop. Dependency, image, and environment changes
require another `make start`. `make stop` preserves containers and database volumes.
`make tests` aliases the existing offline `make test` target; `make up` aliases start.

`make check` runs Ruff lint/format checks and offline pytest tests in Docker. Use fakes at
external boundaries; exercise the actual OpenAI SDK with HTTP transport stubs,
never live credentials. `make integration` starts the stack and runs with
`RUN_INTEGRATION=1` inside the API container, using its internal port 8000 regardless
of the published host port. Run it for persistence,
Weaviate, startup, or Compose changes. Report skipped checks accurately.

Use Ruff (`make format`) and type annotations for public application interfaces.
Test meaningful behavior changes, especially duplicate ingestion, partial
failures, validation, provider configuration, and lifecycle cleanup. Keep
`pyproject.toml` and `uv.lock` consistent. Use `make uv ARGS="add --no-sync PACKAGE"`
or `make uv ARGS="add --dev --no-sync PACKAGE"` to add dependencies, `make lock`
after manual edits, and `make uv ARGS="lock --upgrade"` only for intentional
upgrades. These use a standalone uv container, independent of the app build.
Commit both files, rebuild, and verify with `make check integration`.

## Pre-commit hooks

`make hooks-install` enables the versioned `.githooks/pre-commit` launcher for
this clone via `core.hooksPath`. It runs the pre-commit framework inside Docker
on staged files; `make pre-commit` checks all tracked files. Keep hooks in
`.pre-commit-config.yaml` and use the Ruff version installed from `uv.lock`.
Ruff lint fixes run before formatting. Review and restage hook changes before
retrying a commit; never stage a user's files automatically. Preserve the
forwarded `GIT_INDEX_FILE` and identical host/container repository path so
`git commit -a` and partial commits use the correct index. The hook container
uses the host UID/GID and needs no running databases. CI runs these same hooks.

## Docker development constraints

Compose starts healthy databases before the API, which seeds three examples on
each startup by default. Volumes persist across `docker compose down`.
`docker compose down -v` deletes data; do not run it against existing user data
without explicit authorization. Never commit `.env`, keys, caches, or venvs.
No real OpenAI calls are needed for verification.

`create_all` initializes schemas; it does not migrate them. Add Alembic before
evolving persisted schemas. Keep one API worker; scale-out bootstrap coordination
and reliable background indexing require a separate design. Keep README examples
and environment documentation aligned with changes.
