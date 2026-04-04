"""
RSS/Atom feed extraction provider.

Implements the BaseExtractionProvider interface for parsing RSS and Atom
feed entries and extracting structured article data.

Usage::

    from app.etl.extraction.providers.rss import RssExtractionProvider
    from app.etl.extraction.base import ExtractionRequest

    provider = RssExtractionProvider()
    result = await provider.extract(ExtractionRequest(
        source_url="https://habr.com/rss/",
        source_type="rss",
    ))
"""

import time
from typing import Optional
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from app.etl.extraction.base import (
    BaseExtractionProvider,
    ExtractionRequest,
    ExtractionResult,
    ExtractionError,
)


class RssExtractionProvider(BaseExtractionProvider):
    """
    Extraction provider for parsing RSS/Atom feeds.

    Fetches and parses RSS or Atom feed entries to extract article
    metadata and content. Can also process pre-fetched feed entry data.

    Args:
        timeout: HTTP timeout in seconds.
        max_retries: Maximum retry attempts for transient errors.
        user_agent: User-Agent header for HTTP requests.
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: str = "HabrAgenticPipeline/1.0",
    ) -> None:
        """
        Initialize the RSS/Atom extraction provider.

        Args:
            timeout: HTTP timeout in seconds.
            max_retries: Maximum retry attempts for transient errors.
            user_agent: User-Agent header for HTTP requests.
        """
        super().__init__(timeout=timeout, max_retries=max_retries, user_agent=user_agent)
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.user_agent: str = user_agent
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create an async HTTP client.

        Returns:
            An httpx.AsyncClient instance configured with timeout and headers.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client if it exists."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def _detect_feed_type(self, xml_content: str) -> str:
        """
        Detect whether the XML content is RSS or Atom.

        Args:
            xml_content: Raw XML string.

        Returns:
            'rss' or 'atom' based on the feed type.
        """
        if "<rss" in xml_content or "<channel>" in xml_content:
            return "rss"
        return "atom"

    def _parse_rss_entry(self, item: ElementTree.Element) -> ExtractionResult:
        """
        Parse an RSS item element into an ExtractionResult.

        Args:
            item: The RSS item element.

        Returns:
            ExtractionResult with extracted article data.
        """
        # Extract title
        title_el = item.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        # Extract content
        content = ""
        encoded = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
        if encoded is not None and encoded.text:
            content = encoded.text.strip()
        if not content:
            description = item.find("description")
            if description is not None and description.text:
                content = description.text.strip()

        # Extract excerpt from description
        excerpt = ""
        description = item.find("description")
        if description is not None and description.text:
            excerpt = description.text.strip()

        # Extract author
        author: Optional[str] = None
        creator = item.find("{http://purl.org/dc/elements/1.1/}creator")
        if creator is not None and creator.text:
            author = creator.text.strip()

        # Extract published_at
        published_at: Optional[str] = None
        pub_date = item.find("pubDate")
        if pub_date is not None and pub_date.text:
            published_at = pub_date.text.strip()

        # Extract tags/categories
        tags: list[str] = []
        for category in item.findall("category"):
            if category.text:
                tags.append(category.text.strip())

        # Extract image URLs from media and enclosure
        image_urls: list[str] = []
        # Media content
        media_content = item.find("{http://search.yahoo.com/mrss/}content")
        if media_content is not None and media_content.get("url"):
            image_urls.append(media_content.get("url"))
        # Enclosure
        enclosure = item.find("enclosure")
        if enclosure is not None and enclosure.get("url"):
            image_urls.append(enclosure.get("url"))

        return ExtractionResult(
            title=title,
            content=content,
            excerpt=excerpt,
            author=author,
            published_at=published_at,
            tags=tags,
            hubs=[],
            image_urls=image_urls,
            provider_name=self.name,
        )

    def _parse_atom_entry(self, entry: ElementTree.Element) -> ExtractionResult:
        """
        Parse an Atom entry element into an ExtractionResult.

        Args:
            entry: The Atom entry element.

        Returns:
            ExtractionResult with extracted article data.
        """
        # Extract title
        title_el = entry.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        # Extract content
        content = ""
        content_el = entry.find("content")
        if content_el is not None and content_el.text:
            content = content_el.text.strip()
        if not content:
            summary = entry.find("summary")
            if summary is not None and summary.text:
                content = summary.text.strip()

        # Extract excerpt from summary
        excerpt = ""
        summary = entry.find("summary")
        if summary is not None and summary.text:
            excerpt = summary.text.strip()

        # Extract author
        author: Optional[str] = None
        author_el = entry.find("author")
        if author_el is not None:
            name_el = author_el.find("name")
            if name_el is not None and name_el.text:
                author = name_el.text.strip()

        # Extract published_at
        published_at: Optional[str] = None
        published = entry.find("published")
        if published is not None and published.text:
            published_at = published.text.strip()

        # Extract tags/categories
        tags: list[str] = []
        for category in entry.findall("category"):
            term = category.get("term")
            if term:
                tags.append(term)

        # Extract image URLs from media
        image_urls: list[str] = []
        media_thumbnail = entry.find("{http://search.yahoo.com/mrss/}thumbnail")
        if media_thumbnail is not None and media_thumbnail.get("url"):
            image_urls.append(media_thumbnail.get("url"))
        media_content = entry.find("{http://search.yahoo.com/mrss/}content")
        if media_content is not None and media_content.get("url"):
            image_urls.append(media_content.get("url"))

        return ExtractionResult(
            title=title,
            content=content,
            excerpt=excerpt,
            author=author,
            published_at=published_at,
            tags=tags,
            hubs=[],
            image_urls=image_urls,
            provider_name=self.name,
        )

    def _parse_feed_xml(self, xml_content: str, feed_type: str) -> ExtractionResult:
        """
        Parse RSS or Atom XML content and extract the first entry.

        Args:
            xml_content: Raw XML string.
            feed_type: 'rss' or 'atom'.

        Returns:
            ExtractionResult with extracted article data from the first entry.
        """
        root = ElementTree.fromstring(xml_content)

        if feed_type == "rss":
            channel = root.find("channel")
            if channel is None:
                raise ExtractionError("No channel found in RSS feed", provider=self.name)
            item = channel.find("item")
            if item is None:
                raise ExtractionError("No items found in RSS feed", provider=self.name)
            return self._parse_rss_entry(item)
        else:
            # Atom feed
            entry = root.find("entry")
            if entry is None:
                raise ExtractionError("No entries found in Atom feed", provider=self.name)
            return self._parse_atom_entry(entry)

    def _parse_feed_entry_dict(self, entry_data: dict) -> ExtractionResult:
        """
        Parse a feed entry dictionary into an ExtractionResult.

        Args:
            entry_data: Dictionary containing feed entry data.

        Returns:
            ExtractionResult with extracted article data.
        """
        title = entry_data.get("title", "")
        content = entry_data.get("content", "")
        excerpt = entry_data.get("excerpt", "")

        # Generate excerpt from content if not provided
        if not excerpt and content:
            text_content = BeautifulSoup(content, "html.parser").get_text()
            excerpt = text_content[:200].strip()
            if len(text_content) > 200:
                excerpt += "..."

        return ExtractionResult(
            title=title,
            content=content,
            excerpt=excerpt,
            author=entry_data.get("author"),
            published_at=entry_data.get("published_at"),
            tags=entry_data.get("tags", []),
            hubs=entry_data.get("hubs", []),
            image_urls=entry_data.get("image_urls", []),
            provider_name=self.name,
        )

    async def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """
        Extract article data from an RSS/Atom feed entry.

        If feed_entry is provided in the request, parses it directly.
        Otherwise fetches the feed from source_url and extracts entries.

        Args:
            request: ExtractionRequest with source_url, source_type,
                     and optional feed_entry data.

        Returns:
            ExtractionResult with the extracted article data.

        Raises:
            ExtractionError: If the extraction fails after all retries.
        """
        start_time = time.monotonic()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                # If feed_entry is provided, parse it directly
                if request.feed_entry is not None:
                    result = self._parse_feed_entry_dict(request.feed_entry)
                    result.latency_ms = (time.monotonic() - start_time) * 1000
                    return result

                # Otherwise fetch the feed from source_url
                client = self._get_client()
                response = await client.get(request.source_url)
                response.raise_for_status()
                xml_content = response.text

                # Detect feed type
                feed_type = self._detect_feed_type(xml_content)
                if request.source_type in ("rss", "atom"):
                    feed_type = request.source_type

                result = self._parse_feed_xml(xml_content, feed_type)
                result.latency_ms = (time.monotonic() - start_time) * 1000
                return result

            except Exception as e:
                last_error = e
                if not self._is_retryable_error(e) or attempt == self.max_retries:
                    break

        raise ExtractionError(
            message=f"RSS extraction failed after {self.max_retries} attempts: {last_error}",
            provider=self.name,
            retryable=self._is_retryable_error(last_error) if last_error else True,
        )

    async def health_check(self) -> bool:
        """
        Check if the RSS extraction provider can reach the feed URL.

        Sends a minimal HTTP request to verify connectivity and feed parsing.

        Returns:
            True if the provider can reach and parse the feed, False otherwise.
        """
        try:
            client = self._get_client()
            response = await client.get("https://habr.com/rss/")
            response.raise_for_status()
            # Try to parse as RSS
            self._detect_feed_type(response.text)
            return True
        except Exception:
            return False

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            error: The exception that occurred.

        Returns:
            True if the error is transient and retryable.
        """
        error_str = str(error).lower()
        # Check for timeout errors
        if "timed out" in error_str or "timeout" in error_str:
            return True
        # Check for connection errors
        if "connection" in error_str:
            return True
        # Check for 5xx server errors
        if "503" in error_str or "502" in error_str or "500" in error_str:
            return True
        # Check for 429 rate limiting
        if "429" in error_str:
            return True
        return False
