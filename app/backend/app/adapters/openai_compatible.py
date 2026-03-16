"""OpenAI-compatible adapter — cloud APIs and self-hosted endpoints.

Design doc reference: §19 (adapter contract), §6 (provider source type).
"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncIterator

import httpx

from app.adapters.base import BaseAdapter, HealthResult, ModelInfo
from app.models.chat import ErrorCode, RuntimeOptions, StreamEvent, StreamEventType
from app.models.config import Endpoint

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter(BaseAdapter):
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10))
        return self._client

    def _auth_headers(self, endpoint: Endpoint) -> dict[str, str]:
        if endpoint.auth_ref:
            return {"Authorization": f"Bearer {endpoint.auth_ref}"}
        return {}

    async def health_check(self, endpoint: Endpoint) -> HealthResult:
        client = await self._get_client()
        start = time.monotonic()
        try:
            resp = await client.get(
                f"{endpoint.base_url}/models",
                headers=self._auth_headers(endpoint),
                timeout=endpoint.health_check.timeout_seconds,
            )
            latency = (time.monotonic() - start) * 1000
            if resp.status_code == 401:
                return HealthResult(healthy=False, latency_ms=round(latency, 1), detail="Auth failed")
            return HealthResult(
                healthy=resp.status_code == 200,
                latency_ms=round(latency, 1),
                detail=f"HTTP {resp.status_code}",
            )
        except httpx.ConnectError:
            return HealthResult(healthy=False, detail="Connection refused")
        except httpx.TimeoutException:
            return HealthResult(healthy=False, detail="Timeout")
        except Exception as exc:
            return HealthResult(healthy=False, detail=str(exc))

    async def list_models(self, endpoint: Endpoint) -> list[ModelInfo]:
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{endpoint.base_url}/models",
                headers=self._auth_headers(endpoint),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                ModelInfo(name=m.get("id", "unknown"))
                for m in data.get("data", [])
            ]
        except Exception as exc:
            logger.warning("Failed to list models on %s: %s", endpoint.id, exc)
            return []

    async def chat(
        self,
        endpoint: Endpoint,
        model: str,
        messages: list[dict],
        options: RuntimeOptions,
    ) -> AsyncIterator[StreamEvent]:
        client = await self._get_client()

        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": options.stream,
        }
        if options.temperature is not None:
            payload["temperature"] = options.temperature
        if options.max_tokens is not None:
            payload["max_tokens"] = options.max_tokens

        url = f"{endpoint.base_url}/chat/completions"
        headers = {**self._auth_headers(endpoint), "Content-Type": "application/json"}

        try:
            if options.stream:
                async for event in self._stream_chat(client, url, headers, payload, model):
                    yield event
            else:
                async for event in self._non_stream_chat(client, url, headers, payload, model):
                    yield event
        except httpx.ConnectError:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.endpoint_unreachable,
                error_message=f"Cannot connect to {endpoint.display_name}",
            )
        except httpx.TimeoutException:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.timeout,
                error_message=f"Request to {endpoint.display_name} timed out",
            )
        except Exception as exc:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.provider_error,
                error_message=str(exc),
            )

    async def _stream_chat(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
        payload: dict,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code == 401:
                yield StreamEvent(
                    type=StreamEventType.error,
                    error_code=ErrorCode.auth_failed,
                    error_message="Authentication failed",
                )
                return
            if resp.status_code == 404:
                yield StreamEvent(
                    type=StreamEventType.error,
                    error_code=ErrorCode.model_not_found,
                    error_message=f"Model '{payload['model']}' not found",
                )
                return
            if resp.status_code != 200:
                text = await resp.aread()
                yield StreamEvent(
                    type=StreamEventType.error,
                    error_code=ErrorCode.provider_error,
                    error_message=f"HTTP {resp.status_code}: {text.decode()[:200]}",
                )
                return

            resolved_model = model
            token_usage = None

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # Track model from response
                if "model" in chunk:
                    resolved_model = chunk["model"]

                # Delta content
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield StreamEvent(type=StreamEventType.delta, content=content)

                # Usage in final chunk
                if "usage" in chunk:
                    usage = chunk["usage"]
                    token_usage = {
                        "prompt": usage.get("prompt_tokens", 0),
                        "completion": usage.get("completion_tokens", 0),
                    }

            if token_usage:
                yield StreamEvent(
                    type=StreamEventType.metadata,
                    token_usage=token_usage,
                    model=resolved_model,
                )

            yield StreamEvent(type=StreamEventType.completed, model=resolved_model)

    async def _non_stream_chat(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
        payload: dict,
        model: str,
    ) -> AsyncIterator[StreamEvent]:
        resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code == 401:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.auth_failed,
                error_message="Authentication failed",
            )
            return
        if resp.status_code != 200:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.provider_error,
                error_message=f"HTTP {resp.status_code}",
            )
            return

        data = resp.json()
        resolved_model = data.get("model", model)
        choices = data.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""

        yield StreamEvent(type=StreamEventType.delta, content=content)

        usage = data.get("usage")
        if usage:
            yield StreamEvent(
                type=StreamEventType.metadata,
                token_usage={
                    "prompt": usage.get("prompt_tokens", 0),
                    "completion": usage.get("completion_tokens", 0),
                },
                model=resolved_model,
            )

        yield StreamEvent(type=StreamEventType.completed, model=resolved_model)

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
