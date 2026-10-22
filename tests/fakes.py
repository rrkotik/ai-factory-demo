from uuid import UUID

from app.schemas import Document
from app.service import DependencyUnavailable


class MemoryRepository:
    def __init__(self):
        self.documents: dict[UUID, Document] = {}

    def save(self, documents: list[Document]) -> list[Document]:
        return [self.documents.setdefault(doc.id, doc) for doc in documents]

    def get(self, document_id: UUID) -> Document | None:
        return self.documents.get(document_id)

    def list(self, limit: int, offset: int) -> list[Document]:
        return list(self.documents.values())[offset : offset + limit]

    def check_ready(self) -> None:
        pass


class MemoryVectorStore:
    def __init__(self):
        self.vectors: dict[UUID, list[float]] = {}
        self.available = True

    def upsert(self, document: Document, vector: list[float]) -> None:
        self.check_ready()
        self.vectors[document.id] = vector

    def search(self, vector: list[float], limit: int) -> list[tuple[UUID, float]]:
        self.check_ready()
        distances = [
            (doc_id, 1 - sum(a * b for a, b in zip(vector, stored, strict=True)))
            for doc_id, stored in self.vectors.items()
        ]
        return sorted(distances, key=lambda hit: hit[1])[:limit]

    def check_ready(self) -> None:
        if not self.available:
            raise DependencyUnavailable("Vector store unavailable")
