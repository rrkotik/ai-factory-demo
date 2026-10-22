import pytest

from app.schemas import DocumentInput
from app.service import DependencyUnavailable


def test_repeated_ingestion_preserves_ids_timestamps_and_single_index_entry(service):
    doc = DocumentInput(title="PostgreSQL", content="A relational database.")
    first = service.ingest([doc, doc])
    second = service.ingest([doc])

    assert first == second
    assert len(first) == 1
    assert len(service.list_documents(limit=20, offset=0)) == 1
    assert len(service.vectors.vectors) == 1


def test_retry_repairs_vector_index_after_partial_failure(service):
    doc = DocumentInput(title="FastAPI", content="Build Python APIs.")
    service.vectors.available = False

    with pytest.raises(DependencyUnavailable):
        service.ingest([doc])
    assert len(service.list_documents(limit=20, offset=0)) == 1
    assert service.vectors.vectors == {}

    service.vectors.available = True
    result = service.ingest([doc])
    assert len(service.list_documents(limit=20, offset=0)) == 1
    assert service.search("Python APIs", limit=1)[0].document.id == result[0].id


def test_different_content_creates_distinct_documents(service):
    result = service.ingest(
        [
            DocumentInput(title="Notes", content="First"),
            DocumentInput(title="Notes", content="Second"),
        ]
    )
    assert len({doc.id for doc in result}) == 2


def test_embedding_failure_does_not_persist_documents(service):
    class BrokenEmbeddings:
        def embed(self, texts):
            raise DependencyUnavailable("Embedding service unavailable")

    service.embeddings = BrokenEmbeddings()
    with pytest.raises(DependencyUnavailable):
        service.ingest([DocumentInput(title="Notes", content="First")])
    assert service.list_documents(limit=20, offset=0) == []


def test_short_embedding_response_does_not_persist_documents(service):
    class IncompleteEmbeddings:
        def embed(self, texts):
            return []

    service.embeddings = IncompleteEmbeddings()
    with pytest.raises(DependencyUnavailable):
        service.ingest([DocumentInput(title="Notes", content="First")])
    assert service.list_documents(limit=20, offset=0) == []
