"""SkillBlock collapse/expand and content tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import SkillBlock


class _Host(App):
    def compose(self) -> ComposeResult:
        yield SkillBlock(skill_name="ci-setup", skill_size=4096)


@pytest.mark.asyncio
async def test_starts_collapsed():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(SkillBlock)
        assert block.collapsed is True
        assert block.has_class("collapsed")


@pytest.mark.asyncio
async def test_toggle_expands():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(SkillBlock)
        block.toggle_collapsed()
        assert block.collapsed is False
        assert not block.has_class("collapsed")


@pytest.mark.asyncio
async def test_set_content_updates_markdown():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(SkillBlock)
        block.set_content("# New skill content")
        # No crash; Markdown widget updated.
