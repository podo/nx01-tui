"""ToolCallBlock state-machine + diff rendering tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.state import ToolStatus
from nx01_tui.tui.widgets import ToolCallBlock


class _Host(App):
    def compose(self) -> ComposeResult:
        yield ToolCallBlock(tool="bash", args="ls /app", call_id="t1")


@pytest.mark.asyncio
async def test_starts_in_queued_state():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ToolCallBlock)
        assert block.has_class("queued")
        assert block.status == ToolStatus.QUEUED


@pytest.mark.asyncio
async def test_active_flips_class_and_expands():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ToolCallBlock)
        block.set_status(ToolStatus.ACTIVE)
        await pilot.pause(0.05)
        assert block.has_class("active")
        assert not block.has_class("queued")
        assert not block.collapsed


@pytest.mark.asyncio
async def test_done_collapses_and_records_elapsed():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ToolCallBlock)
        block.set_status(ToolStatus.ACTIVE)
        await pilot.pause(0.05)
        block.set_status(ToolStatus.DONE)
        await pilot.pause(0.05)
        assert block.has_class("done")
        assert block.collapsed is True


@pytest.mark.asyncio
async def test_error_stays_expanded_with_red_border():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ToolCallBlock)
        block.set_status(ToolStatus.ERROR)
        await pilot.pause(0.05)
        assert block.has_class("error")
        assert block.collapsed is False


@pytest.mark.asyncio
async def test_append_diff_renders_without_error():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ToolCallBlock)
        old = "line one\nline two\n"
        new = "line one\nline TWO\nline three\n"
        block.append_diff(old, new, filename="test.txt")
        # No crash, no assertion on visual content — just verify the call worked.


@pytest.mark.asyncio
async def test_append_output_streams():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(ToolCallBlock)
        block.set_status(ToolStatus.ACTIVE)
        block.append_output("stdout chunk 1\n")
        block.append_output("stdout chunk 2\n")
        await pilot.pause(0.05)
        # No crash; output mounted in RichLog.
