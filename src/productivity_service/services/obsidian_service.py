"""Obsidian daily note service."""

import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .github_service import GitHubService

logger = logging.getLogger(__name__)

# Daily note path pattern: 20 - Journal/21 - Daily/{year}/{date} {day}.md
DAILY_NOTE_PATH_TEMPLATE = "20 - Journal/21 - Daily/{year}/{date} {day}.md"

# Template path for new daily notes
DAILY_NOTE_TEMPLATE_PATH = "90 - Templates/daily-notes-template.md"

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

    def _render_template(self, template: str, date: datetime) -> str:
        """Render a daily note template with date variables.

        Supports common Obsidian Templater variables:
        - {{date}} or {{date:YYYY-MM-DD}} -> 2025-12-08
        - {{date:dddd}} -> Monday
        - {{date:MMMM D, YYYY}} -> December 8, 2025
        """
        # Map of Templater format tokens to Python strftime
        format_map = {
            "YYYY": "%Y",
            "YY": "%y",
            "MMMM": "%B",
            "MMM": "%b",
            "MM": "%m",
            "M": "%-m",
            "DD": "%d",
            "D": "%-d",
            "dddd": "%A",
            "ddd": "%a",
            "dd": "%a",
        }

        def replace_date_var(match: re.Match) -> str:
            fmt = match.group(1) if match.group(1) else "YYYY-MM-DD"
            # Convert Templater format to strftime
            py_fmt = fmt
            for templater_token, strftime_token in format_map.items():
                py_fmt = py_fmt.replace(templater_token, strftime_token)
            try:
                return date.strftime(py_fmt)
            except ValueError:
                # If format fails, return original
                return match.group(0)

        # Replace {{date}} and {{date:FORMAT}} patterns
        result = re.sub(r"\{\{date(?::([^}]+))?\}\}", replace_date_var, template)

        # Also handle frontmatter date field (just YYYY-MM-DD)
        result = re.sub(r"^(date:\s*){{date}}",
                        lambda m: m.group(1) + date.strftime("%Y-%m-%d"),
                        result, flags=re.MULTILINE)

        return result

    def create_daily_note_from_template(self, date: datetime | None = None) -> dict:
        """Create a new daily note from the template.

        Args:
            date: Date for the note (default: today)

        Returns:
            Dict with path, commit_sha, created status
        """
        if date is None:
            date = datetime.now(self.tz)
        elif date.tzinfo is None:
            date = date.replace(tzinfo=self.tz)

        note_path = self._get_daily_note_path(date)

        # Check if note already exists
        existing = self.github.get_file_content(note_path)
        if existing is not None:
            return {
                "success": True,
                "path": note_path,
                "created": False,
                "message": "Daily note already exists",
            }

        # Get template
        template_result = self.github.get_file_content(DAILY_NOTE_TEMPLATE_PATH)
        if template_result is None:
            raise FileNotFoundError(f"Template not found: {DAILY_NOTE_TEMPLATE_PATH}")

        template_content, _ = template_result

        # Render template with date
        rendered_content = self._render_template(template_content, date)

        # Create the file
        commit_sha = self.github.update_file(
            path=note_path,
            content=rendered_content,
            message=f"Create daily note for {date.strftime('%Y-%m-%d')}",
            sha=None,  # None = create new file
        )

        logger.info(f"Created daily note: {note_path}")

        return {
            "success": True,
            "path": note_path,
            "commit_sha": commit_sha,
            "created": True,
        }

    def _ensure_daily_note_exists(self, date: datetime | None = None) -> tuple[str, str]:
        """Ensure daily note exists, creating from template if needed.

        Args:
            date: Date for the note (default: today)

        Returns:
            Tuple of (content, sha)
        """
        if date is None:
            date = datetime.now(self.tz)
        elif date.tzinfo is None:
            date = date.replace(tzinfo=self.tz)

        note_path = self._get_daily_note_path(date)
        existing = self.github.get_file_content(note_path)

        if existing is not None:
            return existing

        # Create from template
        logger.info(f"Daily note not found, creating from template: {note_path}")
        result = self.create_daily_note_from_template(date)

        if not result.get("success"):
            raise RuntimeError(f"Failed to create daily note: {result}")

        # Fetch the newly created note
        existing = self.github.get_file_content(note_path)
        if existing is None:
            raise RuntimeError(f"Failed to read newly created daily note: {note_path}")

        return existing

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

        # Get current file content (auto-create if needed)
        current_content, sha = self._ensure_daily_note_exists(date)

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

        # Get current file content (auto-create if needed)
        current_content, sha = self._ensure_daily_note_exists(date)

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
