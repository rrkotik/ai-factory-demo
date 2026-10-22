from uuid import uuid4

import pytest


def test_ingest_list_get_and_search(client):
    response = client.post(
        "/ingest",
        json={"documents": [{"title": "PostgreSQL", "content": "PostgreSQL relational database"}]},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    document = response.json()["documents"][0]
    assert document["title"] == "PostgreSQL"
    assert client.get("/documents").json() == [document]
    assert client.get(f"/documents/{document['id']}").json() == document
    assert (
        client.get("/search", params={"q": "relational database"}).json()[0]["document"] == document
    )


def test_pagination(client):
    client.post(
        "/ingest",
        json={"documents": [{"title": str(i), "content": "Example"} for i in range(3)]},
    )
    page = client.get("/documents?limit=1&offset=1")
    assert page.status_code == 200
    assert len(page.json()) == 1
    assert client.get("/documents?offset=3").json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"documents": []},
        {"documents": [{"title": " ", "content": "Text"}]},
        {"documents": [{"title": "Title", "content": "\n\t"}]},
        {"documents": [{"title": "Title", "content": "x" * 4001}]},
        {"documents": [{"title": "Title", "content": "Text"}] * 101},
    ],
)
def test_invalid_ingestion_returns_422(client, payload):
    assert client.post("/ingest", json=payload).status_code == 422
    assert client.get("/documents").json() == []


@pytest.mark.parametrize(
    "url",
    [
        "/documents?limit=0",
        "/documents?offset=-1",
        "/search?q=",
        "/search?q=%20",
        "/search?q=a&limit=21",
    ],
)
def test_invalid_query_returns_422(client, url):
    assert client.get(url).status_code == 422


def test_missing_and_malformed_document_ids(client):
    assert client.get(f"/documents/{uuid4()}").status_code == 404
    assert client.get("/documents/not-a-uuid").status_code == 422


def test_liveness_and_readiness_reflect_dependency_failure(client, service):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200
    service.vectors.available = False
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    response = client.post("/ingest", json={"documents": [{"title": "Title", "content": "Text"}]})
    assert response.status_code == 503
    assert response.json() == {"detail": "A required service is unavailable. Retry the request."}
