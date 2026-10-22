from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=4000)


class Document(DocumentInput):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentInput] = Field(min_length=1, max_length=100)


class IngestResponse(BaseModel):
    count: int
    documents: list[Document]


class SearchHit(BaseModel):
    document: Document
    distance: float
