"""Tests for task endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.productivity_service.models.task import TaskCreateResponse, TaskParseResponse


def test_parse_task_returns_200(client: TestClient) -> None:
    """Test that parse endpoint returns 200."""
    mock_response = TaskParseResponse(
        title="Buy milk",
        project="Groceries",
        context="@errands",
        due_date="2024-01-15",
        defer_date=None,
        tags=[],
        confidence=0.95,
        raw_input="Buy milk tomorrow for groceries",
    )

    with patch(
        "src.productivity_service.routes.tasks.parse_task_tags",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = client.post(
            "/tasks/parse",
            json={"text": "Buy milk tomorrow for groceries"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Buy milk"
    assert data["project"] == "Groceries"
    assert data["confidence"] == 0.95


def test_parse_task_validates_empty_text(client: TestClient) -> None:
    """Test that parse endpoint validates empty text."""
    response = client.post("/tasks/parse", json={"text": ""})
    assert response.status_code == 422  # Validation error


def test_create_task_returns_200(client: TestClient) -> None:
    """Test that create endpoint returns 200."""
    mock_response = TaskCreateResponse(
        success=True,
        message="Task created: Buy milk",
        task_title="Buy milk",
        mail_drop_subject="Buy milk ::Groceries @errands --2024-01-15",
    )

    with patch(
        "src.productivity_service.routes.tasks.create_omnifocus_task",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        response = client.post(
            "/tasks/create",
            json={
                "title": "Buy milk",
                "project": "Groceries",
                "context": "errands",
                "due_date": "2024-01-15",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Buy milk" in data["message"]


def test_capture_task_parses_and_creates(client: TestClient) -> None:
    """Test that capture endpoint combines parse and create."""
    mock_parse = TaskParseResponse(
        title="Call mom",
        project=None,
        context="@phone",
        due_date=None,
        defer_date=None,
        tags=[],
        confidence=0.9,
        raw_input="Call mom",
    )

    mock_create = TaskCreateResponse(
        success=True,
        message="Task created: Call mom",
        task_title="Call mom",
        mail_drop_subject="Call mom @phone",
    )

    with patch(
        "src.productivity_service.routes.tasks.parse_task_tags",
        new_callable=AsyncMock,
        return_value=mock_parse,
    ), patch(
        "src.productivity_service.routes.tasks.create_omnifocus_task",
        new_callable=AsyncMock,
        return_value=mock_create,
    ):
        response = client.post("/tasks/capture", json={"text": "Call mom"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
