"""Health check and inventory scheduler.

Design doc references: §21 (Ollama-specific), §27 (health/inventory refresh model).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.adapters.base import BaseAdapter, HealthResult, ModelInfo
from app.adapters.registry import get_adapter
from app.models.config import Endpoint, RuntimeConfig

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.health_cache: dict[str, HealthResult] = {}
        self.inventory_cache: dict[str, list[str]] = {}  # endpoint_id -> model names
        self.inventory_details: dict[str, list[ModelInfo]] = {}
        self._health_task: asyncio.Task | None = None
        self._inventory_task: asyncio.Task | None = None

    async def start(self):
        """Start background health and inventory refresh loops."""
        # Run initial checks immediately
        await self.refresh_all_health()
        await self.refresh_all_inventory()

        # Start periodic loops
        self._health_task = asyncio.create_task(self._health_loop())
        self._inventory_task = asyncio.create_task(self._inventory_loop())
        logger.info("Health and inventory schedulers started")

    async def stop(self):
        for task in [self._health_task, self._inventory_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _health_loop(self):
        interval = self.config.app.health_check_interval_seconds
        while True:
            await asyncio.sleep(interval)
            await self.refresh_all_health()

    async def _inventory_loop(self):
        interval = self.config.app.inventory_refresh_interval_seconds
        while True:
            await asyncio.sleep(interval)
            await self.refresh_all_inventory()

    async def refresh_all_health(self):
        """Check health of all endpoints with health checks enabled."""
        for endpoint in self.config.endpoints.values():
            if not endpoint.health_check.enabled:
                continue
            try:
                adapter = get_adapter(endpoint.provider_type)
                result = await adapter.health_check(endpoint)
                self.health_cache[endpoint.id] = result
                logger.debug(
                    "Health check %s: %s (%.1fms)",
                    endpoint.id,
                    "healthy" if result.healthy else "unhealthy",
                    result.latency_ms or 0,
                )
            except Exception as exc:
                self.health_cache[endpoint.id] = HealthResult(
                    healthy=False, detail=str(exc)
                )
                logger.warning("Health check failed for %s: %s", endpoint.id, exc)

    async def refresh_all_inventory(self):
        """Refresh model inventory for all Ollama nodes."""
        for endpoint in self.config.endpoints.values():
            if not endpoint.is_ollama_node:
                continue
            try:
                adapter = get_adapter(endpoint.provider_type)
                models = await adapter.list_models(endpoint)
                self.inventory_cache[endpoint.id] = [m.name for m in models]
                self.inventory_details[endpoint.id] = models
                logger.debug(
                    "Inventory refresh %s: %d models",
                    endpoint.id, len(models),
                )
            except Exception as exc:
                logger.warning("Inventory refresh failed for %s: %s", endpoint.id, exc)

    async def refresh_endpoint_health(self, endpoint_id: str) -> HealthResult | None:
        endpoint = self.config.endpoints.get(endpoint_id)
        if endpoint is None:
            return None
        try:
            adapter = get_adapter(endpoint.provider_type)
            result = await adapter.health_check(endpoint)
            self.health_cache[endpoint_id] = result
            return result
        except Exception as exc:
            result = HealthResult(healthy=False, detail=str(exc))
            self.health_cache[endpoint_id] = result
            return result

    def get_health_summary(self) -> list[dict[str, Any]]:
        summaries = []
        for ep_id, ep in self.config.endpoints.items():
            health = self.health_cache.get(ep_id)
            summaries.append({
                "endpoint_id": ep_id,
                "display_name": ep.display_name,
                "healthy": health.healthy if health else None,
                "latency_ms": health.latency_ms if health else None,
                "detail": health.detail if health else "not checked",
            })
        return summaries

    def get_inventory_summary(self) -> list[dict[str, Any]]:
        summaries = []
        for ep_id, ep in self.config.endpoints.items():
            if not ep.is_ollama_node:
                continue
            models = self.inventory_details.get(ep_id, [])
            summaries.append({
                "endpoint_id": ep_id,
                "display_name": ep.display_name,
                "models": [
                    {"name": m.name, "size": m.size, "modified_at": m.modified_at}
                    for m in models
                ],
                "model_count": len(models),
            })
        return summaries
