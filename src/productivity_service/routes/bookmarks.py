"""Bookmark API routes for saving bookmarks to Obsidian."""

import logging
import os
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from ..models.bookmark import BookmarkSaveRequest, BookmarkSaveResponse
from ..services.bookmark_service import BookmarkService
from ..services.github_service import GitHubService
from ..services.obsidian_service import ObsidianService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@lru_cache(maxsize=1)
def _get_bookmark_service() -> BookmarkService:
    """Get or create BookmarkService singleton."""
    repo = os.environ.get("OBSIDIAN_VAULT_REPO", "")
    branch = os.environ.get("OBSIDIAN_VAULT_BRANCH", "main")
    secret_arn = os.environ.get("GITHUB_PAT_SECRET_ARN", "")

    if not repo:
        raise ValueError("OBSIDIAN_VAULT_REPO environment variable not set")
    if not secret_arn:
        raise ValueError("GITHUB_PAT_SECRET_ARN environment variable not set")

    github_service = GitHubService(
        repo_name=repo,
        branch=branch,
        secret_arn=secret_arn,
    )
    obsidian_service = ObsidianService(github_service)

    return BookmarkService(obsidian_service, github_service)


@router.post("/save", response_model=BookmarkSaveResponse)
async def save_bookmark(request: BookmarkSaveRequest) -> BookmarkSaveResponse:
    """Save a bookmark to Obsidian.

    This endpoint:
    1. Fetches page metadata (title, description, og tags)
    2. Optionally uses AI to generate summary and auto-tags
    3. Appends an entry to the daily note's Bookmarks section
    4. Creates a permanent bookmark file in Bookmarks/ folder

    **Modes:**
    - `auto` (default): Try meta tags first; escalate to AI if low quality
    - `quick`: Meta tags only, no AI processing
    - `rich`: Full page fetch + AI summary + auto-tags
    """
    try:
        service = _get_bookmark_service()
        result = await service.save_bookmark(request)

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error or "Failed to save bookmark")

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error saving bookmark")
        raise HTTPException(status_code=500, detail=f"Failed to save bookmark: {e}")
