# Backend interview starter

A small synchronous FastAPI backend using PostgreSQL as the source of truth and
Weaviate for vector search. Embeddings use either an explicit deterministic local
demo provider or the official OpenAI Python SDK.

## Run

Only Docker Compose and make are required on the host. Copy the example environment
file when customizing configuration:

```bash
cp .env.example .env
make start
```

The API is available on port 8000 by default, with interactive documentation at
/docs. PostgreSQL and Weaviate start before the API; startup idempotently ingests
the three documents in data/sample_documents.json.

Set EMBEDDING_PROVIDER=openai and OPENAI_API_KEY in .env for real embeddings.
Changing provider or model selects a separate vector collection; reingest custom
documents after switching. Local mode is explicit and never a fallback for errors.

## API

- POST /ingest: ingest 1–100 documents with title and content.
- GET /documents: stable pagination through limit and offset.
- GET /documents/{document_id}: UUID lookup.
- GET /search?q=...: vector search with cosine distances.
- GET /health: liveness.
- GET /ready: readiness of both stores, without calling OpenAI.

PostgreSQL commits before vector indexing; retries repair partial indexing failures.
Duplicate ingestion is idempotent, and changed content creates a new document.

## Development

```bash
make build
make check
make pre-commit
make integration
make hooks-install
make stop
```

All Python tooling runs inside Docker. Offline checks use disposable containers
without databases. Integration checks start the stack. Live reload watches app/
and data/; dependency or environment changes require another make start.

make stop preserves containers and database volumes. Do not delete volumes unless
you intend to remove stored data. Environment files, caches, and virtual environments
are ignored by Git.
