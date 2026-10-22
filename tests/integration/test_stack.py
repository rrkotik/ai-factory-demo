import json
import os
import time
from pathlib import Path

import httpx
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="Set RUN_INTEGRATION=1"),
]


def test_seed_ingestion_is_idempotent_and_searchable_in_real_stores():
    payload = json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "sample_documents.json").read_text()
    )
    with httpx.Client(
        base_url=os.getenv("TEST_API_URL", "http://localhost:8000"), timeout=60
    ) as client:
        assert client.get("/ready").status_code == 200
        before = client.get("/documents?limit=100")
        before.raise_for_status()
        seed_titles = {doc["title"] for doc in payload["documents"]}
        assert seed_titles <= {doc["title"] for doc in before.json()}

        first = client.post("/ingest", json=payload)
        first.raise_for_status()
        second = client.post("/ingest", json=payload)
        second.raise_for_status()
        assert first.json() == second.json()
        assert first.json()["count"] == 3
        assert client.get("/documents?limit=100").json() == before.json()

        for doc in first.json()["documents"]:
            assert client.get(f"/documents/{doc['id']}").json() == doc

        # Allow bounded time for the vector index to expose new writes.
        deadline = time.monotonic() + 10
        while True:
            response = client.get("/search", params={"q": "PostgreSQL SQL database", "limit": 10})
            response.raise_for_status()
            hits = response.json()
            found_titles = {hit["document"]["title"] for hit in hits}
            if seed_titles <= found_titles or time.monotonic() >= deadline:
                break
            time.sleep(0.25)
        assert seed_titles <= found_titles
        assert len({hit["document"]["id"] for hit in hits}) == len(hits)
        assert hits[0]["document"]["title"] == "PostgreSQL basics"
