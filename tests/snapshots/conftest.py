"""Fixtures for snapshot tests.

Snapshot tests are platform-dependent (font metrics, ANSI quirks) so
they're skipped in CI via a module-level pytestmark in test_snapshots.py.
"""

from __future__ import annotations

import pytest

from nx01_tui.tui.app import Nx01App


@pytest.fixture
def make_app():
    """Factory: returns a fresh Nx01App configured to never reach a backend."""

    def _factory(flavors: list[str] | None = None) -> Nx01App:
        return Nx01App(
            "http://localhost:9999",
            api_key=None,
            flavors=flavors or ["assistant", "operator"],
        )

    return _factory
