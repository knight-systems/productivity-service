"""Task parsing and creation endpoints."""

from fastapi import APIRouter

from ..models.task import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskParseRequest,
    TaskParseResponse,
)
from ..services.omnifocus import create_omnifocus_task
from ..services.tag_parser import parse_task_tags

router = APIRouter(tags=["tasks"])


@router.post("/parse", response_model=TaskParseResponse)
async def parse_task(request: TaskParseRequest) -> TaskParseResponse:
    """
    Parse natural language task input and extract components.

    Uses Claude AI to intelligently extract:
    - Task title
    - Project name
    - Context (@home, @work, etc.)
    - Due date
    - Defer date
    - Additional tags

    Example input: "Buy milk tomorrow for the grocery project"
    """
    return await parse_task_tags(request.text)


@router.post("/create", response_model=TaskCreateResponse)
async def create_task(request: TaskCreateRequest) -> TaskCreateResponse:
    """
    Create a task in OmniFocus via Mail Drop.

    Sends an email to your OmniFocus Mail Drop address with proper formatting
    for automatic task creation.

    Requires environment variables:
    - PRODUCTIVITY_OMNIFOCUS_MAIL_DROP_ADDRESS
    - PRODUCTIVITY_SES_SENDER_EMAIL
    """
    return await create_omnifocus_task(request)


@router.post("/capture", response_model=TaskCreateResponse)
async def capture_task(request: TaskParseRequest) -> TaskCreateResponse:
    """
    Parse and create task in one step.

    Convenience endpoint that combines /parse and /create:
    1. Parses the natural language input
    2. Creates the task in OmniFocus

    Ideal for voice-to-task workflows where you want minimal latency.
    """
    parsed = await parse_task_tags(request.text)

    create_request = TaskCreateRequest(
        title=parsed.title,
        project=parsed.project,
        context=parsed.context.lstrip("@") if parsed.context else None,
        due_date=parsed.due_date,
        defer_date=parsed.defer_date,
    )

    return await create_omnifocus_task(create_request)
