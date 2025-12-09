"""CLI interface for file classifier daemon."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import ensure_directories, settings
from .database import (
    cleanup_old_plans,
    get_all_corrections,
    get_pending_plans,
    get_plan,
    get_plans_by_status,
    get_relevant_corrections,
    init_db,
    save_correction,
    save_plan,
    update_plan_status,
)
from .executor import execute_all_pending
from .models import Correction, FileAction, FileCategory, PlanStatus
from .rules import classify_file

app = typer.Typer(help="File classifier daemon CLI")
console = Console()


@app.command()
def init():
    """Initialize database and directories."""
    init_db()
    ensure_directories()
    console.print("[green]Initialized database and directories[/green]")


@app.command()
def pending():
    """Show pending plans."""
    plans = get_pending_plans()

    if not plans:
        console.print("[yellow]No pending plans[/yellow]")
        return

    table = Table(title=f"Pending Plans ({len(plans)})")
    table.add_column("ID", style="cyan")
    table.add_column("File")
    table.add_column("Action", style="green")
    table.add_column("Domain")
    table.add_column("Confidence")

    for plan in plans:
        action_color = {
            FileAction.MOVE: "green",
            FileAction.DELETE: "red",
            FileAction.ARCHIVE: "yellow",
            FileAction.SKIP: "dim",
            FileAction.RENAME: "cyan",
        }.get(plan.action, "white")

        rename_suffix = f" ({plan.suggested_name[:15]}...)" if plan.suggested_name else ""
        table.add_row(
            plan.id,
            plan.source_name[:30],
            f"[{action_color}]{plan.action.value}{rename_suffix}[/{action_color}]",
            plan.domain.value if plan.domain else "-",
            f"{plan.confidence:.0%}",
        )

    console.print(table)


@app.command()
def show(plan_id: str):
    """Show details of a specific plan."""
    plan = get_plan(plan_id)

    if not plan:
        console.print(f"[red]Plan not found: {plan_id}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Plan {plan.id}[/bold]")
    console.print(f"  Status: {plan.status.value}")
    console.print(f"  Source: {plan.source_path}")
    console.print(f"  Action: {plan.action.value}")
    console.print(f"  Category: {plan.category.value}")
    console.print(f"  Domain: {plan.domain.value if plan.domain else 'Unknown'}")
    console.print(f"  Subfolder: {plan.subfolder or 'N/A'}")
    console.print(f"  Confidence: {plan.confidence:.0%}")
    console.print(f"  Source: {plan.classification_source}")
    console.print(f"  Reasoning: {plan.reasoning}")
    console.print(f"  Created: {plan.created_at}")
    if plan.destination_path:
        console.print(f"  Destination: {plan.destination_path}")
    if plan.suggested_name:
        console.print(f"  Suggested name: [cyan]{plan.suggested_name}[/cyan]")
    if plan.executed_at:
        console.print(f"  Executed: {plan.executed_at}")
    if plan.error_message:
        console.print(f"  Error: {plan.error_message}")


@app.command()
def history(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of results"),
):
    """Show plan history."""
    if status:
        try:
            plan_status = PlanStatus(status)
            plans = get_plans_by_status(plan_status)[:limit]
        except ValueError:
            console.print(f"[red]Invalid status: {status}[/red]")
            console.print(f"Valid statuses: {[s.value for s in PlanStatus]}")
            raise typer.Exit(1)
    else:
        # Get all plans sorted by date
        from .database import get_connection

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM file_plans ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            from .database import _row_to_plan

            plans = [_row_to_plan(row) for row in rows]

    if not plans:
        console.print("[yellow]No plans found[/yellow]")
        return

    table = Table(title="Plan History")
    table.add_column("ID", style="cyan")
    table.add_column("File")
    table.add_column("Action")
    table.add_column("Status")
    table.add_column("Created")

    for plan in plans:
        status_color = {
            PlanStatus.PENDING: "yellow",
            PlanStatus.APPROVED: "blue",
            PlanStatus.EXECUTED: "green",
            PlanStatus.REJECTED: "red",
            PlanStatus.FAILED: "red",
        }.get(plan.status, "white")

        table.add_row(
            plan.id,
            plan.source_name[:30],
            plan.action.value,
            f"[{status_color}]{plan.status.value}[/{status_color}]",
            plan.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@app.command()
def cleanup(days: int = typer.Option(30, "--days", "-d", help="Delete plans older than N days")):
    """Cleanup old executed/rejected plans."""
    count = cleanup_old_plans(days)
    console.print(f"[green]Deleted {count} old plans[/green]")


@app.command()
def watch():
    """Start the file watcher daemon."""
    from .watcher import main as watcher_main

    watcher_main()


@app.command()
def config():
    """Show current configuration."""
    console.print("\n[bold]Configuration[/bold]")
    console.print(f"  Desktop path: {settings.desktop_path}")
    console.print(f"  Downloads path: {settings.downloads_path}")
    console.print(f"  Areas path: {settings.areas_path}")
    console.print(f"  DB path: {settings.db_path}")
    console.print(f"  Backup path: {settings.backup_path}")
    console.print(f"  Watch Desktop: {settings.watch_desktop}")
    console.print(f"  Watch Downloads: {settings.watch_downloads}")
    console.print(f"  AI enabled: {settings.ai_enabled}")
    console.print(f"  AI threshold: {settings.ai_confidence_threshold}")
    console.print(f"  Debounce: {settings.debounce_seconds}s")
    console.print(f"  Dry run: {settings.dry_run}")


# ============ Revision & Learning Commands ============


@app.command()
def revise(
    plan_id: str,
    feedback: str = typer.Argument(..., help="Natural language feedback (e.g., 'this is a health document')"),
):
    """Revise a plan using natural language feedback.

    The AI will reclassify the file based on your feedback and learn
    from the correction to improve future classifications.

    Examples:
        revise abc123 "this is a trading doc, put it in Finance/Research"
        revise abc123 "this is my blood pressure log"
        revise abc123 "delete this, it's just an old installer"
    """
    from pathlib import Path

    from .classifier import classify_with_ai, extract_correction_pattern

    plan = get_plan(plan_id)
    if not plan:
        console.print(f"[red]Plan not found: {plan_id}[/red]")
        raise typer.Exit(1)

    if plan.status not in [PlanStatus.PENDING, PlanStatus.REVISED]:
        console.print(f"[red]Plan cannot be revised (status: {plan.status.value})[/red]")
        raise typer.Exit(1)

    file_path = Path(plan.source_path)
    if not file_path.exists():
        console.print(f"[red]File no longer exists: {plan.source_path}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Revising plan {plan_id}...[/bold]")
    console.print(f"  File: {plan.source_name}")
    console.print(f"  Current: {plan.action.value} -> {plan.domain.value if plan.domain else 'None'}/{plan.subfolder or 'None'}")
    console.print(f"  Feedback: \"{feedback}\"")

    # Get relevant past corrections for context
    corrections = get_relevant_corrections(plan.source_name)

    # Use AI to reclassify with feedback
    console.print("\n[dim]Calling AI for reclassification...[/dim]")
    new_plan = classify_with_ai(
        file_path=file_path,
        existing_plan=plan,
        user_feedback=feedback,
        learned_corrections=corrections,
    )

    # Mark old plan as revised
    update_plan_status(plan_id, PlanStatus.REVISED)

    # Save new plan
    save_plan(new_plan)

    console.print(f"\n[green]New classification:[/green]")
    console.print(f"  Plan ID: {new_plan.id}")
    console.print(f"  Action: {new_plan.action.value}")
    console.print(f"  Domain: {new_plan.domain.value if new_plan.domain else 'None'}")
    console.print(f"  Subfolder: {new_plan.subfolder or 'None'}")
    console.print(f"  Confidence: {new_plan.confidence:.0%}")
    console.print(f"  Reasoning: {new_plan.reasoning}")

    # Create a correction record for learning
    correction = Correction(
        original_filename=plan.source_name,
        original_action=plan.action,
        original_domain=plan.domain,
        original_subfolder=plan.subfolder,
        corrected_action=new_plan.action,
        corrected_domain=new_plan.domain,
        corrected_subfolder=new_plan.subfolder,
        user_feedback=feedback,
    )

    # Extract patterns for future matching
    console.print("\n[dim]Extracting patterns for future learning...[/dim]")
    correction = extract_correction_pattern(correction)
    save_correction(correction)

    console.print(f"\n[green]Learned from correction![/green]")
    if correction.keywords:
        console.print(f"  Keywords: {', '.join(correction.keywords)}")
    if correction.filename_pattern:
        console.print(f"  Pattern: {correction.filename_pattern}")

    console.print(f"\n[bold]To approve: [cyan]revise-approve {new_plan.id}[/cyan][/bold]")


@app.command()
def corrections():
    """Show all learned corrections."""
    all_corrections = get_all_corrections()

    if not all_corrections:
        console.print("[yellow]No corrections learned yet[/yellow]")
        return

    table = Table(title=f"Learned Corrections ({len(all_corrections)})")
    table.add_column("ID", style="cyan")
    table.add_column("Original")
    table.add_column("Corrected To")
    table.add_column("Keywords")
    table.add_column("Used")

    for c in all_corrections[:20]:  # Show top 20
        original = f"{c.original_domain.value if c.original_domain else '?'}/{c.original_subfolder or '?'}"
        corrected = f"{c.corrected_domain.value if c.corrected_domain else '?'}/{c.corrected_subfolder or '?'}"
        keywords = ", ".join(c.keywords[:3]) if c.keywords else "-"

        table.add_row(
            c.id,
            original[:20],
            corrected[:20],
            keywords[:20],
            str(c.times_applied),
        )

    console.print(table)


# ============ Interactive Review Commands ============


def _display_plan_summary(plans: list, title: str = "Plan Summary"):
    """Display a summary table of plans."""
    from collections import Counter

    # Count by action
    by_action = Counter(p.action.value for p in plans)
    # Count by domain for moves
    by_domain = Counter(p.domain.value for p in plans if p.domain)
    # Count by status
    by_status = Counter(p.status.value for p in plans)

    console.print(f"\n[bold]{title}[/bold]")

    # Action summary
    table = Table(show_header=True, header_style="bold")
    table.add_column("Action", style="cyan")
    table.add_column("Count", justify="right")
    for action, count in sorted(by_action.items()):
        color = {"delete": "red", "move": "green", "skip": "yellow"}.get(action, "white")
        table.add_row(f"[{color}]{action}[/{color}]", str(count))
    console.print(table)

    # Domain breakdown for moves
    if by_domain:
        console.print("\n[dim]Moves by domain:[/dim]")
        for domain, count in sorted(by_domain.items()):
            console.print(f"  {domain}: {count}")

    # Status summary
    console.print(f"\n[dim]Status: {dict(by_status)}[/dim]")


def _interactive_review(plans: list, title: str = "Review") -> int:
    """Interactively review a list of plans. Returns count of reviewed plans."""
    from .models import LifeDomain

    if not plans:
        return 0

    domains = list(LifeDomain)
    subfolders = ["Documents", "Projects", "Research", "Media", "Archive"]

    console.print(f"\n[bold]{title}[/bold] - {len(plans)} items")
    console.print("[dim]Keys: (a)pprove, (d)elete, (s)kip/reject, (m)ove/change, (n)ext, (q)uit[/dim]\n")

    reviewed = 0
    for i, plan in enumerate(plans):
        # Display plan details
        console.print(f"[cyan]━━━ {i+1}/{len(plans)} ━━━[/cyan]")
        console.print(f"  [bold]File:[/bold] {plan.source_name}")

        action_color = {"delete": "red", "move": "green", "skip": "yellow"}.get(plan.action.value, "white")
        console.print(f"  [bold]Action:[/bold] [{action_color}]{plan.action.value}[/{action_color}]")

        if plan.domain:
            console.print(f"  [bold]Domain:[/bold] {plan.domain.value}/{plan.subfolder or 'Documents'}")
        if plan.suggested_name:
            console.print(f"  [bold]Rename to:[/bold] {plan.suggested_name}")
        console.print(f"  [bold]Confidence:[/bold] {plan.confidence:.0%}")

        while True:
            try:
                choice = typer.prompt(
                    "[a]pprove [d]elete [s]kip [m]ove [n]ext [q]uit",
                    default="a",
                    show_default=False,
                ).lower().strip()
            except (KeyboardInterrupt, EOFError):
                choice = "q"

            if choice == "a":
                update_plan_status(plan.id, PlanStatus.APPROVED)
                console.print("[green]✓ Approved[/green]")
                reviewed += 1
                break

            elif choice == "d":
                plan.action = FileAction.DELETE
                plan.domain = None
                plan.subfolder = None
                plan.destination_path = None
                plan.suggested_name = None
                save_plan(plan)
                update_plan_status(plan.id, PlanStatus.APPROVED)
                console.print("[red]✓ Changed to DELETE[/red]")
                reviewed += 1
                break

            elif choice == "s":
                update_plan_status(plan.id, PlanStatus.REJECTED)
                console.print("[yellow]✓ Rejected (file untouched)[/yellow]")
                reviewed += 1
                break

            elif choice == "m":
                console.print("\n[bold]Select domain:[/bold]")
                for j, dom in enumerate(domains):
                    console.print(f"  {j+1}. {dom.value}")

                try:
                    dom_choice = typer.prompt("Domain number", default="1")
                    dom_idx = int(dom_choice) - 1
                    if 0 <= dom_idx < len(domains):
                        new_domain = domains[dom_idx]

                        console.print("\n[bold]Select subfolder:[/bold]")
                        for k, sub in enumerate(subfolders):
                            console.print(f"  {k+1}. {sub}")

                        sub_choice = typer.prompt("Subfolder number", default="1")
                        sub_idx = int(sub_choice) - 1
                        new_subfolder = subfolders[sub_idx] if 0 <= sub_idx < len(subfolders) else "Documents"

                        plan.action = FileAction.MOVE
                        plan.domain = new_domain
                        plan.subfolder = new_subfolder
                        plan.destination_path = str(
                            settings.areas_path
                            / new_domain.value
                            / new_subfolder
                            / (plan.suggested_name or plan.source_name)
                        )
                        save_plan(plan)
                        update_plan_status(plan.id, PlanStatus.APPROVED)
                        console.print(f"[green]✓ Changed to {new_domain.value}/{new_subfolder}[/green]")
                        reviewed += 1
                        break
                except (ValueError, IndexError):
                    console.print("[red]Invalid selection[/red]")
                    continue

            elif choice == "n":
                console.print("[dim]→ Skipped[/dim]")
                break

            elif choice == "q":
                return reviewed

            else:
                console.print("[red]Invalid choice[/red]")

        console.print()

    return reviewed


@app.command()
def organize(
    path: str = typer.Argument(None, help="Directory to organize (default: Desktop)"),
):
    """Complete workflow: scan, review non-deletes, review all, then execute.

    This command runs the full organization workflow:
    1. Scan directory with AI classification
    2. Auto-approve obvious deletes (screenshots, installers)
    3. Interactive review of items NOT marked for delete
    4. Show full summary and option to re-review everything
    5. Execute approved plans or loop back

    Example:
        organize ~/Desktop
        organize ~/Downloads
    """
    from .classifier import classify_batch_with_ai

    scan_path = Path(path).expanduser().resolve() if path else settings.desktop_path

    if not scan_path.exists():
        console.print(f"[red]Directory not found: {scan_path}[/red]")
        raise typer.Exit(1)

    while True:
        # === STEP 1: Scan ===
        console.print(f"\n[bold cyan]═══ STEP 1: Scanning {scan_path} ═══[/bold cyan]")

        files = [f for f in scan_path.iterdir() if f.is_file() and not f.name.startswith(".")]
        if not files:
            console.print("[yellow]No files found[/yellow]")
            return

        console.print(f"Found {len(files)} files")

        # Apply rules first
        console.print("[dim]Applying rules...[/dim]")
        rule_plans = []
        needs_ai = []

        for file_path in files:
            plan = classify_file(file_path)
            if (plan.action == FileAction.SKIP or
                plan.category == FileCategory.UNKNOWN or
                plan.confidence < settings.ai_confidence_threshold):
                needs_ai.append(file_path)
            else:
                rule_plans.append(plan)

        console.print(f"  Rules handled: {len(rule_plans)} files")
        console.print(f"  Needs AI: {len(needs_ai)} files")

        # AI classify remaining
        ai_plans = []
        if needs_ai:
            all_corrections = get_all_corrections()
            batch_size = 20

            for i in range(0, len(needs_ai), batch_size):
                batch = needs_ai[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(needs_ai) + batch_size - 1) // batch_size
                console.print(f"[dim]AI batch {batch_num}/{total_batches}...[/dim]")
                plans = classify_batch_with_ai(batch, learned_corrections=all_corrections)
                ai_plans.extend(plans)

        all_plans = rule_plans + ai_plans

        # Save all plans
        for plan in all_plans:
            save_plan(plan)

        # === STEP 2: Auto-approve deletes ===
        console.print(f"\n[bold cyan]═══ STEP 2: Auto-approving Deletes ═══[/bold cyan]")

        delete_plans = [p for p in all_plans if p.action == FileAction.DELETE]
        non_delete_plans = [p for p in all_plans if p.action != FileAction.DELETE]

        for plan in delete_plans:
            update_plan_status(plan.id, PlanStatus.APPROVED)

        console.print(f"[green]✓ Auto-approved {len(delete_plans)} deletions[/green]")
        console.print(f"  Remaining for review: {len(non_delete_plans)} files")

        # === STEP 3: Review non-deletes ===
        if non_delete_plans:
            console.print(f"\n[bold cyan]═══ STEP 3: Review Moves/Skips ═══[/bold cyan]")

            if typer.confirm("Review non-delete items now?", default=True):
                pending_non_deletes = [p for p in non_delete_plans if p.status == PlanStatus.PENDING]
                _interactive_review(pending_non_deletes, "Review Moves")

        # === STEP 4: Full summary and re-review option ===
        console.print(f"\n[bold cyan]═══ STEP 4: Final Review ═══[/bold cyan]")

        # Reload plans to get updated statuses
        all_saved_plans = get_pending_plans() + get_plans_by_status(PlanStatus.APPROVED) + get_plans_by_status(PlanStatus.REJECTED)
        # Filter to just this scan's files
        scan_file_paths = {str(f) for f in files}
        current_plans = [p for p in all_saved_plans if p.source_path in scan_file_paths]

        _display_plan_summary(current_plans, "Current Plan")

        # Show breakdown
        approved = [p for p in current_plans if p.status == PlanStatus.APPROVED]
        rejected = [p for p in current_plans if p.status == PlanStatus.REJECTED]
        pending = [p for p in current_plans if p.status == PlanStatus.PENDING]

        console.print(f"\n[bold]Ready to execute:[/bold]")
        console.print(f"  [green]Approved:[/green] {len(approved)}")
        console.print(f"  [yellow]Rejected:[/yellow] {len(rejected)} (files left alone)")
        console.print(f"  [dim]Pending:[/dim] {len(pending)}")

        # === STEP 5: Execute or loop ===
        console.print(f"\n[bold cyan]═══ STEP 5: Execute ═══[/bold cyan]")

        while True:
            console.print("\nOptions:")
            console.print("  [bold]e[/bold] - Execute approved plans")
            console.print("  [bold]r[/bold] - Re-review all items")
            console.print("  [bold]d[/bold] - Review only items marked for delete")
            console.print("  [bold]m[/bold] - Review only items marked for move")
            console.print("  [bold]s[/bold] - Rescan directory (start over)")
            console.print("  [bold]q[/bold] - Quit without executing")

            try:
                choice = typer.prompt("Choice", default="e").lower().strip()
            except (KeyboardInterrupt, EOFError):
                choice = "q"

            if choice == "e":
                if not approved:
                    console.print("[yellow]No approved plans to execute[/yellow]")
                    continue

                if typer.confirm(f"Execute {len(approved)} approved plans?", default=True):
                    console.print("\n[bold]Executing...[/bold]")
                    results = execute_all_pending()
                    # results is list of (plan_id, success, message) tuples
                    executed = sum(1 for _, success, _ in results if success)
                    failed = sum(1 for _, success, _ in results if not success)
                    console.print(f"[green]✓ Executed {executed} plans[/green]")
                    if failed:
                        console.print(f"[red]✗ Failed: {failed}[/red]")
                        for plan_id, success, message in results:
                            if not success:
                                console.print(f"  [red]• {plan_id[:8]}: {message}[/red]")
                    return

            elif choice == "r":
                # Re-review all
                all_for_review = [p for p in current_plans if p.status in [PlanStatus.PENDING, PlanStatus.APPROVED]]
                # Reset to pending for re-review
                for p in all_for_review:
                    update_plan_status(p.id, PlanStatus.PENDING)
                _interactive_review(all_for_review, "Re-review All")
                break  # Loop back to step 4

            elif choice == "d":
                # Review deletes only
                delete_for_review = [p for p in current_plans if p.action == FileAction.DELETE and p.status == PlanStatus.APPROVED]
                for p in delete_for_review:
                    update_plan_status(p.id, PlanStatus.PENDING)
                _interactive_review(delete_for_review, "Review Deletes")
                break

            elif choice == "m":
                # Review moves only
                move_for_review = [p for p in current_plans if p.action == FileAction.MOVE]
                for p in move_for_review:
                    if p.status == PlanStatus.APPROVED:
                        update_plan_status(p.id, PlanStatus.PENDING)
                pending_moves = [p for p in move_for_review if p.status == PlanStatus.PENDING]
                _interactive_review(pending_moves, "Review Moves")
                break

            elif choice == "s":
                # Rescan - clear plans and start over
                console.print("[yellow]Rescanning...[/yellow]")
                break  # Will loop back to step 1

            elif choice == "q":
                console.print("[yellow]Exiting without executing[/yellow]")
                console.print("Plans are saved. Run [cyan]execute[/cyan] later to apply.")
                return

            else:
                console.print("[red]Invalid choice[/red]")

        # If we get here, loop back (rescan or re-review)
        continue


@app.command()
def review(
    filter_action: str = typer.Option(None, "--action", "-a", help="Filter by action (move/delete/skip)"),
    filter_domain: str = typer.Option(None, "--domain", "-d", help="Filter by domain"),
):
    """Interactively review pending plans one by one.

    Navigate through plans with keyboard shortcuts:
    - a: Approve (keep as-is)
    - d: Change to DELETE
    - s: Skip (reject, leave file alone)
    - m: Change domain/category
    - n: Next (skip for now)
    - q: Quit review

    Examples:
        review                    # Review all pending plans
        review --action move      # Only review move plans
        review --domain Finance   # Only review Finance plans
    """
    from .models import LifeDomain

    plans = get_pending_plans()

    if not plans:
        console.print("[yellow]No pending plans to review[/yellow]")
        console.print("Run [cyan]ai-scan ~/Desktop --save[/cyan] to generate plans")
        return

    # Apply filters
    if filter_action:
        plans = [p for p in plans if p.action.value == filter_action]
    if filter_domain:
        plans = [p for p in plans if p.domain and p.domain.value == filter_domain]

    if not plans:
        console.print("[yellow]No plans match the filter[/yellow]")
        return

    console.print(f"\n[bold]Interactive Review Mode[/bold] - {len(plans)} plans to review")
    console.print("[dim]Keys: (a)pprove, (d)elete, (s)kip, (m)ove/change domain, (n)ext, (q)uit[/dim]\n")

    domains = list(LifeDomain)
    subfolders = ["Documents", "Projects", "Research", "Media", "Archive"]

    reviewed = 0
    for i, plan in enumerate(plans):
        # Display plan details
        console.print(f"[cyan]━━━ Plan {i+1}/{len(plans)} ━━━[/cyan]")
        console.print(f"  [bold]File:[/bold] {plan.source_name}")
        console.print(f"  [bold]Action:[/bold] {plan.action.value}")
        if plan.domain:
            console.print(f"  [bold]Domain:[/bold] {plan.domain.value}/{plan.subfolder or 'Documents'}")
        if plan.suggested_name:
            console.print(f"  [bold]Rename to:[/bold] {plan.suggested_name}")
        console.print(f"  [bold]Confidence:[/bold] {plan.confidence:.0%}")
        console.print(f"  [dim]Reason: {plan.reasoning}[/dim]")

        while True:
            try:
                choice = typer.prompt(
                    "\n[a]pprove [d]elete [s]kip [m]ove [n]ext [q]uit",
                    default="n",
                    show_default=False,
                ).lower().strip()
            except (KeyboardInterrupt, EOFError):
                choice = "q"

            if choice == "a":
                # Approve as-is
                update_plan_status(plan.id, PlanStatus.APPROVED)
                console.print("[green]✓ Approved[/green]")
                reviewed += 1
                break

            elif choice == "d":
                # Change to delete
                plan.action = FileAction.DELETE
                plan.domain = None
                plan.subfolder = None
                plan.destination_path = None
                plan.suggested_name = None
                save_plan(plan)
                update_plan_status(plan.id, PlanStatus.APPROVED)
                console.print("[red]✓ Changed to DELETE and approved[/red]")
                reviewed += 1
                break

            elif choice == "s":
                # Skip/reject - leave file alone
                update_plan_status(plan.id, PlanStatus.REJECTED)
                console.print("[yellow]✓ Rejected (file will be left alone)[/yellow]")
                reviewed += 1
                break

            elif choice == "m":
                # Change domain
                console.print("\n[bold]Select domain:[/bold]")
                for j, dom in enumerate(domains):
                    console.print(f"  {j+1}. {dom.value}")

                try:
                    dom_choice = typer.prompt("Domain number", default="1")
                    dom_idx = int(dom_choice) - 1
                    if 0 <= dom_idx < len(domains):
                        new_domain = domains[dom_idx]

                        console.print("\n[bold]Select subfolder:[/bold]")
                        for k, sub in enumerate(subfolders):
                            console.print(f"  {k+1}. {sub}")

                        sub_choice = typer.prompt("Subfolder number", default="1")
                        sub_idx = int(sub_choice) - 1
                        new_subfolder = subfolders[sub_idx] if 0 <= sub_idx < len(subfolders) else "Documents"

                        # Update plan
                        plan.action = FileAction.MOVE
                        plan.domain = new_domain
                        plan.subfolder = new_subfolder
                        plan.destination_path = str(
                            settings.areas_path
                            / new_domain.value
                            / new_subfolder
                            / (plan.suggested_name or plan.source_name)
                        )
                        save_plan(plan)
                        update_plan_status(plan.id, PlanStatus.APPROVED)
                        console.print(f"[green]✓ Changed to {new_domain.value}/{new_subfolder} and approved[/green]")
                        reviewed += 1
                        break
                except (ValueError, IndexError):
                    console.print("[red]Invalid selection[/red]")
                    continue

            elif choice == "n":
                # Next without action
                console.print("[dim]→ Skipped for now[/dim]")
                break

            elif choice == "q":
                console.print(f"\n[bold]Review ended.[/bold] Reviewed {reviewed} plans.")
                return

            else:
                console.print("[red]Invalid choice. Use: a, d, s, m, n, or q[/red]")

        console.print()  # Blank line between plans

    console.print(f"\n[bold green]Review complete![/bold green] Reviewed {reviewed} plans.")
    console.print(f"Run [cyan]execute[/cyan] to apply approved changes.")


def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    app()


if __name__ == "__main__":
    main()
