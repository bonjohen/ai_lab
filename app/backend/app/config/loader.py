"""Configuration loader — reads JSON files, validates cross-references,
produces a single RuntimeConfig.

Design doc references: §11 (strategy), §13 (entity definitions), §15 (validation rules).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.models.config import (
    AppConfig,
    CapabilityProfile,
    Endpoint,
    Policy,
    Route,
    RuntimeConfig,
    Source,
)

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration is invalid. Contains all collected errors."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(f"  - {e}" for e in errors))


class ConfigLoader:
    """Loads and validates configuration from a directory of JSON files."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self._errors: list[str] = []

    def load(self) -> RuntimeConfig:
        """Load all config files, validate, and return RuntimeConfig.

        Raises ConfigError if any validation errors are found.
        """
        self._errors = []

        app_config = self._load_app_config()
        capabilities = self._load_list("capabilities.json", CapabilityProfile)
        endpoints = self._load_list("endpoints.json", Endpoint)
        routes = self._load_list("routes.json", Route)
        sources = self._load_list("sources.json", Source)
        policies = self._load_list("policies.json", Policy)

        # Index by id, checking for duplicates
        cap_map = self._index_by_id("capabilities.json", capabilities)
        ep_map = self._index_by_id("endpoints.json", endpoints)
        rt_map = self._index_by_id("routes.json", routes)
        src_map = self._index_by_id("sources.json", sources)
        pol_map = self._index_by_id("policies.json", policies)

        # Cross-reference validation
        self._validate_sources(src_map, ep_map, rt_map, cap_map, pol_map)
        self._validate_routes(rt_map, ep_map)
        self._validate_ollama_endpoints(ep_map, rt_map)

        if self._errors:
            raise ConfigError(self._errors)

        config = RuntimeConfig(
            app=app_config,
            capabilities=cap_map,
            endpoints=ep_map,
            routes=rt_map,
            sources=src_map,
            policies=pol_map,
        )

        logger.info(
            "Config loaded: %d capabilities, %d endpoints, %d routes, %d sources, %d policies",
            len(cap_map), len(ep_map), len(rt_map), len(src_map), len(pol_map),
        )

        return config

    # --- File I/O ---

    def _load_json(self, filename: str) -> Any:
        path = self.config_dir / filename
        if not path.exists():
            self._errors.append(f"{filename}: file not found")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._errors.append(f"{filename}: invalid JSON — {exc}")
            return None

    def _load_app_config(self) -> AppConfig:
        data = self._load_json("app_config.json")
        if data is None:
            return AppConfig()
        try:
            return AppConfig(**data)
        except Exception as exc:
            self._errors.append(f"app_config.json: {exc}")
            return AppConfig()

    def _load_list(self, filename: str, model_cls: type) -> list:
        data = self._load_json(filename)
        if data is None:
            return []
        if not isinstance(data, list):
            self._errors.append(f"{filename}: expected a JSON array at top level")
            return []
        items = []
        for i, entry in enumerate(data):
            try:
                items.append(model_cls(**entry))
            except Exception as exc:
                entry_id = entry.get("id", f"index {i}") if isinstance(entry, dict) else f"index {i}"
                self._errors.append(f"{filename} [{entry_id}]: {exc}")
        return items

    # --- Indexing ---

    def _index_by_id(self, filename: str, items: list) -> dict:
        result = {}
        for item in items:
            if item.id in result:
                self._errors.append(f"{filename}: duplicate id '{item.id}'")
            result[item.id] = item
        return result

    # --- Cross-reference validation (design doc §15) ---

    def _validate_sources(
        self,
        sources: dict[str, Source],
        endpoints: dict[str, Endpoint],
        routes: dict[str, Route],
        capabilities: dict[str, CapabilityProfile],
        policies: dict[str, Policy],
    ) -> None:
        for src in sources.values():
            # Must reference endpoint_id or route_id, not both
            has_ep = src.endpoint_id is not None
            has_rt = src.route_id is not None
            if has_ep and has_rt:
                self._errors.append(
                    f"sources.json [{src.id}]: references both endpoint_id and route_id"
                )
            elif not has_ep and not has_rt:
                self._errors.append(
                    f"sources.json [{src.id}]: must reference endpoint_id or route_id"
                )

            # Endpoint reference must exist
            if has_ep and src.endpoint_id not in endpoints:
                self._errors.append(
                    f"sources.json [{src.id}]: endpoint_id '{src.endpoint_id}' not found in endpoints.json"
                )

            # Route reference must exist
            if has_rt and src.route_id not in routes:
                self._errors.append(
                    f"sources.json [{src.id}]: route_id '{src.route_id}' not found in routes.json"
                )

            # Capability profile must exist
            if src.capability_profile_id not in capabilities:
                self._errors.append(
                    f"sources.json [{src.id}]: capability_profile_id '{src.capability_profile_id}' "
                    f"not found in capabilities.json"
                )

            # Policy reference must exist if specified
            if src.policy_id is not None and src.policy_id not in policies:
                self._errors.append(
                    f"sources.json [{src.id}]: policy_id '{src.policy_id}' not found in policies.json"
                )

    def _validate_routes(
        self,
        routes: dict[str, Route],
        endpoints: dict[str, Endpoint],
    ) -> None:
        for route in routes.values():
            if not route.endpoint_ids:
                self._errors.append(
                    f"routes.json [{route.id}]: must reference at least one endpoint"
                )
            for ep_id in route.endpoint_ids:
                if ep_id not in endpoints:
                    self._errors.append(
                        f"routes.json [{route.id}]: endpoint_id '{ep_id}' not found in endpoints.json"
                    )

    def _validate_ollama_endpoints(
        self,
        endpoints: dict[str, Endpoint],
        routes: dict[str, Route],
    ) -> None:
        for route in routes.values():
            if route.required_model:
                for ep_id in route.endpoint_ids:
                    ep = endpoints.get(ep_id)
                    if ep and not ep.is_ollama_node and ep.provider_type.value != "ollama":
                        self._errors.append(
                            f"routes.json [{route.id}]: requires model presence but endpoint "
                            f"'{ep_id}' is not an Ollama node (cannot query inventory)"
                        )
