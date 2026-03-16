"""SQLite database initialization and migration.

Design doc reference: §31 (SQLite schema direction).
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    source_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    execution_id TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    selected_source_id TEXT NOT NULL,
    resolved_endpoint_id TEXT,
    route_id TEXT,
    requested_model TEXT,
    resolved_model TEXT,
    adapter_type TEXT,
    request_options_json TEXT,
    token_usage_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_code TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    correlation_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS endpoint_health_snapshots (
    id TEXT PRIMARY KEY,
    endpoint_id TEXT NOT NULL,
    status TEXT NOT NULL,
    latency_ms REAL,
    checked_at TEXT NOT NULL,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS endpoint_inventory_snapshots (
    id TEXT PRIMARY KEY,
    endpoint_id TEXT NOT NULL,
    models_json TEXT NOT NULL,
    refreshed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_executions_correlation ON executions(correlation_id);
CREATE INDEX IF NOT EXISTS idx_health_endpoint ON endpoint_health_snapshots(endpoint_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_inventory_endpoint ON endpoint_inventory_snapshots(endpoint_id, refreshed_at);
"""


async def init_database(db_path: str) -> aiosqlite.Connection:
    """Initialize database, create tables if needed, return connection."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    db = await aiosqlite.connect(str(path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(SCHEMA_SQL)
    await db.commit()

    logger.info("Database initialized at %s", db_path)
    return db
