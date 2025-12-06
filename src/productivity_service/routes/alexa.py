"""Alexa Skill webhook endpoint."""

import logging
from typing import Any

from fastapi import APIRouter, Request

from ..services.alexa_handler import handle_alexa_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alexa"])


@router.post("/alexa")
async def alexa_webhook(request: Request) -> dict[str, Any]:
    """
    Handle Alexa Skill requests.

    This endpoint receives requests from the Alexa service when users
    interact with the Task Capture skill.

    Supported intents:
    - LaunchRequest: "Alexa, open Task Capture"
    - CaptureTaskIntent: "Alexa, tell Task Capture to add buy milk tomorrow"
    - AMAZON.HelpIntent: "Alexa, ask Task Capture for help"
    - AMAZON.StopIntent: "Alexa, stop"

    The response is returned in Alexa response format with speech output.
    """
    body = await request.json()

    logger.info(f"Alexa request received: {body.get('request', {}).get('type')}")

    response = await handle_alexa_request(body)

    return response
