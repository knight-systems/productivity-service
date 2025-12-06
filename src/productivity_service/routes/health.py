"""Health check endpoint."""

from fastapi import APIRouter

from ..config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return service health status."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "environment": settings.environment,
    }
