"""Smoke tests for the V1 stub modals: Skills, Tools, Config, Cost, ModelPicker."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from nx01_tui.tui.modals import (
    ConfigModal,
    CostModal,
    ModelPickerModal,
    SkillsModal,
    ToolsModal,
)


class _Host(App):
    def compose(self) -> ComposeResult:
        yield Static("host")


@pytest.mark.asyncio
async def test_skills_modal_empty_state():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await app.push_screen(SkillsModal([]))
        await pilot.pause(0.05)


@pytest.mark.asyncio
async def test_skills_modal_with_entries():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await app.push_screen(SkillsModal([{"name": "ci", "size": 2048, "loaded": True}]))
        await pilot.pause(0.05)


@pytest.mark.asyncio
async def test_tools_modal_with_entries():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await app.push_screen(ToolsModal([{"name": "bash", "description": "Run shell commands"}]))
        await pilot.pause(0.05)


@pytest.mark.asyncio
async def test_config_modal_renders():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await app.push_screen(ConfigModal({"base_url": "http://x", "model": "opus"}))
        await pilot.pause(0.05)


@pytest.mark.asyncio
async def test_cost_modal_renders():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        await app.push_screen(
            CostModal({"tokens": {"input": 100, "output": 50, "total": 150}, "usd": 0.0123})
        )
        await pilot.pause(0.05)


@pytest.mark.asyncio
async def test_model_picker_select():
    app = _Host()
    last: object = None
    async with app.run_test() as pilot:
        await pilot.pause(0.05)

        def cb(r: object) -> None:
            nonlocal last
            last = r

        modal = ModelPickerModal(["opus", "sonnet"], current="opus")
        await app.push_screen(modal, cb)
        await pilot.pause(0.05)
        from textual.widgets import OptionList

        lst = modal.query_one("#model-list", OptionList)
        lst.highlighted = 1  # sonnet
        await pilot.press("enter")
        await pilot.pause(0.1)
        assert last == "sonnet"
