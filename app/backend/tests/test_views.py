"""Tests for UI-safe view model generation."""

from pathlib import Path

from app.config.loader import ConfigLoader
from app.config.views import build_source_detail, build_source_list


class TestBuildSourceList:
    def test_returns_visible_sources(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()
        items = build_source_list(config)

        assert len(items) == 2
        ids = {item.id for item in items}
        assert "src-local" in ids
        assert "src-route" in ids

    def test_source_list_item_fields(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()
        items = build_source_list(config)
        local = next(i for i in items if i.id == "src-local")

        assert local.display_name == "Local Llama"
        assert local.source_class == "local"
        assert local.tags == ["local"]
        assert local.is_route is False
        assert local.default_model == "llama3:latest"  # falls back to endpoint default
        assert local.capabilities.supports_streaming is True

    def test_route_source_flagged(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()
        items = build_source_list(config)
        route = next(i for i in items if i.id == "src-route")

        assert route.is_route is True


class TestBuildSourceDetail:
    def test_direct_endpoint_detail(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()
        detail = build_source_detail(config, "src-local")

        assert detail is not None
        assert detail.endpoint_display_name == "Local Ollama"
        assert detail.route_display_name is None

    def test_route_source_detail(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()
        detail = build_source_detail(config, "src-route")

        assert detail is not None
        assert detail.route_display_name == "Home Route"
        assert detail.route_endpoint_count == 2

    def test_nonexistent_source_returns_none(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()
        assert build_source_detail(config, "nonexistent") is None
