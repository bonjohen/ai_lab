"""Router adapter — wraps an OpenAI-compatible endpoint that may resolve
to a different downstream model.

Design doc references: §6 (router source type), §19 (adapter contract),
§23 (requested vs resolved model).
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.adapters.openai_compatible import OpenAICompatibleAdapter
from app.models.chat import RuntimeOptions, StreamEvent, StreamEventType
from app.models.config import Endpoint

logger = logging.getLogger(__name__)


class RouterAdapter(OpenAICompatibleAdapter):
    """Extends OpenAI-compatible adapter with router-aware metadata.

    The key difference: routers may return a different model in the response
    than what was requested. This adapter tracks both requested and resolved
    model names for provenance.
    """

    async def chat(
        self,
        endpoint: Endpoint,
        model: str,
        messages: list[dict],
        options: RuntimeOptions,
    ) -> AsyncIterator[StreamEvent]:
        requested_model = model

        async for event in super().chat(endpoint, model, messages, options):
            # If the router resolved to a different model, log it
            if event.type == StreamEventType.completed and event.model != requested_model:
                logger.info(
                    "Router resolved %s -> %s on endpoint %s",
                    requested_model, event.model, endpoint.id,
                )
            yield event
