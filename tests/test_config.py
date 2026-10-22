import pytest
from pydantic import ValidationError

from app.config import Settings


def test_openai_mode_requires_a_nonblank_api_key():
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=None, embedding_provider="openai", openai_api_key=" ")


def test_embedding_modes_and_models_use_separate_collections():
    local = Settings(_env_file=None, embedding_provider="local")
    small = Settings(_env_file=None, embedding_provider="openai", openai_api_key="test")
    large = Settings(
        _env_file=None,
        embedding_provider="openai",
        openai_api_key="test",
        openai_embedding_model="text-embedding-3-large",
    )
    assert len({local.collection_name, small.collection_name, large.collection_name}) == 3


def test_product_review_settings_read_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_PRODUCT_MODEL", "configured-vision-model")
    monkeypatch.setenv("OPENAI_PRODUCT_REASONING_EFFORT", "medium")
    settings = Settings(_env_file=None)
    assert settings.openai_product_model == "configured-vision-model"
    assert settings.openai_product_reasoning_effort == "medium"


@pytest.mark.parametrize("effort", ["", "minimal", "typo"])
def test_product_review_rejects_invalid_reasoning_effort(effort):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, openai_product_reasoning_effort=effort)
