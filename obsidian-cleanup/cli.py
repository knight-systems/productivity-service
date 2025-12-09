"""CLI for obsidian-cleanup module."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .classifier import classify_batch_with_ai, classify_with_ai, extract_correction_pattern
from .config import AreaFolder, ensure_directories, get_area_path, settings
from .database import (
    cleanup_old_plans,
    delete_plan,
    get_all_corrections,
    get_pending_plans,
    get_plan,
    get_plans_by_status,
    get_summary,
    init_db,
    save_correction,
    save_plan,
    update_plan,
    update_plan_status,
)
from .executor import dry_run_plan, execute_all_approved
from .models import Correction, NoteAction, NotePlan, PlanStatus
from .rules import classify_note, needs_ai_classification

app = typer.Typer(help="Obsidian vault cleanup tool")
console = Console()

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@app.command()
def init():
    """Initialize database and verify vault path."""
    console.print("[bold]Initializing Obsidian Cleanup...[/bold]")

    # Check vault path
    if not settings.vault_path.exists():
        console.print(f"[red]Vault not found: {settings.vault_path}[/red]")
        console.print("Set OBSIDIAN_CLEANUP_VAULT_PATH environment variable")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Vault found: {settings.vault_path}")

    # Initialize database
    init_db()
    console.print(f"[green]✓[/green] Database: {settings.db_path}")

    # Ensure directories exist
    ensure_directories()
    console.print("[green]✓[/green] Directory structure verified")

    console.print("\n[bold green]Ready![/bold green]")
    console.print("\nRun: [cyan]uv run python -m obsidian-cleanup.cli organize[/cyan]")


@app.command()
def organize(
    path: str = typer.Argument(
        None,
        help="Path to scan (default: vault root)",
    ),
    ai: bool = typer.Option(
        True,
        "--ai/--no-ai",
        help="Use AI for low-confidence classifications",
    ),
):
    """Interactive organize workflow: scan → review → execute."""
    init_db()

    # Determine scan path
    scan_path = Path(path) if path else settings.vault_path
    if not scan_path.exists():
        console.print(f"[red]Path not found: {scan_path}[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]Obsidian Vault Cleanup[/bold]\n"
        f"Scanning: {scan_path}\n"
        f"AI: {'enabled' if ai else 'disabled'}",
        title="organize",
    ))

    # Step 1: Scan and classify notes
    console.print("\n[bold]Step 1: Scanning notes...[/bold]")
    notes = list(scan_path.rglob("*.md"))
    console.print(f"Found {len(notes)} markdown files")

    # Filter out protected paths
    notes_to_classify = []
    for note in notes:
        from .config import is_protected_path
        if not is_protected_path(note):
            notes_to_classify.append(note)

    console.print(f"After filtering protected folders: {len(notes_to_classify)} notes")

    if not notes_to_classify:
        console.print("[yellow]No notes to organize![/yellow]")
        raise typer.Exit(0)

    # Step 2: Classify notes
    console.print("\n[bold]Step 2: Classifying notes...[/bold]")
    plans: list[NotePlan] = []
    low_confidence: list[Path] = []

    for note in notes_to_classify:
        plan = classify_note(note)
        if needs_ai_classification(plan):
            low_confidence.append(note)
        else:
            plans.append(plan)
            save_plan(plan)

    console.print(f"Rules classified: {len(plans)} notes")
    console.print(f"Need AI: {len(low_confidence)} notes")

    # Step 3: AI classification for low-confidence notes
    if ai and low_confidence:
        console.print("\n[bold]Step 3: AI classification...[/bold]")
        corrections = get_all_corrections()

        # Batch classify in groups of 10
        for i in range(0, len(low_confidence), 10):
            batch = low_confidence[i : i + 10]
            console.print(f"  Classifying batch {i//10 + 1}...")
            ai_plans = classify_batch_with_ai(batch, learned_corrections=corrections)
            for plan in ai_plans:
                plans.append(plan)
                save_plan(plan)

    # Step 4: Show summary
    console.print("\n[bold]Step 4: Review classification results...[/bold]")
    _show_plans_table(plans)

    # Filter to only actionable plans (not SKIP)
    actionable = [p for p in plans if p.action != NoteAction.SKIP]
    console.print(f"\nActionable plans: {len(actionable)}")

    if not actionable:
        console.print("[yellow]No notes need organizing![/yellow]")
        raise typer.Exit(0)

    # Step 5: Interactive review
    console.print("\n[bold]Step 5: Interactive review[/bold]")
    console.print("Press: [green]a[/green]=approve [red]r[/red]=reject [yellow]e[/yellow]=edit [cyan]s[/cyan]=skip [blue]A[/blue]=approve all [magenta]q[/magenta]=quit\n")

    approved_count = 0
    for plan in actionable:
        result = _review_plan_interactive(plan)
        if result == "quit":
            break
        if result == "approve_all":
            # Approve remaining plans
            for remaining in actionable[actionable.index(plan) :]:
                remaining.status = PlanStatus.APPROVED
                update_plan(remaining)
                approved_count += 1
            break
        if result == "approved":
            approved_count += 1

    console.print(f"\n[green]Approved: {approved_count} plans[/green]")

    # Step 6: Execute
    if approved_count > 0:
        execute = typer.confirm("\nExecute approved plans?", default=True)
        if execute:
            console.print("\n[bold]Step 6: Executing...[/bold]")
            results = execute_all_approved()
            executed = sum(1 for _, success, _ in results if success)
            failed = sum(1 for _, success, _ in results if not success)
            console.print(f"[green]✓ Executed: {executed}[/green]")
            if failed:
                console.print(f"[red]✗ Failed: {failed}[/red]")
        else:
            console.print("[yellow]Execution cancelled.[/yellow]")

    console.print("\n[bold green]Done![/bold green]")


def _show_plans_table(plans: list[NotePlan]):
    """Show plans in a table format."""
    table = Table(title="Classification Results")
    table.add_column("ID", style="dim")
    table.add_column("Note", style="cyan")
    table.add_column("Action", style="bold")
    table.add_column("Target", style="green")
    table.add_column("Conf", justify="right")
    table.add_column("Source", style="dim")

    for plan in plans[:50]:  # Limit to 50 for display
        action_style = {
            NoteAction.MOVE: "green",
            NoteAction.ARCHIVE: "yellow",
            NoteAction.SKIP: "dim",
        }.get(plan.action, "white")

        conf_style = "green" if plan.confidence >= 0.8 else "yellow" if plan.confidence >= 0.5 else "red"

        table.add_row(
            plan.id,
            plan.source_name[:40],
            f"[{action_style}]{plan.action.value}[/{action_style}]",
            (plan.target_area or "-")[:20],
            f"[{conf_style}]{plan.confidence:.0%}[/{conf_style}]",
            plan.classification_source[:6],
        )

    console.print(table)

    if len(plans) > 50:
        console.print(f"[dim]...and {len(plans) - 50} more[/dim]")


def _review_plan_interactive(plan: NotePlan) -> str:
    """Interactive review of a single plan.

    Returns: 'approved', 'rejected', 'skipped', 'approve_all', or 'quit'
    """
    console.print(f"\n[bold]{plan.source_name}[/bold]")
    console.print(f"  Action: [cyan]{plan.action.value}[/cyan] -> [green]{plan.target_area or 'archive'}[/green]")
    console.print(f"  Confidence: {plan.confidence:.0%} ({plan.classification_source})")
    console.print(f"  Reason: {plan.reasoning[:60]}")

    while True:
        choice = console.input("[a/r/e/s/A/q] > ").strip().lower()

        if choice == "a":
            plan.status = PlanStatus.APPROVED
            update_plan(plan)
            console.print("  [green]✓ Approved[/green]")
            return "approved"

        elif choice == "r":
            plan.status = PlanStatus.REJECTED
            update_plan(plan)
            console.print("  [red]✗ Rejected[/red]")
            return "rejected"

        elif choice == "e":
            _edit_plan(plan)
            return "approved"

        elif choice == "s":
            console.print("  [yellow]→ Skipped[/yellow]")
            return "skipped"

        elif choice == "A":
            plan.status = PlanStatus.APPROVED
            update_plan(plan)
            console.print("  [green]✓ Approved (and all remaining)[/green]")
            return "approve_all"

        elif choice == "q":
            return "quit"

        else:
            console.print("[dim]Invalid choice[/dim]")


def _edit_plan(plan: NotePlan):
    """Edit a plan interactively."""
    console.print("\n  [bold]Edit plan[/bold]")
    console.print(f"  Current: {plan.action.value} -> {plan.target_area}")

    # Choose action
    console.print("  Actions: [1] move [2] archive [3] skip")
    action_choice = console.input("  Action [1/2/3]: ").strip()
    if action_choice == "1":
        plan.action = NoteAction.MOVE
    elif action_choice == "2":
        plan.action = NoteAction.ARCHIVE
    elif action_choice == "3":
        plan.action = NoteAction.SKIP

    # Choose target area (if moving)
    if plan.action == NoteAction.MOVE:
        console.print("  Areas:")
        for i, area in enumerate(AreaFolder.ALL, 1):
            console.print(f"    [{i}] {area}")
        area_choice = console.input("  Area [1-6]: ").strip()
        try:
            idx = int(area_choice) - 1
            if 0 <= idx < len(AreaFolder.ALL):
                plan.target_area = AreaFolder.ALL[idx]
                plan.destination_path = str(get_area_path(plan.target_area, plan.source_name))
        except ValueError:
            pass

    plan.status = PlanStatus.APPROVED
    plan.reasoning = "User edited"
    update_plan(plan)
    console.print(f"  [green]✓ Updated: {plan.action.value} -> {plan.target_area}[/green]")


@app.command()
def pending():
    """Show pending plans."""
    init_db()
    plans = get_pending_plans()

    if not plans:
        console.print("[yellow]No pending plans[/yellow]")
        return

    _show_plans_table(plans)


@app.command()
def show(plan_id: str):
    """Show details of a specific plan."""
    init_db()
    plan = get_plan(plan_id)

    if not plan:
        console.print(f"[red]Plan not found: {plan_id}[/red]")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold]Plan {plan.id}[/bold]\n\n"
        f"Source: {plan.source_path}\n"
        f"Action: {plan.action.value}\n"
        f"Target: {plan.target_area or 'N/A'}\n"
        f"Destination: {plan.destination_path or 'N/A'}\n"
        f"Confidence: {plan.confidence:.0%}\n"
        f"Source: {plan.classification_source}\n"
        f"Status: {plan.status.value}\n"
        f"Reasoning: {plan.reasoning}\n"
        f"Frontmatter category: {plan.frontmatter_category or 'N/A'}\n"
        f"Frontmatter tags: {', '.join(plan.frontmatter_tags) if plan.frontmatter_tags else 'N/A'}",
    ))


@app.command()
def review():
    """Interactive review of pending plans."""
    init_db()
    plans = get_pending_plans()

    if not plans:
        console.print("[yellow]No pending plans to review[/yellow]")
        return

    console.print(f"[bold]Reviewing {len(plans)} pending plans[/bold]")
    console.print("Press: [green]a[/green]=approve [red]r[/red]=reject [yellow]e[/yellow]=edit [cyan]s[/cyan]=skip [blue]A[/blue]=approve all [magenta]q[/magenta]=quit\n")

    approved_count = 0
    for plan in plans:
        result = _review_plan_interactive(plan)
        if result == "quit":
            break
        if result == "approve_all":
            for remaining in plans[plans.index(plan) :]:
                remaining.status = PlanStatus.APPROVED
                update_plan(remaining)
                approved_count += 1
            break
        if result == "approved":
            approved_count += 1

    console.print(f"\n[green]Approved: {approved_count} plans[/green]")


@app.command()
def revise(plan_id: str, feedback: str):
    """Revise a plan based on user feedback and learn from it."""
    init_db()
    plan = get_plan(plan_id)

    if not plan:
        console.print(f"[red]Plan not found: {plan_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Revising plan for: {plan.source_name}[/bold]")
    console.print(f"Original: {plan.action.value} -> {plan.target_area}")
    console.print(f"Feedback: {feedback}")

    # Use AI to reclassify with feedback
    note_path = Path(plan.source_path)
    corrections = get_all_corrections()

    new_plan = classify_with_ai(
        note_path,
        existing_plan=plan,
        user_feedback=feedback,
        learned_corrections=corrections,
    )

    # Save the revision
    save_plan(new_plan)
    update_plan_status(plan.id, PlanStatus.REVISED)

    console.print(f"[green]New plan: {new_plan.action.value} -> {new_plan.target_area}[/green]")
    console.print(f"Reasoning: {new_plan.reasoning}")

    # Learn from this correction
    learn = typer.confirm("Save this as a learned correction?", default=True)
    if learn:
        correction = Correction(
            original_filename=plan.source_name,
            original_action=plan.action,
            original_area=plan.target_area,
            corrected_action=new_plan.action,
            corrected_area=new_plan.target_area,
            user_feedback=feedback,
        )
        correction = extract_correction_pattern(correction)
        save_correction(correction)
        console.print(f"[green]✓ Correction saved with keywords: {correction.keywords}[/green]")


@app.command()
def corrections():
    """Show learned corrections."""
    init_db()
    all_corrections = get_all_corrections()

    if not all_corrections:
        console.print("[yellow]No corrections learned yet[/yellow]")
        return

    table = Table(title="Learned Corrections")
    table.add_column("ID", style="dim")
    table.add_column("Original", style="cyan")
    table.add_column("Corrected", style="green")
    table.add_column("Keywords", style="yellow")
    table.add_column("Used", justify="right")

    for c in all_corrections:
        table.add_row(
            c.id,
            f"{c.original_action.value} -> {c.original_area or '-'}",
            f"{c.corrected_action.value} -> {c.corrected_area or '-'}",
            ", ".join(c.keywords[:3]) if c.keywords else "-",
            str(c.times_applied),
        )

    console.print(table)


@app.command()
def history(limit: int = 20):
    """Show execution history."""
    init_db()
    executed = get_plans_by_status(PlanStatus.EXECUTED)[:limit]
    failed = get_plans_by_status(PlanStatus.FAILED)[:limit]

    if not executed and not failed:
        console.print("[yellow]No history yet[/yellow]")
        return

    if executed:
        console.print(f"\n[bold green]Executed ({len(executed)})[/bold green]")
        for plan in executed[:10]:
            console.print(f"  ✓ {plan.source_name} -> {plan.target_area}")

    if failed:
        console.print(f"\n[bold red]Failed ({len(failed)})[/bold red]")
        for plan in failed[:10]:
            console.print(f"  ✗ {plan.source_name}: {plan.error_message}")


@app.command()
def cleanup(days: int = 30):
    """Clean up old plans from database."""
    init_db()
    count = cleanup_old_plans(days)
    console.print(f"[green]Cleaned up {count} old plans[/green]")


@app.command()
def config():
    """Show current configuration."""
    console.print(Panel.fit(
        f"[bold]Configuration[/bold]\n\n"
        f"Vault path: {settings.vault_path}\n"
        f"Database: {settings.db_path}\n"
        f"Areas folder: {settings.areas_folder}\n"
        f"Archive folder: {settings.archive_folder}\n"
        f"AI enabled: {settings.ai_enabled}\n"
        f"AI threshold: {settings.ai_confidence_threshold}\n"
        f"Protected: {', '.join(settings.protected_folders)}",
    ))


if __name__ == "__main__":
    app()
