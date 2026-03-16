"""Route resolver — selects endpoint from a route's candidate list.

Design doc reference: §20 (route resolution).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.adapters.base import BaseAdapter, HealthResult
from app.models.config import Endpoint, Route, SelectionStrategy

logger = logging.getLogger(__name__)


@dataclass
class ResolutionDecision:
    endpoint_id: str
    action: str  # "selected", "skipped"
    reason: str


@dataclass
class ResolutionResult:
    endpoint: Endpoint | None = None
    decisions: list[ResolutionDecision] = field(default_factory=list)
    error: str | None = None


class RouteResolver:
    def __init__(
        self,
        health_cache: dict[str, HealthResult],
        inventory_cache: dict[str, list[str]],
    ):
        self.health_cache = health_cache
        self.inventory_cache = inventory_cache

    async def resolve(
        self,
        route: Route,
        endpoints: dict[str, Endpoint],
        adapter: BaseAdapter | None = None,
    ) -> ResolutionResult:
        """Resolve a route to a single endpoint.

        Uses cached health and inventory data. If cache is empty for an endpoint,
        optionally performs a live health check via the adapter.
        """
        result = ResolutionResult()

        if not route.endpoint_ids:
            result.error = f"Route '{route.id}' has no candidate endpoints"
            return result

        for ep_id in route.endpoint_ids:
            ep = endpoints.get(ep_id)
            if ep is None:
                result.decisions.append(
                    ResolutionDecision(ep_id, "skipped", "endpoint not found in config")
                )
                continue

            # Check health
            health = self.health_cache.get(ep_id)
            if health is None and adapter is not None:
                # Live check if no cached data
                health = await adapter.health_check(ep)
                self.health_cache[ep_id] = health

            if health is None or not health.healthy:
                reason = "unhealthy" if health else "no health data"
                if health and health.detail:
                    reason = f"unhealthy: {health.detail}"
                result.decisions.append(ResolutionDecision(ep_id, "skipped", reason))
                continue

            # Model presence check for first_healthy_with_model strategy
            if route.strategy == SelectionStrategy.first_healthy_with_model and route.required_model:
                models = self.inventory_cache.get(ep_id, [])
                if route.required_model not in models:
                    result.decisions.append(
                        ResolutionDecision(
                            ep_id, "skipped",
                            f"model '{route.required_model}' not present (has: {', '.join(models[:5]) or 'none'})"
                        )
                    )
                    continue

            # This endpoint passes all checks
            result.decisions.append(ResolutionDecision(ep_id, "selected", "healthy"))
            result.endpoint = ep
            logger.info(
                "Route '%s' resolved to endpoint '%s'", route.id, ep_id,
            )
            return result

        # No endpoint resolved
        if route.strategy == SelectionStrategy.first_healthy_with_model and route.required_model:
            result.error = (
                route.fallback_message
                or f"No healthy endpoint has model '{route.required_model}'"
            )
        else:
            result.error = route.fallback_message or "No healthy endpoint available"

        logger.warning("Route '%s' failed to resolve: %s", route.id, result.error)
        return result
