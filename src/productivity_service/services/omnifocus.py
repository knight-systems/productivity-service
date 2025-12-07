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

    Note: Mail Drop only supports subject (becomes task title) and body (becomes note).
    It does NOT support inline syntax for projects, contexts, tags, or dates.
    Those must be organized manually in OmniFocus after the task arrives in the inbox.
    """
    return task.title


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
