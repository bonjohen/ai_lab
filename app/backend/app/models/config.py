"""Configuration domain models — loaded from JSON files.

Design doc references: §11-15 (configuration strategy, entity definitions, validation rules).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class ProviderType(str, Enum):
    ollama = "ollama"
    openai_compatible = "openai_compatible"
    provider_native = "provider_native"
    router_api = "router_api"


class SourceClass(str, Enum):
    local = "local"
    lan = "lan"
    provider = "provider"
    router = "router"


class SelectionStrategy(str, Enum):
    first_healthy = "first_healthy"
    first_healthy_with_model = "first_healthy_with_model"


# --- Config file models ---

class AppConfig(BaseModel):
    """app_config.json — application-wide behavior."""
    health_check_interval_seconds: int = 30
    inventory_refresh_interval_seconds: int = 120
    database_path: str = "data/ai_lab.db"
    log_level: str = "INFO"


class CapabilityProfile(BaseModel):
    """capabilities.json entry — reusable feature/control definition."""
    id: str
    supports_streaming: bool = True
    supports_system_prompt: bool = True
    supports_temperature: bool = True
    supports_top_p: bool = False
    supports_max_tokens: bool = True
    supports_structured_output: bool = False
    supports_tool_calling: bool = False
    supports_vision: bool = False


class HealthCheckConfig(BaseModel):
    enabled: bool = True
    timeout_seconds: float = 5.0
    path: str = "/"


class Endpoint(BaseModel):
    """endpoints.json entry — one concrete backend target."""
    id: str
    display_name: str
    provider_type: ProviderType
    base_url: str
    default_model: str | None = None
    auth_ref: str | None = None
    is_ollama_node: bool = False
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Route(BaseModel):
    """routes.json entry — logical resolver over multiple endpoints."""
    id: str
    display_name: str
    endpoint_ids: list[str]
    strategy: SelectionStrategy = SelectionStrategy.first_healthy
    required_model: str | None = None
    fallback_message: str | None = None


class Source(BaseModel):
    """sources.json entry — one user-selectable target in the UI."""
    id: str
    display_name: str
    source_class: SourceClass
    endpoint_id: str | None = None
    route_id: str | None = None
    capability_profile_id: str
    default_model: str | None = None
    tags: list[str] = Field(default_factory=list)
    visible: bool = True
    policy_id: str | None = None


class PolicyDefaults(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = True


class PolicyLimits(BaseModel):
    max_temperature: float = 2.0
    max_max_tokens: int = 32768
    timeout_seconds: float = 120.0
    max_retries: int = 1


class PolicyAdvancedOverrides(BaseModel):
    allow_top_p: bool = False
    allow_seed: bool = False
    allow_repetition_penalty: bool = False


class Policy(BaseModel):
    """policies.json entry — runtime limits and allowed overrides."""
    id: str
    display_name: str
    scope: str = "global"
    defaults: PolicyDefaults = Field(default_factory=PolicyDefaults)
    limits: PolicyLimits = Field(default_factory=PolicyLimits)
    advanced_overrides: PolicyAdvancedOverrides = Field(default_factory=PolicyAdvancedOverrides)


# --- Merged runtime config ---

class RuntimeConfig(BaseModel):
    """Complete validated configuration, merged from all JSON files."""
    app: AppConfig
    capabilities: dict[str, CapabilityProfile]
    endpoints: dict[str, Endpoint]
    routes: dict[str, Route]
    sources: dict[str, Source]
    policies: dict[str, Policy]
