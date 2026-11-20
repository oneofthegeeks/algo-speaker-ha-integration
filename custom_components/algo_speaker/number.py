"""Volume sliders (audio.page.vol, audio.ring.vol) on devices that accept writes."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlgoConfigEntry
from .api import parse_db
from .const import KEY_PAGE_VOL, KEY_RING_VOL, VOLUME_MAX_DB, VOLUME_MIN_DB, VOLUME_STEP_DB
from .coordinator import AlgoCoordinator
from .entity import AlgoEntity

PARALLEL_UPDATES = 1

VOLUMES = (("page_volume", KEY_PAGE_VOL), ("ring_volume", KEY_RING_VOL))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlgoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One pair of sliders per writable device."""
    async_add_entities(
        AlgoVolumeNumber(c, key, setting)
        for c in entry.runtime_data.coordinators.values()
        if not c.read_only
        for key, setting in VOLUMES
    )


class AlgoVolumeNumber(AlgoEntity, NumberEntity):
    """0 dB down to -45 dB in 3 dB steps; anything else is snapped onto that grid."""

    _attr_native_min_value = VOLUME_MIN_DB
    _attr_native_max_value = VOLUME_MAX_DB
    _attr_native_step = VOLUME_STEP_DB
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: AlgoCoordinator, key: str, setting: str) -> None:
        """Bind to one settings key."""
        super().__init__(coordinator, key)
        self._setting = setting

    @property
    def native_value(self) -> float | None:
        """Current level in dB."""
        return parse_db(self.settings.get(self._setting))

    async def async_set_native_value(self, value: float) -> None:
        """Write the snapped level and read it back."""
        stored = await self._device_call(self.coordinator.client.set_volume(self._setting, value))
        self.coordinator.patch_settings({self._setting: f"{stored}dB"})
