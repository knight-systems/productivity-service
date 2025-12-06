"""OmniFocus integration via Mail Drop (SES)."""

import logging

import boto3
from botocore.exceptions import ClientError

from ..config import settings
from ..models.task import TaskCreateRequest, TaskCreateResponse

logger = logging.getLogger(__name__)


def _build_mail_drop_subject(task: TaskCreateRequest) -> str:
    """
    Build OmniFocus Mail Drop subject line.

    Mail Drop format:
    - Task title
    - ::Project (double colon prefix)
    - @Context (at sign prefix)
    - #Tag (hash prefix for additional tags)
    - --YYYY-MM-DD (double dash for due date)
    - //YYYY-MM-DD (double slash for defer date)
    - ! (exclamation for flagged)

    Example: "Buy milk ::Grocery @errands --2024-01-15"
    """
    parts = [task.title]

    if task.project:
        parts.append(f"::{task.project}")

    if task.context:
        # Ensure context has @ prefix
        context = task.context if task.context.startswith("@") else f"@{task.context}"
        parts.append(context)

    if task.due_date:
        parts.append(f"--{task.due_date}")

    if task.defer_date:
        parts.append(f"//{task.defer_date}")

    if task.flagged:
        parts.append("!")

    return " ".join(parts)


async def create_omnifocus_task(task: TaskCreateRequest) -> TaskCreateResponse:
    """
    Create a task in OmniFocus via Mail Drop.

    Sends an email to the user's OmniFocus Mail Drop address with the task
    formatted in Mail Drop syntax.

    Args:
        task: Task details to create

    Returns:
        TaskCreateResponse with success status
    """
    if not settings.omnifocus_mail_drop_address:
        return TaskCreateResponse(
            success=False,
            message="OmniFocus Mail Drop address not configured. Set PRODUCTIVITY_OMNIFOCUS_MAIL_DROP_ADDRESS.",
            task_title=task.title,
            mail_drop_subject=None,
        )

    if not settings.ses_sender_email:
        return TaskCreateResponse(
            success=False,
            message="SES sender email not configured. Set PRODUCTIVITY_SES_SENDER_EMAIL.",
            task_title=task.title,
            mail_drop_subject=None,
        )

    subject = _build_mail_drop_subject(task)
    body = task.note or ""

    ses = boto3.client("ses", region_name=settings.aws_region)

    try:
        ses.send_email(
            Source=settings.ses_sender_email,
            Destination={"ToAddresses": [settings.omnifocus_mail_drop_address]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )

        logger.info(f"Task sent to OmniFocus: {subject}")

        return TaskCreateResponse(
            success=True,
            message=f"Task created: {task.title}",
            task_title=task.title,
            mail_drop_subject=subject,
        )

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"SES error ({error_code}): {error_message}")

        return TaskCreateResponse(
            success=False,
            message=f"Failed to send email: {error_message}",
            task_title=task.title,
            mail_drop_subject=subject,
        )
