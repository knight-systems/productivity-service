"""Tests for Alexa webhook endpoint."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.productivity_service.models.task import TaskCreateResponse, TaskParseResponse


def test_alexa_launch_request(client: TestClient) -> None:
    """Test Alexa launch request returns welcome message."""
    response = client.post(
        "/alexa",
        json={
            "version": "1.0",
            "request": {"type": "LaunchRequest", "locale": "en-US"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0"
    assert "Welcome" in data["response"]["outputSpeech"]["text"]
    assert data["response"]["shouldEndSession"] is False


def test_alexa_help_intent(client: TestClient) -> None:
    """Test Alexa help intent returns usage instructions."""
    response = client.post(
        "/alexa",
        json={
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {"name": "AMAZON.HelpIntent"},
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "say" in data["response"]["outputSpeech"]["text"].lower()


def test_alexa_stop_intent(client: TestClient) -> None:
    """Test Alexa stop intent ends session."""
    response = client.post(
        "/alexa",
        json={
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {"name": "AMAZON.StopIntent"},
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["response"]["shouldEndSession"] is True


def test_alexa_capture_task_intent_success(client: TestClient) -> None:
    """Test Alexa capture task intent creates task successfully."""
    mock_parse = TaskParseResponse(
        title="Buy milk",
        project="Groceries",
        context="@errands",
        due_date="2024-01-15",
        defer_date=None,
        tags=[],
        confidence=0.95,
        raw_input="buy milk tomorrow for groceries",
    )

    mock_create = TaskCreateResponse(
        success=True,
        message="Task created",
        task_title="Buy milk",
        mail_drop_subject="Buy milk ::Groceries @errands --2024-01-15",
    )

    with patch(
        "src.productivity_service.services.alexa_handler.parse_task_tags",
        new_callable=AsyncMock,
        return_value=mock_parse,
    ), patch(
        "src.productivity_service.services.alexa_handler.create_omnifocus_task",
        new_callable=AsyncMock,
        return_value=mock_create,
    ):
        response = client.post(
            "/alexa",
            json={
                "version": "1.0",
                "request": {
                    "type": "IntentRequest",
                    "intent": {
                        "name": "CaptureTaskIntent",
                        "slots": {"taskText": {"name": "taskText", "value": "buy milk tomorrow for groceries"}},
                    },
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "Added" in data["response"]["outputSpeech"]["text"]
    assert "Buy milk" in data["response"]["outputSpeech"]["text"]


def test_alexa_capture_task_intent_no_text(client: TestClient) -> None:
    """Test Alexa capture task intent with no task text."""
    response = client.post(
        "/alexa",
        json={
            "version": "1.0",
            "request": {
                "type": "IntentRequest",
                "intent": {
                    "name": "CaptureTaskIntent",
                    "slots": {"taskText": {"name": "taskText", "value": ""}},
                },
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "didn't catch" in data["response"]["outputSpeech"]["text"].lower()
    assert data["response"]["shouldEndSession"] is False
