import hashlib
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.product_review import ReasoningEffort


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://interview:interview@localhost:5432/interview"
    weaviate_host: str = "localhost"
    weaviate_http_port: int = Field(default=8080, ge=1, le=65535)
    weaviate_grpc_port: int = Field(default=50051, ge=1, le=65535)
    embedding_provider: Literal["local", "openai"] = "local"
    openai_api_key: SecretStr = SecretStr("")
    openai_embedding_model: str = "text-embedding-3-small"
    openai_product_model: str = Field(default="gpt-6-sol", min_length=1, pattern=r"\S")
    openai_product_reasoning_effort: ReasoningEffort = "low"
    seed_on_startup: bool = True
    seed_path: Path = Path(__file__).resolve().parent.parent / "data" / "sample_documents.json"

    @model_validator(mode="after")
    def validate_openai_key(self) -> Self:
        if (
            self.embedding_provider == "openai"
            and not self.openai_api_key.get_secret_value().strip()
        ):
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")
        return self

    @property
    def collection_name(self) -> str:
        # Isolate different vector spaces even when they happen to share dimensions.
        identity = (
            "local-hash-v1-64"
            if self.embedding_provider == "local"
            else f"openai:{self.openai_embedding_model}"
        )
        suffix = hashlib.sha256(identity.encode()).hexdigest()[:12]
        return f"InterviewDocument_{suffix}"
