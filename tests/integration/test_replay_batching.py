"""Replay batching: session restore wraps all mounts in batch_update."""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import Nx01App
from nx01_tui.tui.widgets import AssistantMessage, UserMessage


def _make_rows(n: int = 20) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({"role": "user", "content": f"msg {i}", "timestamp": i * 2})
        rows.append({"role": "assistant", "content": f"reply {i}", "timestamp": i * 2 + 1})
    return rows


@pytest.mark.asyncio
async def test_replay_scroll_called_once(monkeypatch):
    """scroll_end called exactly 1 time after replaying 20 user+assistant pairs."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    scroll_calls: list[int] = []

    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        pane = app._panes.get("assistant")
        assert pane is not None, "assistant pane not mounted — bootstrap too slow or broken"
        conv = pane.conversation
        original = conv.scroll_end

        def track(**kw):
            scroll_calls.append(1)
            return original(**kw)

        conv.scroll_end = track  # type: ignore[method-assign]
        scroll_calls.clear()

        app._replay_messages("assistant", _make_rows(20))
        await pilot.pause(0.1)

        assert len(scroll_calls) == 1, f"Expected exactly 1 scroll, got {len(scroll_calls)}"


@pytest.mark.asyncio
async def test_replay_no_scroll_when_scroll_after_false(monkeypatch):
    """scroll_after=False means _replay_messages produces zero scroll_end calls."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])
    scroll_calls: list[int] = []

    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        pane = app._panes.get("assistant")
        assert pane is not None, "assistant pane not mounted — bootstrap too slow or broken"
        conv = pane.conversation
        original = conv.scroll_end

        def track(**kw):
            scroll_calls.append(1)
            return original(**kw)

        conv.scroll_end = track  # type: ignore[method-assign]
        scroll_calls.clear()

        app._replay_messages("assistant", _make_rows(5), scroll_after=False)
        await pilot.pause(0.1)

        n = len(scroll_calls)
        assert n == 0, f"Expected 0 scrolls with scroll_after=False, got {n}"


@pytest.mark.asyncio
async def test_replay_content_correct():
    """All messages render correctly even with batch_update wrapping."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])

    async with app.run_test() as pilot:
        await pilot.pause(0.3)
        pane = app._panes.get("assistant")
        assert pane is not None, "assistant pane not mounted — bootstrap too slow or broken"
        conv = pane.conversation

        rows = [
            {"role": "user", "content": "hello", "timestamp": 1},
            {"role": "assistant", "content": "world", "timestamp": 2},
        ]
        app._replay_messages("assistant", rows)
        await pilot.pause(0.2)

        assert len(list(conv.query(UserMessage))) >= 1
        assert len(list(conv.query(AssistantMessage))) >= 1
