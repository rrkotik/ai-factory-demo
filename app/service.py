import json
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from app.schemas import Document, DocumentInput, SearchHit


class DependencyUnavailable(RuntimeError):
    """An external dependency failed; expose a generic 503 at the HTTP boundary."""


class Repository(Protocol):
    def save(self, documents: list[Document]) -> list[Document]: ...
    def get(self, document_id: UUID) -> Document | None: ...
    def list(self, limit: int, offset: int) -> list[Document]: ...
    def check_ready(self) -> None: ...


class VectorStore(Protocol):
    def upsert(self, document: Document, vector: list[float]) -> None: ...
    def search(self, vector: list[float], limit: int) -> list[tuple[UUID, float]]: ...
    def check_ready(self) -> None: ...


class Embeddings(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DocumentService:
    def __init__(self, repository: Repository, vectors: VectorStore, embeddings: Embeddings):
        self.repository = repository
        self.vectors = vectors
        self.embeddings = embeddings

    def ingest(self, documents: list[DocumentInput]) -> list[Document]:
        unique: dict[UUID, Document] = {}
        for item in documents:
            identity = json.dumps([item.title, item.content], ensure_ascii=False)
            document_id = uuid5(NAMESPACE_URL, f"interview-document:{identity}")
            unique[document_id] = Document(id=document_id, **item.model_dump())

        pending = list(unique.values())
        vectors = self.embeddings.embed([f"{doc.title}\n{doc.content}" for doc in pending])
        if len(vectors) != len(pending):
            raise DependencyUnavailable("Embedding response count did not match the input")

        # Commit the source of truth first. Retrying repairs an interrupted index write.
        saved = self.repository.save(pending)
        for document, vector in zip(saved, vectors, strict=True):
            self.vectors.upsert(document, vector)
        return saved

    def list_documents(self, limit: int, offset: int) -> list[Document]:
        return self.repository.list(limit, offset)

    def get_document(self, document_id: UUID) -> Document | None:
        return self.repository.get(document_id)

    def search(self, query: str, limit: int) -> list[SearchHit]:
        vector = self.embeddings.embed([query])[0]
        hits = self.vectors.search(vector, limit)
        results = []
        for document_id, distance in hits:
            document = self.repository.get(document_id)
            if document is not None:
                results.append(SearchHit(document=document, distance=distance))
        return results

    def check_ready(self) -> None:
        self.repository.check_ready()
        self.vectors.check_ready()
