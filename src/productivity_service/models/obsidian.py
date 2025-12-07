"""Pydantic models for Obsidian API endpoints."""

from datetime import date as date_type

from pydantic import BaseModel, Field


class DailyNoteAppendRequest(BaseModel):
    """Request to append content to a daily note section."""

    heading: str = Field(
        ...,
        description="Target heading name (e.g., 'Brain Dump', 'Bookmarks', 'Journal')",
        examples=["Brain Dump", "Bookmarks"],
    )
    content: str = Field(
        ...,
        description="Content to append to the section",
        min_length=1,
        examples=["Had a great meeting about the project"],
    )
    timestamp: bool = Field(
        default=True,
        description="Whether to prepend HH:MM timestamp to the content",
    )
    date: date_type | None = Field(
        default=None,
        description="Date for the daily note (YYYY-MM-DD). Defaults to today.",
    )


class DailyNoteAppendResponse(BaseModel):
    """Response from daily note append operation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    path: str = Field(..., description="Path to the daily note file")
    commit_sha: str = Field(..., description="Git commit SHA")
    heading: str = Field(..., description="Heading that was appended to")
    content: str = Field(..., description="Content that was appended")
    message: str = Field(default="", description="Additional message")


class DailyNoteGetResponse(BaseModel):
    """Response with daily note content."""

    success: bool = Field(..., description="Whether the operation succeeded")
    path: str = Field(..., description="Path to the daily note file")
    content: str | None = Field(None, description="Daily note content")
    exists: bool = Field(..., description="Whether the daily note exists")
