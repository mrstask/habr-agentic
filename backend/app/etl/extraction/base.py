"""
Extraction provider base class and shared types.

Defines the abstract interface that all extraction providers must implement,
along with shared dataclasses for extraction requests and responses.

Extraction providers are responsible for parsing raw HTML pages or RSS feed
entries and extracting structured article data (title, content, metadata).

Usage::

    from app.etl.extraction.base import BaseExtractionProvider, ExtractionRequest
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractionRequest:
    """
    Encapsulates all data needed for an article extraction operation.

    Attributes:
        source_url: URL of the article or feed to extract from.
        raw_html: Raw HTML content (if already fetched).
        feed_entry: Raw RSS/Atom feed entry data (if extracting from feed).
        source_type: Type of source ('html', 'rss', 'atom').
        source_language: Expected source language code (default 'ru').
    """
    source_url: str
    raw_html: Optional[str] = None
    feed_entry: Optional[dict] = None
    source_type: str = "html"
    source_language: str = "ru"


@dataclass
class ExtractionResult:
    """
    Result of an article extraction operation.

    Attributes:
        title: Extracted article title.
        content: Extracted article body content (HTML or plain text).
        excerpt: Short summary or excerpt of the article.
        author: Author name if available.
        published_at: Publication date string if available.
        tags: List of extracted tags/labels.
        hubs: List of extracted hub/category names.
        image_urls: List of image URLs found in the article.
        provider_name: Name of the provider that produced this result.
        latency_ms: Time taken for the extraction in milliseconds.
        error: Optional error message if the extraction partially failed.
        metadata: Additional provider-specific metadata.
    """
    title: str = ""
    content: str = ""
    excerpt: str = ""
    author: Optional[str] = None
    published_at: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    hubs: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    provider_name: str = ""
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseExtractionProvider(ABC):
    """
    Abstract base class for article extraction providers.

    All extraction providers (HTML parser, RSS feed reader, etc.) must
    inherit from this class and implement the extract and health_check methods.

    Subclasses should handle their own HTTP client initialization,
    HTML parsing, retry logic, and error handling.

    Attributes:
        name: Human-readable provider name (e.g., 'html_extractor', 'rss_extractor').
    """

    def __init__(self, **kwargs) -> None:
        """
        Initialize the extraction provider.

        Args:
            **kwargs: Additional provider-specific configuration
                      (timeout, max_retries, user_agent, etc.).
        """
        self.name: str = self.__class__.__name__.lower().replace("provider", "")
        self._extra_config: dict = kwargs

    @abstractmethod
    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """
        Extract article data from the given source.

        Depending on the source_type, this may fetch and parse HTML,
        parse an RSS/Atom feed entry, or process pre-fetched content.

        Args:
            request: ExtractionRequest containing the source URL and options.

        Returns:
            ExtractionResult with the extracted article data and metadata.

        Raises:
            ExtractionError: If the extraction fails after retries.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the extraction provider is functional.

        For HTML-based providers, this may verify that the HTTP client
        can reach the target domain. For feed-based providers, it may
        verify feed parsing capabilities.

        Returns:
            True if the provider is healthy and ready to accept requests.
        """
        ...


class ExtractionError(Exception):
    """
    Exception raised when an extraction operation fails.

    Attributes:
        message: Human-readable error description.
        provider: Name of the provider that failed.
        retryable: Whether this error is transient and can be retried.
    """

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        retryable: bool = True,
    ) -> None:
        """
        Initialize an ExtractionError.

        Args:
            message: Human-readable error description.
            provider: Name of the provider that failed.
            retryable: Whether this error is transient and can be retried.
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable
