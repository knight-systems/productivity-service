"""Queue models for read queue functionality."""

from enum import Enum


class QueueStatus(str, Enum):
    """Queue consumption status."""

    UNREAD = "unread"
    READING = "reading"
    CONSUMED = "consumed"
    ARCHIVED = "archived"


class QueuePriority(str, Enum):
    """Queue priority levels."""

    MUST_READ = "must-read"  # Important/urgent content
    NORMAL = "normal"  # Standard queue items
    SOMEDAY = "someday"  # Auto-decayed or manually deprioritized
    SNACK = "snack"  # Quick reads < 2 min


class ContentType(str, Enum):
    """Type of content being queued."""

    ARTICLE = "article"
    VIDEO = "video"
    TWEET = "tweet"
    PDF = "pdf"
    DOC = "doc"
    PODCAST = "podcast"
    OTHER = "other"
