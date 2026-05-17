"""Nx01Client HTTP tests using respx mock transport + backoff stream."""

from __future__ import annotations

import httpx
import pytest
import respx

from nx01_tui.tui.client import ConnectionConfig, Nx01Client, stream_with_backoff


@pytest.fixture
def client() -> Nx01Client:
    return Nx01Client(ConnectionConfig(base_url="http://test.local", api_key="secret"))


@respx.mock
@pytest.mark.asyncio
async def test_get_flavors_returns_parsed_dict(client: Nx01Client):
    respx.get("http://test.local/flavors").mock(
        return_value=httpx.Response(200, json={"assistant": {"status": "running"}})
    )
    assert await client.get_flavors() == {"assistant": {"status": "running"}}
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_send_message_includes_bearer_token(client: Nx01Client):
    route = respx.post("http://test.local/message").mock(
        return_value=httpx.Response(200, json={"correlation_id": "c1"})
    )
    await client.send_message("assistant", "hello")
    assert route.calls[0].request.headers["authorization"] == "Bearer secret"
    # Server contract: target_flavor + message (not flavor / text).
    import json as _json
    body = _json.loads(route.calls[0].request.content)
    assert body["target_flavor"] == "assistant"
    assert body["message"] == "hello"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_list_sessions_degrades_to_empty_on_404(client: Nx01Client):
    respx.get("http://test.local/sessions").mock(return_value=httpx.Response(404))
    assert await client.list_sessions() == []
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_read_memory_degrades_to_empty(client: Nx01Client):
    respx.get("http://test.local/memory/agent").mock(return_value=httpx.Response(404))
    assert await client.read_memory("agent") == []
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_list_skills_degrades_to_empty(client: Nx01Client):
    respx.get("http://test.local/skills").mock(return_value=httpx.Response(404))
    assert await client.list_skills() == []
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_abort_swallows_404(client: Nx01Client):
    respx.post("http://test.local/abort").mock(return_value=httpx.Response(404))
    # Should NOT raise.
    await client.abort("c1")
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_stream_events_parses_sse_lines(client: Nx01Client):
    sse_body = (
        b'data: {"type":"AgentChunkEvent","flavor":"a","text":"hi","at":0}\n\n'
        b'data: {"type":"AgentTurnDoneEvent","flavor":"a","stop_reason":"end","at":0}\n\n'
    )
    respx.get("http://test.local/events").mock(return_value=httpx.Response(200, content=sse_body))
    events = []
    async for event in client.stream_events():
        events.append(event)
    assert len(events) == 2
    assert events[0].type == "AgentChunkEvent"
    assert events[1].type == "AgentTurnDoneEvent"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_stream_with_backoff_yields_disconnect_on_failure(client: Nx01Client):
    respx.get("http://test.local/events").mock(side_effect=httpx.ConnectError("boom"))
    gen = stream_with_backoff(client, initial_delay=0.01, max_delay=0.02)
    kinds = []
    # Pull just enough to verify reconnect path
    async for kind, _payload in gen:
        kinds.append(kind)
        if len(kinds) >= 2:
            break
    assert "disconnect" in kinds
    assert "reconnecting" in kinds
    await client.close()
