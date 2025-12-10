"""Queue API routes for managing read queue status."""

import logging
import os
import re
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from ..models.queue import ContentType, QueuePriority, QueueStatus
from ..services.github_service import GitHubService
from ..services.obsidian_service import ObsidianService
from ..services.page_fetcher import fetch_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queue", tags=["queue"])

# Folder for queue items
QUEUE_FOLDER = "ReadQueue"

# Content type detection patterns
CONTENT_TYPE_PATTERNS = {
    ContentType.VIDEO: [
        r"youtube\.com/watch",
        r"youtu\.be/",
        r"vimeo\.com/",
        r"twitch\.tv/",
    ],
    ContentType.TWEET: [
        r"twitter\.com/.+/status/",
        r"x\.com/.+/status/",
    ],
    ContentType.PDF: [
        r"\.pdf$",
        r"\.pdf\?",
    ],
    ContentType.DOC: [
        r"docs\.google\.com/",
        r"notion\.so/",
        r"dropbox\.com/.*\.(docx?|xlsx?|pptx?)",
    ],
    ContentType.PODCAST: [
        r"podcasts\.apple\.com/",
        r"spotify\.com/episode/",
        r"overcast\.fm/",
        r"pocketcasts\.com/",
    ],
}

# Default reading times by content type (minutes)
DEFAULT_READ_TIMES = {
    ContentType.TWEET: 1,
    ContentType.ARTICLE: 5,
    ContentType.VIDEO: 10,
    ContentType.PDF: 10,
    ContentType.DOC: 5,
    ContentType.PODCAST: 30,
    ContentType.OTHER: 5,
}

SNACK_THRESHOLD = 2


class ConsumeRequest(BaseModel):
    """Request to mark a bookmark as consumed."""

    notes: str | None = None  # Optional takeaways/notes


class ConsumeResponse(BaseModel):
    """Response from consuming a bookmark."""

    success: bool
    bookmark_id: str
    status: QueueStatus
    consumed_at: str | None = None
    error: str | None = None


class StatusUpdateRequest(BaseModel):
    """Request to update queue status."""

    status: QueueStatus


class QueueAddRequest(BaseModel):
    """Request to add item to read queue."""

    url: HttpUrl
    title: str | None = None
    meta_description: str | None = None
    priority: QueuePriority = QueuePriority.NORMAL
    notes: str | None = None


class QueueAddResponse(BaseModel):
    """Response from adding to queue."""

    success: bool
    queue_id: str
    title: str
    url: str
    content_type: ContentType
    estimated_time: int
    priority: QueuePriority
    is_snack: bool
    error: str | None = None


def _detect_content_type(url: str) -> ContentType:
    """Detect content type from URL patterns."""
    for content_type, patterns in CONTENT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return content_type
    return ContentType.ARTICLE


