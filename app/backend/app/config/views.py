"""Transforms internal config into UI-safe view models.

Design doc reference: §26 — backend generates view models, never exposes raw config.
"""

from __future__ import annotations

from app.models.config import RuntimeConfig, Source
from app.models.views import CapabilitySummary, SourceDetail, SourceListItem


def _capability_summary(config: RuntimeConfig, source: Source) -> CapabilitySummary:
    cap = config.capabilities.get(source.capability_profile_id)
    if cap is None:
        return CapabilitySummary(
            supports_streaming=False,
            supports_system_prompt=False,
            supports_temperature=False,
            supports_max_tokens=False,
        )
    return CapabilitySummary(
        supports_streaming=cap.supports_streaming,
        supports_system_prompt=cap.supports_system_prompt,
        supports_temperature=cap.supports_temperature,
        supports_max_tokens=cap.supports_max_tokens,
    )


def _resolve_default_model(config: RuntimeConfig, source: Source) -> str | None:
    if source.default_model:
        return source.default_model
    if source.endpoint_id:
        ep = config.endpoints.get(source.endpoint_id)
        if ep and ep.default_model:
            return ep.default_model
    return None


def build_source_list(config: RuntimeConfig) -> list[SourceListItem]:
    items = []
    for source in config.sources.values():
        if not source.visible:
            continue
        items.append(
            SourceListItem(
                id=source.id,
                display_name=source.display_name,
                source_class=source.source_class.value,
                tags=source.tags,
                capabilities=_capability_summary(config, source),
                default_model=_resolve_default_model(config, source),
                is_route=source.route_id is not None,
            )
        )
    return items


def build_source_detail(config: RuntimeConfig, source_id: str) -> SourceDetail | None:
    source = config.sources.get(source_id)
    if source is None:
        return None

    detail = SourceDetail(
        id=source.id,
        display_name=source.display_name,
        source_class=source.source_class.value,
        tags=source.tags,
        capabilities=_capability_summary(config, source),
        default_model=_resolve_default_model(config, source),
        is_route=source.route_id is not None,
    )

    if source.endpoint_id:
        ep = config.endpoints.get(source.endpoint_id)
        if ep:
            detail.endpoint_display_name = ep.display_name

    if source.route_id:
        route = config.routes.get(source.route_id)
        if route:
            detail.route_display_name = route.display_name
            detail.route_endpoint_count = len(route.endpoint_ids)

    return detail
