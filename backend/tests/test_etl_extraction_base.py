"""Tests for extraction base classes and shared types."""

import pytest

from app.etl.extraction.base import (
    BaseExtractionProvider,
    ExtractionError,
    ExtractionRequest,
    ExtractionResult,
)


class ConcreteProvider(BaseExtractionProvider):
    """Concrete implementation for testing the abstract base class."""

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        return ExtractionResult(title="test", provider_name=self.name)

    async def health_check(self) -> bool:
        return True


class TestExtractionRequest:
    def test_default_values(self):
        req = ExtractionRequest(source_url="https://example.com")
        assert req.source_url == "https://example.com"
        assert req.raw_html is None
        assert req.feed_entry is None
        assert req.source_type == "html"
        assert req.source_language == "ru"

    def test_custom_values(self):
        req = ExtractionRequest(
            source_url="https://example.com",
            raw_html="<html></html>",
            feed_entry={"title": "test"},
            source_type="rss",
            source_language="en",
        )
        assert req.raw_html == "<html></html>"
        assert req.feed_entry == {"title": "test"}
        assert req.source_type == "rss"
        assert req.source_language == "en"


class TestExtractionResult:
    def test_default_values(self):
        result = ExtractionResult()
        assert result.title == ""
        assert result.content == ""
        assert result.excerpt == ""
        assert result.author is None
        assert result.published_at is None
        assert result.tags == []
        assert result.hubs == []
        assert result.image_urls == []
        assert result.provider_name == ""
        assert result.latency_ms is None
        assert result.error is None
        assert result.metadata == {}

    def test_populated_result(self):
        result = ExtractionResult(
            title="Test Article",
            content="<p>Hello</p>",
            excerpt="Hello",
            author="John",
            published_at="2024-01-01",
            tags=["python", "testing"],
            hubs=["dev"],
            image_urls=["https://img.png"],
            provider_name="html",
            latency_ms=42.5,
            metadata={"key": "value"},
        )
        assert result.title == "Test Article"
        assert result.tags == ["python", "testing"]
        assert result.latency_ms == 42.5
        assert result.metadata == {"key": "value"}


class TestBaseExtractionProvider:
    def test_provider_name_derived_from_class(self):
        provider = ConcreteProvider()
        assert provider.name == "concrete"

    def test_extra_config_stored(self):
        provider = ConcreteProvider(timeout=60, max_retries=5)
        assert provider._extra_config == {"timeout": 60, "max_retries": 5}

    @pytest.mark.asyncio
    async def test_extract_returns_result(self):
        provider = ConcreteProvider()
        req = ExtractionRequest(source_url="https://example.com")
        result = await provider.extract(req)
        assert result.title == "test"
        assert result.provider_name == "concrete"

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self):
        provider = ConcreteProvider()
        assert await provider.health_check() is True


class TestExtractionError:
    def test_basic_error(self):
        err = ExtractionError("Something failed")
        assert str(err) == "Something failed"
        assert err.message == "Something failed"
        assert err.provider == "unknown"
        assert err.retryable is True

    def test_custom_provider_and_retryable(self):
        err = ExtractionError("Timeout", provider="html", retryable=False)
        assert err.provider == "html"
        assert err.retryable is False
