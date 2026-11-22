"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components/algo_speaker in every test."""


@pytest.fixture(autouse=True)
def no_auth_retry_delay() -> Iterator[None]:
    """Don't wait a real second before re-signing a refused request."""
    with patch("custom_components.algo_speaker.api.AUTH_RETRY_DELAY", 0):
        yield
