"""SlashDropdown widget tests — show/hide on / prefix, fuzzy filter."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from nx01_tui.tui.widgets import SlashDropdown


class _Host(App):
    def compose(self) -> ComposeResult:
        yield SlashDropdown()


@pytest.mark.asyncio
async def test_hidden_when_text_does_not_start_with_slash():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("hello")
        assert not dd.has_class("visible")


@pytest.mark.asyncio
async def test_visible_with_slash_prefix():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("/")
        assert dd.has_class("visible")
        assert dd.option_count > 0


@pytest.mark.asyncio
async def test_fuzzy_filter_narrows_options():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("/")
        full = dd.option_count
        dd.update_for_text("/mem")
        narrowed = dd.option_count
        assert 0 < narrowed < full


@pytest.mark.asyncio
async def test_no_matches_hides_dropdown():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.update_for_text("/xyzdoesnotexist")
        assert not dd.has_class("visible")


@pytest.mark.asyncio
async def test_set_sources_merges_commands_skills_tools():
    """Insertion strings are categorised per D8 (podo/nx01-tui#26)."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.set_sources(
            commands=[{"name": "/help", "description": "show help"}],
            skills=[{"name": "ci-setup", "loaded": False}],
            tools=[{"name": "bash", "description": "shell"}],
        )
        dd.update_for_text("/")
        await pilot.pause(0.05)
        # Three entries, one per category.
        assert dd.option_count == 3
        ids = sorted(dd.get_option_at_index(i).id for i in range(3))
        assert ids == ["/help", "/skill ci-setup", "/tool bash"]


@pytest.mark.asyncio
async def test_set_sources_handles_empty_inputs():
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        # All three empty — should keep defaults (don't blank the list).
        before = dd.option_count
        dd.set_sources(commands=[], skills=[], tools=[])
        dd.update_for_text("/")
        await pilot.pause(0.05)
        # Falls back to seeded defaults if everything is empty.
        assert dd.option_count == before


@pytest.mark.asyncio
async def test_set_sources_fuzzy_filter_across_categories():
    """`/load` should match a skill insertion `/skill ci-setup` only via name,
    while `/bash` matches the tool entry."""
    app = _Host()
    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        dd = app.query_one(SlashDropdown)
        dd.set_sources(
            commands=[{"name": "/help", "description": "show help"}],
            skills=[{"name": "ci-setup", "loaded": False}],
            tools=[{"name": "bash", "description": "shell"}],
        )
        dd.update_for_text("/bash")
        assert dd.option_count == 1
        assert dd.get_option_at_index(0).id == "/tool bash"
