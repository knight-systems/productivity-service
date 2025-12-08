"""Routine automation routes for morning brief and evening summary."""

import json
import logging
from datetime import datetime

import boto3
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..models.routines import (
    EveningSummaryRequest,
    EveningSummaryResponse,
    ExtractedTask,
    MorningBriefRequest,
    MorningBriefResponse,
)
from ..models.task import TaskCreateRequest
from ..services.omnifocus import create_omnifocus_task
from .obsidian import _get_obsidian_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routines", tags=["routines"])


def _call_bedrock(prompt: str, max_tokens: int = 1000) -> str:
    """Call Bedrock Claude with a prompt."""
    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    response = client.invoke_model(
        modelId=settings.bedrock_model_id,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }),
        contentType="application/json",
    )

    response_body = json.loads(response["body"].read())
    return response_body["content"][0]["text"]


def _format_tasks_for_daily_note(tasks: list[dict]) -> str:
    """Format OmniFocus tasks as markdown list for daily note, grouped by priority."""
    if not tasks:
        return "- No flagged tasks for today\n"

    lines = []

    # Group by priority (tasks come pre-sorted by priority from AppleScript)
    by_priority: dict[str, list[dict]] = {"A": [], "B": [], "C": [], "": []}
    for task in tasks:
        priority = task.get("priority", "")
        if priority not in by_priority:
            priority = ""
        by_priority[priority].append(task)

    priority_labels = {
        "A": "🔴 Priority A",
        "B": "🟡 Priority B",
        "C": "🟢 Priority C",
        "": "⚪ No Priority",
    }

    for priority in ["A", "B", "C", ""]:
        priority_tasks = by_priority[priority]
        if not priority_tasks:
            continue

        lines.append(f"**{priority_labels[priority]}**")
        for task in priority_tasks:
            size = f" `{task.get('size')}`" if task.get("size") else ""
            project = f" [{task.get('project')}]" if task.get("project") else ""
            lines.append(f"- [ ] {task['title']}{size}{project}")
        lines.append("")  # Blank line between priorities

    return "\n".join(lines)


def _generate_morning_summary(tasks: list[dict], inbox_count: int = 0, inbox_titles: list[str] | None = None) -> str:
    """Generate AI morning summary."""
    if not tasks and inbox_count == 0:
        return "Good morning! No flagged tasks today. Use this time for deep work or planning."

    # Build task summary for AI, organized by priority
    task_lines = []
    for t in tasks[:20]:
        priority = f"[Priority {t.get('priority')}]" if t.get("priority") else ""
        size = f"({t.get('size')})" if t.get("size") else ""
        task_lines.append(f"- {t['title']} {priority} {size} - {t.get('project', 'No project')}".strip())

    task_text = "\n".join(task_lines)

    # Inbox section
    inbox_section = ""
    if inbox_count > 0:
        inbox_section = f"\n\nInbox ({inbox_count} items needing processing):"
        if inbox_titles:
            inbox_section += "\n" + "\n".join([f"- {t}" for t in inbox_titles[:5]])
            if inbox_count > 5:
                inbox_section += f"\n- ... and {inbox_count - 5} more"

    prompt = f"""You are a helpful productivity assistant. Generate a brief, encouraging morning summary (2-3 sentences) based on today's flagged tasks.

Today's flagged tasks (sorted by priority A → B → C):
{task_text}{inbox_section}

Focus on:
1. What's the main theme or priority for today?
2. One encouraging observation or tip
3. If inbox has items, briefly mention they need processing

Keep it concise and actionable. Don't list the tasks - provide insight."""

    try:
        return _call_bedrock(prompt, max_tokens=200)
    except Exception as e:
        logger.error(f"Failed to generate morning summary: {e}")
        return f"You have {len(tasks)} flagged tasks today. Start with Priority A!"


def _format_inbox_summary(inbox_count: int, inbox_titles: list[str]) -> str:
    """Format inbox summary for daily note."""
    if inbox_count == 0:
        return "✅ Inbox is clear!"

    lines = [f"⚠️ **Inbox: {inbox_count} items need processing**"]
    if inbox_titles:
        # Summarize themes rather than listing all
        lines.append("Themes: " + ", ".join(inbox_titles[:3]))
        if inbox_count > 3:
            lines.append(f"*...and {inbox_count - 3} more*")
    return "\n".join(lines)


