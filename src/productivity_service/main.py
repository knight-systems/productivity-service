"""FastAPI application entrypoint with Lambda handler."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from .config import settings
from .routes import alexa, health, obsidian, tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    logger.info(f"Starting {settings.service_name} in {settings.environment} mode")
    yield
    logger.info(f"Shutting down {settings.service_name}")


app = FastAPI(
    title="Productivity Service",
    description="Voice-to-task capture with AI tag parsing for OmniFocus",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(tasks.router, prefix="/tasks")
app.include_router(alexa.router)
app.include_router(obsidian.router)

# Lambda handler via Mangum
handler = Mangum(app, lifespan="off")
