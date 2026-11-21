"""Music (8301 internet radio) and Strobe switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlgoConfigEntry
from .const import KEY_RADIO_URL, STROBE_DEFAULT_COLOR, STROBE_DEFAULT_PATTERN
from .coordinator import AlgoCoordinator
from .entity import AlgoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlgoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Music on the 8301, Strobe on strobe models."""
    stations = entry.runtime_data.stations
    entities: list[SwitchEntity] = []
    for c in entry.runtime_data.coordinators.values():
        if c.is_radio:
            entities.append(AlgoMusicSwitch(c, "music", stations))
        if c.has_strobe:
            entities.append(AlgoStrobeSwitch(c, "strobe"))
    async_add_entities(entities)


class AlgoMusicSwitch(AlgoEntity, SwitchEntity):
    """On = PLAY the selected station; off = STOP (clears radio.url, radio.use stays "1")."""

    def __init__(
        self, coordinator: AlgoCoordinator, key: str, stations: list[tuple[str, str]]
    ) -> None:
        """Remember the configured stations."""
        super().__init__(coordinator, key)
        self._stations = stations

    @property
    def is_on(self) -> bool:
        """radio.use is "1" and radio.url is set."""
        return self.coordinator.music_on(self.coordinator.data)

    def _station_url(self) -> str:
        """The last station seen playing or chosen, else the first configured one."""
        if self.coordinator.last_station_url:
            return self.coordinator.last_station_url
        if self._stations:
            return self._stations[0][1]
        raise HomeAssistantError("No radio stations are configured (integration options)")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """PLAY."""
        url = self._station_url()
        await self._device_call(self.coordinator.client.play_stream(url))
        self.coordinator.last_station_url = url
        self.coordinator.patch_settings({KEY_RADIO_URL: url})
        await self.coordinator.async_refresh_after_stream_change()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """STOP."""
        await self._device_call(self.coordinator.client.stop_stream())
        self.coordinator.patch_settings({KEY_RADIO_URL: ""})
        await self.coordinator.async_refresh_after_stream_change()


class AlgoStrobeSwitch(AlgoEntity, SwitchEntity):
    """The strobe can't be read back, so its state is what was last sent."""

    _attr_assumed_state = True

    @property
    def is_on(self) -> bool:
        """Last command sent."""
        return self.coordinator.strobe_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Pattern 2 (strobe fast), red, full brightness."""
        c = self.coordinator
        await self._device_call(
            c.client.strobe_start(
                STROBE_DEFAULT_PATTERN,
                STROBE_DEFAULT_COLOR,
                STROBE_DEFAULT_COLOR,
                c.strobe_levels["high"],
            )
        )
        c.strobe_on = True
        c.async_update_listeners()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """strobe/stop."""
        await self._device_call(self.coordinator.client.strobe_stop())
        self.coordinator.strobe_on = False
        self.coordinator.async_update_listeners()
