"""Obsidian daily note service."""

import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .github_service import GitHubService

logger = logging.getLogger(__name__)

# Daily note path pattern: 20 - Journal/21 - Daily/{year}/{date} {day}.md
DAILY_NOTE_PATH_TEMPLATE = "20 - Journal/21 - Daily/{year}/{date} {day}.md"

# Heading mapping (display name -> markdown heading)
# Note: Uses curly apostrophe (') to match Obsidian template
HEADING_MAP = {
    "Brain Dump": "## ☕ Brain Dump",
    "Bookmarks": "## 🔖 Bookmarks",
    "Tasks": "## 📋 Today’s Tasks (from OmniFocus)",
    "Morning Plan": "## 🌅 Morning Plan",
    "Journal": "## 📝 Journal & Reflection",
    "Carry-Over": "## 🔁 Carry-Over Tasks",
}


class ObsidianService:
    """Service for Obsidian vault operations via GitHub API."""

    def __init__(self, github_service: GitHubService, timezone_str: str = "America/New_York"):
        """Initialize Obsidian service.

        Args:
            github_service: GitHubService instance for repository operations
            timezone_str: Timezone for timestamps (default: America/New_York)
        """
        self.github = github_service
        self.tz = ZoneInfo(timezone_str)

    def _get_daily_note_path(self, date: datetime | None = None) -> str:
        """Get the path to a daily note.

        Args:
            date: Date for the note (default: today in configured timezone)

        Returns:
            Path to daily note file
        """
        if date is None:
            date = datetime.now(self.tz)
        elif date.tzinfo is None:
            date = date.replace(tzinfo=self.tz)

        year = date.strftime("%Y")
        date_str = date.strftime("%Y-%m-%d")
        day_str = date.strftime("%a")

        return DAILY_NOTE_PATH_TEMPLATE.format(
            year=year,
            date=date_str,
            day=day_str,
        )

    def _get_current_time_str(self) -> str:
        """Get current time as HH:MM string."""
        return datetime.now(self.tz).strftime("%H:%M")

    def _find_heading_position(self, content: str, heading: str) -> int | None:
        """Find the position right after a heading in the content.

        Args:
            content: Full file content
            heading: Heading to find (e.g., "## ☕ Brain Dump")

        Returns:
            Position after the heading line, or None if not found
        """
        # Escape special regex characters in heading
        escaped_heading = re.escape(heading)
        pattern = rf"^{escaped_heading}\s*$"

        for match in re.finditer(pattern, content, re.MULTILINE):
            # Return position at end of heading line (after newline)
            end_pos = match.end()
            if end_pos < len(content) and content[end_pos] == "\n":
                return end_pos + 1
            return end_pos

        return None

    def _insert_after_heading(
        self,
        content: str,
        heading: str,
        text_to_insert: str,
    ) -> str:
        """Insert text after a heading, before any existing content.

        Args:
            content: Full file content
            heading: Heading to insert after
            text_to_insert: Text to insert

        Returns:
            Modified content
        """
        pos = self._find_heading_position(content, heading)
        if pos is None:
            # Heading not found, append at end with heading
            return content + f"\n\n{heading}\n{text_to_insert}"

        # Find the first non-empty line after the heading (skip the "- " placeholder line)
        # Insert after any empty lines but before actual content
        lines = content[pos:].split("\n")
        insert_after_lines = 0

        for line in lines:
            stripped = line.strip()
            # Skip empty lines and placeholder lines (just "- " or empty)
            if stripped == "" or stripped == "-":
                insert_after_lines += 1
            else:
                break

        # Calculate actual insert position
        actual_pos = pos
        for i in range(insert_after_lines):
            newline_pos = content.find("\n", actual_pos)
            if newline_pos == -1:
                break
            actual_pos = newline_pos + 1

        return content[:actual_pos] + text_to_insert + content[actual_pos:]

    def append_to_daily_note(
        self,
        heading: str,
        content: str,
        timestamp: bool = True,
        date: datetime | None = None,
    ) -> dict:
        """Append content to a section of the daily note.

        Args:
            heading: Section heading name (e.g., "Brain Dump", "Bookmarks")
            content: Content to append
            timestamp: Whether to prepend HH:MM timestamp
            date: Date for the note (default: today)

        Returns:
            Dict with path, commit_sha, and success status
        """
        # Resolve heading to markdown format
        markdown_heading = HEADING_MAP.get(heading)
        if not markdown_heading:
            # Try to use as-is if it looks like a heading
            if heading.startswith("##"):
                markdown_heading = heading
            else:
                raise ValueError(f"Unknown heading: {heading}. Valid options: {list(HEADING_MAP.keys())}")

        # Get daily note path
        note_path = self._get_daily_note_path(date)

        # Format content with optional timestamp
        if timestamp:
            time_str = self._get_current_time_str()
            formatted_content = f"- {time_str} {content}\n"
        else:
            formatted_content = f"- {content}\n"

        # Get current file content
        existing = self.github.get_file_content(note_path)

        if existing is None:
            # Daily note doesn't exist - this is unexpected, let the user know
            raise FileNotFoundError(f"Daily note not found: {note_path}. Please create the daily note first.")

        current_content, sha = existing

        # Insert content after heading
        new_content = self._insert_after_heading(
            current_content,
            markdown_heading,
            formatted_content,
        )

        # Commit the change
        commit_message = f"Add to {heading}: {content[:50]}..."
        commit_sha = self.github.update_file(
            path=note_path,
            content=new_content,
            message=commit_message,
            sha=sha,
        )

        return {
            "success": True,
            "path": note_path,
            "commit_sha": commit_sha,
            "heading": heading,
            "content": content,
        }

    def get_daily_note(self, date: datetime | None = None) -> str | None:
        """Get the content of a daily note.

        Args:
            date: Date for the note (default: today)

        Returns:
            Daily note content or None if not found
        """
        note_path = self._get_daily_note_path(date)
        result = self.github.get_file_content(note_path)
        return result[0] if result else None

    def _find_section_bounds(self, content: str, heading: str) -> tuple[int, int] | None:
        """Find the start and end positions of a section.

        Args:
            content: Full file content
            heading: Heading to find (e.g., "## ☕ Brain Dump")

        Returns:
            Tuple of (start_after_heading, end_before_next_heading) or None if not found
        """
        # Find the heading
        escaped_heading = re.escape(heading)
        pattern = rf"^{escaped_heading}\s*$"

        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            return None

        # Start position is right after heading line
        start_pos = match.end()
        if start_pos < len(content) and content[start_pos] == "\n":
            start_pos += 1

        # Find the next heading (## at start of line)
        next_heading_match = re.search(r"^##\s", content[start_pos:], re.MULTILINE)
        if next_heading_match:
            end_pos = start_pos + next_heading_match.start()
        else:
            end_pos = len(content)

        return (start_pos, end_pos)

    def replace_daily_note_section(
        self,
        heading: str,
        content: str,
        date: datetime | None = None,
    ) -> dict:
        """Replace the content of a section in the daily note.

        This is IDEMPOTENT - calling multiple times with the same content
        will produce the same result.

        Args:
            heading: Section heading name (e.g., "Brain Dump", "Tasks")
            content: New content for the section
            date: Date for the note (default: today)

        Returns:
            Dict with path, commit_sha, and success status
        """
        # Resolve heading to markdown format
        markdown_heading = HEADING_MAP.get(heading)
        if not markdown_heading:
            if heading.startswith("##"):
                markdown_heading = heading
            else:
                raise ValueError(f"Unknown heading: {heading}. Valid options: {list(HEADING_MAP.keys())}")

        # Get daily note path
        note_path = self._get_daily_note_path(date)

        # Get current file content
        existing = self.github.get_file_content(note_path)

        if existing is None:
            raise FileNotFoundError(f"Daily note not found: {note_path}. Please create the daily note first.")

        current_content, sha = existing

        # Find section bounds
        bounds = self._find_section_bounds(current_content, markdown_heading)

        if bounds is None:
            # Section doesn't exist - append at end
            new_content = current_content.rstrip() + f"\n\n{markdown_heading}\n{content}\n"
        else:
            start_pos, end_pos = bounds
            # Replace section content
            new_content = current_content[:start_pos] + content + "\n\n" + current_content[end_pos:].lstrip()

        # Commit the change
        commit_message = f"Update {heading} section"
        commit_sha = self.github.update_file(
            path=note_path,
            content=new_content,
            message=commit_message,
            sha=sha,
        )

        return {
            "success": True,
            "path": note_path,
            "commit_sha": commit_sha,
            "heading": heading,
        }
