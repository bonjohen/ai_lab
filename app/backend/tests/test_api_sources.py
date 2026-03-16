"""Tests for source API endpoints."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config.loader import ConfigLoader


@pytest.fixture
def test_app(tmp_config_dir: Path):
    """Create a FastAPI app with test config."""
    from app.main import create_app

    app = create_app()
    # Manually load config instead of relying on lifespan
    config = ConfigLoader(tmp_config_dir).load()
    app.state.config = config
    return app


@pytest.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestListSources:
    async def test_returns_sources(self, client: AsyncClient):
        resp = await client.get("/api/sources")
        assert resp.status_code == 200

        data = resp.json()
        assert len(data) == 2
        ids = {s["id"] for s in data}
        assert "src-local" in ids
        assert "src-route" in ids

    async def test_source_shape(self, client: AsyncClient):
        resp = await client.get("/api/sources")
        source = next(s for s in resp.json() if s["id"] == "src-local")

        assert source["display_name"] == "Local Llama"
        assert source["source_class"] == "local"
        assert "capabilities" in source
        assert source["capabilities"]["supports_streaming"] is True


class TestGetSource:
    async def test_returns_detail(self, client: AsyncClient):
        resp = await client.get("/api/sources/src-local")
        assert resp.status_code == 200

        data = resp.json()
        assert data["id"] == "src-local"
        assert data["endpoint_display_name"] == "Local Ollama"

    async def test_not_found(self, client: AsyncClient):
        resp = await client.get("/api/sources/nonexistent")
        assert resp.status_code == 404
