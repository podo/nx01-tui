"""ThinkingBlock lifecycle tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import ThinkingBlock


class _Host(App):
    def compose(self) -> ComposeResult:
        yield ThinkingBlock()


@pytest.mark.asyncio
async def test_streams_chunks_while_thinking():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        assert block.thinking is True
        block.append_chunk("step one")
        block.append_chunk("step two")
        await pilot.pause(0.05)
        assert not block.has_class("collapsed")


@pytest.mark.asyncio
async def test_done_auto_collapses_by_default():
    # done() auto-collapses (V1 behaviour); use done(auto_collapse=False) to keep open.
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        block.append_chunk("reasoning")
        block.done()
        await pilot.pause(0.05)
        assert block.thinking is False
        assert block.collapsed is True
        assert block.has_class("collapsed")
        assert block.has_class("done")


@pytest.mark.asyncio
async def test_done_explicit_no_collapse():
    # done(auto_collapse=False) keeps block expanded for review.
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        block.append_chunk("reasoning")
        block.done(auto_collapse=False)
        await pilot.pause(0.05)
        assert block.thinking is False
        assert block.collapsed is False
        assert not block.has_class("collapsed")
        assert block.has_class("done")


@pytest.mark.asyncio
async def test_done_auto_collapse_flag():
    # auto_collapse=True mirrors old replay behaviour.
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        block.done(auto_collapse=True)
        await pilot.pause(0.05)
        assert block.collapsed is True
        assert block.has_class("collapsed")
        assert block.has_class("done")


@pytest.mark.asyncio
async def test_toggle_collapsed_swaps_class():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        block.done(auto_collapse=True)
        await pilot.pause(0.05)
        assert block.has_class("collapsed")
        block.toggle_collapsed()
        assert not block.has_class("collapsed")
        block.toggle_collapsed()
        assert block.has_class("collapsed")


@pytest.mark.asyncio
async def test_click_on_header_toggles():
    """Clicking the header row toggles collapse state."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        block.done(auto_collapse=True)
        await pilot.pause(0.05)
        # Collapsed after done(auto_collapse=True)
        assert block.has_class("collapsed")
        # Click on the header — toggles to expanded
        await pilot.click("ThinkingBlock #header")
        await pilot.pause(0.05)
        assert not block.has_class("collapsed")


@pytest.mark.asyncio
async def test_click_on_body_does_not_toggle():
    """Clicking inside the RichLog body must NOT toggle collapse."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        block.append_chunk("some streamed thought")
        await pilot.pause(0.05)
        # Currently expanded (thinking is True)
        assert not block.has_class("collapsed")
        # Click on the RichLog body
        await pilot.click("ThinkingBlock RichLog")
        await pilot.pause(0.05)
        # Still expanded — body click is inert
        assert not block.has_class("collapsed")


@pytest.mark.asyncio
async def test_append_chunk_single_write_per_chunk():
    """append_chunk() must issue exactly one RichLog.write() per call — change 3."""
    from unittest.mock import patch

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        with patch.object(block._log, "write") as mock_write:
            block.append_chunk("multi\nline\nchunk")
            assert mock_write.call_count == 1

        with patch.object(block._log, "write") as mock_write:
            block.append_chunk("single token")
            assert mock_write.call_count == 1


@pytest.mark.asyncio
async def test_append_chunk_empty_is_noop():
    """append_chunk('') must not call write at all."""
    from unittest.mock import patch

    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        with patch.object(block._log, "write") as mock_write:
            block.append_chunk("")
            assert mock_write.call_count == 0
