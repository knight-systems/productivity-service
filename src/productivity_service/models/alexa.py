"""Alexa Skill request/response models."""

from typing import Any

from pydantic import BaseModel


class AlexaSlot(BaseModel):
    """Alexa slot value."""

    name: str
    value: str | None = None


class AlexaIntent(BaseModel):
    """Alexa intent with slots."""

    name: str
    slots: dict[str, AlexaSlot] = {}


class AlexaRequest(BaseModel):
    """Alexa request payload."""

    type: str
    intent: AlexaIntent | None = None
    locale: str = "en-US"


class AlexaSession(BaseModel):
    """Alexa session information."""

    sessionId: str
    new: bool = True


class AlexaRequestEnvelope(BaseModel):
    """Full Alexa request envelope."""

    version: str = "1.0"
    session: AlexaSession | None = None
    request: AlexaRequest
    context: dict[str, Any] = {}


class AlexaOutputSpeech(BaseModel):
    """Alexa speech output."""

    type: str = "PlainText"
    text: str


class AlexaCard(BaseModel):
    """Alexa card for visual display."""

    type: str = "Simple"
    title: str
    content: str


class AlexaResponseBody(BaseModel):
    """Alexa response body."""

    outputSpeech: AlexaOutputSpeech
    card: AlexaCard | None = None
    shouldEndSession: bool = True


class AlexaResponse(BaseModel):
    """Full Alexa response envelope."""

    version: str = "1.0"
    response: AlexaResponseBody
