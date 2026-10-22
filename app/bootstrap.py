import logging
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

import weaviate
from openai import OpenAI
from sqlalchemy import create_engine
from weaviate.classes.init import AdditionalConfig, Timeout

from app.config import Settings
from app.database import Base, PostgresRepository
from app.embeddings import LocalEmbeddings, OpenAIEmbeddings
from app.schemas import IngestRequest
from app.service import DocumentService
from app.vector_store import WeaviateVectorStore

logger = logging.getLogger(__name__)


@contextmanager
def open_service(settings: Settings) -> Iterator[DocumentService]:
    """Initialize dependencies once and close every acquired resource on exit."""
    with ExitStack() as stack:
        engine = create_engine(
            settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
        )
        stack.callback(engine.dispose)
        Base.metadata.create_all(engine)

        client = weaviate.connect_to_custom(
            http_host=settings.weaviate_host,
            http_port=settings.weaviate_http_port,
            http_secure=False,
            grpc_host=settings.weaviate_host,
            grpc_port=settings.weaviate_grpc_port,
            grpc_secure=False,
            additional_config=AdditionalConfig(timeout=Timeout(init=30, query=10, insert=30)),
        )
        stack.callback(client.close)
        vectors = WeaviateVectorStore(client, settings.collection_name)
        vectors.initialize()

        if settings.embedding_provider == "openai":
            openai = stack.enter_context(
                OpenAI(
                    api_key=settings.openai_api_key.get_secret_value(), timeout=20.0, max_retries=2
                )
            )
            embeddings = OpenAIEmbeddings(openai, settings.openai_embedding_model)
        else:
            embeddings = LocalEmbeddings()

        service = DocumentService(PostgresRepository(engine), vectors, embeddings)
        if settings.seed_on_startup:
            seed = IngestRequest.model_validate_json(settings.seed_path.read_text())
            documents = service.ingest(seed.documents)
            logger.info(
                "Ingested %d sample documents (%s)", len(documents), settings.embedding_provider
            )
        yield service
