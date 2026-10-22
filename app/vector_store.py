from uuid import UUID

from weaviate import WeaviateClient
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.query import MetadataQuery
from weaviate.exceptions import UnexpectedStatusCodeError, WeaviateBaseError

from app.schemas import Document
from app.service import DependencyUnavailable


class WeaviateVectorStore:
    def __init__(self, client: WeaviateClient, collection_name: str):
        self.client = client
        self.collection_name = collection_name
        self.collection = client.collections.use(collection_name)

    def initialize(self) -> None:
        if not self.client.collections.exists(self.collection_name):
            self.client.collections.create(
                name=self.collection_name,
                vector_config=Configure.Vectors.self_provided(),
                properties=[
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="content", data_type=DataType.TEXT),
                ],
            )

    def upsert(self, document: Document, vector: list[float]) -> None:
        properties = {"title": document.title, "content": document.content}
        try:
            if self.collection.data.exists(document.id):
                self.collection.data.replace(uuid=document.id, properties=properties, vector=vector)
            else:
                try:
                    self.collection.data.insert(
                        uuid=document.id, properties=properties, vector=vector
                    )
                except UnexpectedStatusCodeError:
                    # Concurrent ingestion may have inserted the same stable UUID.
                    if not self.collection.data.exists(document.id):
                        raise
                    self.collection.data.replace(
                        uuid=document.id, properties=properties, vector=vector
                    )
        except WeaviateBaseError as exc:
            raise DependencyUnavailable("Weaviate indexing failed") from exc

    def search(self, vector: list[float], limit: int) -> list[tuple[UUID, float]]:
        try:
            response = self.collection.query.near_vector(
                near_vector=vector, limit=limit, return_metadata=MetadataQuery(distance=True)
            )
            return [
                (UUID(str(obj.uuid)), obj.metadata.distance)
                for obj in response.objects
                if obj.metadata.distance is not None
            ]
        except WeaviateBaseError as exc:
            raise DependencyUnavailable("Weaviate search failed") from exc

    def check_ready(self) -> None:
        try:
            if not self.client.is_ready():
                raise DependencyUnavailable("Weaviate is not ready")
        except WeaviateBaseError as exc:
            raise DependencyUnavailable("Weaviate is not ready") from exc
