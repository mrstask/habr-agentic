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

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from a URL."""
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    def _parse_html(self, html: str, source_url: str) -> ExtractionResult:
        """
        Parse HTML and extract article data.

        Args:
            html: Raw HTML content.
            source_url: The source URL for resolving relative image URLs.

        Returns:
            ExtractionResult with extracted data.
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title = self._extract_title(soup)

        # Extract content
        content = self._extract_content(soup)

        # Extract excerpt
        excerpt = self._extract_excerpt(soup, content)

        # Extract metadata
        author = self._extract_author(soup)
        published_at = self._extract_published_at(soup)
        tags = self._extract_tags(soup)
        hubs = self._extract_hubs(soup)

        # Extract image URLs
        image_urls = self._extract_images(soup, source_url)

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

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract the article title from the HTML."""
        # Try Habr-specific selectors first
        title_el = soup.find("h1", class_="tm-article-snippet__title")
        if title_el:
            return title_el.get_text(strip=True)

        # Try og:title meta tag
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # Try standard h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Fallback to <title> tag
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract the article body content from the HTML."""
        # Try Habr-specific content container
        content_el = soup.find("div", class_="tm-article-body")
        if content_el:
            return str(content_el)

        # Try article tag
        article = soup.find("article")
        if article:
            return str(article)

        # Try main content area
        main = soup.find("main")
        if main:
            return str(main)

        # Fallback: return body content
        body = soup.find("body")
        if body:
            return str(body)

        return ""

    def _extract_excerpt(self, soup: BeautifulSoup, content: str) -> str:
        """Extract a short excerpt/summary of the article."""
        # Try meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"].strip()

        # Try og:description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            return og_desc["content"].strip()

        # Generate excerpt from content (first 300 chars of text)
        if content:
            text = BeautifulSoup(content, "lxml").get_text(strip=True)
            if len(text) > 300:
                return text[:300].rsplit(" ", 1)[0] + "..."
            return text

        return ""

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the author name from the HTML."""
        # Try Habr-specific author selector
        author_el = soup.find("a", class_="tm-user-info__username")
        if author_el:
            return author_el.get_text(strip=True)

        # Try meta author
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            return meta_author["content"].strip()

        # Try article author
        author_tag = soup.find("span", class_="post__author")
        if author_tag:
            return author_tag.get_text(strip=True)

        return None

    def _extract_published_at(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the publication date from the HTML."""
        # Try time element with datetime attribute
        time_el = soup.find("time", attrs={"datetime": True})
        if time_el:
            return time_el.get("datetime")

        # Try meta article:published_time
        meta_pub = soup.find("meta", property="article:published_time")
        if meta_pub and meta_pub.get("content"):
            return meta_pub["content"].strip()

        # Try meta date
        meta_date = soup.find("meta", attrs={"name": "date"})
        if meta_date and meta_date.get("content"):
            return meta_date["content"].strip()

        return None

    def _extract_tags(self, soup: BeautifulSoup) -> list[str]:
        """Extract tags/labels from the HTML."""
        tags: list[str] = []

        # Try Habr-specific tag links
        tag_links = soup.find_all("a", class_="tm-article-tags__post")
        for link in tag_links:
            tag_text = link.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)

        # Try generic tag links
        if not tags:
            tag_links = soup.find_all("a", class_=lambda c: c and "tag" in c.lower())
            for link in tag_links:
                tag_text = link.get_text(strip=True)
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)

        return tags

    def _extract_hubs(self, soup: BeautifulSoup) -> list[str]:
        """Extract hub/category names from the HTML."""
        hubs: list[str] = []

        # Try Habr-specific hub links
        hub_links = soup.find_all("a", class_="tm-article-hub")
        for link in hub_links:
            hub_text = link.get_text(strip=True)
            if hub_text:
                hubs.append(hub_text)

        # Try meta article:section
        if not hubs:
            meta_section = soup.find("meta", property="article:section")
            if meta_section and meta_section.get("content"):
                hubs.append(meta_section["content"].strip())

        return hubs

    def _extract_images(self, soup: BeautifulSoup, source_url: str) -> list[str]:
        """Extract image URLs from the HTML page."""
        image_urls: list[str] = []

        # Try og:image first
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"].strip()
            if img_url:
                image_urls.append(urljoin(source_url, img_url))

        # Extract all img src attributes
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                full_url = urljoin(source_url, src)
                if full_url not in image_urls:
                    image_urls.append(full_url)

        return image_urls

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

        for attempt in range(self.max_retries):
            try:
                # If raw_html not provided, fetch via HTTP GET
                html = request.raw_html
                if not html:
                    html = await self._fetch_html(request.source_url)

                # Parse HTML to extract title, content, excerpt, metadata, images
                result = self._parse_html(html, request.source_url)

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
            message=f"HTML extraction failed after {self.max_retries} attempts: {str(last_error)}",
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
            client = await self._get_client()
            response = await client.head("https://habr.com", timeout=10.0)
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
