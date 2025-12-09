"""Bookmark service for saving and enriching bookmarks."""

import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3

from ..config import settings
from ..models.bookmark import (
    AIEnrichment,
    BookmarkMode,
    BookmarkSaveRequest,
    BookmarkSaveResponse,
    PageMetadata,
)
from .github_service import GitHubService
from .obsidian_service import ObsidianService
from .page_fetcher import fetch_full_content, fetch_metadata, is_quality_metadata

logger = logging.getLogger(__name__)

# Bookmark file path in vault
BOOKMARKS_FOLDER = "Bookmarks"


class BookmarkService:
    """Service for saving bookmarks to Obsidian vault."""

    def __init__(
        self,
        obsidian_service: ObsidianService,
        github_service: GitHubService,
        timezone_str: str = "America/New_York",
    ):
        """Initialize bookmark service.

        Args:
            obsidian_service: ObsidianService for daily note operations
            github_service: GitHubService for file operations
            timezone_str: Timezone for timestamps
        """
        self.obsidian = obsidian_service
        self.github = github_service
        self.tz = ZoneInfo(timezone_str)

    async def save_bookmark(self, request: BookmarkSaveRequest) -> BookmarkSaveResponse:
        """Save a bookmark to daily note and permanent file.

        Args:
            request: BookmarkSaveRequest with URL and options

        Returns:
            BookmarkSaveResponse with result details
        """
        url = str(request.url)
        today = datetime.now(self.tz)
        date_str = today.strftime("%Y-%m-%d")

        try:
            # Step 1: Fetch metadata
            logger.info(f"Fetching metadata for {url}")
            metadata = await fetch_metadata(url)

            # Determine title (user override > og:title > title)
            title = request.title or metadata.best_title or _extract_title_from_url(url)

            # Step 2: Determine enrichment level
            # - quick: No AI, just meta tags
            # - auto: AI tags from meta description (no full fetch), meta summary
            # - rich: Full page fetch + AI summary + tags
            summary: str | None = None
            auto_tags: list[str] = []
            category: str | None = None

            if request.mode == BookmarkMode.QUICK:
                # Quick mode: just use meta description, no AI
                summary = metadata.best_description

            elif request.mode == BookmarkMode.AUTO:
                # Auto mode: generate tags from title + meta description (fast)
                summary = metadata.best_description
                try:
                    meta_content = f"{title}\n\n{metadata.best_description or ''}"
                    enrichment = self._get_ai_tags(meta_content)
                    auto_tags = enrichment.tags
                    category = enrichment.category
                except Exception as e:
                    logger.warning(f"Failed to generate tags: {e}")

            else:
                # Rich mode: full fetch + AI summary + tags
                logger.info(f"Fetching full content for AI enrichment: {url}")
                try:
                    content = await fetch_full_content(url)
                    enrichment = self._get_ai_enrichment(content.text_content, title)
                    summary = enrichment.summary
                    auto_tags = enrichment.tags
                    category = enrichment.category
                except Exception as e:
                    logger.warning(f"Failed to enrich bookmark: {e}")
                    summary = metadata.best_description

            # Combine user tags with auto-generated tags
            all_tags = list(request.tags) + auto_tags
            all_tags = list(dict.fromkeys(all_tags))  # Dedupe while preserving order

            # Step 3: Append to daily note
            logger.info("Appending to daily note")
            daily_entry = f"[{title}]({url})"
            if request.notes:
                daily_entry += f" - {request.notes}"

            self.obsidian.append_to_daily_note(
                heading="Bookmarks",
                content=daily_entry,
                timestamp=True,
            )

            # Step 4: Create or update permanent bookmark file
            bookmark_id = _generate_bookmark_id(title, date_str)
            bookmark_path = f"{BOOKMARKS_FOLDER}/{bookmark_id}.md"
            bookmark_content = _build_bookmark_file(
                title=title,
                url=url,
                tags=all_tags,
                category=category,
                date_str=date_str,
                summary=summary,
                notes=request.notes,
                og_image=metadata.og_image,
            )

            # Check if file already exists (for updates)
            existing = self.github.get_file_content(bookmark_path)
            existing_sha = existing[1] if existing else None

            logger.info(f"{'Updating' if existing_sha else 'Creating'} bookmark file: {bookmark_path}")
            self.github.update_file(
                path=bookmark_path,
                content=bookmark_content,
                message=f"{'Update' if existing_sha else 'Add'} bookmark: {title[:50]}",
                sha=existing_sha,
            )

            return BookmarkSaveResponse(
                success=True,
                bookmark_id=bookmark_id,
                title=title,
                status="complete",
                daily_note_updated=True,
                bookmark_file_path=bookmark_path,
                summary=summary,
                tags=all_tags,
            )

        except Exception as e:
            logger.exception(f"Failed to save bookmark: {url}")
            return BookmarkSaveResponse(
                success=False,
                bookmark_id="",
                title=request.title or url,
                status="failed",
                daily_note_updated=False,
                bookmark_file_path="",
                error=str(e),
            )

    def _get_ai_enrichment(self, content: str, title: str) -> AIEnrichment:
        """Get AI-generated summary and tags for content.

        Args:
            content: Page text content
            title: Page title

        Returns:
            AIEnrichment with summary, tags, and category
        """
        prompt = f"""Analyze this webpage and return JSON with exactly these fields:
{{
  "summary": "2-3 sentence summary of the content",
  "tags": ["tag1", "tag2", "tag3"],
  "category": "category"
}}

Rules:
- summary: Concise, informative summary (2-3 sentences max)
- tags: 3-5 relevant tags in kebab-case (e.g., "machine-learning", "web-dev")
- category: One of: tech, reference, article, tool, tutorial, news, personal, business, design, other

Title: {title}

Content:
{content[:6000]}

Return ONLY valid JSON, no explanation."""

        try:
            client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

            response = client.invoke_model(
                modelId=settings.bedrock_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                }),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            response_text = response_body["content"][0]["text"]

            # Extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            return AIEnrichment(
                summary=data.get("summary", ""),
                tags=data.get("tags", []),
                category=data.get("category", "other"),
            )

        except Exception as e:
            logger.error(f"AI enrichment failed: {e}")
            return AIEnrichment(
                summary="",
                tags=[],
                category="other",
            )

    def _get_ai_tags(self, content: str) -> AIEnrichment:
        """Get AI-generated tags from title and description (lightweight).

        Args:
            content: Title and meta description text

        Returns:
            AIEnrichment with tags and category (no summary)
        """
        prompt = f"""Generate tags for this webpage. Return JSON:
{{
  "tags": ["tag1", "tag2", "tag3"],
  "category": "category"
}}

Rules:
- tags: 3-5 relevant tags in kebab-case (e.g., "machine-learning", "web-dev")
- category: One of: tech, reference, article, tool, tutorial, news, personal, business, design, other

Content:
{content[:1000]}

Return ONLY valid JSON, no explanation."""

        try:
            client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

            response = client.invoke_model(
                modelId=settings.bedrock_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                }),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            response_text = response_body["content"][0]["text"]

            # Extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text.strip())

            return AIEnrichment(
                summary="",
                tags=data.get("tags", []),
                category=data.get("category", "other"),
            )

        except Exception as e:
            logger.error(f"AI tag generation failed: {e}")
            return AIEnrichment(
                summary="",
                tags=[],
                category="other",
            )


