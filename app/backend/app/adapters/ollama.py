"""Ollama adapter — local and remote HTTP targets.

Design doc references: §19 (adapter contract), §21 (Ollama-specific design).
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


class OllamaAdapter(BaseAdapter):
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10))
        return self._client

    async def health_check(self, endpoint: Endpoint) -> HealthResult:
        client = await self._get_client()
        start = time.monotonic()
        try:
            resp = await client.get(
                f"{endpoint.base_url}{endpoint.health_check.path}",
                timeout=endpoint.health_check.timeout_seconds,
            )
            latency = (time.monotonic() - start) * 1000
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
            resp = await client.get(f"{endpoint.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return [
                ModelInfo(
                    name=m["name"],
                    size=m.get("size"),
                    modified_at=m.get("modified_at"),
                )
                for m in data.get("models", [])
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

        payload = {
            "model": model,
            "messages": messages,
            "stream": options.stream,
        }

        ollama_options = {}
        if options.temperature is not None:
            ollama_options["temperature"] = options.temperature
        if options.max_tokens is not None:
            ollama_options["num_predict"] = options.max_tokens
        if ollama_options:
            payload["options"] = ollama_options

        url = f"{endpoint.base_url}/api/chat"

        try:
            if options.stream:
                async for event in self._stream_chat(client, url, payload):
                    yield event
            else:
                async for event in self._non_stream_chat(client, url, payload):
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
        self, client: httpx.AsyncClient, url: str, payload: dict
    ) -> AsyncIterator[StreamEvent]:
        async with client.stream("POST", url, json=payload) as resp:
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
                    error_message=f"Ollama returned HTTP {resp.status_code}: {text.decode()[:200]}",
                )
                return

            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if chunk.get("done"):
                    # Final chunk — emit metadata then completed
                    token_usage = {}
                    if "prompt_eval_count" in chunk:
                        token_usage["prompt"] = chunk["prompt_eval_count"]
                    if "eval_count" in chunk:
                        token_usage["completion"] = chunk["eval_count"]

                    timing = {}
                    if "total_duration" in chunk:
                        timing["total_duration_ns"] = chunk["total_duration"]
                    if "eval_duration" in chunk:
                        timing["eval_duration_ns"] = chunk["eval_duration"]

                    if token_usage or timing:
                        yield StreamEvent(
                            type=StreamEventType.metadata,
                            token_usage=token_usage or None,
                            timing=timing or None,
                            model=chunk.get("model"),
                        )

                    yield StreamEvent(type=StreamEventType.completed, model=chunk.get("model"))
                    return

                # Delta chunk
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                if content:
                    yield StreamEvent(type=StreamEventType.delta, content=content)

    async def _non_stream_chat(
        self, client: httpx.AsyncClient, url: str, payload: dict
    ) -> AsyncIterator[StreamEvent]:
        resp = await client.post(url, json=payload)

        if resp.status_code == 404:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.model_not_found,
                error_message=f"Model '{payload['model']}' not found",
            )
            return
        if resp.status_code != 200:
            yield StreamEvent(
                type=StreamEventType.error,
                error_code=ErrorCode.provider_error,
                error_message=f"Ollama returned HTTP {resp.status_code}",
            )
            return

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        yield StreamEvent(type=StreamEventType.delta, content=content)
        yield StreamEvent(type=StreamEventType.completed, model=data.get("model"))

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
