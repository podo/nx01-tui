"""CodeBlock click-to-copy tests."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import CodeBlock


class _Host(App):
    copied: list[str] = []

    def copy_to_clipboard(self, text: str) -> None:  # type: ignore[override]
        self.copied.append(text)

    def compose(self) -> ComposeResult:
        yield CodeBlock(code="print('hi')", language="python")


@pytest.mark.asyncio
async def test_click_copies_code():
    app = _Host()
    app.copied = []
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        block = app.query_one(CodeBlock)
        block.on_click()
        await pilot.pause(0.05)
        assert app.copied == ["print('hi')"]


@pytest.mark.asyncio
async def test_code_property_exposes_text():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        assert app.query_one(CodeBlock).code == "print('hi')"
