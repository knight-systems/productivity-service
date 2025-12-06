"""Task-related Pydantic models."""

from pydantic import BaseModel, Field


class TaskParseRequest(BaseModel):
    """Request to parse natural language task input."""

    text: str = Field(
        ...,
        description="Raw voice/text input like 'Buy milk tomorrow for the grocery project'",
        min_length=1,
        max_length=1000,
    )


class TaskParseResponse(BaseModel):
    """Response with extracted task components."""

    title: str = Field(..., description="Extracted task title")
    project: str | None = Field(None, description="Detected project name")
    context: str | None = Field(None, description="Detected context (@home, @work, etc.)")
    due_date: str | None = Field(None, description="Due date in YYYY-MM-DD format")
    defer_date: str | None = Field(None, description="Defer/start date in YYYY-MM-DD format")
    tags: list[str] = Field(default_factory=list, description="Additional tags")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence score")
    raw_input: str = Field(..., description="Original input text")


class TaskCreateRequest(BaseModel):
    """Request to create a task in OmniFocus."""

    title: str = Field(..., description="Task title", min_length=1)
    project: str | None = Field(None, description="Project name")
    context: str | None = Field(None, description="Context (without @ prefix)")
    due_date: str | None = Field(None, description="Due date in YYYY-MM-DD format")
    defer_date: str | None = Field(None, description="Defer date in YYYY-MM-DD format")
    note: str | None = Field(None, description="Task note/description")
    flagged: bool = Field(False, description="Whether task is flagged")


class TaskCreateResponse(BaseModel):
    """Response from task creation."""

    success: bool
    message: str
    task_title: str
    mail_drop_subject: str | None = Field(None, description="Subject line sent to Mail Drop")
