"""Tests for ConversationView scroll suppression."""
from __future__ import annotations

import pytest
from nx01_tui.tui.app import Nx01App


@pytest.mark.asyncio
async def test_suppress_scroll_prevents_intermediate_scrolls():
    """With suppress_scroll active, scroll_end is not called per-event."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    scroll_calls: list[int] = []

    async with app.run_test() as pilot:
        await pilot.pause(0.3)

        pane = app._panes.get("assistant")
        if pane is None:
            pytest.skip("no assistant pane")

        conv = pane.conversation
        original_scroll = conv.scroll_end

        def track_scroll(**kwargs):
            scroll_calls.append(1)
            return original_scroll(**kwargs)

        conv.scroll_end = track_scroll  # type: ignore[method-assign]
        scroll_calls.clear()

        with conv.suppress_scroll():
            conv.append_assistant("hello ")
            conv.append_assistant("world")

        # No scrolls during suppression
        assert scroll_calls == [], f"Expected no scrolls during suppression, got {len(scroll_calls)}"

        # After suppression is released, _maybe_scroll must fire normally
        conv.append_assistant("post-suppression text")
        assert len(scroll_calls) == 1, (
            f"Expected _maybe_scroll to fire after suppression released, got {len(scroll_calls)}"
        )
