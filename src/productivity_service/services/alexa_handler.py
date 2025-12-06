"""Alexa Skill request handling."""

import logging
from typing import Any

from ..models.task import TaskCreateRequest
from .omnifocus import create_omnifocus_task
from .tag_parser import parse_task_tags

logger = logging.getLogger(__name__)


def _build_response(
    speech: str,
    should_end: bool = True,
    card_title: str | None = None,
    card_content: str | None = None,
) -> dict[str, Any]:
    """Build Alexa response object."""
    response: dict[str, Any] = {
        "version": "1.0",
        "response": {
            "outputSpeech": {"type": "PlainText", "text": speech},
            "shouldEndSession": should_end,
        },
    }

    if card_title and card_content:
        response["response"]["card"] = {
            "type": "Simple",
            "title": card_title,
            "content": card_content,
        }

    return response


async def handle_alexa_request(request: dict[str, Any]) -> dict[str, Any]:
    """
    Process Alexa skill request and return response.

    Supported intents:
    - LaunchRequest: Welcome message
    - CaptureTaskIntent: Parse and create task from voice input
    - AMAZON.HelpIntent: Usage instructions
    - AMAZON.CancelIntent / AMAZON.StopIntent: Exit

    Args:
        request: Full Alexa request envelope

    Returns:
        Alexa response envelope
    """
    request_type = request.get("request", {}).get("type", "")

    logger.info(f"Alexa request type: {request_type}")

    # Launch request - welcome message
    if request_type == "LaunchRequest":
        return _build_response(
            "Welcome to Task Capture. Tell me a task to add, like: "
            "add buy milk tomorrow for groceries.",
            should_end=False,
        )

    # Intent request
    if request_type == "IntentRequest":
        intent = request.get("request", {}).get("intent", {})
        intent_name = intent.get("name", "")

        logger.info(f"Alexa intent: {intent_name}")

        # Capture task intent
        if intent_name == "CaptureTaskIntent":
            return await _handle_capture_task(intent)

        # Help intent
        if intent_name == "AMAZON.HelpIntent":
            return _build_response(
                "You can say things like: Add buy milk tomorrow for groceries. "
                "Or: Add call mom at work. I'll parse your task and send it to OmniFocus.",
                should_end=False,
            )

        # Cancel/Stop intent
        if intent_name in ["AMAZON.CancelIntent", "AMAZON.StopIntent"]:
            return _build_response("Goodbye!")

        # Fallback
        if intent_name == "AMAZON.FallbackIntent":
            return _build_response(
                "I didn't understand that. Try saying: Add, followed by your task.",
                should_end=False,
            )

    # Session ended
    if request_type == "SessionEndedRequest":
        return _build_response("")

    # Unknown request type
    return _build_response(
        "I'm not sure how to help with that. Try saying: Add, followed by your task.",
        should_end=False,
    )


async def _handle_capture_task(intent: dict[str, Any]) -> dict[str, Any]:
    """Handle CaptureTaskIntent - parse and create task."""
    slots = intent.get("slots", {})
    task_text = slots.get("taskText", {}).get("value", "")

    if not task_text:
        return _build_response(
            "I didn't catch the task. Please say: Add, followed by what you want to do.",
            should_end=False,
        )

    logger.info(f"Parsing task: {task_text}")

    # Parse the task with AI
    parsed = await parse_task_tags(task_text)

    logger.info(f"Parsed task: title='{parsed.title}', project={parsed.project}, "
                f"context={parsed.context}, due={parsed.due_date}")

    # Create the task in OmniFocus
    create_request = TaskCreateRequest(
        title=parsed.title,
        project=parsed.project,
        context=parsed.context.lstrip("@") if parsed.context else None,
        due_date=parsed.due_date,
        defer_date=parsed.defer_date,
    )

    result = await create_omnifocus_task(create_request)

    if result.success:
        # Build confirmation message
        parts = [f"Added: {parsed.title}"]
        if parsed.project:
            parts.append(f"to {parsed.project}")
        if parsed.due_date:
            parts.append(f"due {parsed.due_date}")

        speech = ". ".join(parts) + "."

        return _build_response(
            speech,
            card_title="Task Added",
            card_content=result.mail_drop_subject or parsed.title,
        )
    else:
        return _build_response(
            f"Sorry, I couldn't add that task. {result.message}",
        )