def _estimate_read_time(content_type: ContentType, description: str | None = None) -> int:
    """Estimate reading time in minutes."""
    if description and content_type == ContentType.ARTICLE:
        desc_words = len(description.split())
        estimated_total = desc_words * 10
        return max(1, estimated_total // 200)
    return DEFAULT_READ_TIMES.get(content_type, 5)


def _generate_queue_id(title: str, date_str: str) -> str:
    """Generate a safe queue item ID from title and date."""
    safe_title = re.sub(r"[^\w\s-]", "", title.lower())
    safe_title = re.sub(r"[\s_]+", "-", safe_title)
    safe_title = re.sub(r"-+", "-", safe_title).strip("-")
    safe_title = safe_title[:50]
    return f"{date_str}-{safe_title}"


def _build_queue_file(
    title: str,
    url: str,
    date_str: str,
    content_type: ContentType,
    estimated_time: int,
    priority: QueuePriority,
    notes: str | None,
    description: str | None,
    og_image: str | None,
) -> str:
    """Build markdown content for queue item file."""
    safe_title = title.replace('"', "'")

    lines = [
        "---",
        f'title: "{safe_title}"',
        f"url: {url}",
        f"created: {date_str}",
        f"content_type: {content_type.value}",
        f"estimated_time: {estimated_time}",
        "queue_status: unread",
        f"priority: {priority.value}",
        f"added_to_queue: {date_str}",
        f"last_touched: {date_str}",
        "consumed_at:",
        "---",
        "",
        f"# {title}",
        "",
        "## Source",
        url,
        "",
    ]

    if og_image:
        lines.extend([
            "## Preview",
            f"![preview]({og_image})",
            "",
        ])

    lines.extend([
        "## Summary",
        description or "*No description available*",
        "",
        "## Notes",
        notes or "",
        "",
    ])

    return "\n".join(lines)


@lru_cache(maxsize=1)
def _get_github_service() -> GitHubService:
    """Get or create GitHubService singleton."""
    repo = os.environ.get("OBSIDIAN_VAULT_REPO", "")
    branch = os.environ.get("OBSIDIAN_VAULT_BRANCH", "main")
    secret_arn = os.environ.get("GITHUB_PAT_SECRET_ARN", "")

    if not repo:
        raise ValueError("OBSIDIAN_VAULT_REPO environment variable not set")
    if not secret_arn:
        raise ValueError("GITHUB_PAT_SECRET_ARN environment variable not set")

    return GitHubService(
        repo_name=repo,
        branch=branch,
        secret_arn=secret_arn,
    )


def _update_frontmatter_field(content: str, field: str, value: str) -> str:
    """Update a single frontmatter field in markdown content.

    Args:
        content: Full markdown file content
        field: Field name to update
        value: New value for the field

    Returns:
        Updated markdown content
    """
    # Match the field in frontmatter
    pattern = rf"^({field}:).*$"
    replacement = rf"\1 {value}"

    # Only match within frontmatter (between --- markers)
    lines = content.split("\n")
    in_frontmatter = False
    result_lines = []

    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            result_lines.append(line)
            continue

        if in_frontmatter:
            if re.match(rf"^{field}:", line):
                line = f"{field}: {value}"
        result_lines.append(line)

    return "\n".join(result_lines)


@router.post("/add", response_model=QueueAddResponse)
async def add_to_queue(request: QueueAddRequest) -> QueueAddResponse:
    """Add an item to the read queue.

    Creates a new file in ReadQueue/ folder with queue tracking fields.
    Detects content type and estimates reading time.
    """
    url = str(request.url)
    tz = ZoneInfo("America/New_York")
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")

    try:
        github = _get_github_service()

        # Get metadata (from client or fetch)
        if request.title and request.meta_description:
            title = request.title
            description = request.meta_description
            og_image = None
        else:
            try:
                metadata = await fetch_metadata(url)
                title = request.title or metadata.best_title or url
                description = request.meta_description or metadata.best_description
                og_image = metadata.og_image
            except Exception as e:
                logger.warning(f"Failed to fetch metadata: {e}")
                title = request.title or url
                description = request.meta_description
                og_image = None

        # Detect content type and estimate time
        content_type = _detect_content_type(url)
        estimated_time = _estimate_read_time(content_type, description)

        # Determine priority (snacks auto-detected)
        is_snack = estimated_time <= SNACK_THRESHOLD
        priority = QueuePriority.SNACK if is_snack else request.priority

        # Generate ID and build file
        queue_id = _generate_queue_id(title, date_str)
        queue_path = f"{QUEUE_FOLDER}/{queue_id}.md"
        queue_content = _build_queue_file(
            title=title,
            url=url,
            date_str=date_str,
            content_type=content_type,
            estimated_time=estimated_time,
            priority=priority,
            notes=request.notes,
            description=description,
            og_image=og_image,
        )

        # Check if file exists (for updates)
        existing = github.get_file_content(queue_path)
        existing_sha = existing[1] if existing else None

        github.update_file(
            path=queue_path,
            content=queue_content,
            message=f"{'Update' if existing_sha else 'Add to'} read queue: {title[:50]}",
            sha=existing_sha,
        )

        return QueueAddResponse(
            success=True,
            queue_id=queue_id,
            title=title,
            url=url,
            content_type=content_type,
            estimated_time=estimated_time,
            priority=priority,
            is_snack=is_snack,
        )

    except Exception as e:
        logger.exception(f"Failed to add to queue: {url}")
        return QueueAddResponse(
            success=False,
            queue_id="",
            title=request.title or url,
            url=url,
            content_type=ContentType.ARTICLE,
            estimated_time=5,
            priority=request.priority,
            is_snack=False,
            error=str(e),
        )


@router.patch("/{item_id}/consume", response_model=ConsumeResponse)
async def consume_item(
    item_id: str,
    request: ConsumeRequest | None = None,
) -> ConsumeResponse:
    """Mark a queue item as consumed.

    Updates the file's frontmatter:
    - queue_status → consumed
    - consumed_at → current timestamp
    - Optionally adds notes if provided

    Looks in ReadQueue/ folder first, then Bookmarks/.
    """
    try:
        github = _get_github_service()
        tz = ZoneInfo("America/New_York")
        now = datetime.now(tz)
        consumed_at = now.strftime("%Y-%m-%d %H:%M")

        # Try ReadQueue first, then Bookmarks
        item_path = f"{QUEUE_FOLDER}/{item_id}.md"
        file_result = github.get_file_content(item_path)

        if not file_result:
            # Fallback to Bookmarks folder
            item_path = f"Bookmarks/{item_id}.md"
            file_result = github.get_file_content(item_path)

        if not file_result:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")

        content, sha = file_result

        # Update frontmatter fields
        content = _update_frontmatter_field(content, "queue_status", "consumed")
        content = _update_frontmatter_field(content, "consumed_at", consumed_at)
        content = _update_frontmatter_field(content, "last_touched", now.strftime("%Y-%m-%d"))

        # Add notes if provided
        if request and request.notes:
            # Find the Notes section and append
            if "## Notes" in content:
                content = content.replace(
                    "## Notes\n",
                    f"## Notes\n{request.notes}\n",
                )
            else:
                # Add notes section before Related
                content = content.replace(
                    "## Related",
                    f"## Notes\n{request.notes}\n\n## Related",
                )

        # Update file
        github.update_file(
            path=item_path,
            content=content,
            message=f"Mark consumed: {item_id}",
            sha=sha,
        )

        return ConsumeResponse(
            success=True,
            bookmark_id=item_id,
            status=QueueStatus.CONSUMED,
            consumed_at=consumed_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error consuming item: {item_id}")
        return ConsumeResponse(
            success=False,
            bookmark_id=item_id,
            status=QueueStatus.UNREAD,
            error=str(e),
        )


@router.patch("/{item_id}/status", response_model=ConsumeResponse)
async def update_status(
    item_id: str,
    request: StatusUpdateRequest,
) -> ConsumeResponse:
    """Update queue status for an item.

    Useful for marking as 'reading' or 'archived'.
    Looks in ReadQueue/ folder first, then Bookmarks/.
    """
    try:
        github = _get_github_service()
        tz = ZoneInfo("America/New_York")
        now = datetime.now(tz)

        # Try ReadQueue first, then Bookmarks
        item_path = f"{QUEUE_FOLDER}/{item_id}.md"
        file_result = github.get_file_content(item_path)

        if not file_result:
            item_path = f"Bookmarks/{item_id}.md"
            file_result = github.get_file_content(item_path)

        if not file_result:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")

        content, sha = file_result

        # Update frontmatter fields
        content = _update_frontmatter_field(content, "queue_status", request.status.value)
        content = _update_frontmatter_field(content, "last_touched", now.strftime("%Y-%m-%d"))

        # If marking as consumed, also set consumed_at
        consumed_at = None
        if request.status == QueueStatus.CONSUMED:
            consumed_at = now.strftime("%Y-%m-%d %H:%M")
            content = _update_frontmatter_field(content, "consumed_at", consumed_at)

        # Update file
        github.update_file(
            path=item_path,
            content=content,
            message=f"Update status to {request.status.value}: {item_id}",
            sha=sha,
        )

        return ConsumeResponse(
            success=True,
            bookmark_id=item_id,
            status=request.status,
            consumed_at=consumed_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating item status: {item_id}")
        return ConsumeResponse(
            success=False,
            bookmark_id=item_id,
            status=QueueStatus.UNREAD,
            error=str(e),
        )
