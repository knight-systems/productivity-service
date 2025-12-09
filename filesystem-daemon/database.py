"""SQLite database for file classification plans."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .config import settings
from .models import (
    Correction,
    FileAction,
    FileCategory,
    FilePlan,
    LifeDomain,
    PlanStatus,
    PlanSummary,
)


def init_db() -> None:
    """Initialize the database schema."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_plans (
                id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                action TEXT NOT NULL,
                destination_path TEXT,
                category TEXT NOT NULL,
                domain TEXT,
                subfolder TEXT,
                confidence REAL NOT NULL,
                reasoning TEXT,
                classification_source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                executed_at TEXT,
                error_message TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON file_plans(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_path ON file_plans(source_path)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON file_plans(created_at)
        """)

        # Corrections table for learning
        conn.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                original_action TEXT NOT NULL,
                original_domain TEXT,
                original_subfolder TEXT,
                corrected_action TEXT NOT NULL,
                corrected_domain TEXT,
                corrected_subfolder TEXT,
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

        # Add new columns to file_plans if they don't exist (migration)
        try:
            conn.execute("ALTER TABLE file_plans ADD COLUMN user_feedback TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE file_plans ADD COLUMN original_plan_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE file_plans ADD COLUMN revision_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE file_plans ADD COLUMN suggested_name TEXT")
        except sqlite3.OperationalError:
            pass

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


def save_plan(plan: FilePlan) -> None:
    """Save a file plan to the database."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO file_plans
            (id, source_path, action, destination_path, category, domain,
             subfolder, confidence, reasoning, classification_source,
             created_at, status, executed_at, error_message, metadata,
             user_feedback, original_plan_id, revision_count, suggested_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan.id,
                plan.source_path,
                plan.action.value,
                plan.destination_path,
                plan.category.value,
                plan.domain.value if plan.domain else None,
                plan.subfolder,
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
                plan.suggested_name,
            ),
        )
        conn.commit()


def get_plan(plan_id: str) -> FilePlan | None:
    """Get a plan by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM file_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if row:
            return _row_to_plan(row)
    return None


def get_plan_by_source(source_path: str) -> FilePlan | None:
    """Get the most recent plan for a source path."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM file_plans
            WHERE source_path = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (source_path,),
        ).fetchone()
        if row:
            return _row_to_plan(row)
    return None


def get_pending_plans() -> list[FilePlan]:
    """Get all pending plans."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM file_plans
            WHERE status = ?
            ORDER BY created_at ASC
            """,
            (PlanStatus.PENDING.value,),
        ).fetchall()
        return [_row_to_plan(row) for row in rows]


def get_plans_by_status(status: PlanStatus) -> list[FilePlan]:
    """Get all plans with a specific status."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM file_plans
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
            UPDATE file_plans
            SET status = ?, executed_at = ?, error_message = ?
            WHERE id = ?
            """,
            (status.value, executed_at, error_message, plan_id),
        )
        conn.commit()
        return result.rowcount > 0


def delete_plan(plan_id: str) -> bool:
    """Delete a plan by ID."""
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM file_plans WHERE id = ?", (plan_id,)
        )
        conn.commit()
        return result.rowcount > 0


def get_summary() -> PlanSummary:
    """Get a summary of pending plans."""
    plans = get_pending_plans()

    by_action: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    by_category: dict[str, int] = {}
    total_size = 0

    for plan in plans:
        # Count by action
        action = plan.action.value
        by_action[action] = by_action.get(action, 0) + 1

        # Count by domain
        if plan.domain:
            domain = plan.domain.value
            by_domain[domain] = by_domain.get(domain, 0) + 1

        # Count by category
        category = plan.category.value
        by_category[category] = by_category.get(category, 0) + 1

        # Estimate space freed for delete actions
        if plan.action == FileAction.DELETE:
            try:
                total_size += Path(plan.source_path).stat().st_size
            except OSError:
                pass

    return PlanSummary(
        total_plans=len(plans),
        by_action=by_action,
        by_domain=by_domain,
        by_category=by_category,
        estimated_space_freed_bytes=total_size,
    )


def cleanup_old_plans(days: int = 30) -> int:
    """Delete executed/rejected plans older than N days."""
    with get_connection() as conn:
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = cutoff.replace(day=cutoff.day - days)
        result = conn.execute(
            """
            DELETE FROM file_plans
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


def _row_to_plan(row: sqlite3.Row) -> FilePlan:
    """Convert a database row to a FilePlan."""
    return FilePlan(
        id=row["id"],
        source_path=row["source_path"],
        action=FileAction(row["action"]),
        destination_path=row["destination_path"],
        category=FileCategory(row["category"]),
        domain=LifeDomain(row["domain"]) if row["domain"] else None,
        subfolder=row["subfolder"],
        confidence=row["confidence"],
        reasoning=row["reasoning"] or "",
        classification_source=row["classification_source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        status=PlanStatus(row["status"]),
        executed_at=datetime.fromisoformat(row["executed_at"]) if row["executed_at"] else None,
        error_message=row["error_message"],
        metadata=eval(row["metadata"]) if row["metadata"] else {},
        # New fields (handle missing columns gracefully)
        user_feedback=row["user_feedback"] if "user_feedback" in row.keys() else None,
        original_plan_id=row["original_plan_id"] if "original_plan_id" in row.keys() else None,
        revision_count=row["revision_count"] if "revision_count" in row.keys() else 0,
        suggested_name=row["suggested_name"] if "suggested_name" in row.keys() else None,
    )


# ============ Corrections (Learning) ============


def save_correction(correction: Correction) -> None:
    """Save a correction to the database."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO corrections
            (id, created_at, original_filename, original_action, original_domain,
             original_subfolder, corrected_action, corrected_domain, corrected_subfolder,
             user_feedback, filename_pattern, keywords, times_applied, last_applied)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                correction.id,
                correction.created_at.isoformat(),
                correction.original_filename,
                correction.original_action.value,
                correction.original_domain.value if correction.original_domain else None,
                correction.original_subfolder,
                correction.corrected_action.value,
                correction.corrected_domain.value if correction.corrected_domain else None,
                correction.corrected_subfolder,
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
            import re
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
        original_action=FileAction(row["original_action"]),
        original_domain=LifeDomain(row["original_domain"]) if row["original_domain"] else None,
        original_subfolder=row["original_subfolder"],
        corrected_action=FileAction(row["corrected_action"]),
        corrected_domain=LifeDomain(row["corrected_domain"]) if row["corrected_domain"] else None,
        corrected_subfolder=row["corrected_subfolder"],
        user_feedback=row["user_feedback"],
        filename_pattern=row["filename_pattern"],
        keywords=row["keywords"].split(",") if row["keywords"] else [],
        times_applied=row["times_applied"],
        last_applied=datetime.fromisoformat(row["last_applied"]) if row["last_applied"] else None,
    )
