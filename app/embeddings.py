import hashlib
import math
import re

from openai import OpenAI, OpenAIError

from app.service import DependencyUnavailable


class LocalEmbeddings:
    """Deterministic token hashing for a credential-free demo, not semantic AI."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * 64
            tokens = re.findall(r"\w+", text.casefold()) or [text]
            for token in tokens:
                index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4]) % len(vector)
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector])
        return vectors


class OpenAIEmbeddings:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.client.embeddings.create(
                model=self.model, input=texts, encoding_format="float"
            )
        except OpenAIError as exc:
            raise DependencyUnavailable("OpenAI embeddings request failed") from exc

        ordered = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in ordered] != list(range(len(texts))):
            raise DependencyUnavailable("OpenAI returned an incomplete embedding response")
        vectors = [item.embedding for item in ordered]
        if any(
            not vector or not all(math.isfinite(value) for value in vector) for vector in vectors
        ):
            raise DependencyUnavailable("OpenAI returned an invalid embedding vector")
        return vectors
