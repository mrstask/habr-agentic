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

import re
import time
from typing import Optional
from xml.etree import ElementTree

import httpx

from app.etl.extraction.base import (
    BaseExtractionProvider,
    ExtractionRequest,
    ExtractionResult,
    ExtractionError,
)

# XML namespaces commonly used in RSS/Atom feeds
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "media": "http://search.yahoo.com/mrss/",
}


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

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def _fetch_feed(self, url: str) -> str:
        """Fetch RSS/Atom feed content from a URL."""
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    def _detect_feed_type(self, xml: str) -> str:
        """Detect whether the feed is RSS or Atom."""
        if "<feed" in xml and "xmlns" in xml:
            return "atom"
        return "rss"

    def _parse_rss_entry(self, item: ElementTree.Element) -> ExtractionResult:
        """Parse a single RSS <item> element."""
        def find_text(tag: str) -> Optional[str]:
            el = item.find(tag)
            if el is not None and el.text:
                return el.text.strip()
            return None

        def find_text_ns(tag: str) -> Optional[str]:
            """Search with common namespaces."""
            for prefix, uri in NAMESPACES.items():
                el = item.find(f"{{{uri}}}{tag}")
                if el is not None and el.text:
                    return el.text.strip()
            return None

        # Title
        title = find_text("title") or ""

        # Content — try content:encoded first, then description
        content = find_text_ns("encoded") or find_text("description") or ""

        # Excerpt — use description if content is encoded, or truncate content
        excerpt = ""
        if content:
            # Strip HTML tags for excerpt
            plain = ElementTree.fromstring(f"<root>{content}</root>").text if "<" in content else content
            if plain and len(plain) > 300:
                excerpt = plain[:300].rsplit(" ", 1)[0] + "..."
            elif plain:
                excerpt = plain

        # Author
        author = find_text("author") or find_text_ns("creator")

        # Published date
        published_at = find_text("pubDate") or find_text_ns("date")

        # Categories → tags
        tags: list[str] = []
        for cat in item.findall("category"):
            if cat.text and cat.text.strip():
                tags.append(cat.text.strip())

        # Hubs — not typically in RSS, leave empty
        hubs: list[str] = []

        # Image URLs — try media:content, media:thumbnail, enclosure
        image_urls: list[str] = []

        # media:content
        for media_el in item.findall(f"{{{NAMESPACES['media']}}}content"):
            url = media_el.get("url")
            if url and url not in image_urls:
                image_urls.append(url)

        # media:thumbnail
        for media_el in item.findall(f"{{{NAMESPACES['media']}}}thumbnail"):
            url = media_el.get("url")
            if url and url not in image_urls:
                image_urls.append(url)

        # enclosure
        enclosure = item.find("enclosure")
        if enclosure is not None:
            url = enclosure.get("url")
            if url and url not in image_urls:
                image_urls.append(url)

        # Try to find img tags in content/description
        if content and "<img" in content:
            img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']')
            for match in img_pattern.finditer(content):
                img_url = match.group(1)
                if img_url not in image_urls:
                    image_urls.append(img_url)

        return ExtractionResult(
            title=title,
            content=content,
            excerpt=excerpt,
            author=author,
            published_at=published_at,
            tags=tags,
            hubs=hubs,
            image_urls=image_urls,
            provider_name=self.name,
        )

    def _parse_atom_entry(self, entry: ElementTree.Element) -> ExtractionResult:
        """Parse a single Atom <entry> element."""
        def find_text(tag: str) -> Optional[str]:
            el = entry.find(tag)
            if el is not None and el.text:
                return el.text.strip()
            return None

        def find_text_ns(tag: str) -> Optional[str]:
            for prefix, uri in NAMESPACES.items():
                el = entry.find(f"{{{uri}}}{tag}")
                if el is not None and el.text:
                    return el.text.strip()
            return None

        # Title
        title = find_text("title") or ""

        # Content — try content first, then summary
        content = find_text("content") or find_text("summary") or ""

        # Excerpt
        excerpt = ""
        if content:
            plain = ElementTree.fromstring(f"<root>{content}</root>").text if "<" in content else content
            if plain and len(plain) > 300:
                excerpt = plain[:300].rsplit(" ", 1)[0] + "..."
            elif plain:
                excerpt = plain

        # Author
        author_el = entry.find("author")
        author = None
        if author_el is not None:
            name_el = author_el.find("name")
            if name_el is not None and name_el.text:
                author = name_el.text.strip()

        # Published date
        published_at = find_text("published") or find_text("updated")

        # Categories → tags
        tags: list[str] = []
        for cat in entry.findall("category"):
            term = cat.get("term") or cat.get("label")
            if term:
                tags.append(term)

        # Hubs
        hubs: list[str] = []

        # Image URLs — try media:content, media:thumbnail, link with rel=enclosure
        image_urls: list[str] = []

        for media_el in entry.findall(f"{{{NAMESPACES['media']}}}content"):
            url = media_el.get("url")
            if url and url not in image_urls:
                image_urls.append(url)

        for media_el in entry.findall(f"{{{NAMESPACES['media']}}}thumbnail"):
            url = media_el.get("url")
            if url and url not in image_urls:
                image_urls.append(url)

        # Try to find img tags in content
        if content and "<img" in content:
            img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']')
            for match in img_pattern.finditer(content):
                img_url = match.group(1)
                if img_url not in image_urls:
                    image_urls.append(img_url)

        return ExtractionResult(
            title=title,
            content=content,
            excerpt=excerpt,
            author=author,
            published_at=published_at,
            tags=tags,
            hubs=hubs,
            image_urls=image_urls,
            provider_name=self.name,
        )

    def _parse_feed_xml(self, xml: str, source_type: str) -> ExtractionResult:
        """
        Parse RSS/Atom XML and extract the first entry.

        Args:
            xml: Raw XML string.
            source_type: 'rss' or 'atom'.

        Returns:
            ExtractionResult from the first feed entry.
        """
        root = ElementTree.fromstring(xml)

        if source_type == "atom" or self._detect_feed_type(xml) == "atom":
            # Atom feed
            entry = root.find("atom:entry", NAMESPACES) or root.find("{http://www.w3.org/2005/Atom}entry")
            if entry is not None:
                return self._parse_atom_entry(entry)
        else:
            # RSS feed
            channel = root.find("channel")
            if channel is not None:
                item = channel.find("item")
                if item is not None:
                    return self._parse_rss_entry(item)

        return ExtractionResult(
            provider_name=self.name,
            error="No entries found in feed",
        )

    def _parse_feed_entry_dict(self, entry_data: dict) -> ExtractionResult:
        """
        Parse a pre-fetched feed entry dictionary.

        Args:
            entry_data: Dictionary with feed entry fields.

        Returns:
            ExtractionResult from the entry data.
        """
        title = entry_data.get("title", "")
        content = entry_data.get("content", "") or entry_data.get("description", "") or ""
        excerpt = entry_data.get("excerpt", "")
        author = entry_data.get("author")
        published_at = entry_data.get("published_at")
        tags = entry_data.get("tags", [])
        hubs = entry_data.get("hubs", [])
        image_urls = entry_data.get("image_urls", [])

        # Generate excerpt if not provided
        if not excerpt and content:
            plain = content
            if "<" in plain:
                try:
                    plain = ElementTree.fromstring(f"<root>{content}</root>").text or ""
                except ElementTree.ParseError:
                    plain = re.sub(r"<[^>]+>", "", content)
            if len(plain) > 300:
                excerpt = plain[:300].rsplit(" ", 1)[0] + "..."
            else:
                excerpt = plain

        return ExtractionResult(
            title=title,
            content=content,
            excerpt=excerpt,
            author=author,
            published_at=published_at,
            tags=tags,
            hubs=hubs,
            image_urls=image_urls,
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

        for attempt in range(self.max_retries):
            try:
                # If feed_entry provided, parse it directly
                if request.feed_entry:
                    result = self._parse_feed_entry_dict(request.feed_entry)
                    result.latency_ms = (time.monotonic() - start_time) * 1000
                    return result

                # Otherwise fetch feed from source_url via HTTP GET
                xml = await self._fetch_feed(request.source_url)

                # Parse RSS/Atom XML to extract title, content, excerpt
                result = self._parse_feed_xml(xml, request.source_type)

                # Calculate latency
                result.latency_ms = (time.monotonic() - start_time) * 1000

                return result

            except Exception as e:
                last_error = e
                # Don't retry on the last attempt
                if attempt >= self.max_retries - 1:
                    break
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    break

        # All retries exhausted
        raise ExtractionError(
            message=f"RSS extraction failed after {self.max_retries} attempts: {str(last_error)}",
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
            client = await self._get_client()
            response = await client.get("https://habr.com/rss/", timeout=10.0)
            response.raise_for_status()
            # Attempt to parse the response as RSS/Atom XML
            ElementTree.fromstring(response.text)
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
        if any(pattern in error_str for pattern in ["timeout", "timed out"]):
            return True

        # Check for connection errors
        if any(pattern in error_str for pattern in ["connection", "refused", "reset"]):
            return True

        # Check for HTTP 5xx status codes
        if any(pattern in error_str for pattern in [
            "500", "502", "503", "504",
            "internal server error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        ]):
            return True

        # Check for rate limiting (429)
        if any(pattern in error_str for pattern in ["429", "too many requests", "rate limit"]):
            return True

        return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
