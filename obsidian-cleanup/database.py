"""SQLite database for note classification plans."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .config import settings
from .models import (
    Correction,
    NoteAction,
    NotePlan,
    PlanStatus,
    PlanSummary,
)


def init_db() -> None:
    """Initialize the database schema."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS note_plans (
                id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                action TEXT NOT NULL,
                destination_path TEXT,
                target_area TEXT,
                confidence REAL NOT NULL,
                reasoning TEXT,
                classification_source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                executed_at TEXT,
                error_message TEXT,
                metadata TEXT,
                user_feedback TEXT,
                original_plan_id TEXT,
                revision_count INTEGER DEFAULT 0,
                frontmatter_category TEXT,
                frontmatter_tags TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON note_plans(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_path ON note_plans(source_path)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON note_plans(created_at)
        """)

        # Corrections table for learning
        conn.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                original_action TEXT NOT NULL,
                original_area TEXT,
                corrected_action TEXT NOT NULL,
                corrected_area TEXT,
                user_feedback TEXT NOT NULL,
                filename_pattern TEXT,
                keywords TEXT,
                times_applied INTEGER DEFAULT 0,
                last_applied TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_corrections_keywords ON corrections(keywords)
        """)

        conn.commit()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Get a database connection."""
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_plan(plan: NotePlan) -> None:
    """Save a note plan to the database."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO note_plans
            (id, source_path, action, destination_path, target_area, confidence,
             reasoning, classification_source, created_at, status, executed_at,
             error_message, metadata, user_feedback, original_plan_id, revision_count,
             frontmatter_category, frontmatter_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan.id,
                plan.source_path,
                plan.action.value,
                plan.destination_path,
                plan.target_area,
                plan.confidence,
                plan.reasoning,
                plan.classification_source,
                plan.created_at.isoformat(),
                plan.status.value,
                plan.executed_at.isoformat() if plan.executed_at else None,
                plan.error_message,
                str(plan.metadata) if plan.metadata else None,
                plan.user_feedback,
                plan.original_plan_id,
                plan.revision_count,
                plan.frontmatter_category,
                ",".join(plan.frontmatter_tags) if plan.frontmatter_tags else None,
            ),
        )
        conn.commit()


def get_plan(plan_id: str) -> NotePlan | None:
    """Get a plan by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM note_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if row:
            return _row_to_plan(row)
    return None


def get_plan_by_source(source_path: str) -> NotePlan | None:
    """Get the most recent plan for a source path."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM note_plans
            WHERE source_path = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (source_path,),
        ).fetchone()
        if row:
            return _row_to_plan(row)
    return None


def get_pending_plans() -> list[NotePlan]:
    """Get all pending plans."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM note_plans
            WHERE status = ?
            ORDER BY created_at ASC
            """,
            (PlanStatus.PENDING.value,),
        ).fetchall()
        return [_row_to_plan(row) for row in rows]


def get_plans_by_status(status: PlanStatus) -> list[NotePlan]:
    """Get all plans with a specific status."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM note_plans
            WHERE status = ?
            ORDER BY created_at DESC
            """,
            (status.value,),
        ).fetchall()
        return [_row_to_plan(row) for row in rows]


def update_plan_status(
    plan_id: str,
    status: PlanStatus,
    error_message: str | None = None,
) -> bool:
    """Update a plan's status."""
    with get_connection() as conn:
        executed_at = datetime.now().isoformat() if status == PlanStatus.EXECUTED else None
        result = conn.execute(
            """
            UPDATE note_plans
            SET status = ?, executed_at = ?, error_message = ?
            WHERE id = ?
            """,
            (status.value, executed_at, error_message, plan_id),
        )
        conn.commit()
        return result.rowcount > 0


