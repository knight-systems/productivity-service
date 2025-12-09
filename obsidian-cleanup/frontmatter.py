"""YAML frontmatter parsing for Obsidian notes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FrontmatterData:
    """Extracted frontmatter from a note."""

    category: str | None = None
    tags: list[str] | None = None
    title: str | None = None
    created: str | None = None
    modified: str | None = None
    raw: dict | None = None  # Full parsed frontmatter

    def has_useful_metadata(self) -> bool:
        """Check if frontmatter has useful classification info."""
        return bool(self.category or self.tags)


def parse_frontmatter(note_path: Path) -> FrontmatterData | None:
    """Parse YAML frontmatter from an Obsidian note.

    Obsidian frontmatter is a YAML block at the start of the file
    delimited by --- on its own line.

    Example:
    ---
    category: finance
    tags: [trading, research]
    ---
    # Note Title
    """
    try:
        content = note_path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Check if file starts with frontmatter delimiter
    if not content.startswith("---"):
        return FrontmatterData()

    # Find the closing delimiter
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return FrontmatterData()

    yaml_content = match.group(1)

    # Parse YAML manually (avoiding pyyaml dependency)
    data = _parse_simple_yaml(yaml_content)

    return FrontmatterData(
        category=_get_string(data, "category"),
        tags=_get_list(data, "tags"),
        title=_get_string(data, "title"),
        created=_get_string(data, "created"),
        modified=_get_string(data, "modified"),
        raw=data,
    )


def get_note_content(note_path: Path, max_chars: int = 2000) -> str | None:
    """Get note content without frontmatter, truncated to max_chars.

    Used for AI content classification.
    """
    try:
        content = note_path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Remove frontmatter if present
    if content.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
        if match:
            content = content[match.end() :]

    # Truncate to max_chars
    if len(content) > max_chars:
        content = content[:max_chars] + "..."

    return content.strip()


def _parse_simple_yaml(yaml_content: str) -> dict:
    """Simple YAML parser for frontmatter.

    Handles common Obsidian frontmatter patterns:
    - key: value
    - key: [item1, item2]
    - key:
      - item1
      - item2

    Does not handle complex nested structures.
    """
    result: dict = {}
    current_key: str | None = None
    current_list: list | None = None

    for line in yaml_content.split("\n"):
        line = line.rstrip()

        # Skip empty lines
        if not line.strip():
            continue

        # Check for list item (starts with -)
        if line.startswith("  - ") or line.startswith("- "):
            if current_key and current_list is not None:
                # Remove leading "- " and add to list
                item = line.lstrip().lstrip("-").strip()
                # Remove quotes if present
                item = item.strip("\"'")
                current_list.append(item)
            continue

        # Check for key: value
        if ":" in line:
            # Save current list if any
            if current_key and current_list is not None:
                result[current_key] = current_list

            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            current_key = key

            if value:
                # Inline value
                if value.startswith("[") and value.endswith("]"):
                    # Inline list: [item1, item2]
                    items = value[1:-1].split(",")
                    result[key] = [_clean_yaml_value(i) for i in items if i.strip()]
                    current_list = None
                else:
                    # Simple value
                    result[key] = _clean_yaml_value(value)
                    current_list = None
            else:
                # Start of multiline list
                current_list = []
        else:
            # Continuation of previous line or unrecognized format
            pass

    # Save final list if any
    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _clean_yaml_value(value: str) -> str:
    """Clean a YAML value by removing quotes and whitespace."""
    value = value.strip()
    # Remove surrounding quotes
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]
    return value


def _get_string(data: dict, key: str) -> str | None:
    """Get a string value from parsed data."""
    value = data.get(key)
    if isinstance(value, str):
        return value
    return None


def _get_list(data: dict, key: str) -> list[str] | None:
    """Get a list value from parsed data."""
    value = data.get(key)
    if isinstance(value, list):
        return [str(v) for v in value]
    # Single string tag
    if isinstance(value, str):
        return [value]
    return None
