"""HTTP + SSE client for the nx01 API.

Wraps httpx.AsyncClient with bearer-token auth, an SSE stream parser,
and exponential-backoff reconnection. The TUI app calls this from a
Textual @work coroutine and forwards parsed events as messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from .events import SseEvent, parse_event

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    base_url: str
    api_key: str | None = None
    timeout: float = 30.0
    keepalive_seconds: float = 30.0


class Nx01Client:
    """Async HTTP client for nx01 API.

    Methods raise httpx.HTTPError on failure — caller handles.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config
        headers: dict[str, str] = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=headers,
            timeout=config.timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ── Discovery ────────────────────────────────────────────────────

    async def get_flavors(self) -> dict[str, Any]:
        r = await self._client.get("/flavors")
        r.raise_for_status()
        return r.json()

    async def get_health(self) -> dict[str, Any]:
        r = await self._client.get("/health")
        r.raise_for_status()
        return r.json()

    async def get_tools(self, flavor: str | None = None) -> dict[str, Any]:
        params = {"flavor": flavor} if flavor else {}
        r = await self._client.get("/tools", params=params)
        r.raise_for_status()
        return r.json()

    # ── Messaging ────────────────────────────────────────────────────

    async def send_message(
        self,
        flavor: str,
        text: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        # Server contract: MessageRequest expects target_flavor + message.
        body: dict[str, Any] = {"target_flavor": flavor, "message": text}
        if session_id:
            body["session_id"] = session_id
        r = await self._client.post("/message", json=body)
        r.raise_for_status()
        return r.json()

    async def abort(self, correlation_id: str) -> None:
        # Backend gap — TUI sends but server may not yet implement.
        try:
            await self._client.post(f"/abort?correlation_id={correlation_id}")
        except httpx.HTTPError as e:
            logger.warning("abort failed: %s", e)

    # ── Sessions (depends on backend gap #16) ────────────────────────

    async def list_sessions(self, flavor: str | None = None) -> list[dict[str, Any]]:
        try:
            params = {"flavor": flavor} if flavor else None
            r = await self._client.get("/sessions", params=params)
            r.raise_for_status()
            data = r.json()
            # Server returns { sessions: [...], next_cursor: ... }
            return data.get("sessions", []) if isinstance(data, dict) else (data or [])
        except httpx.HTTPError:
            logger.warning("/sessions not yet exposed by backend")
            return []

    async def resume_session(self, session_id: str) -> dict[str, Any]:
        r = await self._client.post(f"/sessions/{session_id}/resume")
        r.raise_for_status()
        return r.json()

    async def fork_session(self, session_id: str) -> dict[str, Any]:
        r = await self._client.post(f"/sessions/{session_id}/fork")
        r.raise_for_status()
        return r.json()

    async def rename_session(self, session_id: str, title: str) -> None:
        r = await self._client.patch(f"/sessions/{session_id}", json={"title": title})
        r.raise_for_status()

    async def delete_session(self, session_id: str) -> None:
        r = await self._client.delete(f"/sessions/{session_id}")
        r.raise_for_status()

    # ── Memory (per-flavor on the backend) ───────────────────────────

    async def read_memory(self, store: str = "agent", flavor: str | None = None) -> list[str]:
        try:
            params = {"flavor": flavor} if flavor else None
            r = await self._client.get(f"/memory/{store}", params=params)
            r.raise_for_status()
            data = r.json()
            return data.get("entries", []) if isinstance(data, dict) else []
        except httpx.HTTPError:
            return []

    async def write_memory(
        self, store: str, action: str, flavor: str | None = None, **kwargs: Any
    ) -> None:
        params = {"flavor": flavor} if flavor else None
        await self._client.post(
            f"/memory/{store}", params=params, json={"action": action, **kwargs}
        )

    # ── Skills ───────────────────────────────────────────────────────

    async def list_skills(self, flavor: str | None = None) -> list[dict[str, Any]]:
        try:
            params = {"flavor": flavor} if flavor else {}
            r = await self._client.get("/skills", params=params)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("skills", [])
        except httpx.HTTPError:
            return []

    # ── Permission flow (depends on backend gap #16) ─────────────────

    async def resolve_permission(self, permission_id: str, decision: str) -> None:
        """decision ∈ {allow, deny, always_allow}"""
        try:
            await self._client.post(f"/permissions/{permission_id}", json={"decision": decision})
        except httpx.HTTPError as e:
            logger.warning("resolve_permission failed: %s", e)

    # ── SSE stream ───────────────────────────────────────────────────

    async def stream_events(self) -> AsyncIterator[SseEvent]:
        """Yields parsed SseEvent from /events.

        Caller wraps in reconnection logic — this raises on stream end.
        """
        async with self._client.stream("GET", "/events") as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload_str = line[5:].strip()
                if not payload_str:
                    continue
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    logger.warning("bad SSE payload: %s", payload_str[:100])
                    continue
                yield parse_event(payload)


async def stream_with_backoff(
    client: Nx01Client,
    *,
    initial_delay: float = 1.0,
    max_delay: float = 16.0,
) -> AsyncIterator[tuple[str, Any]]:
    """Wrap stream_events with reconnect + exponential backoff.

    Yields ('event', SseEvent) on each event, ('disconnect', exception)
    on connection loss, ('reconnecting', attempt_number) before retry,
    ('connected', None) after a successful reconnect.
    """
    attempt = 0
    delay = initial_delay
    while True:
        try:
            if attempt > 0:
                yield ("connected", None)
            attempt = 0  # reset on successful connect
            delay = initial_delay
            async for event in client.stream_events():
                yield ("event", event)
        except (httpx.HTTPError, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            yield ("disconnect", exc)
            attempt += 1
            yield ("reconnecting", attempt)
            await asyncio.sleep(min(delay, max_delay))
            delay = min(delay * 2, max_delay)
