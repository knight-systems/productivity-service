"""Service for fetching and parsing webpage content."""

import logging
import re
from html import unescape

import httpx
from bs4 import BeautifulSoup

from ..models.bookmark import PageContent, PageMetadata

logger = logging.getLogger(__name__)

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 10.0

# User agent to avoid being blocked
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def fetch_metadata(url: str, timeout: float = DEFAULT_TIMEOUT) -> PageMetadata:
    """Fetch metadata from a webpage (title, description, og tags).

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        PageMetadata with extracted information
    """
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract title
    title = None
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = unescape(title_tag.string.strip())

    # Extract meta description
    description = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = unescape(meta_desc["content"].strip())

    # Extract Open Graph tags
    og_title = _get_meta_content(soup, "og:title")
    og_description = _get_meta_content(soup, "og:description")
    og_image = _get_meta_content(soup, "og:image")

    return PageMetadata(
        url=str(response.url),  # Use final URL after redirects
        title=title,
        description=description,
        og_title=og_title,
        og_description=og_description,
        og_image=og_image,
    )


async def fetch_full_content(url: str, timeout: float = DEFAULT_TIMEOUT) -> PageContent:
    """Fetch full page content for AI processing.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        PageContent with cleaned text content
    """
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract title
    title = None
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = unescape(title_tag.string.strip())

    # Remove script, style, nav, header, footer elements
    for element in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
        element.decompose()

    # Try to find main content area
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find(attrs={"id": "content"})
        or soup.find(attrs={"class": "content"})
        or soup.body
    )

    if main_content:
        text = main_content.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    text = _clean_text(text)

    # Truncate to avoid token limits (roughly 10k chars ~ 2.5k tokens)
    max_chars = 10000
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    return PageContent(
        url=str(response.url),
        title=title,
        text_content=text,
    )


def is_quality_metadata(meta: PageMetadata) -> bool:
    """Check if metadata is good enough to skip full fetch.

    Args:
        meta: PageMetadata to evaluate

    Returns:
        True if metadata is sufficient quality
    """
    title = meta.best_title
    description = meta.best_description

    # Must have a title of reasonable length
    if not title or len(title) < 10:
        return False

    # Should have some description
    if not description or len(description) < 20:
        return False

    return True


def _get_meta_content(soup: BeautifulSoup, property_name: str) -> str | None:
    """Extract content from a meta tag by property name."""
    tag = soup.find("meta", attrs={"property": property_name})
    if tag and tag.get("content"):
        return unescape(tag["content"].strip())
    return None


def _clean_text(text: str) -> str:
    """Clean up extracted text content."""
    # Replace multiple newlines with double newline
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Replace multiple spaces with single space
    text = re.sub(r" {2,}", " ", text)
    # Remove leading/trailing whitespace from lines
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines)
