"""Tests for health check endpoint."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test that health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "environment" in data


def test_health_check_returns_service_name(client: TestClient) -> None:
    """Test that health endpoint returns correct service name."""
    response = client.get("/health")
    data = response.json()
    assert data["service"] == "productivity-service"
