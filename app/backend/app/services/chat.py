"""Chat orchestration service.

Design doc references: §16 (chat request/stream), §17 (normalized request),
§19 (adapter selection), §23 (provenance semantics).
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator

import aiosqlite

from app.adapters.registry import get_adapter
from app.models.chat import (
    ChatRequest,
    ErrorCode,
    StreamEvent,
    StreamEventType,
)
from app.models.config import RuntimeConfig
from app.persistence.repositories import ExecutionRepository, MessageRepository

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, config: RuntimeConfig, db: aiosqlite.Connection):
        self.config = config
        self.db = db
        self.msg_repo = MessageRepository(db)
        self.exec_repo = ExecutionRepository(db)

    async def handle_chat(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        correlation_id = str(uuid.uuid4())

        # Resolve source
        source = self.config.sources.get(request.source_id)
        if source is None:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.configuration_error,
                error_message=f"Source '{request.source_id}' not found",
            )
            return

        # Resolve endpoint (direct only for Phase 3 — route resolution in Phase 4)
        endpoint = None
        route_id = None
        if source.endpoint_id:
            endpoint = self.config.endpoints.get(source.endpoint_id)
        elif source.route_id:
            # Placeholder for Phase 4 route resolution
            route_id = source.route_id
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.route_resolution_failed,
                error_message="Route resolution not yet implemented",
            )
            return

        if endpoint is None:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.configuration_error,
                error_message=f"Endpoint for source '{request.source_id}' not found",
            )
            return

        # Resolve model
        model = source.default_model or endpoint.default_model
        if model is None:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.configuration_error,
                error_message="No model configured for this source",
            )
            return

        # Apply policy defaults
        options = request.options
        if source.policy_id:
            policy = self.config.policies.get(source.policy_id)
            if policy:
                if options.temperature is None:
                    options.temperature = policy.defaults.temperature
                if options.max_tokens is None:
                    options.max_tokens = policy.defaults.max_tokens

        # Get adapter
        try:
            adapter = get_adapter(endpoint.provider_type)
        except ValueError as exc:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.configuration_error,
                error_message=str(exc),
            )
            return

        # Create execution record
        execution = await self.exec_repo.create(
            selected_source_id=request.source_id,
            correlation_id=correlation_id,
            resolved_endpoint_id=endpoint.id,
            route_id=route_id,
            requested_model=model,
            adapter_type=endpoint.provider_type.value,
            request_options={"temperature": options.temperature, "max_tokens": options.max_tokens},
        )

        logger.info(
            "[%s] Chat request: source=%s endpoint=%s model=%s",
            correlation_id, source.id, endpoint.id, model,
        )

        # Emit started event
        yield StreamEvent(
            type=StreamEventType.started,
            execution_id=execution["id"],
            source_id=source.id,
            endpoint_id=endpoint.id,
            model=model,
        )

        # Persist user message (last one in the list)
        if request.messages:
            last_msg = request.messages[-1]
            if last_msg.role == "user":
                await self.msg_repo.append(
                    request.conversation_id, "user", last_msg.content
                )

        # Prepare messages for adapter
        adapter_messages = []
        if request.system_prompt:
            adapter_messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            adapter_messages.append({"role": msg.role, "content": msg.content})

        # Stream from adapter
        full_content = []
        resolved_model = None
        token_usage = None
        error_occurred = False

        async for event in adapter.chat(endpoint, model, adapter_messages, options):
            if event.type == StreamEventType.delta:
                full_content.append(event.content or "")
                yield event
            elif event.type == StreamEventType.metadata:
                token_usage = event.token_usage
                resolved_model = event.model or model
                yield event
            elif event.type == StreamEventType.error:
                error_occurred = True
                await self.exec_repo.complete(
                    execution["id"],
                    status="error",
                    error_code=event.error_code,
                    error_message=event.error_message,
                )
                yield event
                return
            elif event.type == StreamEventType.completed:
                resolved_model = event.model or model
                yield event

        if not error_occurred:
            # Persist assistant message and complete execution
            assistant_content = "".join(full_content)
            if assistant_content:
                await self.msg_repo.append(
                    request.conversation_id, "assistant", assistant_content,
                    execution_id=execution["id"],
                )

            await self.exec_repo.complete(
                execution["id"],
                resolved_model=resolved_model,
                token_usage=token_usage,
                status="completed",
            )

            logger.info("[%s] Chat completed: model=%s", correlation_id, resolved_model)
