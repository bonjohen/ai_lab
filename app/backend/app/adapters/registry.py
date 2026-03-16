"""Adapter registry — selects adapter by endpoint provider_type.

Design doc reference: §19 — adapter selection by provider_type, not source type.
"""

from __future__ import annotations

from app.adapters.base import BaseAdapter
from app.adapters.ollama import OllamaAdapter
from app.adapters.openai_compatible import OpenAICompatibleAdapter
from app.adapters.router import RouterAdapter
from app.models.config import ProviderType

_adapters: dict[ProviderType, BaseAdapter] = {}


def get_adapter(provider_type: ProviderType) -> BaseAdapter:
    if provider_type not in _adapters:
        if provider_type == ProviderType.ollama:
            _adapters[provider_type] = OllamaAdapter()
        elif provider_type in (ProviderType.openai_compatible, ProviderType.provider_native):
            _adapters[provider_type] = OpenAICompatibleAdapter()
        elif provider_type == ProviderType.router_api:
            _adapters[provider_type] = RouterAdapter()
        else:
            raise ValueError(f"No adapter registered for provider_type '{provider_type}'")
    return _adapters[provider_type]


async def close_all():
    for adapter in _adapters.values():
        if hasattr(adapter, "close"):
            await adapter.close()
    _adapters.clear()
