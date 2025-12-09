"""Bookmark models for request/response handling."""

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class BookmarkMode(str, Enum):
    """Bookmark processing mode."""

    AUTO = "auto"  # Try meta tags, escalate to full fetch if low quality
    QUICK = "quick"  # Meta tags only, no AI
    RICH = "rich"  # Full page fetch + AI summary + auto-tags


class PageMetadata(BaseModel):
    """Metadata extracted from a webpage."""

    url: str
    title: str | None = None
    description: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    og_image: str | None = None

    @property
    def best_title(self) -> str | None:
        """Return the best available title."""
        return self.og_title or self.title

    @property
    def best_description(self) -> str | None:
        """Return the best available description."""
        return self.og_description or self.description


class PageContent(BaseModel):
    """Full page content for AI processing."""

    url: str
    title: str | None = None
    text_content: str  # Main body text, cleaned


class AIEnrichment(BaseModel):
    """AI-generated enrichment for a bookmark."""

    summary: str
    tags: list[str]
    category: str


class BookmarkSaveRequest(BaseModel):
    """Request to save a bookmark."""

    url: HttpUrl
    mode: BookmarkMode = BookmarkMode.AUTO
    title: str | None = None  # Optional override (or from browser)
    meta_description: str | None = None  # From browser (bypasses fetch)
    notes: str | None = None  # User notes
    tags: list[str] = Field(default_factory=list)  # User-specified tags


class BookmarkSaveResponse(BaseModel):
    """Response from saving a bookmark."""

    success: bool
    bookmark_id: str
    title: str
    status: str  # "complete" or "processing"
    daily_note_updated: bool
    bookmark_file_path: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    error: str | None = None
