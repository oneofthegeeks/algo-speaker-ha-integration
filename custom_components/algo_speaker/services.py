"""Services that act on Algo devices picked by device_id."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
import voluptuous as vol

from .api import is_stream_url, snap_db
from .const import (
    DOMAIN,
    KEY_RADIO_URL,
    KEY_RING_VOL,
    SERVICE_PLAY_STREAM,
    SERVICE_PLAY_TONE,
    SERVICE_STOP_STREAM,
    SERVICE_STOP_TONE,
    SERVICE_STROBE_START,
    SERVICE_STROBE_STOP,
    STROBE_BRIGHTNESS,
    STROBE_COLORS,
    STROBE_DEFAULT_COLOR,
    STROBE_DEFAULT_PATTERN,
    VOLUME_MAX_DB,
    VOLUME_MIN_DB,
)
from .entity import device_call

if TYPE_CHECKING:
    from .coordinator import AlgoCoordinator

ATTR_DEVICE_ID = "device_id"

_DEVICES = {vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}

PLAY_TONE_SCHEMA = vol.Schema(
    {
        **_DEVICES,
        vol.Required("file"): cv.string,
        vol.Optional("loop", default=False): cv.boolean,
        vol.Optional("volume_db"): vol.All(
            vol.Coerce(float), vol.Range(min=VOLUME_MIN_DB, max=VOLUME_MAX_DB)
        ),
    }
)
STROBE_START_SCHEMA = vol.Schema(
    {
        **_DEVICES,
        vol.Optional("pattern", default=STROBE_DEFAULT_PATTERN): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=15)
        ),
        vol.Optional("color1", default=STROBE_DEFAULT_COLOR): vol.In(STROBE_COLORS),
        vol.Optional("color2"): vol.In(STROBE_COLORS),
        vol.Optional("brightness", default="high"): vol.In(list(STROBE_BRIGHTNESS)),
    }
)
PLAY_STREAM_SCHEMA = vol.Schema({**_DEVICES, vol.Required("url"): cv.string})
DEVICES_ONLY_SCHEMA = vol.Schema(_DEVICES)


def _coordinators(hass: HomeAssistant, call: ServiceCall) -> list[AlgoCoordinator]:
    """The loaded coordinators behind the call's device ids."""
    registry = dr.async_get(hass)
    found: list[AlgoCoordinator] = []
    for device_id in call.data[ATTR_DEVICE_ID]:
        device = registry.async_get(device_id)
        match = None
        if device is not None:
            for entry_id in device.config_entries:
                entry = hass.config_entries.async_get_entry(entry_id)
                if entry is None or entry.domain != DOMAIN:
                    continue
                if entry.state is not ConfigEntryState.LOADED:
                    continue
                for coordinator in entry.runtime_data.coordinators.values():
                    if (DOMAIN, coordinator.device_uid) in device.identifiers:
                        match = coordinator
        if match is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_algo_device",
                translation_placeholders={"device": device_id},
            )
        found.append(match)
    return found


def _require(ok: bool, key: str, coordinator: AlgoCoordinator) -> None:
    if not ok:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders={"device": coordinator.host},
        )


async def _each(
    coordinators: list[AlgoCoordinator],
    action: Callable[[AlgoCoordinator], Awaitable[None]],
) -> None:
    """Run ``action`` on every device at once (each device still serialises its own requests)."""
    await asyncio.gather(*(action(c) for c in coordinators))


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's services."""

    def writable(call: ServiceCall) -> list[AlgoCoordinator]:
        coordinators = _coordinators(hass, call)
        for c in coordinators:
            _require(not c.read_only, "read_only", c)
        return coordinators

    async def play_tone(call: ServiceCall) -> None:
        coordinators = writable(call)
        volume = call.data.get("volume_db")

        async def run(c: AlgoCoordinator) -> None:
            if volume is not None:
                stored = await device_call(c.host, c.client.set_volume(KEY_RING_VOL, volume))
                c.patch_settings({KEY_RING_VOL: f"{snap_db(stored)}dB"})
            await device_call(c.host, c.client.tone_start(call.data["file"], call.data["loop"]))

        await _each(coordinators, run)

    async def stop_tone(call: ServiceCall) -> None:
        await _each(writable(call), lambda c: device_call(c.host, c.client.tone_stop()))

    async def strobe_start(call: ServiceCall) -> None:
        coordinators = writable(call)
        for c in coordinators:
            _require(c.has_strobe, "no_strobe", c)
        color1 = call.data["color1"]
        color2 = call.data.get("color2", color1)

        async def run(c: AlgoCoordinator) -> None:
            level = c.strobe_levels[call.data["brightness"]]
            await device_call(
                c.host, c.client.strobe_start(call.data["pattern"], color1, color2, level)
            )
            c.strobe_on = True
            c.async_update_listeners()

        await _each(coordinators, run)

    async def strobe_stop(call: ServiceCall) -> None:
        coordinators = writable(call)
        for c in coordinators:
            _require(c.has_strobe, "no_strobe", c)

        async def run(c: AlgoCoordinator) -> None:
            await device_call(c.host, c.client.strobe_stop())
            c.strobe_on = False
            c.async_update_listeners()

        await _each(coordinators, run)

    def radios(call: ServiceCall) -> list[AlgoCoordinator]:
        coordinators = writable(call)
        for c in coordinators:
            _require(c.is_radio, "not_8301", c)
        return coordinators

    async def play_stream(call: ServiceCall) -> None:
        url = call.data["url"].strip()
        if not is_stream_url(url):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_url")

        async def run(c: AlgoCoordinator) -> None:
            await device_call(c.host, c.client.play_stream(url))
            c.last_station_url = url
            c.patch_settings({KEY_RADIO_URL: url})
            await c.async_request_refresh()

        await _each(radios(call), run)

    async def stop_stream(call: ServiceCall) -> None:
        async def run(c: AlgoCoordinator) -> None:
            await device_call(c.host, c.client.stop_stream())
            c.patch_settings({KEY_RADIO_URL: ""})
            await c.async_request_refresh()

        await _each(radios(call), run)

    for name, handler, schema in (
        (SERVICE_PLAY_TONE, play_tone, PLAY_TONE_SCHEMA),
        (SERVICE_STOP_TONE, stop_tone, DEVICES_ONLY_SCHEMA),
        (SERVICE_STROBE_START, strobe_start, STROBE_START_SCHEMA),
        (SERVICE_STROBE_STOP, strobe_stop, DEVICES_ONLY_SCHEMA),
        (SERVICE_PLAY_STREAM, play_stream, PLAY_STREAM_SCHEMA),
        (SERVICE_STOP_STREAM, stop_stream, DEVICES_ONLY_SCHEMA),
    ):
        hass.services.async_register(DOMAIN, name, handler, schema=schema)
