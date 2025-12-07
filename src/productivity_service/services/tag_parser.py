"""AI-powered task tag extraction using Claude via Bedrock."""

import json
import logging
from datetime import date, timedelta

import boto3
from botocore.exceptions import ClientError

from ..config import settings
from ..models.task import TaskParseResponse

logger = logging.getLogger(__name__)


def _get_today_context() -> str:
    """Get current date context for the AI prompt."""
    today = date.today()
    tomorrow = today + timedelta(days=1)
    return f"Today is {today.strftime('%A, %Y-%m-%d')}. Tomorrow is {tomorrow.strftime('%Y-%m-%d')}."


async def parse_task_tags(text: str) -> TaskParseResponse:
    """
    Use Claude to extract task components from natural language.

    Args:
        text: Raw voice/text input like "Buy milk tomorrow for groceries"

    Returns:
        TaskParseResponse with extracted components
    """
    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    prompt = f"""{_get_today_context()}

Extract task information from this voice input. Return JSON only, no explanation.

Voice input: "{text}"

Extract these fields:
- title: The core task action (clean, imperative form without temporal/project references)
- note: The original input cleaned up with proper capitalization and punctuation (complete sentence)
- project: Project name if mentioned (null if none detected)
- context: Context like @home, @work, @errands, @phone (null if none). Include the @ prefix.
- due_date: Due date in YYYY-MM-DD format (null if none). Convert relative dates:
  - "tomorrow" = {(date.today() + timedelta(days=1)).strftime('%Y-%m-%d')}
  - "next week" = 7 days from today
  - "Friday" = the coming Friday
- defer_date: Start/defer date in YYYY-MM-DD format (null if none)
- tags: List of other relevant tags (empty list if none)
- confidence: Your confidence in the extraction accuracy (0.0-1.0)

Return only valid JSON matching this schema:
{{
  "title": "string",
  "note": "string",
  "project": "string or null",
  "context": "string or null",
  "due_date": "YYYY-MM-DD or null",
  "defer_date": "YYYY-MM-DD or null",
  "tags": ["string"],
  "confidence": 0.0-1.0
}}"""

    try:
        response = client.invoke_model(
            modelId=settings.bedrock_model_id,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            }),
            contentType="application/json",
        )

        response_body = json.loads(response["body"].read())
        content = response_body["content"][0]["text"]

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        parsed = json.loads(content.strip())

        return TaskParseResponse(
            title=parsed.get("title", text),
            note=parsed.get("note"),
            project=parsed.get("project"),
            context=parsed.get("context"),
            due_date=parsed.get("due_date"),
            defer_date=parsed.get("defer_date"),
            tags=parsed.get("tags", []),
            confidence=parsed.get("confidence", 0.5),
            raw_input=text,
        )

    except ClientError as e:
        logger.error(f"Bedrock API error: {e}")
        # Return basic extraction on error
        return TaskParseResponse(
            title=text,
            note=text,  # Use raw input as note on error
            project=None,
            context=None,
            due_date=None,
            defer_date=None,
            tags=[],
            confidence=0.0,
            raw_input=text,
        )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        return TaskParseResponse(
            title=text,
            note=text,  # Use raw input as note on error
            project=None,
            context=None,
            due_date=None,
            defer_date=None,
            tags=[],
            confidence=0.0,
            raw_input=text,
        )
