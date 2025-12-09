"""Configuration for filesystem daemon."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Daemon configuration settings."""

    # Paths to watch
    watch_desktop: bool = True
    watch_downloads: bool = True
    desktop_path: Path = Path.home() / "Desktop"
    downloads_path: Path = Path.home() / "Downloads"

    # Destination base
    areas_path: Path = Path.home() / "Dropbox" / "_Areas"

    # Database
    db_path: Path = Path.home() / ".file-classifier" / "plans.db"
    backup_path: Path = Path.home() / ".file-classifier" / "backups"

    # Classification
    ai_confidence_threshold: float = 0.8  # Below this, use AI classification
    ai_enabled: bool = True
    max_file_size_for_ai_mb: int = 100  # Don't send huge files to AI

    # Watcher behavior
    debounce_seconds: float = 5.0  # Wait before classifying new files
    ignore_hidden: bool = True
    ignore_patterns: list[str] = [
        ".DS_Store",
        ".localized",
        "*.tmp",
        "*.part",
        "*.crdownload",
        "Icon\r",
    ]

    # Safety
    dry_run: bool = False
    backup_before_move: bool = True
    backup_retention_days: int = 30

    # Raycast integration
    raycast_scripts_path: Path = (
        Path.home() / "Dropbox/web-projects/productivity-service/raycast/scripts"
    )

    class Config:
        env_prefix = "FILE_CLASSIFIER_"
        env_file = ".env"


# Singleton settings instance
settings = Settings()


# Domain subfolder structure
DOMAIN_SUBFOLDERS: dict[str, list[str]] = {
    "Finance": ["Documents", "Research", "Projects", "Archive"],
    "Family": ["Documents", "Media", "Archive"],
    "Work": ["Documents", "Projects", "Learning", "Archive"],
    "Health": ["Documents", "Archive"],
    "Property": ["Documents", "Projects", "Archive"],
    "Personal": ["Documents", "Media", "Archive"],
}


def get_destination_path(domain: str, subfolder: str, filename: str) -> Path:
    """Build full destination path for a file."""
    return settings.areas_path / domain / subfolder / filename


def ensure_directories() -> None:
    """Create all required directories."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.backup_path.mkdir(parents=True, exist_ok=True)

    # Ensure all domain subfolders exist
    for domain, subfolders in DOMAIN_SUBFOLDERS.items():
        for subfolder in subfolders:
            (settings.areas_path / domain / subfolder).mkdir(parents=True, exist_ok=True)
