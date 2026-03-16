import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Provide a temp dir pre-populated with valid config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "app_config.json").write_text(json.dumps({
        "health_check_interval_seconds": 30,
        "inventory_refresh_interval_seconds": 120,
        "database_path": "data/test.db",
        "log_level": "DEBUG",
    }))

    (config_dir / "capabilities.json").write_text(json.dumps([
        {"id": "ollama-chat", "supports_streaming": True, "supports_system_prompt": True,
         "supports_temperature": True, "supports_max_tokens": True},
    ]))

    (config_dir / "endpoints.json").write_text(json.dumps([
        {"id": "ep-local", "display_name": "Local Ollama", "provider_type": "ollama",
         "base_url": "http://localhost:11434", "default_model": "llama3:latest",
         "is_ollama_node": True},
        {"id": "ep-remote", "display_name": "Remote Ollama", "provider_type": "ollama",
         "base_url": "http://remote:11434", "is_ollama_node": True},
    ]))

    (config_dir / "routes.json").write_text(json.dumps([
        {"id": "rt-home", "display_name": "Home Route",
         "endpoint_ids": ["ep-local", "ep-remote"], "strategy": "first_healthy"},
    ]))

    (config_dir / "sources.json").write_text(json.dumps([
        {"id": "src-local", "display_name": "Local Llama", "source_class": "local",
         "endpoint_id": "ep-local", "capability_profile_id": "ollama-chat",
         "tags": ["local"], "visible": True, "policy_id": "pol-default"},
        {"id": "src-route", "display_name": "Home Auto", "source_class": "lan",
         "route_id": "rt-home", "capability_profile_id": "ollama-chat",
         "tags": ["lan"], "visible": True},
    ]))

    (config_dir / "policies.json").write_text(json.dumps([
        {"id": "pol-default", "display_name": "Default"},
    ]))

    return config_dir
