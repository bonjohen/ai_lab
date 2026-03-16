"""Tests for chat orchestration service — unit tests with mocked adapter."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.config.loader import ConfigLoader
from app.models.chat import ChatMessage, ChatRequest, RuntimeOptions, StreamEvent, StreamEventType
from app.persistence.database import init_database
from app.services.chat import ChatService


@pytest.fixture
async def db(tmp_path):
    conn = await init_database(str(tmp_path / "test.db"))
    yield conn
    await conn.close()


@pytest.fixture
def config(tmp_config_dir):
    return ConfigLoader(tmp_config_dir).load()


@pytest.fixture
def chat_service(config, db):
    return ChatService(config, db)


def _mock_chat_events():
    """Simulate a successful adapter chat response."""
    async def mock_chat(endpoint, model, messages, options):
        yield StreamEvent(type=StreamEventType.delta, content="Hello ")
        yield StreamEvent(type=StreamEventType.delta, content="there!")
        yield StreamEvent(
            type=StreamEventType.metadata,
            token_usage={"prompt": 5, "completion": 2},
            model="llama3:latest",
        )
        yield StreamEvent(type=StreamEventType.completed, model="llama3:latest")
    return mock_chat


def _mock_error_events():
    async def mock_chat(endpoint, model, messages, options):
        yield StreamEvent(
            type=StreamEventType.error,
            error_code="endpoint_unreachable",
            error_message="Connection refused",
        )
    return mock_chat


class TestChatService:
    async def test_successful_chat(self, chat_service, db):
        from app.persistence.repositories import ConversationRepository
        conv = await ConversationRepository(db).create(source_id="src-local")

        request = ChatRequest(
            conversation_id=conv["id"],
            source_id="src-local",
            messages=[ChatMessage(role="user", content="Hi")],
        )

        mock_adapter = AsyncMock()
        mock_adapter.chat = _mock_chat_events()

        with patch("app.services.chat.get_adapter", return_value=mock_adapter):
            events = []
            async for event in chat_service.handle_chat(request):
                events.append(event)

        types = [e.type for e in events]
        assert StreamEventType.started in types
        assert StreamEventType.delta in types
        assert StreamEventType.completed in types

        # Verify execution was persisted
        from app.persistence.repositories import ExecutionRepository
        started_event = next(e for e in events if e.type == StreamEventType.started)
        exec_record = await ExecutionRepository(db).get(started_event.execution_id)
        assert exec_record["status"] == "completed"
        assert exec_record["resolved_model"] == "llama3:latest"

    async def test_invalid_source(self, chat_service):
        request = ChatRequest(
            conversation_id="conv-1",
            source_id="nonexistent",
            messages=[ChatMessage(role="user", content="Hi")],
        )

        events = []
        async for event in chat_service.handle_chat(request):
            events.append(event)

        assert len(events) == 1
        assert events[0].type == StreamEventType.error
        assert events[0].error_code == "configuration_error"

    async def test_adapter_error_persisted(self, chat_service, db):
        from app.persistence.repositories import ConversationRepository
        conv = await ConversationRepository(db).create(source_id="src-local")

        request = ChatRequest(
            conversation_id=conv["id"],
            source_id="src-local",
            messages=[ChatMessage(role="user", content="Hi")],
        )

        mock_adapter = AsyncMock()
        mock_adapter.chat = _mock_error_events()

        with patch("app.services.chat.get_adapter", return_value=mock_adapter):
            events = []
            async for event in chat_service.handle_chat(request):
                events.append(event)

        error_event = next(e for e in events if e.type == StreamEventType.error)
        assert error_event.error_code == "endpoint_unreachable"

        # Verify execution marked as error
        started_event = next(e for e in events if e.type == StreamEventType.started)
        from app.persistence.repositories import ExecutionRepository
        exec_record = await ExecutionRepository(db).get(started_event.execution_id)
        assert exec_record["status"] == "error"

    async def test_policy_defaults_applied(self, chat_service, db):
        from app.persistence.repositories import ConversationRepository
        conv = await ConversationRepository(db).create(source_id="src-local")

        request = ChatRequest(
            conversation_id=conv["id"],
            source_id="src-local",
            messages=[ChatMessage(role="user", content="Hi")],
            options=RuntimeOptions(),  # no explicit temp/max_tokens
        )

        mock_adapter = AsyncMock()
        mock_adapter.chat = _mock_chat_events()

        captured_options = []
        original_mock = _mock_chat_events()

        async def capturing_chat(endpoint, model, messages, options):
            captured_options.append(options)
            async for event in original_mock(endpoint, model, messages, options):
                yield event

        mock_adapter.chat = capturing_chat

        with patch("app.services.chat.get_adapter", return_value=mock_adapter):
            async for _ in chat_service.handle_chat(request):
                pass

        # Policy default temperature should be 0.7
        assert len(captured_options) == 1
        assert captured_options[0].temperature == 0.7
        assert captured_options[0].max_tokens == 2048
