"""Pydantic models for file classification plans."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class FileAction(str, Enum):
    """Actions that can be taken on a file."""

    MOVE = "move"
    DELETE = "delete"
    ARCHIVE = "archive"
    SKIP = "skip"
    RENAME = "rename"


class FileCategory(str, Enum):
    """Categories for file classification."""

    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    INSTALLER = "installer"
    ARCHIVE = "archive"
    CODE = "code"
    TRADING = "trading"
    RECEIPT = "receipt"
    SCREENSHOT = "screenshot"
    DOWNLOAD = "download"
    UNKNOWN = "unknown"


class LifeDomain(str, Enum):
    """Life domains matching ~/Dropbox/_Areas structure."""

    FINANCE = "Finance"
    FAMILY = "Family"
    WORK = "Work"
    HEALTH = "Health"
    PROPERTY = "Property"
    PERSONAL = "Personal"


class PlanStatus(str, Enum):
    """Status of a file plan."""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"
    REVISED = "revised"  # User provided feedback, waiting for re-classification


class FilePlan(BaseModel):
    """A proposed file operation."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    source_path: str
    action: FileAction
    destination_path: str | None = None
    category: FileCategory = FileCategory.UNKNOWN
    domain: LifeDomain | None = None
    subfolder: str | None = None  # Documents, Projects, Archive, etc.
    confidence: float = 0.0
    reasoning: str = ""
    classification_source: str = "rules"  # "rules" or "ai"
    created_at: datetime = Field(default_factory=datetime.now)
    status: PlanStatus = PlanStatus.PENDING
    executed_at: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Feedback and learning
    user_feedback: str | None = None  # Natural language feedback
    original_plan_id: str | None = None  # If this is a revision, link to original
    revision_count: int = 0  # How many times this file has been reclassified
    # File renaming
    suggested_name: str | None = None  # AI-suggested standardized filename

    @property
    def source_name(self) -> str:
        """Get the filename from source path."""
        return Path(self.source_path).name

    @property
    def destination_name(self) -> str | None:
        """Get the destination folder name."""
        if self.destination_path:
            return Path(self.destination_path).name
        return None

    def to_display(self) -> str:
        """Format for display in Raycast/CLI."""
        action_emoji = {
            FileAction.MOVE: "📁",
            FileAction.DELETE: "🗑️",
            FileAction.ARCHIVE: "📦",
            FileAction.SKIP: "⏭️",
            FileAction.RENAME: "✏️",
        }
        emoji = action_emoji.get(self.action, "❓")
        dest = f" → {self.destination_path}" if self.destination_path else ""
        rename = f" (rename: {self.suggested_name})" if self.suggested_name else ""
        return f"{emoji} [{self.id}] {self.action.value}: {self.source_name}{dest}{rename}"


class PlanSummary(BaseModel):
    """Summary of pending plans for review."""

    total_plans: int = 0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    estimated_space_freed_bytes: int = 0

    @property
    def estimated_space_freed_mb(self) -> float:
        """Get space freed in MB."""
        return self.estimated_space_freed_bytes / (1024 * 1024)


class Correction(BaseModel):
    """A learned correction from user feedback.

    These are used to improve future classifications by providing
    examples of what the user prefers.
    """

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    created_at: datetime = Field(default_factory=datetime.now)

    # What the system originally predicted
    original_filename: str
    original_action: FileAction
    original_domain: LifeDomain | None = None
    original_subfolder: str | None = None

    # What the user corrected it to
    corrected_action: FileAction
    corrected_domain: LifeDomain | None = None
    corrected_subfolder: str | None = None

    # User's explanation (natural language)
    user_feedback: str

    # Extracted patterns for future matching
    filename_pattern: str | None = None  # Regex pattern extracted by LLM
    keywords: list[str] = Field(default_factory=list)  # Keywords to match

    # How many times this correction has been applied
    times_applied: int = 0
    last_applied: datetime | None = None

    def to_rule_description(self) -> str:
        """Format as a rule description for LLM context."""
        return (
            f"Files like '{self.original_filename}' should go to "
            f"{self.corrected_domain.value if self.corrected_domain else 'unknown'}/"
            f"{self.corrected_subfolder or 'Documents'}. "
            f"User said: \"{self.user_feedback}\""
        )
