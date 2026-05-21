"""SSE micro-batching: events accumulate in queue, drained per 60fps frame."""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.events import AgentChunkEvent


@pytest.mark.asyncio
async def test_sse_event_queue_exists():
    """App must expose _event_queue (asyncio.Queue) after mount."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        assert hasattr(app, "_event_queue"), "_event_queue not found on app"
        import asyncio

        assert isinstance(app._event_queue, asyncio.Queue)


@pytest.mark.asyncio
async def test_sse_events_accumulate_then_drain():
    """Events put in queue are drained within one 60fps window (~17ms)."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)

        fake_event = AgentChunkEvent(type="chunk", flavor="assistant", text="hi", at=0)
        app._event_queue.put_nowait(fake_event)

        # Should still be in queue immediately after put
        assert not app._event_queue.empty()

        # After one drain cycle (100ms >> 17ms), queue should be empty
        await pilot.pause(0.1)
        assert app._event_queue.empty()

        # Verify the event was actually dispatched (not silently lost)
        from nx01_tui.tui.state import AgentState

        assert app._states["assistant"].state == AgentState.STREAMING


@pytest.mark.asyncio
async def test_connection_status_still_immediate():
    """ConnectionStatusMessage bypasses the queue and dispatches immediately via post_message."""
    from nx01_tui.tui.app import ConnectionStatusMessage
    from nx01_tui.tui.widgets import AppHeader

    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.2)

        # Force a disconnected state first so we can observe the change.
        app.post_message(ConnectionStatusMessage("disconnected", "test"))
        await pilot.pause(0.05)
        hdr = app.query_one(AppHeader)
        assert hdr.connected is False

        # Now send connected — should take effect without waiting for drain queue.
        app.post_message(ConnectionStatusMessage("connected"))
        await pilot.pause(0.05)
        assert hdr.connected is True
