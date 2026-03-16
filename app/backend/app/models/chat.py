"""Normalized chat request and stream event models.

Design doc references: §17 (chat request), §18 (stream events), §28 (error model).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Normalized Chat Request (§17) ---

class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class RuntimeOptions(BaseModel):
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = True


class ChatRequest(BaseModel):
    conversation_id: str
    source_id: str
    messages: list[ChatMessage]
    system_prompt: str | None = None
    options: RuntimeOptions = Field(default_factory=RuntimeOptions)


# --- Normalized Error Codes (§28) ---

class ErrorCode(str, Enum):
    configuration_error = "configuration_error"
    endpoint_unreachable = "endpoint_unreachable"
    auth_failed = "auth_failed"
    model_not_found = "model_not_found"
    timeout = "timeout"
    invalid_request = "invalid_request"
    provider_error = "provider_error"
    route_resolution_failed = "route_resolution_failed"
    cancelled = "cancelled"


# --- Normalized Stream Events (§18) ---

class StreamEventType(str, Enum):
    started = "started"
    delta = "delta"
    metadata = "metadata"
    completed = "completed"
    error = "error"
    cancelled = "cancelled"


class StreamEvent(BaseModel):
    type: StreamEventType
    # started
    execution_id: str | None = None
    source_id: str | None = None
    endpoint_id: str | None = None
    model: str | None = None
    # delta
    content: str | None = None
    # metadata
    token_usage: dict[str, int] | None = None
    timing: dict[str, Any] | None = None
    # error
    error_code: str | None = None
    error_message: str | None = None
