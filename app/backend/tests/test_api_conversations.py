"""Tests for conversation API endpoints."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config.loader import ConfigLoader
from app.persistence.database import init_database


@pytest.fixture
async def test_app(tmp_config_dir: Path, tmp_path: Path):
    from app.main import create_app

    app = create_app()
    config = ConfigLoader(tmp_config_dir).load()
    app.state.config = config
    app.state.db = await init_database(str(tmp_path / "test.db"))
    yield app
    await app.state.db.close()


@pytest.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestCreateConversation:
    async def test_create(self, client: AsyncClient):
        resp = await client.post(
            "/api/conversations", json={"source_id": "src-local", "title": "Test"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == "src-local"
        assert data["title"] == "Test"

    async def test_create_invalid_source(self, client: AsyncClient):
        resp = await client.post(
            "/api/conversations", json={"source_id": "nonexistent"}
        )
        assert resp.status_code == 400


class TestListConversations:
    async def test_list_empty(self, client: AsyncClient):
        resp = await client.get("/api/conversations")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_after_create(self, client: AsyncClient):
        await client.post("/api/conversations", json={"source_id": "src-local"})
        await client.post("/api/conversations", json={"source_id": "src-route"})

        resp = await client.get("/api/conversations")
        assert len(resp.json()) == 2


class TestGetConversation:
    async def test_get_with_messages(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/conversations", json={"source_id": "src-local"}
        )
        conv_id = create_resp.json()["id"]

        resp = await client.get(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == conv_id
        assert "messages" in resp.json()

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get("/api/conversations/nonexistent")
        assert resp.status_code == 404


class TestForkConversation:
    async def test_fork(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/conversations", json={"source_id": "src-local", "title": "Original"}
        )
        conv_id = create_resp.json()["id"]

        fork_resp = await client.post(
            f"/api/conversations/{conv_id}/fork",
            json={"new_source_id": "src-route"},
        )
        assert fork_resp.status_code == 200
        data = fork_resp.json()
        assert data["source_id"] == "src-route"
        assert "Fork of Original" in data["title"]

    async def test_fork_invalid_source(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/conversations", json={"source_id": "src-local"}
        )
        conv_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/conversations/{conv_id}/fork",
            json={"new_source_id": "nonexistent"},
        )
        assert resp.status_code == 400

    async def test_fork_not_found(self, client: AsyncClient):
        resp = await client.post(
            "/api/conversations/nonexistent/fork",
            json={"new_source_id": "src-local"},
        )
        assert resp.status_code == 404
