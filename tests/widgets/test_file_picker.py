"""FilePickerDropdown tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import FilePickerDropdown
from nx01_tui.tui.widgets.file_picker import _extract_at_token


def test_extract_at_token_finds_trailing():
    assert _extract_at_token("look @api/server") == "api/server"


def test_extract_at_token_requires_whitespace_before():
    assert _extract_at_token("email@host") is None


def test_extract_at_token_at_buffer_start():
    assert _extract_at_token("@README") == "README"


def test_extract_at_token_returns_none_when_no_at():
    assert _extract_at_token("plain text") is None


def test_extract_at_token_returns_none_when_whitespace_after():
    assert _extract_at_token("@api stuff") is None


class _Host(App):
    def compose(self) -> ComposeResult:
        yield FilePickerDropdown()


@pytest.mark.asyncio
async def test_hidden_without_at(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "foo.py").write_text("x")
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(FilePickerDropdown)
        dd.update_for_text("plain")
        assert not dd.has_class("visible")


@pytest.mark.asyncio
async def test_visible_with_at_and_match(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alpha.txt").write_text("x")
    (tmp_path / "beta.txt").write_text("x")
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(FilePickerDropdown)
        dd._candidates = ["alpha.txt", "beta.txt"]  # bypass cwd scan for determinism
        dd.update_for_text("@alpha")
        assert dd.has_class("visible")
        assert dd.option_count >= 1


@pytest.mark.asyncio
async def test_no_matches_hides(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(FilePickerDropdown)
        dd._candidates = ["foo.py"]
        dd.update_for_text("@xyzdoesnotexist")
        assert not dd.has_class("visible")
