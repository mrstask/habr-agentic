"""Tests for extraction provider factory and registry."""

import pytest

from app.etl.extraction.base import BaseExtractionProvider, ExtractionRequest, ExtractionResult
from app.etl.extraction.providers.factory import (
    _EXTRACTION_PROVIDER_REGISTRY,
    register_extraction_provider,
    get_registered_extraction_providers,
    create_extraction_provider,
)


class DummyProvider(BaseExtractionProvider):
    """Dummy provider for testing the factory."""

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: str = "HabrAgenticPipeline/1.0",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        return ExtractionResult(title="dummy", provider_name=self.name)

    async def health_check(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before each test to ensure isolation."""
    _EXTRACTION_PROVIDER_REGISTRY.clear()
    yield
    _EXTRACTION_PROVIDER_REGISTRY.clear()


class TestRegisterExtractionProvider:
    def test_register_provider(self):
        register_extraction_provider("dummy", DummyProvider)
        assert "dummy" in _EXTRACTION_PROVIDER_REGISTRY
        assert _EXTRACTION_PROVIDER_REGISTRY["dummy"] is DummyProvider

    def test_register_overwrites(self):
        register_extraction_provider("dummy", DummyProvider)
        register_extraction_provider("dummy", DummyProvider)
        assert len(_EXTRACTION_PROVIDER_REGISTRY) == 1


class TestGetRegisteredExtractionProviders:
    def test_empty_registry(self):
        assert get_registered_extraction_providers() == []

    def test_returns_registered_names(self):
        register_extraction_provider("alpha", DummyProvider)
        register_extraction_provider("beta", DummyProvider)
        names = get_registered_extraction_providers()
        assert set(names) == {"alpha", "beta"}


class TestCreateExtractionProvider:
    def test_creates_provider_with_defaults(self):
        register_extraction_provider("dummy", DummyProvider)
        provider = create_extraction_provider("dummy")
        assert isinstance(provider, DummyProvider)
        assert provider.timeout == 30
        assert provider.max_retries == 3
        assert provider.user_agent == "HabrAgenticPipeline/1.0"

    def test_creates_provider_with_custom_args(self):
        register_extraction_provider("dummy", DummyProvider)
        provider = create_extraction_provider(
            "dummy",
            timeout=60,
            max_retries=5,
            user_agent="CustomAgent/2.0",
        )
        assert provider.timeout == 60
        assert provider.max_retries == 5
        assert provider.user_agent == "CustomAgent/2.0"

    def test_creates_provider_with_kwargs_fallback(self):
        register_extraction_provider("dummy", DummyProvider)
        provider = create_extraction_provider("dummy", timeout=45, max_retries=7)
        assert provider.timeout == 45
        assert provider.max_retries == 7

    def test_raises_for_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown extraction provider"):
            create_extraction_provider("nonexistent")

    def test_passes_extra_kwargs(self):
        register_extraction_provider("dummy", DummyProvider)
        provider = create_extraction_provider("dummy", custom_option="value")
        assert provider._extra_config.get("custom_option") == "value"
