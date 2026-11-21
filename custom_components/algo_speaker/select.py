"""Station select on the 8301: choosing a station plays it at once (like the 8450 buttons)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlgoConfigEntry
from .const import KEY_RADIO_URL
from .coordinator import AlgoCoordinator
from .entity import AlgoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlgoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One select per 8301, when stations are configured."""
    stations = entry.runtime_data.stations
    if not stations:
        return
    async_add_entities(
        AlgoStationSelect(c, "station", stations)
        for c in entry.runtime_data.coordinators.values()
        if c.is_radio
    )


class AlgoStationSelect(AlgoEntity, SelectEntity):
    """Options are the configured station names."""

    def __init__(
        self, coordinator: AlgoCoordinator, key: str, stations: list[tuple[str, str]]
    ) -> None:
        """Remember the configured stations."""
        super().__init__(coordinator, key)
        self._urls = dict(stations)
        self._attr_options = [name for name, _ in stations]

    @property
    def current_option(self) -> str | None:
        """The station whose URL is in radio.url, else None."""
        url = self.settings.get(KEY_RADIO_URL)
        return next((name for name, u in self._urls.items() if u == url), None)

    async def async_select_option(self, option: str) -> None:
        """PLAY the station."""
        url = self._urls[option]
        await self._device_call(self.coordinator.client.play_stream(url))
        self.coordinator.last_station_url = url
        self.coordinator.patch_settings({KEY_RADIO_URL: url})
        await self.coordinator.async_refresh_after_stream_change()
