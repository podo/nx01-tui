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
async def test_done_collapses_and_records_duration():
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
async def test_toggle_collapsed_swaps_class():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ThinkingBlock)
        block.done()
        await pilot.pause(0.05)
        assert block.has_class("collapsed")
        block.toggle_collapsed()
        assert not block.has_class("collapsed")
        block.toggle_collapsed()
        assert block.has_class("collapsed")
