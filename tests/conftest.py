"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def base_url() -> str:
    return "http://localhost:9999"  # unreachable on purpose


@pytest.fixture
def flavors() -> list[str]:
    return ["assistant", "operator"]
