"""File system watcher for Desktop and Downloads monitoring."""

import logging
import subprocess
import threading
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import settings
from .database import get_plan_by_source, init_db, save_plan
from .models import FileAction, PlanStatus
from .rules import can_use_ai_for_file, classify_file, needs_ai_classification

logger = logging.getLogger(__name__)


class FileClassifierHandler(FileSystemEventHandler):
    """Handle file system events and classify new files."""

    def __init__(self) -> None:
        super().__init__()
        self._pending_files: dict[str, float] = {}
        self._lock = threading.Lock()
        self._debounce_thread: threading.Thread | None = None
        self._running = True

    def start_debounce_processor(self) -> None:
        """Start background thread for debounced file processing."""
        self._debounce_thread = threading.Thread(
            target=self._process_debounced_files,
            daemon=True,
        )
        self._debounce_thread.start()

    def stop(self) -> None:
        """Stop the handler."""
        self._running = False
        if self._debounce_thread:
            self._debounce_thread.join(timeout=2.0)

    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        self._queue_file(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle file move events (files moved INTO watched directories)."""
        if event.is_directory:
            return
        self._queue_file(event.dest_path)

    def _queue_file(self, file_path: str) -> None:
        """Queue a file for debounced processing."""
        path = Path(file_path)

        # Skip if should be ignored
        if self._should_skip(path):
            logger.debug(f"Skipping ignored file: {path.name}")
            return

        with self._lock:
            self._pending_files[file_path] = time.time()
            logger.info(f"Queued for classification: {path.name}")

    def _should_skip(self, path: Path) -> bool:
        """Check if file should be skipped."""
        name = path.name

        # Skip hidden files
        if name.startswith(".") and settings.ignore_hidden:
            return True

        # Skip patterns
        for pattern in settings.ignore_patterns:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif pattern in name:
                return True

        return False

    def _process_debounced_files(self) -> None:
        """Process files after debounce period."""
        while self._running:
            time.sleep(1.0)  # Check every second

            files_to_process: list[str] = []
            current_time = time.time()

            with self._lock:
                for path, queued_time in list(self._pending_files.items()):
                    if current_time - queued_time >= settings.debounce_seconds:
                        files_to_process.append(path)

                for path in files_to_process:
                    del self._pending_files[path]

            for file_path in files_to_process:
                self._classify_and_save(file_path)

    def _classify_and_save(self, file_path: str) -> None:
        """Classify a file and save the plan."""
        path = Path(file_path)

        # Check if file still exists
        if not path.exists():
            logger.debug(f"File no longer exists: {path.name}")
            return

        # Check if we already have a pending plan for this file
        existing_plan = get_plan_by_source(file_path)
        if existing_plan and existing_plan.status == PlanStatus.PENDING:
            logger.debug(f"Plan already exists for: {path.name}")
            return

        # Classify using rules
        plan = classify_file(path)

        # Check if AI classification is needed
        if needs_ai_classification(plan) and can_use_ai_for_file(path):
            logger.info(f"File needs AI classification: {path.name} (confidence: {plan.confidence})")
            # For now, mark as needing review
            # AI classification will be added in classifier.py
            plan.reasoning += " [AI classification recommended]"

        # Save to database
        save_plan(plan)
        logger.info(f"Classified: {path.name} -> {plan.action.value} ({plan.confidence:.0%})")

        # Send notification for non-skip actions
        if plan.action != FileAction.SKIP:
            _send_notification(
                title="File Classified",
                message=f"{path.name} -> {plan.action.value}",
                subtitle=f"Confidence: {plan.confidence:.0%}",
            )


def _send_notification(title: str, message: str, subtitle: str = "") -> None:
    """Send macOS notification."""
    script = f'''
    display notification "{message}" with title "{title}" subtitle "{subtitle}"
    '''
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
    except Exception as e:
        logger.warning(f"Failed to send notification: {e}")


class FileWatcher:
    """Watch Desktop and Downloads for new files."""

    def __init__(self) -> None:
        self.observer = Observer()
        self.handler = FileClassifierHandler()
        self._paths: list[Path] = []

    def setup(self) -> None:
        """Set up watched directories."""
        init_db()

        if settings.watch_desktop and settings.desktop_path.exists():
            self._paths.append(settings.desktop_path)
            self.observer.schedule(
                self.handler,
                str(settings.desktop_path),
                recursive=False,
            )
            logger.info(f"Watching: {settings.desktop_path}")

        if settings.watch_downloads and settings.downloads_path.exists():
            self._paths.append(settings.downloads_path)
            self.observer.schedule(
                self.handler,
                str(settings.downloads_path),
                recursive=False,
            )
            logger.info(f"Watching: {settings.downloads_path}")

    def start(self) -> None:
        """Start watching."""
        self.handler.start_debounce_processor()
        self.observer.start()
        logger.info("File watcher started")

    def stop(self) -> None:
        """Stop watching."""
        self.handler.stop()
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")

    def run_forever(self) -> None:
        """Run until interrupted."""
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.stop()


def main() -> None:
    """Main entry point for watcher."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    watcher = FileWatcher()
    watcher.setup()
    watcher.run_forever()


if __name__ == "__main__":
    main()
