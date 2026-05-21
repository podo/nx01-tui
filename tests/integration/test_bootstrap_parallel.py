"""Bootstrap parallelization: per-flavor API calls run concurrently."""

from __future__ import annotations

import asyncio

import pytest

from nx01_tui.tui.app import Nx01App


@pytest.mark.asyncio
async def test_bootstrap_fetches_flavors_concurrently(monkeypatch):
    """list_skills for alpha and beta are called concurrently, not sequentially."""
    app = Nx01App("http://localhost:9999", flavors=["alpha", "beta"])
    call_log: list[tuple[str, float]] = []

    async def fake_list_skills(flavor: str):
        call_log.append((f"skills:{flavor}", asyncio.get_event_loop().time()))
        await asyncio.sleep(0.05)
        return []

    async def fake_get_tools(flavor: str):
        call_log.append((f"tools:{flavor}", asyncio.get_event_loop().time()))
        await asyncio.sleep(0.05)
        return {}

    async def fake_list_commands():
        return []

    monkeypatch.setattr(app.client, "list_skills", fake_list_skills)
    monkeypatch.setattr(app.client, "get_tools", fake_get_tools)
    monkeypatch.setattr(app.client, "list_commands", fake_list_commands)

    async with app.run_test() as pilot:
        await pilot.pause(2.0)  # let bootstrap complete

    fetched_flavors = {name.split(":")[1] for name, _ in call_log if name.startswith("skills:")}
    assert "alpha" in fetched_flavors
    assert "beta" in fetched_flavors

    alpha_t = next((t for n, t in call_log if n == "skills:alpha"), None)
    beta_t = next((t for n, t in call_log if n == "skills:beta"), None)
    if alpha_t and beta_t:
        gap = abs(alpha_t - beta_t)
        assert gap < 0.03, f"Skills fetches not concurrent: gap={gap:.3f}s"


@pytest.mark.asyncio
async def test_fetch_flavor_dropdown_data_returns_tuple(monkeypatch):
    """_fetch_flavor_dropdown_data returns (skills, tools) tuple."""
    app = Nx01App("http://localhost:9999", flavors=["assistant"])

    async def fake_list_skills(flavor: str):
        return [{"name": "test_skill"}]

    async def fake_get_tools(flavor: str):
        return {"tools": [{"name": "bash"}]}

    monkeypatch.setattr(app.client, "list_skills", fake_list_skills)
    monkeypatch.setattr(app.client, "get_tools", fake_get_tools)

    result = await app._fetch_flavor_dropdown_data("assistant")
    skills, tools = result
    assert len(skills) == 1
    assert len(tools) == 1
