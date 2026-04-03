"""Tests for the HTML extraction provider."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.etl.extraction.base import ExtractionRequest, ExtractionError
from app.etl.extraction.providers.html import HtmlExtractionProvider


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Article Title</title>
    <meta name="description" content="This is a test article excerpt for testing purposes.">
    <meta name="author" content="John Doe">
    <meta property="og:title" content="OG Title">
    <meta property="og:image" content="/images/og-image.jpg">
    <meta property="article:published_time" content="2024-01-15T10:00:00Z">
</head>
<body>
    <h1 class="tm-article-snippet__title">Habr Article Title</h1>
    <a class="tm-user-info__username" href="/user/johndoe/">johndoe</a>
    <time datetime="2024-01-15T10:00:00Z">Jan 15</time>
    <div class="tm-article-body">
        <p>This is the article body content with some text.</p>
        <img src="/images/article-img.jpg" alt="Article image">
    </div>
    <a class="tm-article-tags__post" href="/tags/python/">python</a>
    <a class="tm-article-tags__post" href="/tags/testing/">testing</a>
    <a class="tm-article-hub" href="/hub/development/">Development</a>
</body>
</html>
"""


class TestHtmlExtractionProviderInit:
    def test_default_values(self):
        provider = HtmlExtractionProvider()
        assert provider.timeout == 30
        assert provider.max_retries == 3
        assert provider.user_agent == "HabrAgenticPipeline/1.0"
        assert provider._client is None

    def test_custom_values(self):
        provider = HtmlExtractionProvider(timeout=60, max_retries=5, user_agent="Custom/1.0")
        assert provider.timeout == 60
        assert provider.max_retries == 5
        assert provider.user_agent == "Custom/1.0"

    def test_provider_name(self):
        provider = HtmlExtractionProvider()
        assert provider.name == "htmlextraction"


class TestHtmlExtractionProviderParseHtml:
    def test_parse_habr_html(self):
        provider = HtmlExtractionProvider()
        result = provider._parse_html(SAMPLE_HTML, "https://habr.com/article/123/")

        assert result.title == "Habr Article Title"
        assert "tm-article-body" in result.content
        assert result.author == "johndoe"
        assert result.published_at == "2024-01-15T10:00:00Z"
        assert result.tags == ["python", "testing"]
        assert result.hubs == ["Development"]
        assert result.provider_name == "htmlextraction"

    def test_parse_html_with_fallback_title(self):
        html = "<html><head><title>Fallback Title</title></head><body><p>Content</p></body></html>"
        provider = HtmlExtractionProvider()
        result = provider._parse_html(html, "https://example.com/")
        assert result.title == "Fallback Title"

    def test_parse_html_with_og_title(self):
        html = """<html><head><meta property="og:title" content="OG Title"></head><body></body></html>"""
        provider = HtmlExtractionProvider()
        result = provider._parse_html(html, "https://example.com/")
        assert result.title == "OG Title"

    def test_parse_html_extracts_images(self):
        provider = HtmlExtractionProvider()
        result = provider._parse_html(SAMPLE_HTML, "https://habr.com/article/123/")
        assert len(result.image_urls) > 0
        # og:image should be resolved
        assert any("og-image" in url for url in result.image_urls)

    def test_parse_html_extracts_excerpt_from_meta(self):
        provider = HtmlExtractionProvider()
        result = provider._parse_html(SAMPLE_HTML, "https://habr.com/article/123/")
        assert "test article excerpt" in result.excerpt.lower()


class TestHtmlExtractionProviderExtract:
    @pytest.mark.asyncio
    async def test_extract_with_raw_html(self):
        provider = HtmlExtractionProvider()
        request = ExtractionRequest(
            source_url="https://habr.com/article/123/",
            raw_html=SAMPLE_HTML,
        )
        result = await provider.extract(request)
        assert result.title == "Habr Article Title"
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_extract_fetches_html_when_not_provided(self):
        provider = HtmlExtractionProvider()
        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(provider, "_get_client", return_value=mock_client):
            request = ExtractionRequest(source_url="https://habr.com/article/123/")
            result = await provider.extract(request)

        assert result.title == "Habr Article Title"
        mock_client.get.assert_called_once_with("https://habr.com/article/123/")

    @pytest.mark.asyncio
    async def test_extract_raises_on_failure(self):
        provider = HtmlExtractionProvider(max_retries=1)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.is_closed = False

        with patch.object(provider, "_get_client", return_value=mock_client):
            request = ExtractionRequest(source_url="https://example.com/")
            with pytest.raises(ExtractionError, match="HTML extraction failed"):
                await provider.extract(request)


class TestHtmlExtractionProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        provider = HtmlExtractionProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        provider = HtmlExtractionProvider()
        mock_client = AsyncMock()
        mock_client.head = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.is_closed = False

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.health_check()
        assert result is False


class TestHtmlExtractionProviderRetryableError:
    def test_timeout_is_retryable(self):
        provider = HtmlExtractionProvider()
        assert provider._is_retryable_error(Exception("Request timed out")) is True

    def test_connection_error_is_retryable(self):
        provider = HtmlExtractionProvider()
        assert provider._is_retryable_error(Exception("Connection refused")) is True

    def test_503_is_retryable(self):
        provider = HtmlExtractionProvider()
        assert provider._is_retryable_error(Exception("503 Service Unavailable")) is True

    def test_429_is_retryable(self):
        provider = HtmlExtractionProvider()
        assert provider._is_retryable_error(Exception("429 Too Many Requests")) is True

    def test_404_is_not_retryable(self):
        provider = HtmlExtractionProvider()
        assert provider._is_retryable_error(Exception("404 Not Found")) is False


class TestHtmlExtractionProviderClose:
    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        provider = HtmlExtractionProvider()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        provider._client = mock_client

        await provider.close()
        mock_client.aclose.assert_called_once()
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        provider = HtmlExtractionProvider()
        await provider.close()  # Should not raise
