"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from src.productivity_service.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)
