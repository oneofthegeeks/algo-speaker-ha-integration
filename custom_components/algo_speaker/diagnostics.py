"""Diagnostics download, with the password redacted."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import AlgoConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AlgoConfigEntry
) -> dict[str, Any]:
    """Entry config plus what each device last reported."""
    devices = {}
    for host, c in entry.runtime_data.coordinators.items():
        devices[host] = {
            "identity": c.identity.as_dict(),
            "scheme": c.client.scheme,
            "auth_mode": c.client.auth_mode,
            "last_update_success": c.last_update_success,
            "data": asdict(c.data) if c.data else None,
        }
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "devices": devices,
    }
