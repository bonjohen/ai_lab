"""Tests for persistence — CRUD operations, fork integrity, execution linkage."""

import pytest

from app.persistence.database import init_database
from app.persistence.repositories import (
    ConversationRepository,
    ExecutionRepository,
    MessageRepository,
)


@pytest.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = await init_database(db_path)
    yield conn
    await conn.close()


@pytest.fixture
def conv_repo(db):
    return ConversationRepository(db)


@pytest.fixture
def msg_repo(db):
    return MessageRepository(db)


@pytest.fixture
def exec_repo(db):
    return ExecutionRepository(db)


class TestConversationCRUD:
    async def test_create_and_get(self, conv_repo):
        conv = await conv_repo.create(source_id="src-1", title="Test Chat")
        assert conv["id"]
        assert conv["source_id"] == "src-1"
        assert conv["title"] == "Test Chat"

        fetched = await conv_repo.get(conv["id"])
        assert fetched is not None
        assert fetched["id"] == conv["id"]

    async def test_list_all(self, conv_repo):
        await conv_repo.create(source_id="src-1", title="Chat 1")
        await conv_repo.create(source_id="src-2", title="Chat 2")

        convs = await conv_repo.list_all()
        assert len(convs) == 2

    async def test_get_nonexistent_returns_none(self, conv_repo):
        assert await conv_repo.get("nonexistent") is None

    async def test_update_title(self, conv_repo):
        conv = await conv_repo.create(source_id="src-1", title="Old")
        await conv_repo.update_title(conv["id"], "New Title")

        fetched = await conv_repo.get(conv["id"])
        assert fetched["title"] == "New Title"


class TestMessages:
    async def test_append_and_retrieve(self, conv_repo, msg_repo):
        conv = await conv_repo.create(source_id="src-1")
        msg = await msg_repo.append(conv["id"], "user", "Hello")

        assert msg["role"] == "user"
        assert msg["content"] == "Hello"

        full = await conv_repo.get_with_messages(conv["id"])
        assert len(full["messages"]) == 1
        assert full["messages"][0]["content"] == "Hello"

    async def test_message_order(self, conv_repo, msg_repo):
        conv = await conv_repo.create(source_id="src-1")
        await msg_repo.append(conv["id"], "user", "First")
        await msg_repo.append(conv["id"], "assistant", "Second")
        await msg_repo.append(conv["id"], "user", "Third")

        full = await conv_repo.get_with_messages(conv["id"])
        contents = [m["content"] for m in full["messages"]]
        assert contents == ["First", "Second", "Third"]


class TestExecutionLinkage:
    async def test_execution_attached_to_message(self, conv_repo, msg_repo, exec_repo):
        conv = await conv_repo.create(source_id="src-1")
        await msg_repo.append(conv["id"], "user", "Hello")

        execution = await exec_repo.create(
            selected_source_id="src-1",
            correlation_id="corr-123",
            resolved_endpoint_id="ep-1",
            requested_model="llama3",
        )

        await exec_repo.complete(
            execution["id"],
            resolved_model="llama3:latest",
            token_usage={"prompt": 10, "completion": 20},
            status="completed",
        )

        await msg_repo.append(conv["id"], "assistant", "Hi there!", execution_id=execution["id"])

        full = await conv_repo.get_with_messages(conv["id"])
        assistant_msg = full["messages"][1]
        assert assistant_msg["execution_id"] == execution["id"]
        assert assistant_msg["execution"]["resolved_model"] == "llama3:latest"
        assert assistant_msg["execution"]["status"] == "completed"

    async def test_execution_error_state(self, exec_repo):
        execution = await exec_repo.create(
            selected_source_id="src-1", correlation_id="corr-err"
        )
        await exec_repo.complete(
            execution["id"],
            status="error",
            error_code="endpoint_unreachable",
            error_message="Connection refused",
        )
        fetched = await exec_repo.get(execution["id"])
        assert fetched["status"] == "error"
        assert fetched["error_code"] == "endpoint_unreachable"


class TestConversationFork:
    async def test_fork_copies_messages(self, conv_repo, msg_repo, exec_repo):
        conv = await conv_repo.create(source_id="src-1", title="Original")
        await msg_repo.append(conv["id"], "user", "Hello")

        execution = await exec_repo.create(
            selected_source_id="src-1", correlation_id="corr-1"
        )
        await msg_repo.append(conv["id"], "assistant", "Hi!", execution_id=execution["id"])

        forked = await conv_repo.fork(conv["id"], "src-2")

        assert forked is not None
        assert forked["source_id"] == "src-2"
        assert forked["title"] == "Fork of Original"
        assert len(forked["messages"]) == 2
        assert forked["messages"][0]["content"] == "Hello"
        assert forked["messages"][1]["content"] == "Hi!"
        # Forked assistant message retains original execution provenance
        assert forked["messages"][1]["execution_id"] == execution["id"]

    async def test_fork_nonexistent_returns_none(self, conv_repo):
        result = await conv_repo.fork("nonexistent", "src-2")
        assert result is None
