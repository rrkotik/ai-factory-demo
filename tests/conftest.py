import pytest
from fastapi.testclient import TestClient

from app.embeddings import LocalEmbeddings
from app.main import create_app
from app.service import DocumentService
from tests.fakes import MemoryRepository, MemoryVectorStore


@pytest.fixture
def service():
    return DocumentService(MemoryRepository(), MemoryVectorStore(), LocalEmbeddings())


@pytest.fixture
def client(service):
    with TestClient(create_app(service=service)) as client:
        yield client