@router.post("/morning-brief", response_model=MorningBriefResponse)
async def morning_brief(request: MorningBriefRequest) -> MorningBriefResponse:
    """Generate morning brief and inject tasks into daily note.

    This endpoint is IDEMPOTENT - it replaces the Tasks section content,
    so it can be safely re-run multiple times on the same day.

    This endpoint:
    1. Formats OmniFocus tasks as a markdown checklist (grouped by priority)
    2. Generates an AI summary of the day ahead
    3. Shows inbox count and themes
    4. REPLACES the Tasks section content (idempotent)
    """
    try:
        obsidian = _get_obsidian_service()

        # Format tasks for daily note
        tasks_markdown = _format_tasks_for_daily_note(
            [t.model_dump() for t in request.tasks]
        )

        # Format inbox summary
        inbox_summary = _format_inbox_summary(request.inbox_count, request.inbox_titles)

        # Generate AI summary if requested
        summary = ""
        if request.generate_summary:
            summary = _generate_morning_summary(
                [t.model_dump() for t in request.tasks],
                request.inbox_count,
                request.inbox_titles,
            )

        # Build content to inject
        content_parts = []
        if summary:
            content_parts.append(f"**AI Summary**: {summary}")
            content_parts.append("")
        content_parts.append(inbox_summary)
        content_parts.append("")
        content_parts.append(tasks_markdown)

        full_content = "\n".join(content_parts)

        # REPLACE Tasks section (idempotent - safe to re-run)
        result = obsidian.replace_daily_note_section(
            heading="Tasks",
            content=full_content,
        )

        return MorningBriefResponse(
            success=True,
            path=result["path"],
            commit_sha=result["commit_sha"],
            task_count=len(request.tasks),
            summary=summary,
            message=f"Morning brief generated ({len(request.tasks)} tasks, {request.inbox_count} inbox items)",
        )

    except Exception as e:
        logger.exception("Error generating morning brief")
        raise HTTPException(status_code=500, detail=f"Failed to generate morning brief: {e}")


def _extract_action_items(daily_note_content: str) -> list[ExtractedTask]:
    """Use AI to extract action items from daily note."""
    prompt = f"""Analyze this daily note and extract any action items or tasks that should be added to a task manager.

Look for:
- Items mentioned in Brain Dump that are actionable
- Tasks mentioned in Journal that weren't completed
- Any "TODO" or action-oriented items

Daily note content:
{daily_note_content[:4000]}  # Limit for token efficiency

Return a JSON array of tasks. Each task should have:
- "title": Clear, actionable task title (imperative form)
- "context": Where in the note you found it (e.g., "Brain Dump", "Journal")

Return ONLY the JSON array, no explanation. If no action items found, return empty array [].

Example:
[{{"title": "Schedule dentist appointment", "context": "Brain Dump"}}]"""

    try:
        response = _call_bedrock(prompt, max_tokens=500)

        # Extract JSON from response
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        tasks = json.loads(response.strip())
        return [ExtractedTask(**t) for t in tasks]

    except Exception as e:
        logger.error(f"Failed to extract action items: {e}")
        return []


def _generate_evening_summary(daily_note_content: str) -> str:
    """Generate AI evening summary of the day."""
    prompt = f"""You are a helpful productivity assistant. Generate a brief evening reflection (2-3 sentences) based on this daily note.

Daily note:
{daily_note_content[:3000]}

Focus on:
1. What was accomplished today?
2. One positive observation

Keep it brief and encouraging."""

    try:
        return _call_bedrock(prompt, max_tokens=200)
    except Exception as e:
        logger.error(f"Failed to generate evening summary: {e}")
        return "Day complete. Great job on whatever you accomplished!"


@router.post("/evening-summary", response_model=EveningSummaryResponse)
async def evening_summary(request: EveningSummaryRequest) -> EveningSummaryResponse:
    """Generate evening summary and extract action items.

    This endpoint:
    1. Reads the daily note
    2. Extracts action items using AI
    3. Sends extracted tasks to OmniFocus via Mail Drop
    4. Appends an evening summary to the Journal section
    """
    try:
        obsidian = _get_obsidian_service()

        # Get daily note content
        note_date = None
        if request.date:
            note_date = datetime.combine(request.date, datetime.min.time())

        daily_content = obsidian.get_daily_note(date=note_date)

        if not daily_content:
            return EveningSummaryResponse(
                success=False,
                message="Daily note not found",
            )

        path = obsidian._get_daily_note_path(date=note_date)
        extracted_tasks: list[ExtractedTask] = []
        tasks_sent = 0
        summary = ""

        # Extract action items if requested
        if request.extract_tasks:
            extracted_tasks = _extract_action_items(daily_content)

            # Send to OmniFocus
            for task in extracted_tasks:
                try:
                    task_request = TaskCreateRequest(
                        title=task.title,
                        note=f"Extracted from daily note ({task.context})",
                    )
                    result = await create_omnifocus_task(task_request)
                    if result.success:
                        tasks_sent += 1
                    else:
                        logger.warning(f"Failed to create task '{task.title}': {result.message}")
                except Exception as e:
                    logger.error(f"Failed to create task '{task.title}': {e}")

        # Generate evening summary if requested
        if request.generate_summary:
            summary = _generate_evening_summary(daily_content)

            # Append to Journal section
            try:
                obsidian.append_to_daily_note(
                    heading="Journal",
                    content=f"**Evening Reflection**: {summary}",
                    timestamp=True,
                )
            except Exception as e:
                logger.warning(f"Failed to append evening summary: {e}")

        return EveningSummaryResponse(
            success=True,
            path=path,
            extracted_tasks=extracted_tasks,
            tasks_sent=tasks_sent,
            summary=summary,
            message=f"Evening summary complete. Extracted {len(extracted_tasks)} tasks, sent {tasks_sent} to OmniFocus.",
        )

    except Exception as e:
        logger.exception("Error generating evening summary")
        raise HTTPException(status_code=500, detail=f"Failed to generate evening summary: {e}")
