"""Tests for ConversationView scroll suppression."""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import Nx01App


@pytest.mark.asyncio
async def test_suppress_scroll_prevents_intermediate_scrolls():
    """With suppress_scroll active, scroll_end is not called per-event."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    async with app.run_test() as pilot:
        await pilot.pause(0.3)

        pane = app._panes.get("assistant")
        if pane is None:
            pytest.skip("no assistant pane")

        conv = pane.conversation
        conv._scroll_pending = False

        with conv.suppress_scroll():
            conv.append_assistant("hello ")
            conv.append_assistant("world")

        # Suppression prevents _scroll_pending from being set
        assert not conv._scroll_pending, "scroll_pending must stay False during suppression"

        # After suppression released, _request_scroll sets _scroll_pending
        conv.append_assistant("post-suppression text")
        assert conv._scroll_pending, "scroll_pending must be True after suppression released"
