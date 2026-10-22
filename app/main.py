import logging
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.bootstrap import open_product_verifier, open_service
from app.config import Settings
from app.product_verification import ProductVerifier
from app.request_limits import ProductBodyLimit
from app.schemas import (
    Document,
    IngestRequest,
    IngestResponse,
    ProductInput,
    ProductVerification,
    SearchHit,
)
from app.service import DependencyUnavailable, DocumentService

logger = logging.getLogger(__name__)


def get_service(request: Request) -> DocumentService:
    return request.app.state.service


Service = Annotated[DocumentService, Depends(get_service)]


def get_verifier(request: Request) -> ProductVerifier:
    return request.app.state.verifier


Verifier = Annotated[ProductVerifier, Depends(get_verifier)]


def create_app(
    service: DocumentService | None = None, verifier: ProductVerifier | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        with ExitStack() as stack:
            if service is not None:
                app.state.service = service
                app.state.verifier = verifier if verifier is not None else ProductVerifier()
            else:
                settings = Settings()
                app.state.service = stack.enter_context(open_service(settings))
                app.state.verifier = (
                    verifier
                    if verifier is not None
                    else stack.enter_context(open_product_verifier(settings))
                )
            yield

    application = FastAPI(
        title="Interview Starter",
        version="0.1.0",
        description="Ingest documents into PostgreSQL and search their Weaviate vectors.",
        lifespan=lifespan,
    )
    application.add_middleware(ProductBodyLimit)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path.rstrip("/") == "/products/verify":
            # Do not reflect potentially megabytes of private base64 image data.
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                        for error in exc.errors()
                    ]
                },
            )
        return await request_validation_exception_handler(request, exc)

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

    @application.post("/products/verify", response_model=ProductVerification, tags=["products"])
    def verify_product(payload: ProductInput, verifier: Verifier) -> ProductVerification:
        return verifier.verify(payload)

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
