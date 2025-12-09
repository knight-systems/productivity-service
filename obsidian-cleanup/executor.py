"""Execute note organization plans."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .config import settings
from .database import get_plans_by_status, update_plan_status
from .models import NoteAction, NotePlan, PlanStatus

logger = logging.getLogger(__name__)


def execute_plan(plan: NotePlan) -> tuple[bool, str]:
    """Execute a single note plan.

    Returns:
        Tuple of (success, message)
    """
    source = Path(plan.source_path)

    # Check if source exists
    if not source.exists():
        message = f"Source note not found: {source}"
        update_plan_status(plan.id, PlanStatus.FAILED, message)
        return False, message

    if plan.action == NoteAction.SKIP:
        message = "Skipped (no action needed)"
        update_plan_status(plan.id, PlanStatus.EXECUTED)
        return True, message

    if plan.action in (NoteAction.MOVE, NoteAction.ARCHIVE):
        if not plan.destination_path:
            message = "No destination path specified"
            update_plan_status(plan.id, PlanStatus.FAILED, message)
            return False, message

        destination = Path(plan.destination_path)

        # Create destination directory if needed
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Check for existing file at destination
        if destination.exists():
            # Generate unique name
            base = destination.stem
            suffix = destination.suffix
            counter = 1
            while destination.exists():
                destination = destination.parent / f"{base}_{counter}{suffix}"
                counter += 1
            logger.info(f"Renamed to avoid conflict: {destination.name}")

        try:
            # Move the file
            shutil.move(str(source), str(destination))
            message = f"Moved to {destination.parent.name}/{destination.name}"
            update_plan_status(plan.id, PlanStatus.EXECUTED)
            logger.info(f"Executed: {plan.source_name} -> {destination}")
            return True, message

        except Exception as e:
            message = f"Move failed: {e}"
            update_plan_status(plan.id, PlanStatus.FAILED, message)
            logger.error(message)
            return False, message

    message = f"Unknown action: {plan.action}"
    update_plan_status(plan.id, PlanStatus.FAILED, message)
    return False, message


def execute_all_approved() -> list[tuple[str, bool, str]]:
    """Execute all approved plans.

    Returns:
        List of (plan_id, success, message) tuples
    """
    results: list[tuple[str, bool, str]] = []

    # Get approved plans (plans that have been reviewed)
    plans = get_plans_by_status(PlanStatus.APPROVED)

    for plan in plans:
        success, message = execute_plan(plan)
        results.append((plan.id, success, message))

    return results


def dry_run_plan(plan: NotePlan) -> str:
    """Show what would happen if a plan were executed.

    Returns:
        Description of the action that would be taken
    """
    source = Path(plan.source_path)

    if not source.exists():
        return f"[ERROR] Source not found: {source}"

    if plan.action == NoteAction.SKIP:
        return f"[SKIP] {source.name} (no action)"

    if plan.action == NoteAction.MOVE:
        return f"[MOVE] {source.name} -> {plan.target_area}/"

    if plan.action == NoteAction.ARCHIVE:
        return f"[ARCHIVE] {source.name} -> {settings.archive_folder}/"

    return f"[UNKNOWN] {source.name}"
