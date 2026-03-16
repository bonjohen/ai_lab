"""Tests for configuration loader — validation rules from design doc §15."""

import json
from pathlib import Path

import pytest

from app.config.loader import ConfigError, ConfigLoader


class TestValidConfig:
    def test_loads_successfully(self, tmp_config_dir: Path):
        loader = ConfigLoader(tmp_config_dir)
        config = loader.load()

        assert len(config.sources) == 2
        assert len(config.endpoints) == 2
        assert len(config.routes) == 1
        assert len(config.capabilities) == 1
        assert len(config.policies) == 1

    def test_source_references_resolved(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()

        src_local = config.sources["src-local"]
        assert src_local.endpoint_id == "ep-local"
        assert src_local.route_id is None

        src_route = config.sources["src-route"]
        assert src_route.route_id == "rt-home"
        assert src_route.endpoint_id is None

    def test_app_config_defaults(self, tmp_config_dir: Path):
        config = ConfigLoader(tmp_config_dir).load()
        assert config.app.health_check_interval_seconds == 30
        assert config.app.log_level == "DEBUG"


class TestDuplicateIds:
    def test_duplicate_endpoint_ids(self, tmp_config_dir: Path):
        ep_file = tmp_config_dir / "endpoints.json"
        eps = json.loads(ep_file.read_text())
        eps.append(eps[0].copy())  # duplicate
        ep_file.write_text(json.dumps(eps))

        with pytest.raises(ConfigError, match="duplicate id 'ep-local'"):
            ConfigLoader(tmp_config_dir).load()


class TestMissingReferences:
    def test_source_references_missing_endpoint(self, tmp_config_dir: Path):
        src_file = tmp_config_dir / "sources.json"
        sources = json.loads(src_file.read_text())
        sources.append({
            "id": "src-bad", "display_name": "Bad", "source_class": "local",
            "endpoint_id": "nonexistent", "capability_profile_id": "ollama-chat",
        })
        src_file.write_text(json.dumps(sources))

        with pytest.raises(ConfigError, match="endpoint_id 'nonexistent' not found"):
            ConfigLoader(tmp_config_dir).load()

    def test_source_references_missing_capability(self, tmp_config_dir: Path):
        src_file = tmp_config_dir / "sources.json"
        sources = json.loads(src_file.read_text())
        sources.append({
            "id": "src-bad", "display_name": "Bad", "source_class": "local",
            "endpoint_id": "ep-local", "capability_profile_id": "nonexistent",
        })
        src_file.write_text(json.dumps(sources))

        with pytest.raises(ConfigError, match="capability_profile_id 'nonexistent' not found"):
            ConfigLoader(tmp_config_dir).load()

    def test_source_references_missing_policy(self, tmp_config_dir: Path):
        src_file = tmp_config_dir / "sources.json"
        sources = json.loads(src_file.read_text())
        sources.append({
            "id": "src-bad", "display_name": "Bad", "source_class": "local",
            "endpoint_id": "ep-local", "capability_profile_id": "ollama-chat",
            "policy_id": "nonexistent",
        })
        src_file.write_text(json.dumps(sources))

        with pytest.raises(ConfigError, match="policy_id 'nonexistent' not found"):
            ConfigLoader(tmp_config_dir).load()

    def test_route_references_missing_endpoint(self, tmp_config_dir: Path):
        rt_file = tmp_config_dir / "routes.json"
        routes = json.loads(rt_file.read_text())
        routes.append({
            "id": "rt-bad", "display_name": "Bad Route",
            "endpoint_ids": ["nonexistent"],
        })
        rt_file.write_text(json.dumps(routes))

        with pytest.raises(ConfigError, match="endpoint_id 'nonexistent' not found"):
            ConfigLoader(tmp_config_dir).load()


class TestSourceTargetValidation:
    def test_source_with_both_endpoint_and_route(self, tmp_config_dir: Path):
        src_file = tmp_config_dir / "sources.json"
        sources = json.loads(src_file.read_text())
        sources.append({
            "id": "src-both", "display_name": "Both", "source_class": "local",
            "endpoint_id": "ep-local", "route_id": "rt-home",
            "capability_profile_id": "ollama-chat",
        })
        src_file.write_text(json.dumps(sources))

        with pytest.raises(ConfigError, match="references both endpoint_id and route_id"):
            ConfigLoader(tmp_config_dir).load()

    def test_source_with_neither_endpoint_nor_route(self, tmp_config_dir: Path):
        src_file = tmp_config_dir / "sources.json"
        sources = json.loads(src_file.read_text())
        sources.append({
            "id": "src-none", "display_name": "None", "source_class": "local",
            "capability_profile_id": "ollama-chat",
        })
        src_file.write_text(json.dumps(sources))

        with pytest.raises(ConfigError, match="must reference endpoint_id or route_id"):
            ConfigLoader(tmp_config_dir).load()


class TestMissingFiles:
    def test_missing_config_file_reports_error(self, tmp_path: Path):
        config_dir = tmp_path / "empty"
        config_dir.mkdir()
        # Only create app_config.json
        (config_dir / "app_config.json").write_text("{}")
        # All list files missing — should collect errors but not crash
        with pytest.raises(ConfigError, match="file not found"):
            ConfigLoader(config_dir).load()


class TestMalformedJson:
    def test_invalid_json_reports_error(self, tmp_config_dir: Path):
        (tmp_config_dir / "endpoints.json").write_text("not json")

        with pytest.raises(ConfigError, match="invalid JSON"):
            ConfigLoader(tmp_config_dir).load()

    def test_wrong_type_reports_error(self, tmp_config_dir: Path):
        (tmp_config_dir / "endpoints.json").write_text(json.dumps({"not": "an array"}))

        with pytest.raises(ConfigError, match="expected a JSON array"):
            ConfigLoader(tmp_config_dir).load()
