"""UI-safe view models — never contain auth data or private network details.

Design doc reference: §26 (source listing view model).
"""

from __future__ import annotations

from pydantic import BaseModel


class CapabilitySummary(BaseModel):
    supports_streaming: bool
    supports_system_prompt: bool
    supports_temperature: bool
    supports_max_tokens: bool


class SourceListItem(BaseModel):
    id: str
    display_name: str
    source_class: str
    tags: list[str]
    capabilities: CapabilitySummary
    default_model: str | None = None
    is_route: bool = False
    health_status: str | None = None


class SourceDetail(BaseModel):
    id: str
    display_name: str
    source_class: str
    tags: list[str]
    capabilities: CapabilitySummary
    default_model: str | None = None
    is_route: bool = False
    health_status: str | None = None
    endpoint_display_name: str | None = None
    route_display_name: str | None = None
    route_endpoint_count: int | None = None