def update_plan(plan: NotePlan) -> bool:
    """Update an existing plan."""
    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE note_plans
            SET action = ?, destination_path = ?, target_area = ?, confidence = ?,
                reasoning = ?, status = ?
            WHERE id = ?
            """,
            (
                plan.action.value,
                plan.destination_path,
                plan.target_area,
                plan.confidence,
                plan.reasoning,
                plan.status.value,
                plan.id,
            ),
        )
        conn.commit()
        return result.rowcount > 0


def delete_plan(plan_id: str) -> bool:
    """Delete a plan by ID."""
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM note_plans WHERE id = ?", (plan_id,)
        )
        conn.commit()
        return result.rowcount > 0


def get_summary() -> PlanSummary:
    """Get a summary of pending plans."""
    plans = get_pending_plans()

    by_action: dict[str, int] = {}
    by_area: dict[str, int] = {}

    for plan in plans:
        # Count by action
        action = plan.action.value
        by_action[action] = by_action.get(action, 0) + 1

        # Count by area
        if plan.target_area:
            by_area[plan.target_area] = by_area.get(plan.target_area, 0) + 1

    return PlanSummary(
        total_plans=len(plans),
        by_action=by_action,
        by_area=by_area,
    )


def cleanup_old_plans(days: int = 30) -> int:
    """Delete executed/rejected plans older than N days."""
    from datetime import timedelta

    with get_connection() as conn:
        cutoff = datetime.now() - timedelta(days=days)
        result = conn.execute(
            """
            DELETE FROM note_plans
            WHERE status IN (?, ?, ?)
            AND created_at < ?
            """,
            (
                PlanStatus.EXECUTED.value,
                PlanStatus.REJECTED.value,
                PlanStatus.FAILED.value,
                cutoff.isoformat(),
            ),
        )
        conn.commit()
        return result.rowcount


def _row_to_plan(row: sqlite3.Row) -> NotePlan:
    """Convert a database row to a NotePlan."""
    return NotePlan(
        id=row["id"],
        source_path=row["source_path"],
        action=NoteAction(row["action"]),
        destination_path=row["destination_path"],
        target_area=row["target_area"],
        confidence=row["confidence"],
        reasoning=row["reasoning"] or "",
        classification_source=row["classification_source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        status=PlanStatus(row["status"]),
        executed_at=(
            datetime.fromisoformat(row["executed_at"]) if row["executed_at"] else None
        ),
        error_message=row["error_message"],
        metadata=eval(row["metadata"]) if row["metadata"] else {},
        user_feedback=row["user_feedback"],
        original_plan_id=row["original_plan_id"],
        revision_count=row["revision_count"] or 0,
        frontmatter_category=row["frontmatter_category"],
        frontmatter_tags=(
            row["frontmatter_tags"].split(",") if row["frontmatter_tags"] else []
        ),
    )


# ============ Corrections (Learning) ============


def save_correction(correction: Correction) -> None:
    """Save a correction to the database."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO corrections
            (id, created_at, original_filename, original_action, original_area,
             corrected_action, corrected_area, user_feedback, filename_pattern,
             keywords, times_applied, last_applied)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                correction.id,
                correction.created_at.isoformat(),
                correction.original_filename,
                correction.original_action.value,
                correction.original_area,
                correction.corrected_action.value,
                correction.corrected_area,
                correction.user_feedback,
                correction.filename_pattern,
                ",".join(correction.keywords) if correction.keywords else None,
                correction.times_applied,
                correction.last_applied.isoformat() if correction.last_applied else None,
            ),
        )
        conn.commit()


def get_all_corrections() -> list[Correction]:
    """Get all corrections, ordered by most used."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM corrections
            ORDER BY times_applied DESC, created_at DESC
            """
        ).fetchall()
        return [_row_to_correction(row) for row in rows]


def get_relevant_corrections(filename: str, limit: int = 10) -> list[Correction]:
    """Get corrections that might be relevant for a filename.

    Uses keyword matching and pattern matching to find similar corrections.
    """
    import re

    corrections = get_all_corrections()
    relevant = []

    filename_lower = filename.lower()

    for correction in corrections:
        score = 0

        # Check keyword matches
        for keyword in correction.keywords:
            if keyword.lower() in filename_lower:
                score += 2

        # Check pattern match
        if correction.filename_pattern:
            try:
                if re.search(correction.filename_pattern, filename, re.IGNORECASE):
                    score += 5
            except re.error:
                pass

        # Check filename similarity
        if correction.original_filename.lower() in filename_lower:
            score += 3

        if score > 0:
            relevant.append((score, correction))

    # Sort by score and return top matches
    relevant.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in relevant[:limit]]


def increment_correction_usage(correction_id: str) -> None:
    """Increment the usage count for a correction."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE corrections
            SET times_applied = times_applied + 1, last_applied = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(), correction_id),
        )
        conn.commit()


def _row_to_correction(row: sqlite3.Row) -> Correction:
    """Convert a database row to a Correction."""
    return Correction(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        original_filename=row["original_filename"],
        original_action=NoteAction(row["original_action"]),
        original_area=row["original_area"],
        corrected_action=NoteAction(row["corrected_action"]),
        corrected_area=row["corrected_area"],
        user_feedback=row["user_feedback"],
        filename_pattern=row["filename_pattern"],
        keywords=row["keywords"].split(",") if row["keywords"] else [],
        times_applied=row["times_applied"],
        last_applied=(
            datetime.fromisoformat(row["last_applied"]) if row["last_applied"] else None
        ),
    )
