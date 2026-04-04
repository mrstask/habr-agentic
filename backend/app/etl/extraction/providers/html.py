"""
HTML extraction provider.

Implements the BaseExtractionProvider interface for parsing raw HTML pages
and extracting structured article data (title, content, metadata, images).

Uses an HTTP client to fetch pages and an HTML parser (e.g., BeautifulSoup)
to extract article content.

Usage::

    from app.etl.extraction.providers.html import HtmlExtractionProvider
    from app.etl.extraction.base import ExtractionRequest

    provider = HtmlExtractionProvider()
    result = await provider.extract(ExtractionRequest(source_url="https://..."))
"""

import time
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.etl.extraction.base import (
    BaseExtractionProvider,
    ExtractionRequest,
    ExtractionResult,
    ExtractionError,
)


class HtmlExtractionProvider(BaseExtractionProvider):
    """
    Extraction provider for parsing HTML pages.

    Fetches web pages via HTTP and extracts article content using
    HTML parsing libraries. Handles Habr-specific HTML structure
    for optimal extraction.

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
        Initialize the HTML extraction provider.

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

    def _parse_html(self, html: str, source_url: str) -> ExtractionResult:
        """
        Parse raw HTML and extract article data.

        Args:
            html: Raw HTML string to parse.
            source_url: The URL of the page (used for resolving relative URLs).

        Returns:
            ExtractionResult with extracted article data.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title — try Habr-specific selector first, then fallbacks
        title = ""
        habr_title = soup.select_one("h1.tm-article-snippet__title")
        if habr_title:
            title = habr_title.get_text(strip=True)
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
        if not title:
            title_tag = soup.select_one("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

        # Extract content — try Habr-specific body div
        content_div = soup.select_one("div.tm-article-body")
        if content_div:
            content = str(content_div)
        else:
            body = soup.select_one("body")
            content = str(body) if body else html

        # Extract excerpt from meta description
        excerpt = ""
        meta_desc = soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get("content"):
            excerpt = meta_desc["content"].strip()

        # Extract author
        author: Optional[str] = None
        author_el = soup.select_one("a.tm-user-info__username")
        if author_el:
            author = author_el.get_text(strip=True)
        if not author:
            meta_author = soup.select_one('meta[name="author"]')
            if meta_author and meta_author.get("content"):
                author = meta_author["content"].strip()

        # Extract published_at
        published_at: Optional[str] = None
        time_el = soup.select_one("time[datetime]")
        if time_el and time_el.get("datetime"):
            published_at = time_el["datetime"].strip()
        if not published_at:
            meta_time = soup.select_one('meta[property="article:published_time"]')
            if meta_time and meta_time.get("content"):
                published_at = meta_time["content"].strip()

        # Extract tags
        tags: list[str] = []
        for tag_el in soup.select("a.tm-article-tags__post"):
            tag_text = tag_el.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)

        # Extract hubs
        hubs: list[str] = []
        for hub_el in soup.select("a.tm-article-hub"):
            hub_text = hub_el.get_text(strip=True)
            if hub_text:
                hubs.append(hub_text)

        # Extract image URLs
        image_urls: list[str] = []
        # From og:image meta tag
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image and og_image.get("content"):
            img_url = og_image["content"].strip()
            if img_url:
                image_urls.append(urljoin(source_url, img_url))
        # From img tags
        for img in soup.select("img[src]"):
            img_url = img.get("src", "").strip()
            if img_url:
                full_url = urljoin(source_url, img_url)
                if full_url not in image_urls:
                    image_urls.append(full_url)

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
        Extract article data from an HTML page.

        Fetches the page if raw_html is not provided, then parses
        the HTML to extract title, content, metadata, and images.

        Args:
            request: ExtractionRequest with source_url and optional raw_html.

        Returns:
            ExtractionResult with the extracted article data.

        Raises:
            ExtractionError: If the extraction fails after all retries.
        """
        start_time = time.monotonic()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                raw_html = request.raw_html
                if raw_html is None:
                    client = self._get_client()
                    response = await client.get(request.source_url)
                    response.raise_for_status()
                    raw_html = response.text

                result = self._parse_html(raw_html, request.source_url)
                result.latency_ms = (time.monotonic() - start_time) * 1000
                return result

            except Exception as e:
                last_error = e
                if not self._is_retryable_error(e) or attempt == self.max_retries:
                    break

        raise ExtractionError(
            message=f"HTML extraction failed after {self.max_retries} attempts: {last_error}",
            provider=self.name,
            retryable=self._is_retryable_error(last_error) if last_error else True,
        )

    async def health_check(self) -> bool:
        """
        Check if the HTML extraction provider can reach the target domain.

        Sends a minimal HTTP request to verify connectivity.

        Returns:
            True if the provider can reach the target, False otherwise.
        """
        try:
            client = self._get_client()
            response = await client.head("https://habr.com/")
            return response.status_code < 500
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
