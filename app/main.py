import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.bootstrap import open_service
from app.config import Settings
from app.schemas import Document, IngestRequest, IngestResponse, SearchHit
from app.service import DependencyUnavailable, DocumentService

logger = logging.getLogger(__name__)


def get_service(request: Request) -> DocumentService:
    return request.app.state.service


Service = Annotated[DocumentService, Depends(get_service)]


def create_app(service: DocumentService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if service is not None:
            app.state.service = service
            yield
        else:
            with open_service(Settings()) as managed_service:
                app.state.service = managed_service
                yield

    application = FastAPI(
        title="Interview Starter",
        version="0.1.0",
        description="Ingest documents into PostgreSQL and search their Weaviate vectors.",
        lifespan=lifespan,
    )

    @application.exception_handler(DependencyUnavailable)
    async def dependency_unavailable(request: Request, exc: DependencyUnavailable) -> JSONResponse:
        logger.warning("Dependency failure on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "A required service is unavailable. Retry the request."},
        )

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", tags=["health"])
    def ready(service: Service) -> dict[str, str]:
        service.check_ready()
        return {"status": "ready"}

    @application.post("/ingest", response_model=IngestResponse, tags=["documents"])
    def ingest(payload: IngestRequest, service: Service) -> IngestResponse:
        documents = service.ingest(payload.documents)
        return IngestResponse(count=len(documents), documents=documents)

    @application.get("/documents", response_model=list[Document], tags=["documents"])
    def list_documents(
        service: Service,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[Document]:
        return service.list_documents(limit=limit, offset=offset)

    @application.get("/documents/{document_id}", response_model=Document, tags=["documents"])
    def get_document(document_id: UUID, service: Service) -> Document:
        document = service.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return document

    @application.get("/search", response_model=list[SearchHit], tags=["search"])
    def search(
        service: Service,
        q: Annotated[str, Query(min_length=1, max_length=4000, pattern=r"\S")],
        limit: Annotated[int, Query(ge=1, le=20)] = 5,
    ) -> list[SearchHit]:
        return service.search(q.strip(), limit=limit)

    return application


app = create_app()
