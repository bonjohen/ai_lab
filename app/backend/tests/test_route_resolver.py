"""Tests for route resolver — endpoint selection logic."""

import pytest

from app.adapters.base import HealthResult
from app.models.config import Endpoint, ProviderType, Route, SelectionStrategy
from app.services.route_resolver import RouteResolver


def _make_endpoint(ep_id: str, **kwargs) -> Endpoint:
    return Endpoint(
        id=ep_id,
        display_name=f"EP {ep_id}",
        provider_type=ProviderType.ollama,
        base_url=f"http://{ep_id}:11434",
        is_ollama_node=True,
        **kwargs,
    )


def _make_route(endpoint_ids: list[str], **kwargs) -> Route:
    return Route(
        id="test-route",
        display_name="Test Route",
        endpoint_ids=endpoint_ids,
        **kwargs,
    )


class TestFirstHealthyStrategy:
    async def test_selects_first_healthy(self):
        ep1, ep2 = _make_endpoint("ep1"), _make_endpoint("ep2")
        endpoints = {"ep1": ep1, "ep2": ep2}
        health = {
            "ep1": HealthResult(healthy=False, detail="down"),
            "ep2": HealthResult(healthy=True, latency_ms=10),
        }
        route = _make_route(["ep1", "ep2"])
        resolver = RouteResolver(health, {})

        result = await resolver.resolve(route, endpoints)
        assert result.endpoint is not None
        assert result.endpoint.id == "ep2"
        assert len(result.decisions) == 2
        assert result.decisions[0].action == "skipped"
        assert result.decisions[1].action == "selected"

    async def test_all_unhealthy(self):
        ep1, ep2 = _make_endpoint("ep1"), _make_endpoint("ep2")
        endpoints = {"ep1": ep1, "ep2": ep2}
        health = {
            "ep1": HealthResult(healthy=False),
            "ep2": HealthResult(healthy=False),
        }
        route = _make_route(["ep1", "ep2"], fallback_message="All nodes down")
        resolver = RouteResolver(health, {})

        result = await resolver.resolve(route, endpoints)
        assert result.endpoint is None
        assert result.error == "All nodes down"

    async def test_first_healthy_wins(self):
        ep1, ep2 = _make_endpoint("ep1"), _make_endpoint("ep2")
        endpoints = {"ep1": ep1, "ep2": ep2}
        health = {
            "ep1": HealthResult(healthy=True, latency_ms=5),
            "ep2": HealthResult(healthy=True, latency_ms=10),
        }
        route = _make_route(["ep1", "ep2"])
        resolver = RouteResolver(health, {})

        result = await resolver.resolve(route, endpoints)
        assert result.endpoint.id == "ep1"


class TestModelPresenceStrategy:
    async def test_skips_endpoint_without_model(self):
        ep1, ep2 = _make_endpoint("ep1"), _make_endpoint("ep2")
        endpoints = {"ep1": ep1, "ep2": ep2}
        health = {
            "ep1": HealthResult(healthy=True),
            "ep2": HealthResult(healthy=True),
        }
        inventory = {
            "ep1": ["other-model"],
            "ep2": ["llama3:latest", "other-model"],
        }
        route = _make_route(
            ["ep1", "ep2"],
            strategy=SelectionStrategy.first_healthy_with_model,
            required_model="llama3:latest",
        )
        resolver = RouteResolver(health, inventory)

        result = await resolver.resolve(route, endpoints)
        assert result.endpoint.id == "ep2"

    async def test_no_endpoint_has_model(self):
        ep1 = _make_endpoint("ep1")
        endpoints = {"ep1": ep1}
        health = {"ep1": HealthResult(healthy=True)}
        inventory = {"ep1": ["other-model"]}
        route = _make_route(
            ["ep1"],
            strategy=SelectionStrategy.first_healthy_with_model,
            required_model="missing-model",
        )
        resolver = RouteResolver(health, inventory)

        result = await resolver.resolve(route, endpoints)
        assert result.endpoint is None
        assert "missing-model" in result.error


class TestEdgeCases:
    async def test_empty_route(self):
        route = _make_route([])
        resolver = RouteResolver({}, {})

        result = await resolver.resolve(route, {})
        assert result.endpoint is None
        assert "no candidate" in result.error.lower()

    async def test_missing_endpoint_in_config(self):
        route = _make_route(["nonexistent"])
        resolver = RouteResolver({}, {})

        result = await resolver.resolve(route, {})
        assert result.endpoint is None
        assert result.decisions[0].reason == "endpoint not found in config"

    async def test_no_health_data_skips(self):
        ep1 = _make_endpoint("ep1")
        endpoints = {"ep1": ep1}
        # No health cache, no adapter — should skip
        route = _make_route(["ep1"])
        resolver = RouteResolver({}, {})

        result = await resolver.resolve(route, endpoints, adapter=None)
        assert result.endpoint is None
