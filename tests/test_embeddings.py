import json
import math

import httpx
import pytest
from openai import OpenAI

from app.embeddings import LocalEmbeddings, OpenAIEmbeddings
from app.service import DependencyUnavailable


def test_local_embeddings_are_stable_normalized_and_support_nonword_text():
    embeddings = LocalEmbeddings()
    first = embeddings.embed(["PostgreSQL database", "!!!", "数据库"])
    assert first == embeddings.embed(["PostgreSQL database", "!!!", "数据库"])
    assert all(len(vector) == 64 for vector in first)
    assert all(math.isclose(sum(x * x for x in vector), 1.0) for vector in first)


def test_openai_sdk_embeds_batch_and_restores_response_order():
    def handle(request):
        assert request.url.path == "/v1/embeddings"
        assert json.loads(request.content) == {
            "input": ["first", "second"],
            "model": "text-embedding-3-small",
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [
                    {"object": "embedding", "index": 1, "embedding": [0.0, 1.0]},
                    {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]},
                ],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    with OpenAI(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        max_retries=0,
    ) as client:
        provider = OpenAIEmbeddings(client, "text-embedding-3-small")
        assert provider.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_openai_errors_are_reported_without_silent_fallback():
    with (
        OpenAI(
            api_key="test-key",
            http_client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(429, json={"error": "quota"})
                )
            ),
            max_retries=0,
        ) as client,
        pytest.raises(DependencyUnavailable),
    ):
        OpenAIEmbeddings(client, "text-embedding-3-small").embed(["Text"])
