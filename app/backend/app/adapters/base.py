"""Base adapter contract.

Design doc reference: §19 — each adapter implements a common interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.models.chat import ChatRequest, RuntimeOptions, StreamEvent
from app.models.config import Endpoint


class HealthResult:
    def __init__(self, healthy: bool, latency_ms: float | None = None, detail: str | None = None):
        self.healthy = healthy
        self.latency_ms = latency_ms
        self.detail = detail


class ModelInfo:
    def __init__(self, name: str, size: int | None = None, modified_at: str | None = None):
        self.name = name
        self.size = size
        self.modified_at = modified_at


class BaseAdapter(ABC):
    """Common interface for all provider adapters."""

    @abstractmethod
    async def health_check(self, endpoint: Endpoint) -> HealthResult:
        ...

    @abstractmethod
    async def list_models(self, endpoint: Endpoint) -> list[ModelInfo]:
        ...

    @abstractmethod
    async def chat(
        self,
        endpoint: Endpoint,
        model: str,
        messages: list[dict],
        options: RuntimeOptions,
    ) -> AsyncIterator[StreamEvent]:
        ...

    def validate_options(self, options: RuntimeOptions) -> RuntimeOptions:
        """Validate and normalize runtime options. Override in subclasses."""
        return options
