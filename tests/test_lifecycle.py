from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import bootstrap, main
from app.config import Settings


def test_application_opens_and_closes_managed_service(monkeypatch, service):
    events = []

    @contextmanager
    def managed_service(settings):
        events.append("open")
        try:
            yield service
        finally:
            events.append("close")

    monkeypatch.setattr(main, "open_service", managed_service)
    with TestClient(main.create_app()) as client:
        assert client.get("/ready").status_code == 200
        assert events == ["open"]
    assert events == ["open", "close"]


def test_bootstrap_disposes_engine_when_schema_initialization_fails(monkeypatch):
    events = []

    class Engine:
        def dispose(self):
            events.append("dispose")

    def fail_schema(engine):
        raise RuntimeError("schema failed")

    monkeypatch.setattr(bootstrap, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(bootstrap.Base.metadata, "create_all", fail_schema)
    with (
        pytest.raises(RuntimeError, match="schema failed"),
        bootstrap.open_service(Settings(_env_file=None)),
    ):
        pytest.fail("Initialization must fail before yielding")
    assert events == ["dispose"]


def test_bootstrap_closes_vector_client_when_collection_initialization_fails(monkeypatch):
    events = []

    class Engine:
        def dispose(self):
            events.append("dispose")

    class Client:
        def close(self):
            events.append("close")

    class BrokenVectorStore:
        def __init__(self, *args):
            pass

        def initialize(self):
            raise RuntimeError("collection failed")

    monkeypatch.setattr(bootstrap, "create_engine", lambda *args, **kwargs: Engine())
    monkeypatch.setattr(bootstrap.Base.metadata, "create_all", lambda engine: None)
    monkeypatch.setattr(bootstrap.weaviate, "connect_to_custom", lambda **kwargs: Client())
    monkeypatch.setattr(bootstrap, "WeaviateVectorStore", BrokenVectorStore)
    with (
        pytest.raises(RuntimeError, match="collection failed"),
        bootstrap.open_service(Settings(_env_file=None)),
    ):
        pytest.fail("Initialization must fail before yielding")
    assert events == ["close", "dispose"]
