# Interview starter design

Build a small Python backend that can be extended during an interview. The user
requested PostgreSQL, Weaviate, FastAPI GET/POST endpoints, ingestion, OpenAI
clients, pytest, Ruff, agent instructions, and Docker Compose startup seeding.

Use synchronous FastAPI handlers with SQLAlchemy/psycopg, the Weaviate v4 client,
and the official OpenAI Python SDK. PostgreSQL is the document source of truth;
Weaviate holds searchable vectors. Keep each adapter separate from ingestion.

`POST /ingest` accepts 1–100 short documents. Stable IDs derived from title and
content make repeated ingestion safe. PostgreSQL commits before vector indexing;
a failed index operation returns 503 and can be repaired by repeating ingestion.
This starter deliberately does not implement distributed transactions or workers.

`GET /documents`, `GET /documents/{id}`, and `GET /search` expose the data.
`/health` is liveness; `/ready` checks both stores. Invalid inputs return 422,
unknown IDs return 404, and external dependency failures return 503.

Docker Compose starts PostgreSQL and Weaviate with health checks and persistent
volumes, then the API initializes schemas and ingests three bundled documents.
Local demo embeddings work without credentials. Explicit OpenAI mode requires a
key and uses `text-embedding-3-small`; it never silently falls back. Collection
names separate providers/models so changing modes cannot mix incompatible vectors.

Unit tests run without Docker or credentials. An opt-in integration suite checks
the actual running stack, including repeated seed ingestion. Ruff checks imports,
lint, and formatting. README and AGENTS.md document commands and tradeoffs.

Use uv with `pyproject.toml`, a development dependency group, and `uv.lock` for
Docker development and CI. `.python-version` selects Python 3.11. The host needs
only Docker Compose and make; all Python execution and dependency tooling run
inside containers, including tests, lint, formatting, and lock updates.
