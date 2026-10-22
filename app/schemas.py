from datetime import UTC, datetime
from typing import Annotated, Literal
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


class ProductInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    images: list[Annotated[str, Field(min_length=1, max_length=7 * 1024 * 1024)]] = Field(
        min_length=1, max_length=20
    )


class ProductVerification(BaseModel):
    status: Literal["approved", "rejected"]
    comments: list[str]
