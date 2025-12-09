"""Execute approved file plans with safety measures."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from .config import settings
from .database import get_pending_plans, get_plan, update_plan_status
from .models import FileAction, FilePlan, PlanStatus

logger = logging.getLogger(__name__)


def execute_plan(plan_id: str) -> tuple[bool, str]:
    """Execute a single plan by ID.

    Returns:
        Tuple of (success, message)
    """
    plan = get_plan(plan_id)
    if not plan:
        return False, f"Plan not found: {plan_id}"

    if plan.status != PlanStatus.PENDING:
        return False, f"Plan is not pending: {plan.status.value}"

    return _execute_plan_impl(plan)


def execute_all_pending() -> list[tuple[str, bool, str]]:
    """Execute all approved plans (plans that have been reviewed and approved).

    Returns:
        List of (plan_id, success, message) tuples
    """
    from .database import get_plans_by_status

    results: list[tuple[str, bool, str]] = []
    # Execute APPROVED plans (reviewed and ready for execution)
    plans = get_plans_by_status(PlanStatus.APPROVED)

    for plan in plans:
        success, message = _execute_plan_impl(plan)
        results.append((plan.id, success, message))

    return results


def _execute_plan_impl(plan: FilePlan) -> tuple[bool, str]:
    """Execute a single plan implementation."""
    source = Path(plan.source_path)

    # Verify source exists
    if not source.exists():
        update_plan_status(plan.id, PlanStatus.FAILED, "Source file no longer exists")
        return False, "Source file no longer exists"

    try:
        if plan.action == FileAction.MOVE:
            return _execute_move(plan, source)
        elif plan.action == FileAction.DELETE:
            return _execute_delete(plan, source)
        elif plan.action == FileAction.ARCHIVE:
            return _execute_archive(plan, source)
        elif plan.action == FileAction.RENAME:
            return _execute_rename(plan, source)
        elif plan.action == FileAction.SKIP:
            update_plan_status(plan.id, PlanStatus.EXECUTED)
            return True, "Skipped as requested"
        else:
            return False, f"Unknown action: {plan.action}"
    except Exception as e:
        error_msg = str(e)
        update_plan_status(plan.id, PlanStatus.FAILED, error_msg)
        logger.error(f"Failed to execute plan {plan.id}: {error_msg}")
        return False, error_msg


def _execute_move(plan: FilePlan, source: Path) -> tuple[bool, str]:
    """Execute a move action, optionally renaming the file."""
    if not plan.destination_path:
        update_plan_status(plan.id, PlanStatus.FAILED, "No destination specified")
        return False, "No destination specified"

    dest = Path(plan.destination_path)

    # If a suggested name is provided, use it for the destination filename
    if plan.suggested_name:
        dest = dest.parent / plan.suggested_name

    # Create destination directory if needed
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Handle existing file at destination
    if dest.exists():
        # Add counter to avoid overwrite
        counter = 1
        stem = dest.stem
        suffix = dest.suffix
        while dest.exists():
            dest = dest.parent / f"{stem}-{counter}{suffix}"
            counter += 1

    # Backup if configured
    if settings.backup_before_move and not settings.dry_run:
        _backup_file(source)

    # Execute move
    if settings.dry_run:
        logger.info(f"[DRY RUN] Would move: {source} -> {dest}")
    else:
        shutil.move(str(source), str(dest))
        logger.info(f"Moved: {source.name} -> {dest}")

    update_plan_status(plan.id, PlanStatus.EXECUTED)
    return True, f"Moved to {dest}"


def _execute_delete(plan: FilePlan, source: Path) -> tuple[bool, str]:
    """Execute a delete action."""
    # Backup if configured
    if settings.backup_before_move and not settings.dry_run:
        _backup_file(source)

    # Execute delete (move to trash on macOS)
    if settings.dry_run:
        logger.info(f"[DRY RUN] Would delete: {source}")
    else:
        _move_to_trash(source)
        logger.info(f"Deleted: {source.name}")

    update_plan_status(plan.id, PlanStatus.EXECUTED)
    return True, "Deleted (moved to Trash)"


def _execute_archive(plan: FilePlan, source: Path) -> tuple[bool, str]:
    """Execute an archive action."""
    # Archive to Personal/Archive by default
    archive_path = settings.areas_path / "Personal" / "Archive"
    dest = archive_path / source.name

    # Handle existing file
    if dest.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{dest.stem}_{timestamp}{dest.suffix}"
        dest = archive_path / new_name

    # Backup if configured
    if settings.backup_before_move and not settings.dry_run:
        _backup_file(source)

    # Execute archive
    if settings.dry_run:
        logger.info(f"[DRY RUN] Would archive: {source} -> {dest}")
    else:
        archive_path.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        logger.info(f"Archived: {source.name} -> {dest}")

    update_plan_status(plan.id, PlanStatus.EXECUTED)
    return True, f"Archived to {dest}"


def _execute_rename(plan: FilePlan, source: Path) -> tuple[bool, str]:
    """Execute a rename action (rename in place, no move)."""
    if not plan.suggested_name:
        update_plan_status(plan.id, PlanStatus.FAILED, "No suggested name provided")
        return False, "No suggested name provided"

    new_path = source.parent / plan.suggested_name

    # Handle existing file at destination
    if new_path.exists():
        # Add counter to avoid overwrite
        counter = 1
        stem = new_path.stem
        suffix = new_path.suffix
        while new_path.exists():
            new_path = source.parent / f"{stem}-{counter}{suffix}"
            counter += 1

    # Backup if configured
    if settings.backup_before_move and not settings.dry_run:
        _backup_file(source)

    # Execute rename
    if settings.dry_run:
        logger.info(f"[DRY RUN] Would rename: {source.name} -> {new_path.name}")
    else:
        source.rename(new_path)
        logger.info(f"Renamed: {source.name} -> {new_path.name}")

    update_plan_status(plan.id, PlanStatus.EXECUTED)
    return True, f"Renamed to {new_path.name}"


def _backup_file(source: Path) -> None:
    """Create a backup of a file."""
    settings.backup_path.mkdir(parents=True, exist_ok=True)

    # Create date-based backup folder
    date_folder = settings.backup_path / datetime.now().strftime("%Y-%m-%d")
    date_folder.mkdir(exist_ok=True)

    # Copy file to backup
    backup_dest = date_folder / source.name
    if backup_dest.exists():
        timestamp = datetime.now().strftime("%H%M%S")
        backup_dest = date_folder / f"{source.stem}_{timestamp}{source.suffix}"

    shutil.copy2(str(source), str(backup_dest))
    logger.debug(f"Backed up: {source.name} -> {backup_dest}")


def _move_to_trash(source: Path) -> None:
    """Move file to macOS Trash."""
    import subprocess

    # Use osascript to move to Trash (safer than direct delete)
    script = f'''
    tell application "Finder"
        delete POSIX file "{source}"
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to move to trash: {result.stderr}")


def reject_plan(plan_id: str, reason: str = "") -> tuple[bool, str]:
    """Reject a plan."""
    plan = get_plan(plan_id)
    if not plan:
        return False, f"Plan not found: {plan_id}"

    if plan.status != PlanStatus.PENDING:
        return False, f"Plan is not pending: {plan.status.value}"

    update_plan_status(plan.id, PlanStatus.REJECTED, reason)
    return True, "Plan rejected"


def approve_plan(plan_id: str) -> tuple[bool, str]:
    """Approve and execute a plan."""
    plan = get_plan(plan_id)
    if not plan:
        return False, f"Plan not found: {plan_id}"

    if plan.status != PlanStatus.PENDING:
        return False, f"Plan is not pending: {plan.status.value}"

    # Mark as approved first
    update_plan_status(plan.id, PlanStatus.APPROVED)

    # Then execute
    return execute_plan(plan_id)
