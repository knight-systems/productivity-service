"""Pydantic models for note classification plans."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class NoteAction(str, Enum):
    """Actions that can be taken on a note."""

    MOVE = "move"  # Move to correct area folder
    ARCHIVE = "archive"  # Move to archives
    SKIP = "skip"  # Leave in place


class PlanStatus(str, Enum):
    """Status of a note plan."""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"
    REVISED = "revised"  # User provided feedback, waiting for re-classification


class NotePlan(BaseModel):
    """A proposed note organization operation."""

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    source_path: str  # Full path to the note
    action: NoteAction
    destination_path: str | None = None
    target_area: str | None = None  # e.g., "41 - Finance"
    confidence: float = 0.0
    reasoning: str = ""
    classification_source: str = "rules"  # "rules", "ai", or "learned"
    created_at: datetime = Field(default_factory=datetime.now)
    status: PlanStatus = PlanStatus.PENDING
    executed_at: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Feedback and learning
    user_feedback: str | None = None  # Natural language feedback
    original_plan_id: str | None = None  # If this is a revision, link to original
    revision_count: int = 0  # How many times this note has been reclassified
    # Frontmatter info
    frontmatter_category: str | None = None
    frontmatter_tags: list[str] = Field(default_factory=list)

    @property
    def source_name(self) -> str:
        """Get the filename from source path."""
        return Path(self.source_path).name

    @property
    def destination_name(self) -> str | None:
        """Get the destination folder name."""
        if self.destination_path:
            return Path(self.destination_path).parent.name
        return None

    def to_display(self) -> str:
        """Format for display in CLI."""
        action_emoji = {
            NoteAction.MOVE: "📁",
            NoteAction.ARCHIVE: "📦",
            NoteAction.SKIP: "⏭️",
        }
        emoji = action_emoji.get(self.action, "❓")
        dest = f" → {self.target_area}" if self.target_area else ""
        return f"{emoji} [{self.id}] {self.action.value}: {self.source_name}{dest}"


class PlanSummary(BaseModel):
    """Summary of pending plans for review."""

    total_plans: int = 0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_area: dict[str, int] = Field(default_factory=dict)

    def to_display(self) -> str:
        """Format for display in CLI."""
        lines = [f"Total: {self.total_plans} notes"]

        if self.by_action:
            action_str = ", ".join(f"{k}: {v}" for k, v in self.by_action.items())
            lines.append(f"By action: {action_str}")

        if self.by_area:
            area_str = ", ".join(f"{k}: {v}" for k, v in self.by_area.items())
            lines.append(f"By area: {area_str}")

        return "\n".join(lines)


class Correction(BaseModel):
    """A learned correction from user feedback.

    These are used to improve future classifications by providing
    examples of what the user prefers.
    """

    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    created_at: datetime = Field(default_factory=datetime.now)

    # What the system originally predicted
    original_filename: str
    original_action: NoteAction
    original_area: str | None = None

    # What the user corrected it to
    corrected_action: NoteAction
    corrected_area: str | None = None

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
            f"Notes like '{self.original_filename}' should go to "
            f"'{self.corrected_area or 'archive'}'. "
            f"User said: \"{self.user_feedback}\""
        )
