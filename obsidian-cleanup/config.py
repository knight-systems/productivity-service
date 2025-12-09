"""Configuration for obsidian-cleanup module."""

from pathlib import Path

from pydantic_settings import BaseSettings


class AreaFolder:
    """Area folders in the Obsidian vault (PARA-style structure)."""

    FINANCE = "41 - Finance"
    FAMILY = "42 - Family"
    WORK = "43 - Work"
    HEALTH = "44 - Health"
    LEARNING = "45 - Learning"
    PROJECTS = "46 - Projects"

    # All area folders for iteration
    ALL = [FINANCE, FAMILY, WORK, HEALTH, LEARNING, PROJECTS]

    # Mapping from slug to full name
    SLUG_MAP = {
        "finance": FINANCE,
        "family": FAMILY,
        "work": WORK,
        "health": HEALTH,
        "learning": LEARNING,
        "projects": PROJECTS,
    }


class Settings(BaseSettings):
    """Obsidian cleanup configuration settings."""

    # Vault path - iCloud Obsidian vault
    vault_path: Path = (
        Path.home()
        / "Library"
        / "Mobile Documents"
        / "iCloud~md~obsidian"
        / "Documents"
        / "Second Brain"
    )

    # Database path for plans and corrections
    db_path: Path = Path.home() / ".obsidian-cleanup" / "plans.db"

    # Protected folders (never move notes from these)
    protected_folders: list[str] = [
        "10 - Meta",  # System/meta notes
        "20 - Journal",  # Daily notes
        "Bookmarks",  # Saved bookmarks
        "52 - Templates",  # Note templates (alternate location)
        "53 - Literature Notes",  # Zettelkasten literature notes
        "54 - Permanent Notes",  # Zettelkasten permanent notes
        "60 - Archives",  # Already archived items
        "90 - Templates",  # Note templates
        ".obsidian",  # Obsidian config
        ".git",  # Git folder
        "00 - Inbox",  # Inbox is intentionally unsorted
    ]

    # Areas folder prefix (where notes should be organized to)
    areas_folder: str = "40 - Areas"

    # Archive folder for old notes
    archive_folder: str = "60 - Archives"

    # AI classification settings
    ai_confidence_threshold: float = 1.0  # Always use AI classification (set to 1.0 to skip rules)
    ai_enabled: bool = True
    max_content_chars_for_ai: int = 2000  # Truncate content for AI

    # File patterns to ignore
    ignore_patterns: list[str] = [
        ".DS_Store",
        "*.canvas",  # Skip canvas files for now
        "*.excalidraw",  # Skip excalidraw files
    ]

    class Config:
        env_prefix = "OBSIDIAN_CLEANUP_"
        env_file = ".env"


# Singleton settings instance
settings = Settings()


def get_area_path(area_folder: str, filename: str | None = None) -> Path:
    """Build path to an area folder or file within it."""
    base = settings.vault_path / settings.areas_folder / area_folder
    if filename:
        return base / filename
    return base


def get_archive_path(filename: str | None = None) -> Path:
    """Build path to archive folder or file within it."""
    base = settings.vault_path / settings.archive_folder
    if filename:
        return base / filename
    return base


def is_protected_path(note_path: Path) -> bool:
    """Check if a path is in a protected folder."""
    # Get relative path from vault root
    try:
        rel_path = note_path.relative_to(settings.vault_path)
        parts = rel_path.parts

        # Check if any part of the path is a protected folder
        for protected in settings.protected_folders:
            if protected in parts:
                return True

        # Also protect the root of areas (but not subfolders)
        if len(parts) == 1:
            return True  # Files at vault root are protected

        return False
    except ValueError:
        # Path is not relative to vault - protect it
        return True


def ensure_directories() -> None:
    """Create all required directories."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure all area folders exist
    for area in AreaFolder.ALL:
        (settings.vault_path / settings.areas_folder / area).mkdir(
            parents=True, exist_ok=True
        )

    # Ensure archive folder exists
    (settings.vault_path / settings.archive_folder).mkdir(parents=True, exist_ok=True)
