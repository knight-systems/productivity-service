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
    """Format OmniFocus tasks as markdown list for daily note."""
    if not tasks:
        return "- No tasks for today\n"

    lines = []
    # Group by project
    by_project: dict[str, list[dict]] = {}
    for task in tasks:
        project = task.get("project", "Inbox") or "Inbox"
        if project not in by_project:
            by_project[project] = []
        by_project[project].append(task)

    for project, project_tasks in sorted(by_project.items()):
        lines.append(f"**{project}**")
        for task in project_tasks:
            flag = " 🚩" if task.get("flagged") else ""
            lines.append(f"- [ ] {task['title']}{flag}")
        lines.append("")  # Blank line between projects

    return "\n".join(lines)


def _generate_morning_summary(tasks: list[dict]) -> str:
    """Generate AI morning summary."""
    if not tasks:
        return "Good morning! No tasks scheduled for today. Use this time for deep work or planning."

    # Build task summary for AI
    task_text = "\n".join([
        f"- {t['title']} ({t.get('project', 'No project')}){' [FLAGGED]' if t.get('flagged') else ''}"
        for t in tasks[:20]  # Limit for token efficiency
    ])

    prompt = f"""You are a helpful productivity assistant. Generate a brief, encouraging morning summary (2-3 sentences) based on today's tasks.

Today's tasks:
{task_text}

Focus on:
1. What's the main theme or priority for today?
2. One encouraging observation or tip

Keep it concise and actionable. Don't list the tasks - provide insight."""

    try:
        return _call_bedrock(prompt, max_tokens=200)
    except Exception as e:
        logger.error(f"Failed to generate morning summary: {e}")
        return f"You have {len(tasks)} tasks today. Focus on the flagged items first!"


@router.post("/morning-brief", response_model=MorningBriefResponse)
async def morning_brief(request: MorningBriefRequest) -> MorningBriefResponse:
    """Generate morning brief and inject tasks into daily note.

    This endpoint:
    1. Formats OmniFocus tasks as a markdown checklist
    2. Generates an AI summary of the day ahead
    3. Appends both to the daily note's Tasks section
    """
    try:
        obsidian = _get_obsidian_service()

        # Format tasks for daily note
        tasks_markdown = _format_tasks_for_daily_note(
            [t.model_dump() for t in request.tasks]
        )

        # Generate AI summary if requested
        summary = ""
        if request.generate_summary:
            summary = _generate_morning_summary(
                [t.model_dump() for t in request.tasks]
            )

        # Build content to inject
        content_parts = []
        if summary:
            content_parts.append(f"**AI Summary**: {summary}")
            content_parts.append("")
        content_parts.append(tasks_markdown)

        full_content = "\n".join(content_parts)

        # Append to Tasks section
        result = obsidian.append_to_daily_note(
            heading="Tasks",
            content=full_content,
            timestamp=False,  # No timestamp for task injection
        )

        return MorningBriefResponse(
            success=True,
            path=result["path"],
            commit_sha=result["commit_sha"],
            task_count=len(request.tasks),
            summary=summary,
            message="Morning brief generated successfully",
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