def _generate_bookmark_id(title: str, date_str: str) -> str:
    """Generate a safe bookmark ID from title and date.

    Args:
        title: Page title
        date_str: Date string (YYYY-MM-DD)

    Returns:
        Safe filename like "2025-12-09-example-title"
    """
    # Remove special chars, lowercase, replace spaces with dashes
    safe_title = re.sub(r"[^\w\s-]", "", title.lower())
    safe_title = re.sub(r"[\s_]+", "-", safe_title)
    safe_title = re.sub(r"-+", "-", safe_title).strip("-")

    # Truncate to reasonable length
    safe_title = safe_title[:50]

    return f"{date_str}-{safe_title}"


def _extract_title_from_url(url: str) -> str:
    """Extract a readable title from a URL as fallback.

    Args:
        url: URL string

    Returns:
        Readable title derived from URL
    """
    # Remove protocol and www
    title = re.sub(r"^https?://(www\.)?", "", url)
    # Remove trailing slash and query params
    title = re.sub(r"[?#].*$", "", title).rstrip("/")
    # Replace slashes and dashes with spaces
    title = re.sub(r"[-_/]", " ", title)
    # Capitalize words
    title = title.title()

    return title[:100]


def _build_bookmark_file(
    title: str,
    url: str,
    tags: list[str],
    category: str | None,
    date_str: str,
    summary: str | None,
    notes: str | None,
    og_image: str | None,
) -> str:
    """Build markdown content for bookmark file.

    Args:
        title: Page title
        url: Page URL
        tags: List of tags
        category: Content category
        date_str: Creation date
        summary: AI or meta summary
        notes: User notes
        og_image: Open Graph image URL

    Returns:
        Markdown file content
    """
    # Build tags list for frontmatter
    all_tags = ["bookmark"]
    if category:
        all_tags.append(category)
    all_tags.extend(tags)
    all_tags = list(dict.fromkeys(all_tags))  # Dedupe
    tags_str = ", ".join(all_tags)

    # Escape quotes in title for YAML frontmatter
    safe_title = title.replace('"', "'")

    lines = [
        "---",
        f'title: "{safe_title}"',
        f"url: {url}",
        f"tags: [{tags_str}]",
        f"created: {date_str}",
        "---",
        "",
        f"# {title}",
        "",
        "## Source",
        url,
        "",
    ]

    # Add image if available
    if og_image:
        lines.extend([
            "## Preview",
            f"![preview]({og_image})",
            "",
        ])

    lines.extend([
        "## Summary",
        summary or "*No summary available*",
        "",
        "## Notes",
        notes or "",
        "",
        "## Related",
        "",
    ])

    return "\n".join(lines)
