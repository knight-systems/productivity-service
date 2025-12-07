"""Obsidian API routes for daily note operations."""

import logging
import os
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException

from ..models.obsidian import (
    DailyNoteAppendRequest,
    DailyNoteAppendResponse,
    DailyNoteGetResponse,
)
from ..services.github_service import GitHubService
from ..services.obsidian_service import ObsidianService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


@lru_cache(maxsize=1)
def _get_obsidian_service() -> ObsidianService:
    """Get or create ObsidianService singleton."""
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
    return ObsidianService(github_service)


@router.post("/daily/append", response_model=DailyNoteAppendResponse)
async def append_to_daily_note(request: DailyNoteAppendRequest) -> DailyNoteAppendResponse:
    """Append content to a section of the daily note.

    Appends the provided content under the specified heading in today's
    (or a specified date's) daily note. Optionally prepends a timestamp.

    **Valid headings:**
    - Brain Dump
    - Bookmarks
    - Tasks
    - Morning Plan
    - Journal
    - Carry-Over
    """
    try:
        service = _get_obsidian_service()

        # Convert date if provided
        note_date = None
        if request.date:
            note_date = datetime.combine(request.date, datetime.min.time())

        result = service.append_to_daily_note(
            heading=request.heading,
            content=request.content,
            timestamp=request.timestamp,
            date=note_date,
        )

        return DailyNoteAppendResponse(
            success=True,
            path=result["path"],
            commit_sha=result["commit_sha"],
            heading=result["heading"],
            content=result["content"],
            message="Content appended successfully",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error appending to daily note")
        raise HTTPException(status_code=500, detail=f"Failed to append to daily note: {e}")


@router.get("/daily", response_model=DailyNoteGetResponse)
async def get_daily_note(date: str | None = None) -> DailyNoteGetResponse:
    """Get the content of a daily note.

    Args:
        date: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    try:
        service = _get_obsidian_service()

        note_date = None
        if date:
            note_date = datetime.strptime(date, "%Y-%m-%d")

        content = service.get_daily_note(date=note_date)
        path = service._get_daily_note_path(date=note_date)

        return DailyNoteGetResponse(
            success=True,
            path=path,
            content=content,
            exists=content is not None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.exception("Error getting daily note")
        raise HTTPException(status_code=500, detail=f"Failed to get daily note: {e}")
