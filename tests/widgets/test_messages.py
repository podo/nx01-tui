"""AssistantMessage streaming, finalise, and freeze lifecycle tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Markdown

from nx01_tui.tui.widgets.messages import AssistantMessage


class _Host(App):
    def compose(self) -> ComposeResult:
        yield AssistantMessage()


class _HostWithInitial(App):
    def compose(self) -> ComposeResult:
        yield AssistantMessage(initial="hello")


# ── Change 1: Static during streaming, Markdown after finalise ────────────


@pytest.mark.asyncio
async def test_stream_view_visible_during_streaming():
    """_stream_view (Static) is present and Markdown is hidden while streaming."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        assert msg._stream_view is not None
        assert msg._stream_view.display is True
        assert msg._md is not None
        assert msg._md.display is False


@pytest.mark.asyncio
async def test_buffer_accumulates_chunks():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("Hello ")
        msg.append("world")
        assert msg._buffer == "Hello world"


@pytest.mark.asyncio
async def test_flush_timer_updates_stream_view():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("streamed text")
        # Wait for the 50ms flush timer to fire
        await pilot.pause(0.15)
        assert msg._dirty is False


@pytest.mark.asyncio
async def test_finalise_shows_markdown_removes_static():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("**bold** response")
        msg.finalise()
        await pilot.pause(0.15)
        # Markdown visible, stream view removed
        assert msg._md is not None
        assert msg._md.display is True
        assert msg._stream_view is None
        assert msg._finalised is True


@pytest.mark.asyncio
async def test_finalise_sets_markdown_content():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("# Title\n\nParagraph text.")
        msg.finalise()
        await pilot.pause(0.15)
        assert msg._buffer == "# Title\n\nParagraph text."


@pytest.mark.asyncio
async def test_finalise_stops_flush_timer():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("text")
        msg.finalise()
        await pilot.pause(0.1)
        # Timer is stopped — _flush_timer should be None after finalise
        assert msg._flush_timer is None


@pytest.mark.asyncio
async def test_no_flush_after_finalise():
    """append() after finalise() must not trigger any DOM update (guarded by _finalised)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.finalise()
        await pilot.pause(0.1)
        # Calling append after finalise should not crash or update stream_view
        msg.append("late chunk")
        assert msg._buffer == "late chunk"
        assert msg._stream_view is None  # already removed


@pytest.mark.asyncio
async def test_initial_content_flushes_on_mount():
    """AssistantMessage with initial content marks dirty and flushes on first tick."""
    app = _HostWithInitial()
    async with app.run_test() as pilot:
        await pilot.pause(0.15)
        msg = app.query_one(AssistantMessage)
        assert msg._buffer == "hello"
        assert msg._dirty is False  # flushed by timer


# ── Change 2: freeze() collapses Markdown widget tree ────────────────────


@pytest.mark.asyncio
async def test_freeze_removes_markdown_widget():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("some **markdown** text")
        msg.finalise()
        await pilot.pause(0.15)
        assert msg._md is not None
        msg.freeze()
        await pilot.pause(0.1)
        assert msg._md is None


@pytest.mark.asyncio
async def test_freeze_mounts_static_replacement():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("response text")
        msg.finalise()
        await pilot.pause(0.15)
        msg.freeze()
        await pilot.pause(0.15)
        # After freeze, the Markdown widget is replaced by a Static
        # The AssistantMessage should have no Markdown child
        md_widgets = list(msg.query(Markdown))
        assert len(md_widgets) == 0


@pytest.mark.asyncio
async def test_freeze_is_idempotent():
    """Calling freeze() twice must not crash."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("text")
        msg.finalise()
        await pilot.pause(0.15)
        msg.freeze()
        msg.freeze()  # second call is a no-op
        await pilot.pause(0.1)
        assert msg._md is None


@pytest.mark.asyncio
async def test_freeze_before_finalise_is_safe():
    """freeze() before finalise() must not crash (md is hidden but exists)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        msg = app.query_one(AssistantMessage)
        msg.append("text")
        # freeze without finalise — _md exists but hasn't been updated yet
        msg.freeze()
        await pilot.pause(0.1)
