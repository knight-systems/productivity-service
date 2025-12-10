"""Queue models for review queue functionality."""

from enum import Enum


class QueueStatus(str, Enum):
    """Queue consumption status."""

    UNREVIEWED = "unreviewed"
    REVIEWING = "reviewing"
    CONSUMED = "consumed"
    ARCHIVED = "archived"


class QueuePriority(str, Enum):
    """Queue priority levels."""

    MUST_REVIEW = "must-review"  # Important/urgent content
    NORMAL = "normal"  # Standard queue items
    SOMEDAY = "someday"  # Auto-decayed or manually deprioritized
    SNACK = "snack"  # Quick reviews < 2 min


class ContentType(str, Enum):
    """Type of content being queued."""

    ARTICLE = "article"
    VIDEO = "video"
    TWEET = "tweet"
    PDF = "pdf"
    DOC = "doc"
    PODCAST = "podcast"
    OTHER = "other"
