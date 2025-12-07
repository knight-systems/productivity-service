"""Pydantic models for routine automation endpoints."""

from datetime import date as date_type

from pydantic import BaseModel, Field


class OmniFocusTask(BaseModel):
    """Task extracted from OmniFocus."""

    title: str = Field(..., description="Task title")
    project: str = Field(default="", description="Project name")
    flagged: bool = Field(default=False, description="Whether task is flagged")
    tags: str = Field(default="", description="Comma-separated tags")
    due: str | None = Field(default=None, description="Due date (YYYY-MM-DD)")


class MorningBriefRequest(BaseModel):
    """Request for morning brief generation."""

    tasks: list[OmniFocusTask] = Field(
        default_factory=list,
        description="Tasks from OmniFocus",
    )
    include_calendar: bool = Field(
        default=False,
        description="Whether to include calendar events (not yet implemented)",
    )
    generate_summary: bool = Field(
        default=True,
        description="Whether to generate AI summary",
    )


class MorningBriefResponse(BaseModel):
    """Response from morning brief generation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    path: str = Field(default="", description="Path to the daily note")
    commit_sha: str = Field(default="", description="Git commit SHA")
    task_count: int = Field(default=0, description="Number of tasks injected")
    summary: str = Field(default="", description="AI-generated summary")
    message: str = Field(default="", description="Status message")


class EveningSummaryRequest(BaseModel):
    """Request for evening summary generation."""

    date: date_type | None = Field(
        default=None,
        description="Date to summarize (YYYY-MM-DD). Defaults to today.",
    )
    extract_tasks: bool = Field(
        default=True,
        description="Whether to extract action items and send to OmniFocus",
    )
    generate_summary: bool = Field(
        default=True,
        description="Whether to generate AI day summary",
    )


class ExtractedTask(BaseModel):
    """Task extracted from daily note."""

    title: str = Field(..., description="Task title")
    context: str = Field(default="", description="Where in the note it was found")


class EveningSummaryResponse(BaseModel):
    """Response from evening summary generation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    path: str = Field(default="", description="Path to the daily note")
    extracted_tasks: list[ExtractedTask] = Field(
        default_factory=list,
        description="Tasks extracted from the daily note",
    )
    tasks_sent: int = Field(default=0, description="Number of tasks sent to OmniFocus")
    summary: str = Field(default="", description="AI-generated day summary")
    message: str = Field(default="", description="Status message")
