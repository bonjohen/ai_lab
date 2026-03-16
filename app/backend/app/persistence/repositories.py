"""Repository pattern for persistence operations.

Design doc references: §22 (persistence model), §23 (provenance semantics), §24 (conversation rules).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row: aiosqlite.Row) -> dict:
    return dict(row)


class ConversationRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create(self, source_id: str, title: str | None = None) -> dict:
        conv_id = _new_id()
        now = _now()
        await self.db.execute(
            "INSERT INTO conversations (id, title, source_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, title, source_id, now, now),
        )
        await self.db.commit()
        return {"id": conv_id, "title": title, "source_id": source_id,
                "created_at": now, "updated_at": now, "archived": False}

    async def list_all(self) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM conversations WHERE archived = 0 ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def get(self, conversation_id: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def get_with_messages(self, conversation_id: str) -> dict | None:
        conv = await self.get(conversation_id)
        if conv is None:
            return None

        cursor = await self.db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        messages = [_row_to_dict(r) for r in await cursor.fetchall()]

        # Attach execution summaries to assistant messages
        for msg in messages:
            if msg.get("execution_id"):
                exec_cursor = await self.db.execute(
                    "SELECT * FROM executions WHERE id = ?", (msg["execution_id"],)
                )
                exec_row = await exec_cursor.fetchone()
                if exec_row:
                    msg["execution"] = _row_to_dict(exec_row)

        conv["messages"] = messages
        return conv

    async def update_title(self, conversation_id: str, title: str) -> None:
        await self.db.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now(), conversation_id),
        )
        await self.db.commit()

    async def fork(self, conversation_id: str, new_source_id: str) -> dict | None:
        """Fork a conversation to a new source (design doc §24).

        Copies visible messages into a new conversation. Copied assistant messages
        retain their original execution provenance.
        """
        original = await self.get_with_messages(conversation_id)
        if original is None:
            return None

        new_conv = await self.create(
            source_id=new_source_id,
            title=f"Fork of {original.get('title') or conversation_id[:8]}",
        )

        for msg in original.get("messages", []):
            await self.db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, created_at, execution_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (_new_id(), new_conv["id"], msg["role"], msg["content"],
                 msg["created_at"], msg.get("execution_id")),
            )
        await self.db.commit()

        return await self.get_with_messages(new_conv["id"])


class MessageRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def append(
        self,
        conversation_id: str,
        role: str,
        content: str,
        execution_id: str | None = None,
    ) -> dict:
        msg_id = _new_id()
        now = _now()
        await self.db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at, execution_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, now, execution_id),
        )
        # Update conversation timestamp
        await self.db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        await self.db.commit()
        return {"id": msg_id, "conversation_id": conversation_id, "role": role,
                "content": content, "created_at": now, "execution_id": execution_id}


class ExecutionRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def create(
        self,
        selected_source_id: str,
        correlation_id: str,
        resolved_endpoint_id: str | None = None,
        route_id: str | None = None,
        requested_model: str | None = None,
        adapter_type: str | None = None,
        request_options: dict | None = None,
    ) -> dict:
        exec_id = _new_id()
        now = _now()
        await self.db.execute(
            "INSERT INTO executions "
            "(id, selected_source_id, resolved_endpoint_id, route_id, requested_model, "
            "adapter_type, request_options_json, status, started_at, correlation_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (exec_id, selected_source_id, resolved_endpoint_id, route_id,
             requested_model, adapter_type,
             json.dumps(request_options) if request_options else None,
             now, correlation_id),
        )
        await self.db.commit()
        return {"id": exec_id, "selected_source_id": selected_source_id,
                "status": "pending", "started_at": now, "correlation_id": correlation_id}

    async def complete(
        self,
        execution_id: str,
        resolved_model: str | None = None,
        token_usage: dict | None = None,
        status: str = "completed",
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await self.db.execute(
            "UPDATE executions SET resolved_model = ?, token_usage_json = ?, "
            "status = ?, error_code = ?, error_message = ?, completed_at = ? WHERE id = ?",
            (resolved_model,
             json.dumps(token_usage) if token_usage else None,
             status, error_code, error_message, _now(), execution_id),
        )
        await self.db.commit()

    async def get(self, execution_id: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM executions WHERE id = ?", (execution_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None
